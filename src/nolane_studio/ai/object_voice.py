from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol, Sequence


@dataclass(frozen=True, slots=True)
class TranscriptWord:
    text: str
    start: float
    end: float

    def __post_init__(self) -> None:
        text = str(self.text).strip()
        start = float(self.start)
        end = float(self.end)
        if not text:
            raise ValueError("transcript word must not be blank")
        if start < 0 or end < start:
            raise ValueError("invalid transcript word timing")
        object.__setattr__(self, "text", text)
        object.__setattr__(self, "start", start)
        object.__setattr__(self, "end", end)


@dataclass(frozen=True, slots=True)
class GroundedObject:
    label: str
    phrase: str
    box: tuple[float, float, float, float]

    def __post_init__(self) -> None:
        label = str(self.label).strip()
        phrase = str(self.phrase).strip()
        if not label:
            raise ValueError("grounded object label must not be blank")
        if len(self.box) != 4:
            raise ValueError("box must be (x1, y1, x2, y2)")
        x1, y1, x2, y2 = (float(value) for value in self.box)
        x1, y1, x2, y2 = (max(0.0, min(1.0, value)) for value in (x1, y1, x2, y2))
        if x2 < x1 or y2 < y1:
            raise ValueError("box maximums must be >= minimums")
        object.__setattr__(self, "label", label)
        object.__setattr__(self, "phrase", phrase or label)
        object.__setattr__(self, "box", (x1, y1, x2, y2))


@dataclass(frozen=True, slots=True)
class TimedObject:
    label: str
    phrase: str
    box: tuple[float, float, float, float]
    start: float
    end: float


@dataclass(frozen=True, slots=True)
class ObjectVoiceAnalysis:
    scene_id: str
    transcript_text: str
    words: tuple[TranscriptWord, ...]
    objects: tuple[TimedObject, ...]
    content_hash: str

    def to_metadata(self) -> dict[str, Any]:
        return {
            "scene_id": self.scene_id,
            "transcript": self.transcript_text,
            "words": [asdict(word) for word in self.words],
            "objects": [
                {
                    "label": obj.label,
                    "phrase": obj.phrase,
                    "box": list(obj.box),
                    "start": obj.start,
                    "end": obj.end,
                }
                for obj in self.objects
            ],
            "content_hash": self.content_hash,
        }


class STTLike(Protocol):
    def transcribe_with_timestamps(
        self, audio_bytes: bytes, *, language: str | None = None
    ) -> Sequence[TranscriptWord]: ...


class VisionLike(Protocol):
    def ground_objects(
        self,
        image_bytes: bytes,
        *,
        transcript: str,
        target_phrases: Sequence[str] | None = None,
    ) -> Sequence[GroundedObject]: ...


BoxRefiner = Callable[[bytes, tuple[float, float, float, float]], tuple[float, float, float, float]]


def _normalize_token(value: str) -> str:
    return re.sub(r"[^\w]+", "", value.casefold(), flags=re.UNICODE)


def _phrase_window(words: Sequence[TranscriptWord], phrase: str) -> tuple[float, float]:
    tokens = [_normalize_token(token) for token in phrase.split()]
    tokens = [token for token in tokens if token]
    normalized_words = [_normalize_token(word.text) for word in words]
    if tokens:
        width = len(tokens)
        for index in range(0, len(normalized_words) - width + 1):
            if normalized_words[index : index + width] == tokens:
                return words[index].start, words[index + width - 1].end
    if words:
        return words[0].start, words[-1].end
    return 0.0, 0.0


def _identity_refiner(
    _image_bytes: bytes, box: tuple[float, float, float, float]
) -> tuple[float, float, float, float]:
    return GroundedObject("box", "box", box).box


def merge_analysis_metadata(existing: Mapping[str, Any] | None, analysis: Mapping[str, Any]) -> dict[str, Any]:
    merged = dict(existing or {})
    merged["ai_analysis"] = dict(analysis)
    return merged


