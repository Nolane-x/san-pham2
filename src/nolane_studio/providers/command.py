from __future__ import annotations

import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Protocol, Sequence

from nolane_studio.domain import VoiceRequest


class CommandRunner(Protocol):
    def run(self, command: Sequence[str], *, input_text: str, output_path: str, timeout: float) -> None: ...


class SubprocessCommandRunner:
    def run(self, command: Sequence[str], *, input_text: str, output_path: str, timeout: float) -> None:
        result = subprocess.run(
            list(command), input=input_text, text=True, capture_output=True, timeout=timeout,
            check=False, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode != 0:
            raise RuntimeError(f"local TTS command failed ({result.returncode}): {result.stderr[-2000:]}")
        if not Path(output_path).is_file():
            raise RuntimeError("local TTS command did not create its output file")


class CommandTTSProvider:
    """Thin adapter for optional local engines.

    Template placeholders: {voice}, {language}, {output}, {reference_audio},
    {reference_text}, {design_instructions}, {speed}. Text is passed on stdin so
    long scripts never need shell escaping. The command is executed directly,
    never through a shell.
    """

    def __init__(
        self,
        command_template: Sequence[str],
        *,
        runner: CommandRunner | None = None,
        temp_dir: str | Path | None = None,
        timeout: float = 300.0,
    ) -> None:
        if not command_template:
            raise ValueError("command_template must not be empty")
        self.command_template = list(command_template)
        self.runner = runner or SubprocessCommandRunner()
        self.temp_dir = Path(temp_dir) if temp_dir is not None else Path(tempfile.gettempdir()) / "nolane_studio-tts"
        self.timeout = timeout

    def synthesize(self, request: VoiceRequest) -> bytes:
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        output = self.temp_dir / f"voice-{uuid.uuid4().hex}.wav"
        fields = {
            "voice": request.voice or "",
            "language": request.language,
            "output": str(output),
            "reference_audio": request.reference_audio or "",
            "reference_text": request.reference_text or "",
            "design_instructions": request.design_instructions or "",
            "speed": str(request.speed),
        }
        command = [part.format_map(fields) for part in self.command_template]
        try:
            self.runner.run(command, input_text=request.text, output_path=str(output), timeout=self.timeout)
            return output.read_bytes()
        finally:
            try:
                output.unlink(missing_ok=True)
            except OSError:
                pass
