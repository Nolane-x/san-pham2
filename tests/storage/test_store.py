import sqlite3
from nolane_studio.storage.store import ProjectStore


def test_initialize_is_idempotent_and_creates_recovered_core_tables(tmp_path):
    db = tmp_path / "nolane_studio.db"
    store = ProjectStore(db)
    store.initialize()
    store.initialize()
    with sqlite3.connect(db) as conn:
        tables = {r[0] for r in conn.execute("select name from sqlite_master where type='table'")}
    assert {"batch_projects", "batch_items", "batch_videos", "visual_editor_media", "visual_editor_timeline_state", "user_project_library"} <= tables


def test_project_item_and_timeline_round_trip(tmp_path):
    store = ProjectStore(tmp_path / "nolane_studio.db")
    store.initialize()
    store.create_project("p1", "Demo", expected_image_count=2, output_w=1920, output_h=1080)
    store.add_item("p1", 0, "a.png", "/tmp/a.png", reveal_duration=7.0, hold_duration=1.5, config={"style":"whiteboard"})
    project = store.get_project("p1")
    assert project["title"] == "Demo"
    assert project["output_w"] == 1920
    items = store.list_items("p1")
    assert items[0]["image_index"] == 0
    assert items[0]["config"] == {"style": "whiteboard"}

    state = {"clips": {"0": {"start": 0.0}}, "videoClips": [], "audioClips": [], "mediaOrder": ["0"]}
    store.save_timeline("p1", state)
    loaded = store.load_timeline("p1")
    assert loaded == state


def test_create_project_is_transactional_and_rejects_duplicates(tmp_path):
    store = ProjectStore(tmp_path / "nolane_studio.db")
    store.initialize()
    store.create_project("p1", "Demo")
    try:
        store.create_project("p1", "Duplicate")
    except ValueError as exc:
        assert "already exists" in str(exc)
    else:
        raise AssertionError("duplicate project was accepted")


def test_list_projects_returns_newest_library_entries(tmp_path):
    from nolane_studio.storage.store import ProjectStore

    store = ProjectStore(tmp_path / "studio.db")
    store.initialize()
    store.create_project("a", "First")
    store.create_project("b", "Second")
    projects = store.list_projects()
    assert [row["project_id"] for row in projects] == ["b", "a"]
    assert projects[0]["title"] == "Second"


def test_media_library_round_trips_in_project_order(tmp_path):
    from nolane_studio.storage.store import ProjectStore

    store = ProjectStore(tmp_path / "studio.db")
    store.initialize()
    store.create_project("p", "Media")
    first = store.add_media("p", "image", "cover.png", "/tmp/cover.png")
    second = store.add_media("p", "video", "clip.mp4", "/tmp/clip.mp4", duration=3.5)
    media = store.list_media("p")
    assert [m["id"] for m in media] == [first, second]
    assert media[1]["duration"] == 3.5
