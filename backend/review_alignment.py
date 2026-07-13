#!/usr/bin/env python3
"""
review_alignment.py

Answers "did MFA actually align this correctly?" the only way that's really
answerable: by looking at it. Plots the waveform with every tier's interval
boundaries drawn on top (typically "words" and "phones" for MFA output), so
you can see whether a boundary actually sits where the sound changes, not
just trust that MFA didn't crash.

Usage:
    python3 review_alignment.py --audio avatar.wav --textgrid aligned.TextGrid --out review.png

What to actually look for in the PNG (in order of how much they matter):
  1. RED FLAGS printed to the console -- read these first.
  2. Word boundaries (top label strip) should fall where you can visually
     see the waveform's amplitude pattern change -- a word starting should
     roughly line up with energy picking up after a gap/lower-energy patch.
  3. Total word count printed should match your input sentence's word count.
     If it doesn't, MFA silently dropped or merged a word -- almost always
     an out-of-vocabulary (OOV) word not in the pronunciation dictionary.
  4. Phone durations that are very long (>400-500ms) or suspiciously
     short/zero are flagged automatically -- both usually mean alignment
     struggled around that word, often the same OOV cause as #3.
  5. If it "looks reasonable" to your eye and the counts match, that's
     about as far as visual inspection alone can confirm without a
     phonetics background -- which is fine, that's the right bar for this
     check. This tool is for catching broken alignment, not grading
     phonetic precision.
"""

import argparse
import sys
import wave
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


def parse_all_tiers(path):
    """Returns {tier_name: [(start, end, label), ...]} for every interval
    tier in the TextGrid -- unlike the pipeline's own parser, which only
    returns the one tier it picked to use for lip-sync. Reviewing alignment
    quality wants to see words AND phones together."""
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    lines = [line.strip() for line in text.splitlines()]

    tiers = {}
    current_tier = None
    xmin = xmax = None

    for line in lines:
        if line.startswith("item ["):
            current_tier = None
            continue
        if current_tier is None and line.startswith("name ="):
            current_tier = line.split("=", 1)[1].strip().strip('"')
            tiers.setdefault(current_tier, [])
            continue
        if line.startswith("intervals ["):
            xmin = xmax = None
            continue
        if current_tier and line.startswith("xmin ="):
            try:
                xmin = float(line.split("=", 1)[1].strip())
            except ValueError:
                xmin = None
            continue
        if current_tier and line.startswith("xmax ="):
            try:
                xmax = float(line.split("=", 1)[1].strip())
            except ValueError:
                xmax = None
            continue
        if current_tier and line.startswith("text ="):
            label = line.split("=", 1)[1].strip().strip('"').strip()
            if xmin is not None and xmax is not None and xmax > xmin:
                tiers.setdefault(current_tier, []).append((xmin, xmax, label))
            xmin = xmax = None
            continue

    if not tiers:
        raise ValueError(f"No interval tiers found in {path}")
    return tiers


def load_waveform(wav_path):
    with wave.open(str(wav_path), "rb") as w:
        sr = w.getframerate()
        n = w.getnframes()
        raw = w.readframes(n)
        channels = w.getnchannels()
    samples = np.frombuffer(raw, dtype=np.int16)
    if channels > 1:
        samples = samples.reshape(-1, channels).mean(axis=1)
    return samples.astype(np.float32) / 32768.0, sr


def is_silence_label(label):
    return label.strip().lower() in {"", "sp", "sil", "silence", "<eps>", "<unk>", "#0", "spn"}


