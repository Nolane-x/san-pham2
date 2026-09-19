import importlib.util

from nolane_studio.storage.store import ProjectStore


def test_ai_analyze_result_can_be_persisted_without_destroying_existing_scene_metadata(tmp_path):
    assert importlib.util.find_spec("nolane_studio.ai.object_voice") is not None
    from nolane_studio.ai.object_voice import merge_analysis_metadata

    store = ProjectStore(tmp_path / "studio.db")
    store.initialize()
    store.create_project("p1", "Analyze")
    scene_id = store.add_scene("p1", "Scene", metadata={"custom": "keep"})
    scene = store.list_scenes("p1")[0]

    merged = merge_analysis_metadata(scene["metadata"], {"transcript": "hello", "objects": [{"label": "cat"}]})
    store.update_scene(scene_id, metadata=merged)

    metadata = store.list_scenes("p1")[0]["metadata"]
    assert metadata["custom"] == "keep"
    assert metadata["ai_analysis"]["transcript"] == "hello"
    assert metadata["ai_analysis"]["objects"][0]["label"] == "cat"