class ObjectVoiceAnalyzer:
    """Recovered AI Analyze semantics: STT decides WHEN, vision decides WHAT/rough WHERE.

    A lightweight local refiner can be injected for OpenCV contour tightening. The
    default only validates/clamps the normalized box, keeping startup free of heavy
    optional computer-vision imports.
    """

    CACHE_VERSION = "object-voice-v1"

    def __init__(
        self,
        stt_provider: STTLike,
        vision_provider: VisionLike,
        *,
        cache_dir: str | Path | None = None,
        box_refiner: BoxRefiner | None = None,
    ) -> None:
        self.stt_provider = stt_provider
        self.vision_provider = vision_provider
        self.cache_dir = Path(cache_dir) if cache_dir is not None else None
        self.box_refiner = box_refiner or _identity_refiner

    @classmethod
    def _content_hash(cls, image_bytes: bytes, audio_bytes: bytes) -> str:
        digest = hashlib.sha256()
        digest.update(cls.CACHE_VERSION.encode("ascii"))
        digest.update(b"\0image\0")
        digest.update(image_bytes)
        digest.update(b"\0audio\0")
        digest.update(audio_bytes)
        return digest.hexdigest()

    def _cache_path(self, content_hash: str) -> Path | None:
        if self.cache_dir is None:
            return None
        return self.cache_dir / f"{content_hash}.json"

    @staticmethod
    def _decode_cached(raw: Mapping[str, Any]) -> ObjectVoiceAnalysis:
        words = tuple(
            TranscriptWord(str(row["text"]), float(row["start"]), float(row["end"]))
            for row in raw.get("words", [])
        )
        objects = tuple(
            TimedObject(
                label=str(row["label"]),
                phrase=str(row.get("phrase") or row["label"]),
                box=tuple(float(value) for value in row["box"]),
                start=float(row["start"]),
                end=float(row["end"]),
            )
            for row in raw.get("objects", [])
        )
        return ObjectVoiceAnalysis(
            scene_id=str(raw["scene_id"]),
            transcript_text=str(raw.get("transcript", "")),
            words=words,
            objects=objects,
            content_hash=str(raw["content_hash"]),
        )

    def _read_cache(self, path: Path | None) -> ObjectVoiceAnalysis | None:
        if path is None or not path.exists():
            return None
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                return None
            return self._decode_cached(raw)
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            return None

    def _write_cache(self, path: Path | None, result: ObjectVoiceAnalysis) -> None:
        if path is None:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + ".tmp")
        temp.write_text(
            json.dumps(result.to_metadata(), ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        temp.replace(path)

    def analyze(
        self,
        *,
        scene_id: str,
        image_bytes: bytes,
        audio_bytes: bytes,
        language: str | None = None,
        target_phrases: Sequence[str] | None = None,
    ) -> ObjectVoiceAnalysis:
        if not image_bytes:
            raise ValueError("AI Analyze requires scene image bytes")
        if not audio_bytes:
            raise ValueError("AI Analyze requires scene audio bytes")
        content_hash = self._content_hash(image_bytes, audio_bytes)
        cache_path = self._cache_path(content_hash)
        cached = self._read_cache(cache_path)
        if cached is not None:
            return ObjectVoiceAnalysis(
                scene_id=scene_id,
                transcript_text=cached.transcript_text,
                words=cached.words,
                objects=cached.objects,
                content_hash=cached.content_hash,
            )

        words = tuple(self.stt_provider.transcribe_with_timestamps(audio_bytes, language=language))
        transcript = " ".join(word.text for word in words).strip()
        grounded = self.vision_provider.ground_objects(
            image_bytes,
            transcript=transcript,
            target_phrases=target_phrases,
        )
        timed: list[TimedObject] = []
        for item in grounded:
            refined = self.box_refiner(image_bytes, item.box)
            safe_box = GroundedObject(item.label, item.phrase, refined).box
            start, end = _phrase_window(words, item.phrase)
            timed.append(TimedObject(item.label, item.phrase, safe_box, start, end))

        result = ObjectVoiceAnalysis(scene_id, transcript, words, tuple(timed), content_hash)
        self._write_cache(cache_path, result)
        return result
