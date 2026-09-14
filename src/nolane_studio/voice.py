from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .domain import VoiceRequest
from .providers.registry import ProviderRegistry
from .storage.store import ProjectStore


@dataclass(frozen=True, slots=True)
class VoiceArtifact:
    scene_id: str
    media_id: str
    path: str


class VoiceFromContentService:
    """Generate narration per scene and attach it to durable project media."""

    def __init__(
        self,
        store: ProjectStore,
        providers: ProviderRegistry,
        workspace_root: str | Path,
    ) -> None:
        self.store = store
        self.providers = providers
        self.workspace_root = Path(workspace_root)

    def _scene(self, project_id: str, scene_id: str) -> dict:
        for scene in self.store.list_scenes(project_id):
            if scene["id"] == scene_id:
                return scene
        raise KeyError(scene_id)

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
        provider = self.providers.get(provider_name)
        text = str(scene.get("voice_text") or scene.get("text") or "").strip()
        if not text:
            raise ValueError("scene has no text for voice generation")
        audio = provider.synthesize(
            VoiceRequest(text=text, language=language, voice=voice, speed=speed)
        )
        if not isinstance(audio, (bytes, bytearray)) or not audio:
            raise ValueError("TTS provider returned empty audio")

        output_dir = self.workspace_root / "voice" / project_id
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / f"{scene_id}.mp3"
        temp = path.with_suffix(path.suffix + ".tmp")
        temp.write_bytes(bytes(audio))
        temp.replace(path)

        media_id = f"voice-{scene_id}"
        existing = {item["id"]: item for item in self.store.list_media(project_id)}
        if media_id not in existing:
            self.store.add_media(
                project_id,
                "audio",
                f"Voice - {scene.get('text', 'scene')[:48]}",
                str(path),
                media_id=media_id,
            )

        metadata = dict(scene.get("metadata") or {})
        metadata.update(
            {
                "voice_media_id": media_id,
                "voice_path": str(path),
                "voice_provider": provider_name,
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
