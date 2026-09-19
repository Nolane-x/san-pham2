from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .domain import VoiceRequest
from .providers.registry import ProviderRegistry
from .storage.store import ProjectStore


@dataclass(frozen=True, slots=True)
class VoiceArtifact:
    scene_id: str
    media_id: str
    path: str


class VoiceFromContentService:
    """Generate one durable narration asset per scene and reuse it while inputs are unchanged."""

    CACHE_VERSION = "voice-from-content-v1"

    def __init__(
        self,
        store: ProjectStore,
        providers: ProviderRegistry,
        workspace_root: str | Path,
    ) -> None:
        self.store = store
        self.providers = providers
        self.workspace_root = Path(workspace_root)

    def _scene(self, project_id: str, scene_id: str) -> dict[str, Any]:
        for scene in self.store.list_scenes(project_id):
            if scene["id"] == scene_id:
                return scene
        raise KeyError(scene_id)

    @classmethod
    def _cache_key(
        cls,
        *,
        text: str,
        provider_name: str,
        language: str,
        voice: str | None,
        speed: float,
    ) -> str:
        payload = {
            "version": cls.CACHE_VERSION,
            "text": text,
            "provider": provider_name,
            "language": language,
            "voice": voice,
            "speed": speed,
        }
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def synthesize_scene(
        self,
        project_id: str,
        scene_id: str,
        *,
        provider_name: str = "tts-api",
        language: str = "vi-VN",
        voice: str | None = None,
        speed: float = 1.0,
    ) -> VoiceArtifact:
        scene = self._scene(project_id, scene_id)
        text = str(scene.get("voice_text") or scene.get("text") or "").strip()
        if not text:
            raise ValueError("scene has no text for voice generation")
        provider_name = str(provider_name).strip()
        if not provider_name:
            raise ValueError("provider_name must not be blank")
        language = str(language).strip()
        if not language:
            raise ValueError("language must not be blank")
        speed_value = float(speed)
        if not math.isfinite(speed_value) or speed_value <= 0:
            raise ValueError("speed must be a positive finite number")

        cache_key = self._cache_key(
            text=text,
            provider_name=provider_name,
            language=language,
            voice=voice,
            speed=speed_value,
        )
        media_id = f"voice-{scene_id}"
        output_dir = self.workspace_root / "voice" / project_id
        path = output_dir / f"{scene_id}.mp3"
        metadata = dict(scene.get("metadata") or {})
        existing_media = {item["id"]: item for item in self.store.list_media(project_id)}

        if metadata.get("voice_cache_key") == cache_key and path.is_file():
            if media_id not in existing_media:
                self.store.add_media(
                    project_id,
                    "audio",
                    f"Voice - {str(scene.get('text') or 'scene')[:48]}",
                    str(path),
                    media_id=media_id,
                )
            return VoiceArtifact(scene_id=scene_id, media_id=media_id, path=str(path))

        provider = self.providers.get(provider_name)
        audio = provider.synthesize(
            VoiceRequest(
                text=text,
                language=language,
                voice=voice,
                speed=speed_value,
            )
        )
        if not isinstance(audio, (bytes, bytearray)) or not audio:
            raise ValueError("TTS provider returned empty audio")

        output_dir.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + ".tmp")
        temp.write_bytes(bytes(audio))
        temp.replace(path)

        if media_id not in existing_media:
            self.store.add_media(
                project_id,
                "audio",
                f"Voice - {str(scene.get('text') or 'scene')[:48]}",
                str(path),
                media_id=media_id,
            )

        metadata.update(
            {
                "voice_media_id": media_id,
                "voice_path": str(path),
                "voice_provider": provider_name,
                "voice_language": language,
                "voice_name": voice,
                "voice_speed": speed_value,
                "voice_cache_key": cache_key,
            }
        )
        self.store.update_scene(scene_id, metadata=metadata)
        return VoiceArtifact(scene_id=scene_id, media_id=media_id, path=str(path))

    def synthesize_project(
        self,
        project_id: str,
        *,
        provider_name: str = "tts-api",
        language: str = "vi-VN",
        voice: str | None = None,
        speed: float = 1.0,
    ) -> list[VoiceArtifact]:
        return [
            self.synthesize_scene(
                project_id,
                scene["id"],
                provider_name=provider_name,
                language=language,
                voice=voice,
                speed=speed,
            )
            for scene in self.store.list_scenes(project_id)
        ]
