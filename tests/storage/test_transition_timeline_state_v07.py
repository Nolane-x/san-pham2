from __future__ import annotations

import sqlite3

from nolane_studio.storage.store import ProjectStore


def test_timeline_transition_state_round_trips_and_migrates_existing_database(tmp_path):
    db = tmp_path / "studio.db"
    store = ProjectStore(db)
    store.initialize()
    store.create_project("p1", "Transitions")

    state = {
        "clips": {},
        "videoClips": [],
        "audioClips": [],
        "mediaOrder": ["scene-a", "scene-b"],
        "transitions": [
            {
                "from_id": "scene-a",
                "to_id": "scene-b",
                "effect": "fade",
                "duration": 0.75,
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
    assert "transitions_json" in columns


def test_initialize_adds_transition_column_to_pre_v07_timeline_table(tmp_path):
    db = tmp_path / "legacy.db"
    with sqlite3.connect(db) as conn:
        conn.executescript(
            """
            PRAGMA foreign_keys = OFF;
            CREATE TABLE batch_projects (
                id TEXT PRIMARY KEY,
                cleanup_after REAL,
                source_cleanup_after REAL
            );
            INSERT INTO batch_projects(id) VALUES('p1');
            CREATE TABLE visual_editor_timeline_state (
                project_id TEXT PRIMARY KEY,
                user_google_id TEXT NOT NULL DEFAULT 'local',
                clips_json TEXT NOT NULL DEFAULT '{}',
                video_clips_json TEXT NOT NULL DEFAULT '[]',
                audio_clips_json TEXT NOT NULL DEFAULT '[]',
                media_order_json TEXT NOT NULL DEFAULT '[]',
                revision INTEGER NOT NULL DEFAULT 1,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            INSERT INTO visual_editor_timeline_state(project_id) VALUES('p1');
            """
        )

    ProjectStore(db).initialize()

    with sqlite3.connect(db) as conn:
        columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(visual_editor_timeline_state)")
        }
        value = conn.execute(
            "SELECT transitions_json FROM visual_editor_timeline_state WHERE project_id='p1'"
        ).fetchone()[0]
    assert "transitions_json" in columns
    assert value == "[]"
