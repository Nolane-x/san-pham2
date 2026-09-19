from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ProviderSettings:
    analysis_base_url: str = ""
    analysis_model: str = ""
    image_base_url: str = ""
    image_model: str = ""
    vision_base_url: str = ""
    vision_model: str = ""
    stt_base_url: str = ""
    stt_model: str = ""
    tts_base_url: str = ""
    tts_model: str = ""


def default_data_dir() -> Path:
    base = Path(os.getenv("LOCALAPPDATA") or (Path.home() / ".local" / "share"))
    return base / "Nolane Studio"


class SettingsStore:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else default_data_dir() / "settings.json"

    def load(self) -> ProviderSettings:
        if not self.path.exists():
            return ProviderSettings()
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, TypeError):
            return ProviderSettings()
        if not isinstance(raw, dict):
            return ProviderSettings()
        allowed = {
            field: str(raw.get(field, "")).strip()
            for field in ProviderSettings.__dataclass_fields__
        }
        return ProviderSettings(**allowed)

    def save(self, settings: ProviderSettings) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(self.path.suffix + ".tmp")
        temp.write_text(
            json.dumps(asdict(settings), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temp.replace(self.path)
