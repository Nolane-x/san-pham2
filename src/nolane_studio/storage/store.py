from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping

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
        import uuid

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
