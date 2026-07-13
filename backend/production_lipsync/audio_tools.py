from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf


def save_wav_float32(path: str | Path, audio, sample_rate: int) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    arr = np.asarray(audio)
    if arr.ndim > 1:
        arr = np.mean(arr, axis=1)
    if arr.dtype == np.int16:
        arr = arr.astype(np.float32) / 32768.0
    else:
        arr = arr.astype(np.float32)
    peak = float(np.max(np.abs(arr))) if arr.size else 0.0
    if peak > 1.0:
        arr = arr / peak
    sf.write(str(path), arr, sample_rate, subtype="PCM_16")


def read_wav_duration_seconds(path: str | Path) -> float:
    info = sf.info(str(path))
    if info.samplerate <= 0:
        return 0.0
    return float(info.frames) / float(info.samplerate)
