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

def test_openai_compatible_vision_serializes_image_context_and_parses_grounded_objects():
    from nolane_studio.providers import OpenAICompatibleVisionProvider

    payload = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "objects": [
                                {
                                    "label": "sun",
                                    "phrase": "bright sun",
                                    "box": [0.1, 0.2, 0.5, 0.6],
                                }
                            ]
                        }
                    )
                }
            }
        ]
    }
    tr = FakeTransport(
        [HttpResponse(200, {"content-type": "application/json"}, json.dumps(payload).encode())]
    )
    provider = OpenAICompatibleVisionProvider(
        "https://example.test/v1",
        "secret",
        "vision-model",
        transport=tr,
    )

    result = provider.ground_objects(
        b"\x89PNG\r\n\x1a\nimage",
        transcript="draw the bright sun",
        target_phrases=["bright sun"],
    )

    assert len(result) == 1
    assert result[0].label == "sun"
    assert result[0].phrase == "bright sun"
    assert result[0].box == (0.1, 0.2, 0.5, 0.6)
    call = tr.calls[0]
    assert call["url"] == "https://example.test/v1/chat/completions"
    assert call["headers"]["Authorization"] == "Bearer secret"
    assert call["json_body"]["model"] == "vision-model"
    user_content = call["json_body"]["messages"][1]["content"]
    assert json.loads(user_content[0]["text"]) == {
        "transcript": "draw the bright sun",
        "target_phrases": ["bright sun"],
    }
    assert user_content[1]["image_url"]["url"].startswith("data:image/png;base64,")


def test_openai_compatible_vision_rejects_non_success_status_before_decoding():
    from nolane_studio.providers import OpenAICompatibleVisionProvider

    tr = FakeTransport([HttpResponse(503, {}, b"unavailable")])
    provider = OpenAICompatibleVisionProvider(
        "https://example.test/v1", None, "vision-model", transport=tr
    )

    import pytest

    with pytest.raises(RuntimeError, match=r"^vision provider returned HTTP 503$"):
        provider.ground_objects(b"image", transcript="hello")


def test_openai_compatible_stt_uses_injected_multipart_transport_and_parses_words():
    from nolane_studio.providers import OpenAICompatibleSTTProvider

    class MultipartTransport:
        def __init__(self):
            self.calls = []

        def request(
            self,
            method,
            url,
            *,
            headers=None,
            json_body=None,
            body=None,
            timeout=60.0,
        ):
            self.calls.append(
                {
                    "method": method,
                    "url": url,
                    "headers": headers or {},
                    "json_body": json_body,
                    "body": body,
                    "timeout": timeout,
                }
            )
            response = {
                "text": "xin chao",
                "words": [
                    {"word": "xin", "start": 0.0, "end": 0.4},
                    {"word": "chao", "start": 0.4, "end": 0.8},
                ],
            }
            return HttpResponse(200, {"content-type": "application/json"}, json.dumps(response).encode())

    tr = MultipartTransport()
    provider = OpenAICompatibleSTTProvider(
        "https://example.test/v1",
        "secret",
        "stt-model",
        transport=tr,
    )

    words = provider.transcribe_with_timestamps(b"ID3-audio", language="vi-VN")

    assert [(word.text, word.start, word.end) for word in words] == [
        ("xin", 0.0, 0.4),
        ("chao", 0.4, 0.8),
    ]
    call = tr.calls[0]
    assert call["url"] == "https://example.test/v1/audio/transcriptions"
    assert call["headers"]["Authorization"] == "Bearer secret"
    assert call["headers"]["Content-Type"].startswith("multipart/form-data; boundary=")
    assert call["json_body"] is None
    assert b'form-data; name="model"' in call["body"]
    assert b"stt-model" in call["body"]
    assert b'form-data; name="language"' in call["body"]
    assert b"vi" in call["body"]
    assert b'filename="scene-audio.mp3"' in call["body"]
    assert b"ID3-audio" in call["body"]


def test_openai_compatible_stt_rejects_non_success_status_before_decoding():
    from nolane_studio.providers import OpenAICompatibleSTTProvider

    class ErrorTransport:
        def request(self, method, url, *, headers=None, json_body=None, body=None, timeout=60.0):
            return HttpResponse(429, {}, b"rate limited")

    provider = OpenAICompatibleSTTProvider(
        "https://example.test/v1",
        None,
        "stt-model",
        transport=ErrorTransport(),
    )

    import pytest

    with pytest.raises(RuntimeError, match=r"^STT provider returned HTTP 429$"):
        provider.transcribe_with_timestamps(b"ID3-audio")

