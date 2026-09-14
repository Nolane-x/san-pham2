from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Mapping, Protocol, Sequence

from nolane_studio.domain import ImageRequest, Scene, VoiceRequest


@dataclass(frozen=True, slots=True)
class HttpResponse:
    status: int
    headers: Mapping[str, str]
    body: bytes


class HttpTransport(Protocol):
    def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        json_body: Mapping[str, Any] | None = None,
        timeout: float = 60.0,
    ) -> HttpResponse: ...


class UrllibTransport:
    def request(self, method, url, *, headers=None, json_body=None, timeout=60.0) -> HttpResponse:
        body = None if json_body is None else json.dumps(json_body, ensure_ascii=False).encode("utf-8")
        merged = {"User-Agent": "Nolane Studio-Rebuild/0.1", **dict(headers or {})}
        if body is not None:
            merged.setdefault("Content-Type", "application/json")
        req = urllib.request.Request(url, data=body, headers=merged, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                return HttpResponse(response.status, dict(response.headers.items()), response.read())
        except urllib.error.HTTPError as exc:
            payload = exc.read()
            raise RuntimeError(f"HTTP {exc.code} from provider: {payload[:500]!r}") from exc


def _join(base_url: str, suffix: str) -> str:
    return base_url.rstrip("/") + "/" + suffix.lstrip("/")


def _auth_headers(api_key: str | None) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}"} if api_key else {}


class OpenAICompatibleTTSProvider:
    def __init__(
        self,
        base_url: str,
        api_key: str | None,
        model: str,
        *,
        default_voice: str = "alloy",
        transport: HttpTransport | None = None,
        timeout: float = 120.0,
    ) -> None:
        self.base_url = base_url
        self.api_key = api_key
        self.model = model
        self.default_voice = default_voice
        self.transport = transport or UrllibTransport()
        self.timeout = timeout

    def synthesize(self, request: VoiceRequest) -> bytes:
        response = self.transport.request(
            "POST",
            _join(self.base_url, "audio/speech"),
            headers=_auth_headers(self.api_key),
            json_body={
                "model": self.model,
                "input": request.text,
                "voice": request.voice or self.default_voice,
                "speed": request.speed,
                "response_format": "mp3",
            },
            timeout=self.timeout,
        )
        if not 200 <= response.status < 300:
            raise RuntimeError(f"TTS provider returned HTTP {response.status}")
        return response.body


class GenericHttpTTSProvider:
    """Simple JSON-in/binary-out provider useful for self-hosted wrappers."""

    def __init__(self, endpoint: str, *, headers: Mapping[str, str] | None = None, transport: HttpTransport | None = None):
        self.endpoint = endpoint
        self.headers = dict(headers or {})
        self.transport = transport or UrllibTransport()

    def synthesize(self, request: VoiceRequest) -> bytes:
        payload = {
            "text": request.text,
            "language": request.language,
            "voice": request.voice,
            "reference_audio": request.reference_audio,
            "reference_text": request.reference_text,
            "design_instructions": request.design_instructions,
            "speed": request.speed,
        }
        response = self.transport.request("POST", self.endpoint, headers=self.headers, json_body=payload, timeout=300.0)
        if not 200 <= response.status < 300:
            raise RuntimeError(f"generic TTS provider returned HTTP {response.status}")
        return response.body


class OpenAICompatibleImageProvider:
    def __init__(
        self,
        base_url: str,
        api_key: str | None,
        model: str,
        *,
        transport: HttpTransport | None = None,
        timeout: float = 180.0,
    ) -> None:
        self.base_url = base_url
        self.api_key = api_key
        self.model = model
        self.transport = transport or UrllibTransport()
        self.timeout = timeout

    def generate(self, request: ImageRequest) -> bytes:
        response = self.transport.request(
            "POST",
            _join(self.base_url, "images/generations"),
            headers=_auth_headers(self.api_key),
            json_body={
                "model": self.model,
                "prompt": request.prompt,
                "size": request.size,
                "response_format": "b64_json",
                "n": 1,
            },
            timeout=self.timeout,
        )
        if not 200 <= response.status < 300:
            raise RuntimeError(f"image provider returned HTTP {response.status}")
        try:
            envelope = json.loads(response.body.decode("utf-8"))
            encoded = envelope["data"][0]["b64_json"]
            if not isinstance(encoded, str) or not encoded:
                raise ValueError
            return base64.b64decode(encoded, validate=True)
        except (KeyError, IndexError, TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("image provider returned malformed response") from exc


class OpenAICompatibleAnalysisProvider:
    def __init__(
        self,
        base_url: str,
        api_key: str | None,
        model: str,
        *,
        transport: HttpTransport | None = None,
        timeout: float = 120.0,
    ) -> None:
        self.base_url = base_url
        self.api_key = api_key
        self.model = model
        self.transport = transport or UrllibTransport()
        self.timeout = timeout

    def enrich(self, scenes: Sequence[Scene], instructions: str = "") -> list[Scene]:
        source = [{"index": s.index, "text": s.text} for s in scenes]
        system = (
            "You enrich already-split video scenes. Never merge, delete, reorder, or create scenes. "
            "Return JSON only as {\"scenes\":[{\"index\":0,\"image_prompt\":\"...\"}]}. "
            "Image prompts must describe visuals rather than copying narration verbatim."
        )
        user = json.dumps({"instructions": instructions, "scenes": source}, ensure_ascii=False)
        response = self.transport.request(
            "POST",
            _join(self.base_url, "chat/completions"),
            headers=_auth_headers(self.api_key),
            json_body={
                "model": self.model,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                "response_format": {"type": "json_object"},
            },
            timeout=self.timeout,
        )
        if not 200 <= response.status < 300:
            raise RuntimeError(f"analysis provider returned HTTP {response.status}")
        try:
            envelope = json.loads(response.body.decode("utf-8"))
            content = envelope["choices"][0]["message"]["content"]
            decoded = json.loads(content) if isinstance(content, str) else content
            rows = decoded["scenes"]
        except (KeyError, IndexError, TypeError, ValueError, UnicodeDecodeError) as exc:
            raise ValueError("analysis provider returned malformed structured output") from exc

        by_index: dict[int, str] = {}
        for row in rows:
            if not isinstance(row, dict):
                continue
            idx = row.get("index")
            prompt = row.get("image_prompt")
            if isinstance(idx, int) and isinstance(prompt, str) and prompt.strip():
                by_index[idx] = prompt.strip()

        expected = {scene.index for scene in scenes}
        if set(by_index) != expected:
            raise ValueError("analysis provider changed or omitted scene slots")
        return [
            Scene(
                index=scene.index,
                text=scene.text,
                image_prompt=by_index[scene.index],
                voice_text=scene.voice_text,
                metadata=scene.metadata,
            )
            for scene in scenes
        ]
