#!/usr/bin/env python3
"""
extract_viseme_frames.py

Your video has the same burned-in-caption issue as your existing sprite
set (tested and confirmed: "Pack my box..." / "The quick brown fox..." are
baked into the pixels, same as before). This tool does NOT try to guess
which timestamp shows which viseme -- that needs a human eye, not a script.
What it does:

  1. BROWSE mode: dumps a labeled contact sheet (a grid of thumbnails with
     timestamps) so you can find the right moment for each of your 21
     visemes by looking at it, quickly, without scrubbing a video player
     frame by frame.

  2. EXTRACT mode: once you've picked timestamps, give it a config file
     (viseme name -> timestamp) and it pulls 5 frames per viseme with the
     correct FRAME_<NN>_<NAME>_<0-4>.png naming, ready to drop into
     Assets/Sprites/FullFrameSequences/.

Caption handling (--mode flag on extract):
  - "crop" (default): cut the frame above where captions start. Clean, zero
    artifacts. Changes framing to a closer waist-up shot -- tested and
    looks good on your actual video.
  - "inpaint": try to remove just the text, keep full framing. Tested
    against your real video: leaves visible ghosting over the text and
    warps the zipper/drawstring texture. NOT recommended as-is -- included
    only in case you want to experiment with tuning it further yourself.
  - "none": leave frames completely untouched (captions included).

Usage:
    # Step 1: browse to find timestamps
    python3 extract_viseme_frames.py browse --video clip.mp4 --out contact_sheet.png --interval 0.1

    # Step 2: write a config (see example_config.json), then extract
    python3 extract_viseme_frames.py extract --video clip.mp4 --config visemes.json --out-dir sprites --caption-mode crop
"""

import argparse
import json
import math
import os
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

VISEME_ORDER = [
    "REST_CLOSED", "AA_WIDE", "EE_NARROW", "OO_ROUND", "UH_MISC",
    "M_B_P", "F_V", "TH", "L_D_T", "SH_CH", "K_G", "S_Z",
    "I_NEAR_EE", "O_HALF_OPEN", "AW_VOWEL", "N_CONSONANT", "UR_VOWEL",
    "W_SOUND", "H_BREATH", "AE_SHORT", "ERR_MODIFIER",
]


def get_video_info(video_path):
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", video_path],
        capture_output=True, text=True, check=True,
    )
    info = json.loads(result.stdout)
    vstream = next(s for s in info["streams"] if s["codec_type"] == "video")
    fps_num, fps_den = vstream["avg_frame_rate"].split("/")
    fps = float(fps_num) / float(fps_den)
    duration = float(info["format"]["duration"])
    return {"fps": fps, "duration": duration, "width": vstream["width"], "height": vstream["height"]}


def read_frame_at(cap, t_seconds, fps):
    frame_idx = int(round(t_seconds * fps))
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
    ok, frame = cap.read()
    if not ok:
        return None
    return frame


def browse(args):
    info = get_video_info(args.video)
    print(f"Video: {info['width']}x{info['height']}, {info['fps']:.2f} fps, {info['duration']:.2f}s")

    cap = cv2.VideoCapture(args.video)
    timestamps = list(np.arange(0, info["duration"], args.interval))

    thumb_w, thumb_h = 120, int(120 * info["height"] / info["width"])
    cols = 8
    rows = math.ceil(len(timestamps) / cols)
    label_h = 16
    sheet = np.full((rows * (thumb_h + label_h), cols * thumb_w, 3), 255, dtype="uint8")

    for i, t in enumerate(timestamps):
        frame = read_frame_at(cap, t, info["fps"])
        if frame is None:
            continue
        thumb = cv2.resize(frame, (thumb_w, thumb_h))
        r, c = divmod(i, cols)
        y0 = r * (thumb_h + label_h)
        x0 = c * thumb_w
        sheet[y0:y0 + thumb_h, x0:x0 + thumb_w] = thumb
        cv2.putText(sheet, f"{t:.2f}s", (x0 + 2, y0 + thumb_h + 12),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 0, 0), 1, cv2.LINE_AA)

    cv2.imwrite(args.out, sheet)
    cap.release()
    print(f"Wrote contact sheet: {args.out} ({len(timestamps)} timestamps, {args.interval}s apart)")
    print("Find the timestamp that best matches each viseme, then fill in a config like example_config.json.")


