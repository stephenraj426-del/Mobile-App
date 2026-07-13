from __future__ import annotations

from .schema import AlignedUnit, VisemeFrame


def build_qa_report(
    raw_text: str,
    normalized_text: str,
    language: str,
    duration: float,
    units: list[AlignedUnit],
    frames: list[VisemeFrame],
) -> dict:
    unit_durations = [u.duration for u in units]
    frame_durations = [max(0.0, f.end - f.time) for f in frames]
    unique_visemes = sorted({f.viseme for f in frames})
    warnings: list[str] = []

    if not units:
        warnings.append("No aligned units found. Lip sync will stay closed.")
    if duration <= 0:
        warnings.append("Audio duration is zero or unreadable.")
    if unit_durations and max(unit_durations) > 0.6:
        warnings.append("Some aligned units are very long. Check MFA model/dictionary and normalized text.")
    if len(unique_visemes) <= 3 and duration > 1.0:
        warnings.append("Very low viseme variety. Check TextGrid tier selection or sprite mapping.")
    if frames and frames[-1].end < duration - 0.15:
        warnings.append("Last lip-sync frame ends before audio. Check alignment duration.")

    overlap_count = 0
    ordered_frames = sorted(frames, key=lambda f: (f.time, f.end))
    for a, b in zip(ordered_frames, ordered_frames[1:]):
        if a.end > b.time + 1e-6:
            overlap_count += 1
    if overlap_count:
        warnings.append(
            f"{overlap_count} frame(s) overlap in time. A frame client-side player that advances a "
            "cursor by 'time reached this frame's end' will skip whichever frame is fully inside "
            "another frame's window. Check smoothing.py's clamping logic."
        )

    return {
        "language": language,
        "durationSeconds": round(duration, 4),
        "rawText": raw_text,
        "normalizedText": normalized_text,
        "alignedUnitCount": len(units),
        "frameCount": len(frames),
        "uniqueVisemes": unique_visemes,
        "avgAlignedUnitMs": round((sum(unit_durations) / len(unit_durations) * 1000.0), 2) if unit_durations else 0,
        "avgFrameMs": round((sum(frame_durations) / len(frame_durations) * 1000.0), 2) if frame_durations else 0,
        "overlappingFramePairs": overlap_count,
        "warnings": warnings,
    }
