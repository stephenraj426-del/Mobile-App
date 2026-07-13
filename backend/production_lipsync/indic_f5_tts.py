from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np
from transformers import AutoModel

from .audio_tools import save_wav_float32


class IndicF5TTS:
    """Small production wrapper around AI4Bharat IndicF5.

    The model API follows the official IndicF5 README:
      model(text, ref_audio_path=..., ref_text=...)

    Keep this class isolated so you can later swap to an optimized server,
    ONNX export, or a persistent worker without changing the lip-sync pipeline.
    """

    def __init__(self, repo_id: str = "ai4bharat/IndicF5", device: Optional[str] = None):
        self.repo_id = repo_id
        self.device = device
        self.model = AutoModel.from_pretrained(repo_id, trust_remote_code=True)
        if device and hasattr(self.model, "to"):
            self.model = self.model.to(device)

    def synthesize_to_wav(
        self,
        text: str,
        ref_audio_path: str | Path,
        ref_text: str,
        output_wav: str | Path,
        sample_rate: int = 24000,
    ) -> Path:
        if not text.strip():
            raise ValueError("Cannot synthesize empty text.")
        ref_audio_path = Path(ref_audio_path)
        if not ref_audio_path.exists():
            raise FileNotFoundError(f"Reference audio not found: {ref_audio_path}")
        if not ref_text.strip():
            raise ValueError("ref_text is required for IndicF5 voice prompting.")

        audio = self.model(
            text,
            ref_audio_path=str(ref_audio_path),
            ref_text=ref_text,
        )
        save_wav_float32(output_wav, np.asarray(audio), sample_rate)
        return Path(output_wav)