def remove_caption_inpaint(frame):
    h, w = frame.shape[:2]
    band_y0 = int(h * 0.65)
    band = frame[band_y0:, :, :]
    gray = cv2.cvtColor(band, cv2.COLOR_BGR2GRAY)
    mask_band = ((gray < 50) | (gray > 220)).astype("uint8") * 255
    mask_band = cv2.dilate(mask_band, np.ones((5, 5), np.uint8), iterations=2)
    full_mask = np.zeros((h, w), dtype="uint8")
    full_mask[band_y0:, :] = mask_band
    return cv2.inpaint(frame, full_mask, inpaintRadius=7, flags=cv2.INPAINT_TELEA)


def apply_caption_mode(frame, mode, crop_fraction=0.70):
    if mode == "crop":
        h = frame.shape[0]
        return frame[: int(h * crop_fraction), :, :]
    if mode == "inpaint":
        return remove_caption_inpaint(frame)
    return frame  # "none"


def extract(args):
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    info = get_video_info(args.video)
    cap = cv2.VideoCapture(args.video)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    frame_step = args.stride / info["fps"]
    missing = [v for v in config if v not in VISEME_ORDER]
    if missing:
        print(f"WARNING: these config keys aren't in the standard 21-viseme list: {missing}")

    for viseme_name, center_t in config.items():
        idx = VISEME_ORDER.index(viseme_name) + 1 if viseme_name in VISEME_ORDER else 0
        prefix = f"{idx:02d}_{viseme_name}"
        offsets = [(-2 + i) * frame_step for i in range(5)]
        for i, off in enumerate(offsets):
            t = max(0.0, min(info["duration"] - 1.0 / info["fps"], center_t + off))
            frame = read_frame_at(cap, t, info["fps"])
            if frame is None:
                print(f"  WARNING: couldn't read frame for {viseme_name} at t={t:.3f}s")
                continue
            processed = apply_caption_mode(frame, args.caption_mode, args.crop_fraction)
            out_path = out_dir / f"FRAME_{prefix}_{i}.png"
            cv2.imwrite(str(out_path), processed)
        print(f"{viseme_name}: 5 frames written around t={center_t:.2f}s")

    cap.release()
    print(f"\nDone. {len(config)} viseme(s) processed into {out_dir}/")
    if len(config) < 21:
        have = set(config.keys())
        missing_visemes = [v for v in VISEME_ORDER if v not in have]
        print(f"Still need timestamps for: {missing_visemes}")


def write_example_config(path):
    example = {name: 0.5 + i * 0.4 for i, name in enumerate(VISEME_ORDER)}
    Path(path).write_text(json.dumps(example, indent=2), encoding="utf-8")
    print(f"Wrote example config to {path} -- edit the timestamps to match your video, remove entries you haven't found yet.")


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="command", required=True)

    b = sub.add_parser("browse", help="Generate a labeled contact sheet to find timestamps")
    b.add_argument("--video", required=True)
    b.add_argument("--out", default="contact_sheet.png")
    b.add_argument("--interval", type=float, default=0.1, help="Seconds between thumbnails")

    e = sub.add_parser("extract", help="Extract 5 frames per viseme from a timestamp config")
    e.add_argument("--video", required=True)
    e.add_argument("--config", required=True, help="JSON: {\"VISEME_NAME\": timestamp_seconds, ...}")
    e.add_argument("--out-dir", default="sprites_out")
    e.add_argument("--stride", type=int, default=1, help="Video frames between each of the 5 sub-frames (1 = consecutive frames)")
    e.add_argument("--caption-mode", choices=["crop", "inpaint", "none"], default="crop")
    e.add_argument("--crop-fraction", type=float, default=0.70, help="Keep the top N fraction of each frame's height when --caption-mode=crop. Lower this if captions still show up -- caption position varies by video.")

    c = sub.add_parser("example-config", help="Write an example config file to fill in")
    c.add_argument("--out", default="example_config.json")

    args = p.parse_args()
    if args.command == "browse":
        browse(args)
    elif args.command == "extract":
        extract(args)
    elif args.command == "example-config":
        write_example_config(args.out)


if __name__ == "__main__":
    main()
