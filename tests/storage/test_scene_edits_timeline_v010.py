from __future__ import annotations

import sqlite3

import pytest

from nolane_studio.storage.store import ProjectStore


def test_scene_edits_round_trip_in_explicit_rebuild_timeline_field(tmp_path):
    db = tmp_path / "studio.db"
    store = ProjectStore(db)
    store.initialize()
    store.create_project("p1", "Scene edits")

    state = {
        "clips": {},
        "videoClips": [],
        "audioClips": [],
        "mediaOrder": [],
        "sceneEdits": [
            {
                "scene_id": "scene-a",
                "trim_start": 1.25,
                "trim_end": 5.75,
                "speed": 1.5,
            }
        ],
    }
    store.save_timeline("p1", state)

    assert store.load_timeline("p1") == state
    with sqlite3.connect(db) as conn:
        columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(visual_editor_timeline_state)")
        }
    assert "scene_edits_json" in columns


def test_scene_edits_migrate_existing_timeline_schema(tmp_path):
    db = tmp_path / "old.db"
    conn = sqlite3.connect(db)
    conn.executescript(
        """
        CREATE TABLE batch_projects(\n            id TEXT PRIMARY KEY,\n            cleanup_after REAL,\n            source_cleanup_after REAL\n        );
        CREATE TABLE visual_editor_timeline_state(
            project_id TEXT PRIMARY KEY,
            user_google_id TEXT NOT NULL DEFAULT 'local',
            clips_json TEXT NOT NULL DEFAULT '{}',
            video_clips_json TEXT NOT NULL DEFAULT '[]',
            audio_clips_json TEXT NOT NULL DEFAULT '[]',
            media_order_json TEXT NOT NULL DEFAULT '[]',
            transitions_json TEXT NOT NULL DEFAULT '[]',
            revision INTEGER NOT NULL DEFAULT 1,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    conn.close()

    store = ProjectStore(db)
    store.initialize()

    with sqlite3.connect(db) as conn:
        columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(visual_editor_timeline_state)")
        }
    assert "scene_edits_json" in columns
