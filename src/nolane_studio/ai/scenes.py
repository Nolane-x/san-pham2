from __future__ import annotations

import re

from nolane_studio.domain import Scene

_SENTENCE_RE = re.compile(r"(?<=[.!?…])\s+|\n+")


def _chunks(words: list[str], max_words: int) -> list[list[str]]:
    return [words[i : i + max_words] for i in range(0, len(words), max_words)]


def split_script_into_scenes(text: str, min_words: int = 30, max_words: int = 50) -> list[Scene]:
    """Deterministically group a script into bounded semantic-ish scene units.

    This intentionally mirrors the recovered architecture: structure is decided locally,
    while an optional model may enrich the already-bounded scenes later.
    """
    text = " ".join(str(text or "").replace("\r", "\n").split())
    if not text:
        return []
    if min_words < 1 or max_words < min_words:
        raise ValueError("require 1 <= min_words <= max_words")

    raw_sentences = [s.strip() for s in _SENTENCE_RE.split(text) if s.strip()]
    units: list[list[str]] = []
    for sentence in raw_sentences:
        words = sentence.split()
        units.extend(_chunks(words, max_words) if len(words) > max_words else [words])

    grouped: list[list[str]] = []
    current: list[str] = []
    for unit in units:
        if not current:
            current = list(unit)
            continue
        # Prefer a full scene once min_words is reached; only append if it still fits.
        if len(current) >= min_words or len(current) + len(unit) > max_words:
            grouped.append(current)
            current = list(unit)
        else:
            current.extend(unit)
    if current:
        grouped.append(current)

    # If the final fragment is short and can fit into its predecessor, merge it.
    if len(grouped) > 1 and len(grouped[-1]) < min_words and len(grouped[-2]) + len(grouped[-1]) <= max_words:
        grouped[-2].extend(grouped.pop())

    return [Scene(index=i, text=" ".join(words)) for i, words in enumerate(grouped)]
