from __future__ import annotations

import base64
import json

import pytest

from nolane_studio.domain import ImageRequest
from nolane_studio.providers.http import HttpResponse, OpenAICompatibleImageProvider


class FakeTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def request(self, method, url, *, headers=None, json_body=None, timeout=60.0):
        self.calls.append({"method": method, "url": url, "headers": headers or {}, "json_body": json_body, "timeout": timeout})
        return self.responses.pop(0)


def test_openai_compatible_image_provider_returns_decoded_bytes():
    encoded = base64.b64encode(b"PNG-DATA").decode("ascii")
    payload = json.dumps({"data": [{"b64_json": encoded}]}).encode("utf-8")
    tr = FakeTransport([HttpResponse(200, {"content-type": "application/json"}, payload)])
    provider = OpenAICompatibleImageProvider(
        "https://example.test/v1", "secret", "image-model", transport=tr
    )

    result = provider.generate(ImageRequest("minimal whiteboard diagram", size="1024x1024"))

    assert result == b"PNG-DATA"
    call = tr.calls[0]
    assert call["url"] == "https://example.test/v1/images/generations"
    assert call["headers"]["Authorization"] == "Bearer secret"
    assert call["json_body"] == {
        "model": "image-model",
        "prompt": "minimal whiteboard diagram",
        "size": "1024x1024",
        "response_format": "b64_json",
        "n": 1,
    }


def test_image_provider_rejects_malformed_response():
    tr = FakeTransport([HttpResponse(200, {}, b'{"data": [{}]}')])
    provider = OpenAICompatibleImageProvider("https://example.test/v1", None, "image-model", transport=tr)
    with pytest.raises(ValueError, match="malformed"):
        provider.generate(ImageRequest("scene"))
