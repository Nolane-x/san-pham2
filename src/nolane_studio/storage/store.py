from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

from ..render.config import InvalidRenderConfig, normalize_render_config
from .schema import SCHEMA_SQL


class ProjectStore:
    _VISUAL_OBJECT_KINDS = {"image", "video", "text", "shape", "drawing"}

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
    def _stored_render_config(metadata: Mapping[str, Any]) -> dict[str, Any]:
        raw = metadata.get("render_config")
        if raw is None:
            return {}
        if not isinstance(raw, Mapping):
            raise InvalidRenderConfig("render_config must be a mapping")
        return dict(raw)

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

    def update_scene_render_settings(
        self,
        scene_id: str,
        *,
        reveal_duration: float | None = None,
        hold_duration: float | None = None,
        settings: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM visual_editor_scenes WHERE id=?", (scene_id,)).fetchone()
            if row is None:
                raise KeyError(scene_id)
            metadata = json.loads(row["metadata_json"] or "{}")
            stored = self._stored_render_config(metadata)
            stored.update(dict(settings or {}))
            stored["reveal_duration"] = row["reveal_duration"] if reveal_duration is None else reveal_duration
            stored["hold_duration"] = row["hold_duration"] if hold_duration is None else hold_duration
            normalized = normalize_render_config(stored)
            canonical = dict(normalized)
            extras = dict(canonical.pop("extras", {}) or {})
            canonical.update(extras)
            metadata["render_config"] = {
                key: value
                for key, value in canonical.items()
                if key not in {"reveal_duration", "hold_duration"}
            }
            conn.execute(
                """UPDATE visual_editor_scenes
                   SET reveal_duration=?, hold_duration=?, metadata_json=?, updated_at=CURRENT_TIMESTAMP
                   WHERE id=?""",
                (
                    normalized["reveal_duration"],
                    normalized["hold_duration"],
                    json.dumps(metadata, ensure_ascii=False, separators=(",", ":")),
                    scene_id,
                ),
            )
            conn.execute(
                "UPDATE user_project_library SET updated_at=CURRENT_TIMESTAMP WHERE project_id=?",
                (row["project_id"],),
            )
        return normalized

    def get_scene_render_settings(self, scene_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM visual_editor_scenes WHERE id=?", (scene_id,)).fetchone()
        if row is None:
            raise KeyError(scene_id)
        metadata = json.loads(row["metadata_json"] or "{}")
        raw = self._stored_render_config(metadata)
        raw["reveal_duration"] = row["reveal_duration"]
        raw["hold_duration"] = row["hold_duration"]
        return normalize_render_config(raw)

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

    @classmethod
    def _normalize_visual_object_values(
        cls,
        *,
        kind: str,
        width: float,
        height: float,
        opacity: float,
    ) -> tuple[str, float, float, float]:
        normalized_kind = str(kind).strip().lower()
        if normalized_kind not in cls._VISUAL_OBJECT_KINDS:
            allowed = ", ".join(sorted(cls._VISUAL_OBJECT_KINDS))
            raise ValueError(f"kind must be one of: {allowed}")
        width_value = float(width)
        height_value = float(height)
        opacity_value = float(opacity)
        if width_value <= 0:
            raise ValueError("width must be > 0")
        if height_value <= 0:
            raise ValueError("height must be > 0")
        if not 0.0 <= opacity_value <= 1.0:
            raise ValueError("opacity must be within 0..1")
        return normalized_kind, width_value, height_value, opacity_value

    @classmethod
    def _decode_stored_object_kind(cls, value: Any, *, object_id: str) -> Any:
        raw = str(value)
        canonical = raw.strip().lower()
        if canonical in cls._VISUAL_OBJECT_KINDS and raw != canonical:
            allowed = ", ".join(sorted(cls._VISUAL_OBJECT_KINDS))
            raise ValueError(
                f"visual object {object_id} kind must be stored canonically as one of: {allowed}"
            )
        return value


    @staticmethod
    def _decode_stored_object_flag(value: Any, *, object_id: str, field: str) -> bool:
        if type(value) is not int or value not in {0, 1}:
            raise ValueError(
                f"visual object {object_id} {field} must be stored as 0 or 1"
            )
        return bool(value)

    @staticmethod
    def _touch_project_for_scene(conn: sqlite3.Connection, scene_id: str) -> None:
        row = conn.execute("SELECT project_id FROM visual_editor_scenes WHERE id=?", (scene_id,)).fetchone()
        if row is None:
            return
        project_id = str(row["project_id"])
        conn.execute(
            "UPDATE user_project_library SET updated_at=CURRENT_TIMESTAMP WHERE project_id=?",
            (project_id,),
        )

    def add_visual_object(
        self,
        scene_id: str,
        kind: str,
        *,
        name: str = "",
        source: str = "",
        x: float = 0.0,
        y: float = 0.0,
        width: float = 320.0,
        height: float = 180.0,
        rotation: float = 0.0,
        opacity: float = 1.0,
        visible: bool = True,
        locked: bool = False,
        payload: Mapping[str, Any] | None = None,
        z_index: int | None = None,
    ) -> str:
        normalized_kind, width_value, height_value, opacity_value = self._normalize_visual_object_values(
            kind=kind,
            width=width,
            height=height,
            opacity=opacity,
        )
        with self._connect() as conn:
            if conn.execute("SELECT 1 FROM visual_editor_scenes WHERE id=?", (scene_id,)).fetchone() is None:
                raise KeyError(scene_id)
            count = int(
                conn.execute(
                    "SELECT COUNT(*) FROM visual_editor_objects WHERE scene_id=?",
                    (scene_id,),
                ).fetchone()[0]
            )
            target = count if z_index is None else int(z_index)
            if target < 0 or target > count:
                raise ValueError(f"z_index must be within 0..{count}")
            conn.execute(
                "UPDATE visual_editor_objects SET z_index=z_index+1, updated_at=CURRENT_TIMESTAMP WHERE scene_id=? AND z_index>=?",
                (scene_id, target),
            )
            object_id = uuid.uuid4().hex
            conn.execute(
                """INSERT INTO visual_editor_objects(
                       id,scene_id,z_index,kind,name,source,x,y,width,height,rotation,
                       opacity,visible,locked,payload_json
                   ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    object_id,
                    scene_id,
                    target,
                    normalized_kind,
                    str(name or ""),
                    str(source or ""),
                    float(x),
                    float(y),
                    width_value,
                    height_value,
                    float(rotation),
                    opacity_value,
                    1 if visible else 0,
                    1 if locked else 0,
                    json.dumps(dict(payload or {}), ensure_ascii=False, separators=(",", ":")),
                ),
            )
            self._touch_project_for_scene(conn, scene_id)
            return object_id

    def list_visual_objects(self, scene_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM visual_editor_objects WHERE scene_id=? ORDER BY z_index, rowid",
                (scene_id,),
            ).fetchall()
        result: list[dict[str, Any]] = []
        seen_z_indices: set[int] = set()
        for row in rows:
            item = dict(row)
            object_id = str(item["id"])
            z_index = int(item["z_index"])
            if z_index in seen_z_indices:
                raise ValueError(
                    f"scene {scene_id} visual object z_index {z_index} must be unique"
                )
            seen_z_indices.add(z_index)
            item["kind"] = self._decode_stored_object_kind(
                item["kind"],
                object_id=object_id,
            )
            item["visible"] = self._decode_stored_object_flag(
                item["visible"],
                object_id=object_id,
                field="visible",
            )
            item["locked"] = self._decode_stored_object_flag(
                item["locked"],
                object_id=object_id,
                field="locked",
            )
            item["payload"] = json.loads(item.pop("payload_json") or "{}")
            result.append(item)
        return result

    def update_visual_object(
        self,
        object_id: str,
        *,
        name: str | None = None,
        source: str | None = None,
        x: float | None = None,
        y: float | None = None,
        width: float | None = None,
        height: float | None = None,
        rotation: float | None = None,
        opacity: float | None = None,
        visible: bool | None = None,
        locked: bool | None = None,
        payload: Mapping[str, Any] | None = None,
    ) -> None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM visual_editor_objects WHERE id=?", (object_id,)).fetchone()
            if row is None:
                raise KeyError(object_id)
            _, width_value, height_value, opacity_value = self._normalize_visual_object_values(
                kind=str(row["kind"]),
                width=float(row["width"]) if width is None else float(width),
                height=float(row["height"]) if height is None else float(height),
                opacity=float(row["opacity"]) if opacity is None else float(opacity),
            )
            updates: list[str] = []
            values: list[Any] = []
            for column, value in (
                ("name", None if name is None else str(name)),
                ("source", None if source is None else str(source)),
                ("x", None if x is None else float(x)),
                ("y", None if y is None else float(y)),
                ("rotation", None if rotation is None else float(rotation)),
            ):
                if value is not None:
                    updates.append(f"{column}=?")
                    values.append(value)
            if width is not None:
                updates.append("width=?")
                values.append(width_value)
            if height is not None:
                updates.append("height=?")
                values.append(height_value)
            if opacity is not None:
                updates.append("opacity=?")
                values.append(opacity_value)
            if visible is not None:
                updates.append("visible=?")
                values.append(1 if visible else 0)
            if locked is not None:
                updates.append("locked=?")
                values.append(1 if locked else 0)
            if payload is not None:
                updates.append("payload_json=?")
                values.append(json.dumps(dict(payload), ensure_ascii=False, separators=(",", ":")))
            if not updates:
                return
            updates.append("updated_at=CURRENT_TIMESTAMP")
            values.append(object_id)
            conn.execute(f"UPDATE visual_editor_objects SET {', '.join(updates)} WHERE id=?", values)
            self._touch_project_for_scene(conn, str(row["scene_id"]))

    def move_visual_object(self, object_id: str, new_z_index: int) -> None:
        target = int(new_z_index)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT scene_id, z_index FROM visual_editor_objects WHERE id=?",
                (object_id,),
            ).fetchone()
            if row is None:
                raise KeyError(object_id)
            scene_id = str(row["scene_id"])
            current = int(row["z_index"])
            count = int(
                conn.execute(
                    "SELECT COUNT(*) FROM visual_editor_objects WHERE scene_id=?",
                    (scene_id,),
                ).fetchone()[0]
            )
            if target < 0 or target >= count:
                raise ValueError(f"z_index must be within 0..{max(0, count - 1)}")
            if target == current:
                return
            if current < target:
                conn.execute(
                    """UPDATE visual_editor_objects
                       SET z_index=z_index-1, updated_at=CURRENT_TIMESTAMP
                       WHERE scene_id=? AND z_index>? AND z_index<=?""",
                    (scene_id, current, target),
                )
            else:
                conn.execute(
                    """UPDATE visual_editor_objects
                       SET z_index=z_index+1, updated_at=CURRENT_TIMESTAMP
                       WHERE scene_id=? AND z_index>=? AND z_index<?""",
                    (scene_id, target, current),
                )
            conn.execute(
                "UPDATE visual_editor_objects SET z_index=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (target, object_id),
            )
            self._touch_project_for_scene(conn, scene_id)

    def delete_visual_object(self, object_id: str) -> None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT scene_id, z_index FROM visual_editor_objects WHERE id=?",
                (object_id,),
            ).fetchone()
            if row is None:
                raise KeyError(object_id)
            scene_id = str(row["scene_id"])
            z_index = int(row["z_index"])
            conn.execute("DELETE FROM visual_editor_objects WHERE id=?", (object_id,))
            conn.execute(
                "UPDATE visual_editor_objects SET z_index=z_index-1, updated_at=CURRENT_TIMESTAMP WHERE scene_id=? AND z_index>?",
                (scene_id, z_index),
            )
            self._touch_project_for_scene(conn, scene_id)

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
