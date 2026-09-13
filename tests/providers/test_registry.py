from nolane_studio.providers.base import ProviderCapabilities
from nolane_studio.providers.registry import ProviderRegistry


def test_registry_is_lazy_and_filters_by_capability():
    built = []
    reg = ProviderRegistry()
    reg.register("api-tts", ProviderCapabilities(tts=True, clone=False), lambda: built.append("api-tts") or object())
    reg.register("clone-tts", ProviderCapabilities(tts=True, clone=True), lambda: built.append("clone-tts") or object())
    assert built == []
    assert [d.name for d in reg.find(tts=True, clone=True)] == ["clone-tts"]
    instance = reg.get("clone-tts")
    assert built == ["clone-tts"]
    assert reg.get("clone-tts") is instance
    assert built == ["clone-tts"]


def test_registry_descriptors_do_not_construct_provider():
    reg = ProviderRegistry()
    reg.register("analysis", ProviderCapabilities(analysis=True), lambda: (_ for _ in ()).throw(RuntimeError("constructed")))
    assert reg.describe("analysis").capabilities.analysis is True
