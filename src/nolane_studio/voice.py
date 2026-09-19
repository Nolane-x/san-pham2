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
    """Generate durable scene narration while honoring provider voice capabilities."""

    CACHE_VERSION = "voice-from-content-v2"

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

    @staticmethod
    def _optional_text(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None

    @staticmethod
    def _reference_audio(
        value: str | Path | None,
    ) -> tuple[str | None, str | None]:
        if value is None:
            return None, None
        path = Path(value)
        if not path.is_file():
            raise ValueError(f"reference audio is missing: {path}")
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
        return str(path), digest.hexdigest()

    @classmethod
    def _cache_key(
        cls,
        *,
        text: str,
        provider_name: str,
        language: str,
        voice: str | None,
        speed: float,
        reference_hash: str | None = None,
        reference_text: str | None = None,
        design_instructions: str | None = None,
    ) -> str:
        payload = {
            "version": cls.CACHE_VERSION,
            "text": text,
            "provider": provider_name,
            "language": language,
            "voice": voice,
            "speed": speed,
            "reference_hash": reference_hash,
            "reference_text": reference_text,
            "design_instructions": design_instructions,
        }
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def _validate_capabilities(
        self,
        provider_name: str,
        *,
        reference_audio: str | None,
        design_instructions: str | None,
    ) -> None:
        descriptor = self.providers.describe(provider_name)
        capabilities = descriptor.capabilities
        if not capabilities.tts:
            raise RuntimeError(
                f"provider {provider_name!r} does not advertise tts capability"
            )
        if reference_audio is not None and not capabilities.clone:
            raise RuntimeError(
                f"provider {provider_name!r} does not advertise clone capability"
            )
        if design_instructions is not None and not capabilities.design:
            raise RuntimeError(
                f"provider {provider_name!r} does not advertise design capability"
            )

    def list_voices(self, provider_name: str) -> list[str]:
        provider_name = str(provider_name).strip()
        if not provider_name:
            raise ValueError("provider_name must not be blank")
        descriptor = self.providers.describe(provider_name)
        if not descriptor.capabilities.list_voices:
            raise RuntimeError(
                f"provider {provider_name!r} does not advertise list_voices capability"
            )
        provider = self.providers.get(provider_name)
        list_method = getattr(provider, "list_voices", None)
        if not callable(list_method):
            raise RuntimeError(
                f"provider {provider_name!r} advertises list_voices but has no list_voices()"
            )
        values = list_method()
        if not isinstance(values, (list, tuple)):
            raise ValueError("voice provider returned an invalid voice catalog")
        result: list[str] = []
        seen: set[str] = set()
        for value in values:
            name = str(value).strip()
            if not name or name in seen:
                continue
            seen.add(name)
            result.append(name)
        return result

    def synthesize_scene(
        self,
        project_id: str,
        scene_id: str,
        *,
        provider_name: str = "tts-api",
        language: str = "vi-VN",
        voice: str | None = None,
        speed: float = 1.0,
        reference_audio: str | Path | None = None,
        reference_text: str | None = None,
        design_instructions: str | None = None,
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

        reference_path, reference_hash = self._reference_audio(reference_audio)
        normalized_reference_text = self._optional_text(reference_text)
        normalized_design = self._optional_text(design_instructions)
        normalized_voice = self._optional_text(voice)
        if normalized_reference_text is not None and reference_path is None:
            raise ValueError("reference_text requires reference_audio")
        self._validate_capabilities(
            provider_name,
            reference_audio=reference_path,
            design_instructions=normalized_design,
        )

        cache_key = self._cache_key(
            text=text,
            provider_name=provider_name,
            language=language,
            voice=normalized_voice,
            speed=speed_value,
            reference_hash=reference_hash,
            reference_text=normalized_reference_text,
            design_instructions=normalized_design,
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
                voice=normalized_voice,
                reference_audio=reference_path,
                reference_text=normalized_reference_text,
                design_instructions=normalized_design,
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
                "voice_name": normalized_voice,
                "voice_speed": speed_value,
                "voice_reference_audio": reference_path,
                "voice_reference_hash": reference_hash,
                "voice_reference_text": normalized_reference_text,
                "voice_design_instructions": normalized_design,
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
        reference_audio: str | Path | None = None,
        reference_text: str | None = None,
        design_instructions: str | None = None,
    ) -> list[VoiceArtifact]:
        return [
            self.synthesize_scene(
                project_id,
                scene["id"],
                provider_name=provider_name,
                language=language,
                voice=voice,
                speed=speed,
                reference_audio=reference_audio,
                reference_text=reference_text,
                design_instructions=design_instructions,
            )
            for scene in self.store.list_scenes(project_id)
        ]
