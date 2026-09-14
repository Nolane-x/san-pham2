from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .base import ProviderCapabilities


@dataclass(frozen=True, slots=True)
class ProviderDescriptor:
    name: str
    capabilities: ProviderCapabilities


class ProviderRegistry:
    """Lazy provider registry so merely opening Nolane Studio never loads heavy engines."""

    def __init__(self) -> None:
        self._entries: dict[str, tuple[ProviderCapabilities, Callable[[], Any]]] = {}
        self._instances: dict[str, Any] = {}

    def register(self, name: str, capabilities: ProviderCapabilities, factory: Callable[[], Any]) -> None:
        name = name.strip()
        if not name:
            raise ValueError("provider name must not be blank")
        if name in self._entries:
            raise ValueError(f"provider {name!r} is already registered")
        self._entries[name] = (capabilities, factory)

    def describe(self, name: str) -> ProviderDescriptor:
        try:
            caps, _ = self._entries[name]
        except KeyError as exc:
            raise KeyError(f"unknown provider {name!r}") from exc
        return ProviderDescriptor(name, caps)

    def find(self, **required: bool) -> list[ProviderDescriptor]:
        result: list[ProviderDescriptor] = []
        for name, (caps, _) in self._entries.items():
            if all(getattr(caps, field) is value for field, value in required.items()):
                result.append(ProviderDescriptor(name, caps))
        return result

    def descriptors(self) -> list[ProviderDescriptor]:
        return [ProviderDescriptor(name, caps) for name, (caps, _) in self._entries.items()]

    def get(self, name: str) -> Any:
        if name not in self._instances:
            try:
                _, factory = self._entries[name]
            except KeyError as exc:
                raise KeyError(f"unknown provider {name!r}") from exc
            self._instances[name] = factory()
        return self._instances[name]
