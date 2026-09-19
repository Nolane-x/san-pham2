import importlib.util


def test_object_voice_analyzer_maps_phrase_timing_and_uses_content_cache(tmp_path):
    assert importlib.util.find_spec("nolane_studio.ai.object_voice") is not None

    from nolane_studio.ai.object_voice import GroundedObject, ObjectVoiceAnalyzer, TranscriptWord

    class FakeSTT:
        def __init__(self):
            self.calls = 0

        def transcribe_with_timestamps(self, audio_bytes: bytes, *, language: str | None = None):
            self.calls += 1
            assert audio_bytes == b"voice"
            return [
                TranscriptWord("draw", 0.0, 0.25),
                TranscriptWord("sun", 0.25, 0.80),
                TranscriptWord("now", 0.80, 1.00),
            ]

    class FakeVision:
        def __init__(self):
            self.calls = 0

        def ground_objects(self, image_bytes: bytes, *, transcript: str, target_phrases=None):
            self.calls += 1
            assert image_bytes == b"image"
            assert transcript == "draw sun now"
            return [GroundedObject(label="sun", phrase="sun", box=(0.10, 0.15, 0.45, 0.60))]

    stt = FakeSTT()
    vision = FakeVision()
    analyzer = ObjectVoiceAnalyzer(stt, vision, cache_dir=tmp_path)

    first = analyzer.analyze(scene_id="scene-1", image_bytes=b"image", audio_bytes=b"voice")
    assert first.transcript_text == "draw sun now"
    assert len(first.objects) == 1
    target = first.objects[0]
    assert target.label == "sun"
    assert target.phrase == "sun"
    assert target.box == (0.10, 0.15, 0.45, 0.60)
    assert target.start == 0.25
    assert target.end == 0.80

    second = analyzer.analyze(scene_id="scene-1", image_bytes=b"image", audio_bytes=b"voice")
    assert second == first
    assert stt.calls == 1
    assert vision.calls == 1