def print_red_flags(tiers, expected_word_count=None):
    print("=== Red flags ===")
    any_flag = False

    for tier_name in ("words", "word"):
        if tier_name in tiers:
            words = [t for t in tiers[tier_name] if not is_silence_label(t[2])]
            print(f"Word tier '{tier_name}': {len(words)} words aligned.")
            if expected_word_count is not None and len(words) != expected_word_count:
                print(f"  FLAG: expected {expected_word_count} words from your input text, got {len(words)}.")
                print("        Almost always means an out-of-vocabulary word -- check for words")
                print("        MFA's dictionary wouldn't recognize (names, slang, typos).")
                any_flag = True
            for start, end, label in words:
                if is_silence_label(label):
                    continue
                # MFA emits <unk> or the word itself with a flat/guessed
                # alignment for OOV words depending on config; a single word
                # spanning an unusually long duration is the visible symptom.
                if (end - start) > 1.2:
                    print(f"  FLAG: word '{label}' spans {end-start:.2f}s ({start:.2f}-{end:.2f}) -- unusually long for one word.")
                    any_flag = True
            break

    for tier_name in ("phones", "phone"):
        if tier_name in tiers:
            phones = [t for t in tiers[tier_name] if not is_silence_label(t[2])]
            print(f"Phone tier '{tier_name}': {len(phones)} phones aligned.")
            long_flags = [(s, e, l) for s, e, l in phones if (e - s) > 0.45]
            short_flags = [(s, e, l) for s, e, l in phones if (e - s) < 0.015]
            for s, e, l in long_flags:
                print(f"  FLAG: phone '{l}' spans {e-s:.3f}s ({s:.2f}-{e:.2f}) -- unusually long for a single phone.")
                any_flag = True
            for s, e, l in short_flags:
                print(f"  FLAG: phone '{l}' spans only {e-s:.3f}s ({s:.2f}-{e:.2f}) -- suspiciously short.")
                any_flag = True
            break

    if not any_flag:
        print("None found by these checks. Still look at the plot -- these are sanity checks, not proof.")
    print()


def plot_review(wav_path, textgrid_path, out_path, expected_word_count=None):
    samples, sr = load_waveform(wav_path)
    duration = len(samples) / sr
    tiers = parse_all_tiers(textgrid_path)

    print_red_flags(tiers, expected_word_count)

    tier_order = [t for t in ("words", "word", "phones", "phone") if t in tiers]
    if not tier_order:
        tier_order = list(tiers.keys())

    fig, axes = plt.subplots(
        1 + len(tier_order), 1, figsize=(max(10, duration * 3), 2 + 1.4 * len(tier_order)),
        sharex=True, gridspec_kw={"height_ratios": [2] + [1] * len(tier_order)},
    )
    if len(tier_order) == 0:
        axes = [axes]

    t = np.linspace(0, duration, len(samples))
    axes[0].plot(t, samples, linewidth=0.5, color="#2b6cb0")
    axes[0].set_ylabel("waveform")
    axes[0].set_xlim(0, duration)

    boundary_times = set()
    for tier_name in tier_order:
        for start, end, label in tiers[tier_name]:
            boundary_times.add(round(start, 4))
            boundary_times.add(round(end, 4))

    for bt in boundary_times:
        axes[0].axvline(bt, color="#cbd5e0", linewidth=0.5, zorder=0)

    for row, tier_name in enumerate(tier_order, start=1):
        ax = axes[row]
        ax.set_xlim(0, duration)
        ax.set_ylim(0, 1)
        ax.set_yticks([])
        ax.set_ylabel(tier_name, rotation=0, ha="right", va="center")
        toggle = 0
        for start, end, label in tiers[tier_name]:
            if is_silence_label(label):
                face = "#e2e8f0"
            else:
                face = "#90cdf4" if toggle == 0 else "#63b3ed"
                toggle = 1 - toggle
            ax.axvspan(start, end, facecolor=face, edgecolor="#2d3748", linewidth=0.8)
            mid = (start + end) / 2
            if (end - start) > 0.02:
                ax.text(mid, 0.5, label, ha="center", va="center", fontsize=7, rotation=0, clip_on=True)

    axes[-1].set_xlabel("time (s)")
    fig.suptitle(f"{Path(wav_path).name}  |  {duration:.2f}s  |  {Path(textgrid_path).name}")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    print(f"Wrote {out_path}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--audio", required=True)
    p.add_argument("--textgrid", required=True)
    p.add_argument("--out", default="alignment_review.png")
    p.add_argument("--expected-words", type=int, default=None,
                    help="Word count of your input sentence. Prefer --text instead if you have it handy.")
    p.add_argument("--text", default=None,
                    help='The exact sentence you synthesized, e.g. --text "Hello there friend" -- word count is computed for you.')
    args = p.parse_args()

    expected = args.expected_words
    if args.text is not None:
        expected = len(args.text.split())

    plot_review(args.audio, args.textgrid, args.out, expected)


if __name__ == "__main__":
    main()
