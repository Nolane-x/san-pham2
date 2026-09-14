from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

from .schema import SCHEMA_SQL


class ProjectStore:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def initialize(self) -> None:
        with self._connect() as conn:
            conn.executescript(SCHEMA_SQL)
            # Old builds used cleanup timers. A local desktop project is durable.
            conn.execute("UPDATE batch_projects SET cleanup_after=NULL, source_cleanup_after=NULL")

    def create_project(
        self,
        project_id: str,
        title: str,
        *,
        expected_image_count: int = 0,
        output_w: int = 1280,
        output_h: int = 720,
    ) -> None:
        if expected_image_count < 0:
            raise ValueError("expected_image_count must be >= 0")
        try:
            with self._connect() as conn:
                conn.execute(
                    """INSERT INTO batch_projects(id,user_google_id,expected_image_count,output_w,output_h)
                       VALUES(?, 'local', ?, ?, ?)""",
                    (project_id, expected_image_count, output_w, output_h),
                )
                conn.execute(
                    """INSERT INTO user_project_library(project_id,user_google_id,title)
                       VALUES(?, 'local', ?)""",
                    (project_id, title),
                )
        except sqlite3.IntegrityError as exc:
            raise ValueError(f"project {project_id!r} already exists") from exc

    def get_project(self, project_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                """SELECT p.*, l.title, l.pinned, l.archived
                   FROM batch_projects p
                   LEFT JOIN user_project_library l ON l.project_id=p.id
                   WHERE p.id=?""",
                (project_id,),
            ).fetchone()
        if row is None:
            raise KeyError(project_id)
        return dict(row)

    def list_projects(self, *, limit: int = 100) -> list[dict[str, Any]]:
        if limit < 1:
            raise ValueError("limit must be >= 1")
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT l.project_id, l.title, l.pinned, l.archived, l.updated_at,
                          p.expected_image_count, p.output_w, p.output_h, p.status
                   FROM user_project_library l
                   JOIN batch_projects p ON p.id=l.project_id
                   ORDER BY datetime(l.updated_at) DESC, l.rowid DESC
                   LIMIT ?""",
                (int(limit),),
            ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def _scene_payload(scene: Any) -> tuple[str, str, str, str]:
        text = str(getattr(scene, "text", "")).strip()
        if not text:
            raise ValueError("scene text must not be blank")
        image_prompt = str(getattr(scene, "image_prompt", "") or "")
        voice_text = str(getattr(scene, "voice_text", "") or text)
        metadata = getattr(scene, "metadata", {}) or {}
        return text, image_prompt, voice_text, json.dumps(dict(metadata), ensure_ascii=False, separators=(",", ":"))

    @staticmethod
    def _sync_scene_count(conn: sqlite3.Connection, project_id: str) -> None:
        count = int(
            conn.execute(
                "SELECT COUNT(*) FROM visual_editor_scenes WHERE project_id=?",
                (project_id,),
            ).fetchone()[0]
        )
        conn.execute(
            "UPDATE batch_projects SET expected_image_count=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (count, project_id),
        )
        conn.execute(
            "UPDATE user_project_library SET updated_at=CURRENT_TIMESTAMP WHERE project_id=?",
            (project_id,),
        )

    def replace_scenes(self, project_id: str, scenes: Sequence[Any]) -> None:
        with self._connect() as conn:
            if conn.execute("SELECT 1 FROM batch_projects WHERE id=?", (project_id,)).fetchone() is None:
                raise KeyError(project_id)
            conn.execute("DELETE FROM visual_editor_scenes WHERE project_id=?", (project_id,))
            for position, scene in enumerate(scenes):
                text, image_prompt, voice_text, metadata_json = self._scene_payload(scene)
                conn.execute(
                    """INSERT INTO visual_editor_scenes(
                           id,project_id,position,text,image_prompt,voice_text,metadata_json
                       ) VALUES(?,?,?,?,?,?,?)""",
                    (uuid.uuid4().hex, project_id, position, text, image_prompt, voice_text, metadata_json),
                )
            self._sync_scene_count(conn, project_id)

    def list_scenes(self, project_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM visual_editor_scenes WHERE project_id=? ORDER BY position, rowid",
                (project_id,),
            ).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            scene = dict(row)
            scene["metadata"] = json.loads(scene.pop("metadata_json") or "{}")
            result.append(scene)
        return result

    def add_scene(
        self,
        project_id: str,
        text: str,
        *,
        position: int | None = None,
        image_prompt: str = "",
        voice_text: str = "",
        metadata: Mapping[str, Any] | None = None,
    ) -> str:
        text = str(text).strip()
        if not text:
            raise ValueError("scene text must not be blank")
        with self._connect() as conn:
            if conn.execute("SELECT 1 FROM batch_projects WHERE id=?", (project_id,)).fetchone() is None:
                raise KeyError(project_id)
            count = int(
                conn.execute(
                    "SELECT COUNT(*) FROM visual_editor_scenes WHERE project_id=?",
                    (project_id,),
                ).fetchone()[0]
            )
            target = count if position is None else int(position)
            if target < 0 or target > count:
                raise ValueError(f"position must be within 0..{count}")
            conn.execute(
                "UPDATE visual_editor_scenes SET position=position+1, updated_at=CURRENT_TIMESTAMP WHERE project_id=? AND position>=?",
                (project_id, target),
            )
            scene_id = uuid.uuid4().hex
            conn.execute(
                """INSERT INTO visual_editor_scenes(
                       id,project_id,position,text,image_prompt,voice_text,metadata_json
                   ) VALUES(?,?,?,?,?,?,?)""",
                (
                    scene_id,
                    project_id,
                    target,
                    text,
                    str(image_prompt or ""),
                    str(voice_text or text),
                    json.dumps(dict(metadata or {}), ensure_ascii=False, separators=(",", ":")),
                ),
            )
            self._sync_scene_count(conn, project_id)
            return scene_id

    def update_scene(
        self,
        scene_id: str,
        *,
        text: str | None = None,
        image_prompt: str | None = None,
        voice_text: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM visual_editor_scenes WHERE id=?", (scene_id,)).fetchone()
            if row is None:
                raise KeyError(scene_id)
            updates: list[str] = []
            values: list[Any] = []
            if text is not None:
                normalized = str(text).strip()
                if not normalized:
                    raise ValueError("scene text must not be blank")
                updates.append("text=?")
                values.append(normalized)
            if image_prompt is not None:
                updates.append("image_prompt=?")
                values.append(str(image_prompt))
            if voice_text is not None:
                updates.append("voice_text=?")
                values.append(str(voice_text))
            if metadata is not None:
                updates.append("metadata_json=?")
                values.append(json.dumps(dict(metadata), ensure_ascii=False, separators=(",", ":")))
            if not updates:
                return
            updates.append("updated_at=CURRENT_TIMESTAMP")
            values.append(scene_id)
            conn.execute(f"UPDATE visual_editor_scenes SET {', '.join(updates)} WHERE id=?", values)
            conn.execute(
                "UPDATE user_project_library SET updated_at=CURRENT_TIMESTAMP WHERE project_id=?",
                (row["project_id"],),
            )

    def move_scene(self, scene_id: str, new_position: int) -> None:
        target = int(new_position)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT project_id, position FROM visual_editor_scenes WHERE id=?",
                (scene_id,),
            ).fetchone()
            if row is None:
                raise KeyError(scene_id)
            project_id = str(row["project_id"])
            current = int(row["position"])
            count = int(
                conn.execute(
                    "SELECT COUNT(*) FROM visual_editor_scenes WHERE project_id=?",
                    (project_id,),
                ).fetchone()[0]
            )
            if target < 0 or target >= count:
                raise ValueError(f"position must be within 0..{max(0, count - 1)}")
            if target == current:
                return
            if current < target:
                conn.execute(
                    """UPDATE visual_editor_scenes
                       SET position=position-1, updated_at=CURRENT_TIMESTAMP
                       WHERE project_id=? AND position>? AND position<=?""",
                    (project_id, current, target),
                )
            else:
                conn.execute(
                    """UPDATE visual_editor_scenes
                       SET position=position+1, updated_at=CURRENT_TIMESTAMP
                       WHERE project_id=? AND position>=? AND position<?""",
                    (project_id, target, current),
                )
            conn.execute(
                "UPDATE visual_editor_scenes SET position=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (target, scene_id),
            )
            conn.execute(
                "UPDATE user_project_library SET updated_at=CURRENT_TIMESTAMP WHERE project_id=?",
                (project_id,),
            )

    def delete_scene(self, scene_id: str) -> None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT project_id, position FROM visual_editor_scenes WHERE id=?",
                (scene_id,),
            ).fetchone()
            if row is None:
                raise KeyError(scene_id)
            project_id = str(row["project_id"])
            position = int(row["position"])
            conn.execute("DELETE FROM visual_editor_scenes WHERE id=?", (scene_id,))
            conn.execute(
                "UPDATE visual_editor_scenes SET position=position-1, updated_at=CURRENT_TIMESTAMP WHERE project_id=? AND position>?",
                (project_id, position),
            )
            self._sync_scene_count(conn, project_id)

    def add_item(
        self,
        project_id: str,
        image_index: int,
        original_filename: str,
        image_path: str,
        *,
        reveal_duration: float = 8.0,
        hold_duration: float = 1.0,
        config: Mapping[str, Any] | None = None,
    ) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                """INSERT INTO batch_items(
                       project_id,image_index,original_filename,image_path,
                       reveal_duration,hold_duration,config_json,status
                   ) VALUES(?,?,?,?,?,?,?,'uploaded')""",
                (
                    project_id,
                    image_index,
                    original_filename,
                    image_path,
                    reveal_duration,
                    hold_duration,
                    json.dumps(dict(config or {}), ensure_ascii=False, separators=(",", ":")),
                ),
            )
            conn.execute(
                """UPDATE batch_projects
                   SET expected_image_count=max(expected_image_count, ?), updated_at=CURRENT_TIMESTAMP
                   WHERE id=?""",
                (image_index + 1, project_id),
            )
            return int(cur.lastrowid)

    def list_items(self, project_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM batch_items WHERE project_id=? ORDER BY image_index", (project_id,)
            ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["config"] = json.loads(item.pop("config_json") or "{}")
            result.append(item)
        return result

    def add_media(
        self,
        project_id: str,
        kind: str,
        original_name: str,
        file_path: str,
        *,
        duration: float | None = None,
        media_id: str | None = None,
    ) -> str:
        kind = str(kind).strip().lower()
        if kind not in {"image", "video", "audio"}:
            raise ValueError("kind must be image, video, or audio")
        media_id = media_id or uuid.uuid4().hex
        with self._connect() as conn:
            if conn.execute("SELECT 1 FROM batch_projects WHERE id=?", (project_id,)).fetchone() is None:
                raise KeyError(project_id)
            conn.execute(
                """INSERT INTO visual_editor_media(id, project_id, kind, original_name, file_path, duration)
                   VALUES(?,?,?,?,?,?)""",
                (media_id, project_id, kind, original_name, file_path, duration),
            )
            conn.execute(
                "UPDATE user_project_library SET updated_at=CURRENT_TIMESTAMP WHERE project_id=?",
                (project_id,),
            )
        return media_id

    def list_media(self, project_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM visual_editor_media WHERE project_id=? ORDER BY rowid",
                (project_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def save_timeline(self, project_id: str, state: Mapping[str, Any]) -> None:
        clips = state.get("clips", {})
        video = state.get("videoClips", [])
        audio = state.get("audioClips", [])
        order = state.get("mediaOrder", [])
        with self._connect() as conn:
            if conn.execute("SELECT 1 FROM batch_projects WHERE id=?", (project_id,)).fetchone() is None:
                raise KeyError(project_id)
            conn.execute(
                """INSERT INTO visual_editor_timeline_state(
                       project_id,user_google_id,clips_json,video_clips_json,audio_clips_json,media_order_json,revision
                   ) VALUES(?, 'local', ?, ?, ?, ?, 1)
                   ON CONFLICT(project_id) DO UPDATE SET
                     clips_json=excluded.clips_json,
                     video_clips_json=excluded.video_clips_json,
                     audio_clips_json=excluded.audio_clips_json,
                     media_order_json=excluded.media_order_json,
                     revision=visual_editor_timeline_state.revision+1,
                     updated_at=CURRENT_TIMESTAMP""",
                tuple(
                    [project_id]
                    + [json.dumps(v, ensure_ascii=False, separators=(",", ":")) for v in (clips, video, audio, order)]
                ),
            )

    def load_timeline(self, project_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM visual_editor_timeline_state WHERE project_id=?", (project_id,)
            ).fetchone()
        if row is None:
            return {"clips": {}, "videoClips": [], "audioClips": [], "mediaOrder": []}
        return {
            "clips": json.loads(row["clips_json"]),
            "videoClips": json.loads(row["video_clips_json"]),
            "audioClips": json.loads(row["audio_clips_json"]),
            "mediaOrder": json.loads(row["media_order_json"]),
        }
