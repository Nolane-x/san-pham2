from __future__ import annotations

import base64
import json
import mimetypes
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from typing import Any, Mapping, Protocol, Sequence

from nolane_studio.ai.object_voice import GroundedObject, TranscriptWord
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
        body: bytes | None = None,
        timeout: float = 60.0,
    ) -> HttpResponse: ...


class UrllibTransport:
    def request(
        self,
        method,
        url,
        *,
        headers=None,
        json_body=None,
        body=None,
        timeout=60.0,
    ) -> HttpResponse:
        if json_body is not None and body is not None:
            raise ValueError("request cannot contain both json_body and body")
        payload = body
        if json_body is not None:
            payload = json.dumps(json_body, ensure_ascii=False).encode("utf-8")
        merged = {"User-Agent": "Nolane Studio-Rebuild/0.1", **dict(headers or {})}
        if json_body is not None:
            merged.setdefault("Content-Type", "application/json")
        req = urllib.request.Request(url, data=payload, headers=merged, method=method)
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


def _image_mime(payload: bytes) -> str:
    if payload.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if payload.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if payload.startswith(b"RIFF") and payload[8:12] == b"WEBP":
        return "image/webp"
    return "application/octet-stream"


def _multipart_body(
    fields: Mapping[str, str],
    file_field: str,
    filename: str,
    payload: bytes,
) -> tuple[str, bytes]:
    boundary = f"----NolaneStudio{uuid.uuid4().hex}"
    chunks: list[bytes] = []
    for name, value in fields.items():
        chunks.extend(
            [
                f"--{boundary}\r\n".encode(),
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
                str(value).encode("utf-8"),
                b"\r\n",
            ]
        )
    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    chunks.extend(
        [
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="{file_field}"; filename="{filename}"\r\n'.encode(),
            f"Content-Type: {content_type}\r\n\r\n".encode(),
            payload,
            b"\r\n",
            f"--{boundary}--\r\n".encode(),
        ]
    )
    return boundary, b"".join(chunks)


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

class OpenAICompatibleVisionProvider:
    """OpenAI-compatible multimodal grounding used by AI Analyze."""

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

    def ground_objects(
        self,
        image_bytes: bytes,
        *,
        transcript: str,
        target_phrases: Sequence[str] | None = None,
    ) -> list[GroundedObject]:
        if not image_bytes:
            raise ValueError("vision provider requires image bytes")
        encoded = base64.b64encode(image_bytes).decode("ascii")
        context = {
            "transcript": str(transcript),
            "target_phrases": list(target_phrases or ()),
        }
        response = self.transport.request(
            "POST",
            _join(self.base_url, "chat/completions"),
            headers=_auth_headers(self.api_key),
            json_body={
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Ground visible objects referred to by the narration. "
                            "Return JSON only as {\"objects\":[{\"label\":\"...\","
                            "\"phrase\":\"exact spoken phrase\","
                            "\"box\":[x1,y1,x2,y2]}]}. "
                            "Coordinates must be normalized 0..1 and tight."
                        ),
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(context, ensure_ascii=False),
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": (
                                        f"data:{_image_mime(image_bytes)};base64,{encoded}"
                                    )
                                },
                            },
                        ],
                    },
                ],
                "response_format": {"type": "json_object"},
            },
            timeout=self.timeout,
        )
        if not 200 <= response.status < 300:
            raise RuntimeError(f"vision provider returned HTTP {response.status}")
        try:
            envelope = json.loads(response.body.decode("utf-8"))
            content = envelope["choices"][0]["message"]["content"]
            decoded = json.loads(content) if isinstance(content, str) else content
            if not isinstance(decoded, Mapping):
                raise ValueError
            rows = decoded.get("objects", [])
            if not isinstance(rows, list):
                raise ValueError
        except (
            KeyError,
            IndexError,
            TypeError,
            ValueError,
            UnicodeDecodeError,
            json.JSONDecodeError,
        ) as exc:
            raise ValueError("vision provider returned malformed structured output") from exc

        result: list[GroundedObject] = []
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            box = row.get("box")
            if not isinstance(box, (list, tuple)) or len(box) != 4:
                continue
            result.append(
                GroundedObject(
                    label=str(row.get("label") or row.get("phrase") or "object"),
                    phrase=str(row.get("phrase") or row.get("label") or "object"),
                    box=tuple(float(value) for value in box),
                )
            )
        return result


class OpenAICompatibleSTTProvider:
    """Timestamped OpenAI-compatible transcription through the shared HTTP transport."""

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

    def transcribe_with_timestamps(
        self,
        audio_bytes: bytes,
        *,
        language: str | None = None,
    ) -> list[TranscriptWord]:
        if not audio_bytes:
            raise ValueError("STT requires audio bytes")
        fields = {
            "model": self.model,
            "response_format": "verbose_json",
            "timestamp_granularities[]": "word",
        }
        if language and language.lower() not in {"auto", "auto-detect"}:
            fields["language"] = language.split("-", 1)[0]
        boundary, payload = _multipart_body(
            fields,
            "file",
            "scene-audio.mp3",
            audio_bytes,
        )
        response = self.transport.request(
            "POST",
            _join(self.base_url, "audio/transcriptions"),
            headers={
                **_auth_headers(self.api_key),
                "Content-Type": f"multipart/form-data; boundary={boundary}",
            },
            body=payload,
            timeout=self.timeout,
        )
        if not 200 <= response.status < 300:
            raise RuntimeError(f"STT provider returned HTTP {response.status}")
        try:
            decoded = json.loads(response.body.decode("utf-8"))
            if not isinstance(decoded, Mapping):
                raise ValueError
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            raise ValueError("STT provider returned malformed JSON") from exc

        rows = decoded.get("words") or decoded.get("segments") or []
        if not isinstance(rows, list):
            raise ValueError("STT provider returned malformed timestamps")
        result: list[TranscriptWord] = []
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            text = row.get("word") or row.get("text")
            start = row.get("start")
            end = row.get("end")
            if (
                isinstance(text, str)
                and isinstance(start, (int, float))
                and isinstance(end, (int, float))
            ):
                result.append(TranscriptWord(text, float(start), float(end)))
        if not result:
            text = decoded.get("text")
            if isinstance(text, str) and text.strip():
                result.append(TranscriptWord(text, 0.0, 0.0))
        return result

