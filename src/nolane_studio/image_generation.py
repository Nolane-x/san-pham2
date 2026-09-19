from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .ai.prompts import build_image_prompt
from .domain import ImageRequest, Scene
from .providers.registry import ProviderRegistry
from .storage.store import ProjectStore


@dataclass(frozen=True, slots=True)
class ImageArtifact:
    scene_id: str
    media_id: str
    path: str


class ImageGenerationService:
    """Generate durable scene visuals and reuse them while inputs are unchanged."""

    CACHE_VERSION = "generated-image-v1"

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
    def _style(scene: Mapping[str, Any]) -> str:
        metadata = scene.get("metadata") or {}
        if not isinstance(metadata, Mapping):
            raise ValueError("scene metadata must be a mapping")
        render_config = metadata.get("render_config")
        if render_config is None:
            return "whiteboard"
        if not isinstance(render_config, Mapping):
            raise ValueError("scene render_config must be a mapping")
        return str(render_config.get("style") or "whiteboard").strip().lower() or "whiteboard"

    @staticmethod
    def _domain_scene(scene: Mapping[str, Any]) -> Scene:
        return Scene(
            index=int(scene.get("position", 0)),
            text=str(scene.get("text") or ""),
            image_prompt=str(scene.get("image_prompt") or ""),
            voice_text=str(scene.get("voice_text") or ""),
            metadata=dict(scene.get("metadata") or {}),
        )

    @classmethod
    def _cache_key(
        cls,
        *,
        prompt: str,
        provider_name: str,
        size: str,
    ) -> str:
        payload = {
            "version": cls.CACHE_VERSION,
            "prompt": prompt,
            "provider": provider_name,
            "size": size,
        }
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def generate_scene(
        self,
        project_id: str,
        scene_id: str,
        *,
        provider_name: str = "image-api",
        size: str = "1024x1024",
        additional_prompt: str = "",
    ) -> ImageArtifact:
        scene = self._scene(project_id, scene_id)
        provider_name = str(provider_name).strip()
        if not provider_name:
            raise ValueError("provider_name must not be blank")

        request = ImageRequest(
            build_image_prompt(
                self._domain_scene(scene),
                self._style(scene),
                additional_prompt,
            ),
            size=size,
        )
        cache_key = self._cache_key(
            prompt=request.prompt,
            provider_name=provider_name,
            size=request.size,
        )

        media_id = f"image-{scene_id}"
        output_dir = self.workspace_root / "images" / project_id
        path = output_dir / f"{scene_id}.png"
        metadata = dict(scene.get("metadata") or {})
        existing_media = {
            item["id"]: item for item in self.store.list_media(project_id)
        }

        if metadata.get("image_cache_key") == cache_key and path.is_file():
            if media_id not in existing_media:
                self.store.add_media(
                    project_id,
                    "image",
                    f"Generated - {str(scene.get('text') or 'scene')[:48]}",
                    str(path),
                    media_id=media_id,
                )
            return ImageArtifact(scene_id=scene_id, media_id=media_id, path=str(path))

        provider = self.providers.get(provider_name)
        image_bytes = provider.generate(request)
        if not isinstance(image_bytes, (bytes, bytearray)) or not image_bytes:
            raise ValueError("image provider returned empty image")

        output_dir.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + ".tmp")
        temp.write_bytes(bytes(image_bytes))
        temp.replace(path)

        if media_id not in existing_media:
            self.store.add_media(
                project_id,
                "image",
                f"Generated - {str(scene.get('text') or 'scene')[:48]}",
                str(path),
                media_id=media_id,
            )

        metadata.update(
            {
                "visual_media_id": media_id,
                "visual_path": str(path),
                "image_path": str(path),
                "image_provider": provider_name,
                "image_size": request.size,
                "image_cache_key": cache_key,
            }
        )
        self.store.update_scene(scene_id, metadata=metadata)
        return ImageArtifact(scene_id=scene_id, media_id=media_id, path=str(path))

    def generate_project(
        self,
        project_id: str,
        *,
        provider_name: str = "image-api",
        size: str = "1024x1024",
        additional_prompt: str = "",
    ) -> list[ImageArtifact]:
        return [
            self.generate_scene(
                project_id,
                scene["id"],
                provider_name=provider_name,
                size=size,
                additional_prompt=additional_prompt,
            )
            for scene in self.store.list_scenes(project_id)
        ]
