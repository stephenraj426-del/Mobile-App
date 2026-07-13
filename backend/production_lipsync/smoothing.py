from __future__ import annotations

from dataclasses import replace

from .schema import VisemeFrame
from .indic_viseme_mapper import DEFAULT_JAW, DEFAULT_SCALE, VISEME_TO_INDEX

VOWELS = {
    "AA_WIDE", "EE_NARROW", "OO_ROUND", "UH_MISC",
    "I_NEAR_EE", "O_HALF_OPEN", "AW_VOWEL", "UR_VOWEL", "AE_SHORT",
}
SNAP_CONSONANTS = {"M_B_P", "W_SOUND"}


def smooth_frames(
    frames: list[VisemeFrame],
    duration: float,
    anticipation_ms: int = 42,
    minimum_hold_ms: int = 48,
    silence_close_after_ms: int = 70,
    vowel_dominance_ms: int = 55,
    max_frame_gap_ms: int = 80,
) -> list[VisemeFrame]:
    """Convert raw aligned units to animator-friendly frames.

    Rules:
    - anticipate next mouth 30-50 ms early
    - remove micro frames
    - insert closed mouth during pauses
    - keep vowels visible slightly longer
    - keep MBP snappy
    """
    if not frames:
        return [rest(0.0, duration)] if duration > 0 else []

    anticipation = anticipation_ms / 1000.0
    min_hold = minimum_hold_ms / 1000.0
    silence_gap = silence_close_after_ms / 1000.0
    vowel_extra = vowel_dominance_ms / 1000.0
    max_gap = max_frame_gap_ms / 1000.0

    ordered = sorted(frames, key=lambda f: (f.time, f.end))
    adjusted: list[VisemeFrame] = []

    # Initial rest if audio starts with silence.
    if ordered[0].time > 0.02:
        adjusted.append(rest(0.0, max(0.0, ordered[0].time - anticipation)))

    for i, f in enumerate(ordered):
        # Cap anticipation at half the gap to the previous phone's raw time.
        # Without this, two phones close together (e.g. 30ms apart, common
        # right at the start of an utterance) can both get pulled to the
        # exact same clamped instant by the flat anticipation shift -- which
        # then collapses the earlier one to zero duration and drops it
        # entirely. Confirmed with real data: "The" -> the TH frame vanished
        # completely because its anticipated start collided exactly with
        # the following vowel's anticipated start, both landing on t=0.
        effective_anticipation = anticipation
        if i > 0:
            gap_before = f.time - ordered[i - 1].time
            effective_anticipation = min(anticipation, max(0.0, gap_before) / 2)

        start = max(0.0, f.time - effective_anticipation)
        end = max(start + min_hold, f.end)

        # Vowels visually dominate because consonants are often too short for 2D sprites.
        if f.viseme in VOWELS:
            end += vowel_extra

        # Snappy mouth-close consonants should not be over-extended too much.
        if f.viseme in SNAP_CONSONANTS:
            end = min(end, f.end + 0.035)

        # Hard cap: a frame's end must never cross into the next frame's start,
        # regardless of viseme type or minimum-hold. Letting vowels (or a large
        # minimum_hold_ms) skip past next_start used to let one frame's window
        # fully swallow the next one or two frames' time ranges. Since the
        # Unity player advances its cursor only once playback time reaches a
        # frame's own `end`, any frame whose [time, end] sits entirely inside
        # a previous frame's window is never reached at all -- its viseme
        # silently never appears on screen. This cap is unconditional so that
        # can't happen: min_hold and vowel_extra are "hold this long if there's
        # room", never "hold this long no matter what."
        next_start = None
        if i + 1 < len(ordered):
            next_gap = ordered[i + 1].time - f.time
            next_effective_anticipation = min(anticipation, max(0.0, next_gap) / 2)
            next_start = max(0.0, ordered[i + 1].time - next_effective_anticipation)
            if end > next_start:
                end = max(start, next_start)

        adjusted_end = round(min(end, duration), 4)
        adjusted.append(replace(f, time=round(start, 4), end=adjusted_end))

        # Insert rest during long pauses between aligned units. r_start is
        # floored at adjusted_end (this frame's own just-computed end, which
        # vowel_extra/min_hold may have pushed later than the raw MFA end
        # used for the gap check) and both branches end at next_start, so the
        # rest frame can't overlap either the frame before it or after it.
        if next_start is not None:
            gap = ordered[i + 1].time - f.end
            if gap >= silence_gap:
                r_start = max(adjusted_end, min(duration, f.end + 0.02, next_start))
                r_end = max(r_start, min(r_start + 0.03, next_start))
                if r_end > r_start:
                    adjusted.append(rest(r_start, min(r_end, duration)))
            elif gap >= max_gap:
                r_start = max(adjusted_end, min(f.end, next_start))
                if next_start > r_start:
                    adjusted.append(rest(r_start, min(next_start, duration)))

    last_end = max(f.end for f in adjusted) if adjusted else 0.0
    if duration - last_end > 0.05:
        adjusted.append(rest(last_end, duration))

    merged = merge_repeated(adjusted, min_hold)
    return [f for f in merged if f.end > f.time]


def rest(start: float, end: float) -> VisemeFrame:
    sx, sy = DEFAULT_SCALE["REST_CLOSED"]
    return VisemeFrame(
        time=round(max(0.0, start), 4),
        end=round(max(start, end), 4),
        unit="sil",
        viseme="REST_CLOSED",
        spriteIndex=VISEME_TO_INDEX["REST_CLOSED"],
        jawOpen=DEFAULT_JAW["REST_CLOSED"],
        mouthScaleX=sx,
        mouthScaleY=sy,
        confidence=1.0,
    )


def merge_repeated(frames: list[VisemeFrame], min_hold: float) -> list[VisemeFrame]:
    if not frames:
        return []
    ordered = sorted(frames, key=lambda f: (f.time, f.end))
    out: list[VisemeFrame] = []
    for f in ordered:
        if out and out[-1].spriteIndex == f.spriteIndex and f.time <= out[-1].end + min_hold:
            prev = out[-1]
            out[-1] = replace(prev, end=round(max(prev.end, f.end), 4), unit=prev.unit if prev.unit == f.unit else f"{prev.unit}+{f.unit}")
        else:
            out.append(f)
    return out
