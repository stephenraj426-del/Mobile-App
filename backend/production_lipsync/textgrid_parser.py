from __future__ import annotations

from pathlib import Path

from .schema import AlignedUnit


def _clean_label(label: str) -> str:
    return label.strip().strip('"').strip()


def parse_textgrid_intervals(path: str | Path, preferred_tiers: tuple[str, ...] = ("phones", "phone", "segments", "letters", "characters")) -> list[AlignedUnit]:
    """Parse a Praat TextGrid and return the best phone/letter-like interval tier.

    This intentionally avoids an external TextGrid dependency. It handles the
    common long TextGrid format exported by MFA.
    """
    path = Path(path)
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = [line.strip() for line in text.splitlines()]

    tiers: dict[str, list[AlignedUnit]] = {}
    current_tier_name: str | None = None
    current_xmin: float | None = None
    current_xmax: float | None = None
    inside_item = False

    for line in lines:
        if line.startswith("item ["):
            inside_item = True
            current_tier_name = None
            continue

        if inside_item and line.startswith("name ="):
            current_tier_name = _clean_label(line.split("=", 1)[1])
            tiers.setdefault(current_tier_name, [])
            continue

        if line.startswith("intervals ["):
            current_xmin = None
            current_xmax = None
            continue

        if current_tier_name and line.startswith("xmin ="):
            try:
                current_xmin = float(line.split("=", 1)[1].strip())
            except ValueError:
                current_xmin = None
            continue

        if current_tier_name and line.startswith("xmax ="):
            try:
                current_xmax = float(line.split("=", 1)[1].strip())
            except ValueError:
                current_xmax = None
            continue

        if current_tier_name and line.startswith("text ="):
            label = _clean_label(line.split("=", 1)[1])
            if current_xmin is not None and current_xmax is not None:
                if current_xmax > current_xmin:
                    tiers.setdefault(current_tier_name, []).append(
                        AlignedUnit(start=current_xmin, end=current_xmax, label=label, tier=current_tier_name)
                    )
            current_xmin = None
            current_xmax = None
            continue

    if not tiers:
        raise ValueError(f"No interval tiers found in TextGrid: {path}")

    normalized_names = {name.lower(): name for name in tiers.keys()}
    for wanted in preferred_tiers:
        if wanted.lower() in normalized_names:
            selected = normalized_names[wanted.lower()]
            return _filter_units(tiers[selected])

    # MFA sometimes uses speaker-dependent tier names. Prefer the shortest tier
    # units, because phones/letters are shorter than words.
    candidates = []
    for name, units in tiers.items():
        filtered = _filter_units(units)
        if filtered:
            avg_duration = sum(u.duration for u in filtered) / len(filtered)
            candidates.append((avg_duration, name, filtered))
    if not candidates:
        raise ValueError(f"Only empty/silence intervals found in TextGrid: {path}")
    candidates.sort(key=lambda x: x[0])
    return candidates[0][2]


def _filter_units(units: list[AlignedUnit]) -> list[AlignedUnit]:
    bad = {"", "sp", "sil", "silence", "<eps>", "<unk>", "#0"}
    return [u for u in units if u.label.strip().lower() not in bad and u.duration > 0.005]
