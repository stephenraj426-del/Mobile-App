from __future__ import annotations

import argparse
from pathlib import Path

from .audio_tools import read_wav_duration_seconds
from .file_utils import save_json
from .indic_viseme_mapper import map_units_to_frames
from .quality_report import build_qa_report
from .smoothing import smooth_frames
from .textgrid_parser import parse_textgrid_intervals


def main() -> None:
    p = argparse.ArgumentParser(description="Build lipsync.json from an existing WAV + TextGrid.")
    p.add_argument("--lang", required=True, choices=["ta", "ml", "hi", "te", "kn"])
    p.add_argument("--audio", required=True)
    p.add_argument("--textgrid", required=True)
    p.add_argument("--text", required=True)
    p.add_argument("--out", required=True)
    args = p.parse_args()

    duration = read_wav_duration_seconds(args.audio)
    units = parse_textgrid_intervals(args.textgrid)
    frames = smooth_frames(map_units_to_frames(units, args.lang), duration=duration)
    out = Path(args.out)
    save_json(out, {
        "version": "1.0",
        "source": "existing-wav-textgrid + 21-sprite-viseme-map",
        "language": args.lang,
        "audioFile": Path(args.audio).name,
        "duration": round(duration, 4),
        "rawText": args.text,
        "normalizedText": args.text,
        "spriteProfile": "21-indic-universal",
        "frames": [f.to_json() for f in frames],
    })
    save_json(out.with_name("qa_report.json"), build_qa_report(args.text, args.text, args.lang, duration, units, frames))
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
