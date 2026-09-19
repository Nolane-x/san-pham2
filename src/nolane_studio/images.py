from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .ai.prompts import build_image_prompt
from .domain import ImageRequest, Scene
from .providers.registry import ProviderRegistry
from .storage.store import ProjectStore


@dataclass(frozen=True, slots=True)
class GeneratedImageArtifact:
    scene_id: str
    media_id: str
    path: str
    prompt: str


class GeneratedImageService:
    """Generate durable per-scene image assets from recovered hardened prompts."""

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

    @classmethod
    def _cache_key(
        cls,
        *,
        prompt: str,
        provider_name: str,
        size: str,
    ) -> str:
        encoded = json.dumps(
            {
                "version": cls.CACHE_VERSION,
                "prompt": prompt,
                "provider": provider_name,
                "size": size,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def _ensure_canvas_layer(
        self,
        scene_id: str,
        *,
        media_id: str,
        path: Path,
    ) -> str:
        matches = []
        for obj in self.store.list_visual_objects(scene_id):
            if str(obj.get("kind", "")).strip().lower() != "image":
                continue
            payload = obj.get("payload")
            if not isinstance(payload, dict):
                continue
            if payload.get("generated_scene_image") is True:
                matches.append(obj)

        if len(matches) > 1:
            raise ValueError(
                f"scene {scene_id} contains multiple generated image canvas layers"
            )

        payload = {
            "media_id": media_id,
            "fit": "contain",
            "generated_scene_image": True,
        }
        if matches:
            object_id = str(matches[0]["id"])
            self.store.update_visual_object(
                object_id,
                source=str(path),
                payload=payload,
            )
            return object_id

        return self.store.add_visual_object(
            scene_id,
            "image",
            name="Generated scene image",
            source=str(path),
            x=0.0,
            y=0.0,
            width=1280.0,
            height=720.0,
            payload=payload,
            z_index=0,
        )

    def generate_scene(
        self,
        project_id: str,
        scene_id: str,
        *,
        provider_name: str = "image-api",
        style: str = "whiteboard",
        size: str = "1024x1024",
        additional_prompt: str = "",
    ) -> GeneratedImageArtifact:
        scene = self._scene(project_id, scene_id)
        provider_name = str(provider_name).strip()
        if not provider_name:
            raise ValueError("provider_name must not be blank")

        scene_model = Scene(
            index=int(scene.get("position", 0)),
            text=str(scene.get("text") or ""),
            image_prompt=str(scene.get("image_prompt") or ""),
            voice_text=str(scene.get("voice_text") or ""),
            metadata=scene.get("metadata") or {},
        )
        prompt = build_image_prompt(scene_model, style, additional_prompt)
        request = ImageRequest(prompt=prompt, size=size)
        cache_key = self._cache_key(
            prompt=request.prompt,
            provider_name=provider_name,
            size=request.size,
        )

        media_id = f"image-{scene_id}"
        output_dir = self.workspace_root / "images" / project_id
        path = output_dir / f"{scene_id}.png"
        metadata = dict(scene.get("metadata") or {})
        existing_media = {item["id"]: item for item in self.store.list_media(project_id)}

        if metadata.get("generated_image_cache_key") == cache_key and path.is_file():
            if media_id not in existing_media:
                self.store.add_media(
                    project_id,
                    "image",
                    f"Generated - {str(scene.get('text') or 'scene')[:48]}",
                    str(path),
                    media_id=media_id,
                )
            self._ensure_canvas_layer(
                scene_id,
                media_id=media_id,
                path=path,
            )
            return GeneratedImageArtifact(scene_id, media_id, str(path), request.prompt)

        provider = self.providers.get(provider_name)
        payload = provider.generate(request)
        if not isinstance(payload, (bytes, bytearray)) or not payload:
            raise ValueError("image provider returned empty image")

        output_dir.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + ".tmp")
        temp.write_bytes(bytes(payload))
        temp.replace(path)

        if media_id not in existing_media:
            self.store.add_media(
                project_id,
                "image",
                f"Generated - {str(scene.get('text') or 'scene')[:48]}",
                str(path),
                media_id=media_id,
            )

        self._ensure_canvas_layer(
            scene_id,
            media_id=media_id,
            path=path,
        )

        metadata.update(
            {
                "generated_image_media_id": media_id,
                "generated_image_path": str(path),
                "generated_image_provider": provider_name,
                "generated_image_prompt": request.prompt,
                "generated_image_size": request.size,
                "generated_image_cache_key": cache_key,
                # Recovered AI Analyze consumes the active scene visual.
                "visual_media_id": media_id,
                "visual_path": str(path),
            }
        )
        self.store.update_scene(scene_id, metadata=metadata)
        return GeneratedImageArtifact(scene_id, media_id, str(path), request.prompt)

    def generate_project(
        self,
        project_id: str,
        *,
        provider_name: str = "image-api",
        style: str = "whiteboard",
        size: str = "1024x1024",
        additional_prompt: str = "",
    ) -> list[GeneratedImageArtifact]:
        return [
            self.generate_scene(
                project_id,
                scene["id"],
                provider_name=provider_name,
                style=style,
                size=size,
                additional_prompt=additional_prompt,
            )
            for scene in self.store.list_scenes(project_id)
        ]
