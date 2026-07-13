from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional

from .file_utils import assert_file_exists, ensure_empty_dir


class MfaAlignmentError(RuntimeError):
    pass


def _model_or_path(value: str | Path, label: str) -> str:
    """Return a local file path or an MFA model name.

    IndicMFA usually uses downloaded local dictionary/model files.
    English can use installed MFA model names such as 'english_mfa'.
    """
    s = str(value)
    if any(sep in s for sep in ("/", "\\")) or Path(s).suffix:
        return str(assert_file_exists(s, label))
    return s


class MfaAligner:
    """Runs Montreal Forced Aligner as a subprocess."""

    def __init__(self, mfa_bin: str = "mfa"):
        self.mfa_bin = mfa_bin

    def validate_available(self) -> None:
        result = subprocess.run(
            [self.mfa_bin, "version"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if result.returncode != 0:
            raise MfaAlignmentError(
                "MFA is not available. Install Montreal Forced Aligner and make sure 'mfa version' works.\n"
                f"STDERR:\n{result.stderr}"
            )

    def align(
        self,
        corpus_dir: str | Path,
        dictionary_path: str | Path,
        acoustic_model_path: str | Path,
        output_dir: str | Path,
        clean: bool = True,
        overwrite: bool = True,
        num_jobs: Optional[int] = None,
    ) -> Path:
        corpus_dir = assert_file_exists(corpus_dir, "MFA corpus folder")
        dictionary_arg = _model_or_path(dictionary_path, "MFA dictionary")
        acoustic_arg = _model_or_path(acoustic_model_path, "MFA acoustic model")
        output_dir = ensure_empty_dir(output_dir)

        cmd = [
            self.mfa_bin,
            "align",
            str(corpus_dir),
            dictionary_arg,
            acoustic_arg,
            str(output_dir),
        ]
        if clean:
            cmd.append("--clean")
        if overwrite:
            cmd.append("--overwrite")
        if num_jobs:
            cmd.extend(["--num_jobs", str(num_jobs)])

        result = subprocess.run(
            cmd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if result.returncode != 0:
            raise MfaAlignmentError(
                "MFA alignment failed.\n"
                f"Command: {' '.join(cmd)}\n\n"
                f"STDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}"
            )

        textgrids = sorted(output_dir.rglob("*.TextGrid")) + sorted(output_dir.rglob("*.textgrid"))
        if not textgrids:
            raise MfaAlignmentError(
                "MFA completed but no TextGrid was found. Check corpus .lab name matches .wav name.\n"
                f"STDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}"
            )
        return textgrids[0]
