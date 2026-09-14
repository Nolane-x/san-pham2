import json
from nolane_studio.cli import main


def test_init_db_command_creates_database(tmp_path, capsys):
    db = tmp_path / "nolane_studio.db"
    assert main(["init-db", str(db)]) == 0
    assert db.exists()
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "ok"
    assert out["database"] == str(db)


def test_analyze_command_runs_without_api_or_network(capsys):
    text = "Câu thứ nhất mô tả một ý tưởng rõ ràng. Câu thứ hai mở rộng ý tưởng đó bằng một ví dụ cụ thể."
    assert main(["analyze", text, "--min-words", "5", "--max-words", "12", "--style", "whiteboard"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["provider_used"] is None
    assert result["scenes"]
    assert "pure white background" in result["scenes"][0]["image_prompt"].lower()


def test_render_plan_reports_additive_transition_duration(capsys):
    rc = main([
        "render-plan",
        "--clip", "a:8", "--clip", "b:7",
        "--transition", "a:b:fade:0.6",
    ])
    assert rc == 0
    result = json.loads(capsys.readouterr().out)
    assert result["base_duration"] == 15.0
    assert result["transition_duration"] == 0.6
    assert result["final_duration"] == 15.6


def test_providers_command_is_safe_with_empty_environment(monkeypatch, capsys):
    for key in ["NOLANE_STUDIO_AI_BASE_URL", "NOLANE_STUDIO_AI_MODEL", "NOLANE_STUDIO_TTS_BASE_URL", "NOLANE_STUDIO_TTS_MODEL"]:
        monkeypatch.delenv(key, raising=False)
    assert main(["providers"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result == []
