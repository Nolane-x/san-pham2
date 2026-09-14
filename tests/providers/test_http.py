import json
from nolane_studio.domain import Scene, VoiceRequest
from nolane_studio.providers.http import HttpResponse, OpenAICompatibleAnalysisProvider, OpenAICompatibleTTSProvider


class FakeTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def request(self, method, url, *, headers=None, json_body=None, timeout=60.0):
        self.calls.append({"method":method,"url":url,"headers":headers or {},"json_body":json_body,"timeout":timeout})
        return self.responses.pop(0)


def test_openai_compatible_tts_serializes_without_vendor_sdk():
    tr = FakeTransport([HttpResponse(200, {"content-type":"audio/mpeg"}, b"MP3")])
    p = OpenAICompatibleTTSProvider(
        base_url="https://example.test/v1", api_key="secret", model="tts-model", transport=tr
    )
    audio = p.synthesize(VoiceRequest("Xin chào", language="vi-VN", voice="alloy", speed=1.1))
    assert audio == b"MP3"
    call = tr.calls[0]
    assert call["url"] == "https://example.test/v1/audio/speech"
    assert call["headers"]["Authorization"] == "Bearer secret"
    assert call["json_body"] == {
        "model":"tts-model", "input":"Xin chào", "voice":"alloy", "speed":1.1, "response_format":"mp3"
    }


def test_openai_compatible_analysis_enriches_only_existing_scene_slots():
    body = {"choices":[{"message":{"content":json.dumps({"scenes":[
        {"index":0,"image_prompt":"a clean diagram"},
        {"index":1,"image_prompt":"a second diagram"}
    ]})}}]}
    tr = FakeTransport([HttpResponse(200, {"content-type":"application/json"}, json.dumps(body).encode())])
    p = OpenAICompatibleAnalysisProvider("https://example.test/v1", "k", "analysis-model", transport=tr)
    original = [Scene(0,"one"), Scene(1,"two")]
    enriched = p.enrich(original, "whiteboard")
    assert [s.text for s in enriched] == ["one", "two"]
    assert [s.image_prompt for s in enriched] == ["a clean diagram", "a second diagram"]
    sent = tr.calls[0]["json_body"]
    assert sent["model"] == "analysis-model"
    assert len(sent["messages"]) == 2


def test_generic_http_tts_sends_clone_and_design_fields_without_heavy_imports():
    from nolane_studio.providers.http import GenericHttpTTSProvider
    tr = FakeTransport([HttpResponse(200, {}, b"WAV")])
    p = GenericHttpTTSProvider("http://127.0.0.1:9999/tts", transport=tr)
    audio = p.synthesize(VoiceRequest(
        "hello", language="vi-VN", voice="v1", reference_audio="r.wav",
        reference_text="ref", design_instructions="warm narrator"
    ))
    assert audio == b"WAV"
    body = tr.calls[0]["json_body"]
    assert body["reference_audio"] == "r.wav"
    assert body["design_instructions"] == "warm narrator"
