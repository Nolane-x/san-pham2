SCHEMA_SQL = r'''
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS batch_projects (
    id TEXT PRIMARY KEY,
    user_google_id TEXT NOT NULL DEFAULT 'local',
    expected_image_count INTEGER NOT NULL DEFAULT 0,
    audio_mode TEXT NOT NULL DEFAULT 'global',
    status TEXT NOT NULL DEFAULT 'editing',
    current_index INTEGER,
    operation_kind TEXT,
    operation_stage TEXT,
    operation_progress REAL NOT NULL DEFAULT 0,
    operation_started_at REAL,
    operation_finished_at REAL,
    operation_done INTEGER NOT NULL DEFAULT 0,
    operation_total INTEGER NOT NULL DEFAULT 0,
    render_control TEXT NOT NULL DEFAULT 'running',
    delete_requested INTEGER NOT NULL DEFAULT 0,
    default_config_json TEXT NOT NULL DEFAULT '{}',
    batch_effects_json TEXT NOT NULL DEFAULT '{}',
    output_w INTEGER,
    output_h INTEGER,
    global_audio_path TEXT,
    global_audio_name TEXT,
    global_audio_duration REAL,
    final_video_id INTEGER,
    cleanup_after REAL,
    source_cleanup_after REAL,
    error TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS batch_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL,
    image_index INTEGER NOT NULL,
    original_filename TEXT NOT NULL,
    image_path TEXT NOT NULL,
    audio_path TEXT,
    audio_name TEXT,
    audio_duration REAL,
    audio_start REAL,
    audio_end REAL,
    reveal_duration REAL NOT NULL DEFAULT 8.0,
    hold_duration REAL NOT NULL DEFAULT 1.0,
    config_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'uploaded',
    progress REAL NOT NULL DEFAULT 0,
    video_id INTEGER,
    video_duration REAL,
    error TEXT,
    source_media_id TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(project_id, image_index),
    FOREIGN KEY(project_id) REFERENCES batch_projects(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS batch_videos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL,
    item_id INTEGER,
    kind TEXT NOT NULL,
    file_path TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(project_id) REFERENCES batch_projects(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS visual_editor_media (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    original_name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    duration REAL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(project_id) REFERENCES batch_projects(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS visual_editor_scenes (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    position INTEGER NOT NULL CHECK(position >= 0),
    text TEXT NOT NULL,
    image_prompt TEXT NOT NULL DEFAULT '',
    voice_text TEXT NOT NULL DEFAULT '',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    reveal_duration REAL NOT NULL DEFAULT 8.0,
    hold_duration REAL NOT NULL DEFAULT 1.0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(project_id) REFERENCES batch_projects(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS visual_editor_objects (
    id TEXT PRIMARY KEY,
    scene_id TEXT NOT NULL,
    z_index INTEGER NOT NULL CHECK(z_index >= 0),
    kind TEXT NOT NULL,
    name TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT '',
    x REAL NOT NULL DEFAULT 0,
    y REAL NOT NULL DEFAULT 0,
    width REAL NOT NULL DEFAULT 320 CHECK(width > 0),
    height REAL NOT NULL DEFAULT 180 CHECK(height > 0),
    rotation REAL NOT NULL DEFAULT 0,
    opacity REAL NOT NULL DEFAULT 1 CHECK(opacity >= 0 AND opacity <= 1),
    visible INTEGER NOT NULL DEFAULT 1,
    locked INTEGER NOT NULL DEFAULT 0,
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(scene_id) REFERENCES visual_editor_scenes(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS visual_editor_timeline_state (
    project_id TEXT PRIMARY KEY,
    user_google_id TEXT NOT NULL DEFAULT 'local',
    clips_json TEXT NOT NULL DEFAULT '{}',
    video_clips_json TEXT NOT NULL DEFAULT '[]',
    audio_clips_json TEXT NOT NULL DEFAULT '[]',
    media_order_json TEXT NOT NULL DEFAULT '[]',
    revision INTEGER NOT NULL DEFAULT 1,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(project_id) REFERENCES batch_projects(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS user_project_library (
    project_id TEXT PRIMARY KEY,
    user_google_id TEXT NOT NULL DEFAULT 'local',
    title TEXT NOT NULL DEFAULT '',
    pinned INTEGER NOT NULL DEFAULT 0,
    archived INTEGER NOT NULL DEFAULT 0,
    last_snapshot_hash TEXT,
    last_snapshot_at REAL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(project_id) REFERENCES batch_projects(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_batch_items_project ON batch_items(project_id, image_index);
CREATE INDEX IF NOT EXISTS idx_batch_videos_project ON batch_videos(project_id);
CREATE INDEX IF NOT EXISTS idx_batch_items_source_media ON batch_items(project_id, source_media_id);
CREATE INDEX IF NOT EXISTS idx_visual_scenes_project ON visual_editor_scenes(project_id, position);
CREATE INDEX IF NOT EXISTS idx_visual_objects_scene ON visual_editor_objects(scene_id, z_index);
CREATE INDEX IF NOT EXISTS idx_visual_timeline_user ON visual_editor_timeline_state(user_google_id);
CREATE INDEX IF NOT EXISTS idx_user_project_library_user ON user_project_library(user_google_id, archived, updated_at);
'''
