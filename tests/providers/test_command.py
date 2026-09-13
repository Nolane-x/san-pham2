from pathlib import Path
from nolane_studio.domain import VoiceRequest
from nolane_studio.providers.command import CommandTTSProvider


class FakeRunner:
    def __init__(self): self.calls = []
    def run(self, command, *, input_text, output_path, timeout):
        self.calls.append((command, input_text, output_path, timeout))
        Path(output_path).write_bytes(b"AUDIO")


def test_command_tts_is_lazy_adapter_for_local_engines(tmp_path):
    runner = FakeRunner()
    provider = CommandTTSProvider(
        ["local-tts", "--voice", "{voice}", "--language", "{language}", "--output", "{output}"],
        runner=runner,
        temp_dir=tmp_path,
    )
    result = provider.synthesize(VoiceRequest("Xin chào", voice="viet", language="vi-VN"))
    assert result == b"AUDIO"
    command, stdin, output, timeout = runner.calls[0]
    assert command[:5] == ["local-tts", "--voice", "viet", "--language", "vi-VN"]
    assert stdin == "Xin chào"
    assert str(tmp_path) in output
