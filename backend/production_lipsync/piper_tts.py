from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional

from .file_utils import assert_file_exists


class PiperTTSError(RuntimeError):
    pass


class PiperTTS:
    """Production wrapper for the Piper CLI.

    Install Piper separately and make sure this works:
      piper --help

    Typical command used by this wrapper:
      piper --model voice.onnx --config voice.onnx.json --output_file avatar.wav

    Text is passed through stdin so punctuation/prosody remain intact.
    """

    def __init__(self, piper_bin: str = "piper"):
        self.piper_bin = piper_bin

    def validate_available(self) -> None:
        result = subprocess.run(
            [self.piper_bin, "--help"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if result.returncode != 0:
            raise PiperTTSError(
                "Piper is not available. Install Piper and make sure 'piper --help' works.\n"
                f"STDERR:\n{result.stderr}"
            )

    def synthesize_to_wav(
        self,
        text: str,
        model_path: str | Path,
        output_wav: str | Path,
        config_path: Optional[str | Path] = None,
        length_scale: Optional[float] = None,
    ) -> Path:
        if not text.strip():
            raise ValueError("Cannot synthesize empty English text.")

        model_path = assert_file_exists(model_path, "Piper ONNX voice model")
        output_wav = Path(output_wav)
        output_wav.parent.mkdir(parents=True, exist_ok=True)

        cmd = [self.piper_bin, "--model", str(model_path), "--output_file", str(output_wav)]
        if config_path:
            config_path = assert_file_exists(config_path, "Piper voice config")
            cmd.extend(["--config", str(config_path)])
        if length_scale:
            # Piper's own speed control. 1.0 = default. >1.0 = slower
            # (1.2 = 20% slower), <1.0 = faster. Affects the source audio
            # directly, so MFA/the mapper/the Unity player need no changes
            # at all -- they just respond to however long the real audio is.
            cmd.extend(["--length_scale", str(length_scale)])

        result = subprocess.run(
            cmd,
            input=text + "\n",
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if result.returncode != 0:
            raise PiperTTSError(
                "Piper TTS failed.\n"
                f"Command: {' '.join(cmd)}\n\nSTDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}"
            )
        if not output_wav.exists():
            raise PiperTTSError(f"Piper completed but output WAV was not created: {output_wav}")
        return output_wav
