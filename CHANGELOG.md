# Fix pass — what changed and why

Same flow as before (Piper/IndicF5 → MFA/IndicMFA → 18-sprite viseme map →
smoothing → Unity). Nothing architectural moved. Every fix below was run
against your actual bundled Piper model and verified, not just read.

## How to apply

1. **Delete `backend/src/`** from your project entirely.
2. Copy every file in this package into your project at the matching path
   (they overwrite the originals 1:1).
3. Nothing else needs to change — no new dependencies, no new config keys.

## Critical (broke the documented setup)

**`backend/production_lipsync/file_utils.py`** — `project_root()` used
`parents[2]`, which is only correct if this file lives at
`backend/src/production_lipsync/file_utils.py`. The package that's actually
installed (`pyproject.toml`'s `where=["."]`) is the top-level
`backend/production_lipsync/`, one directory shallower — `parents[2]` was
resolving to the folder *above* `backend/`, breaking every relative path in
`config/languages.json`. Fixed to `parents[1]`. Verified: ran your README's
exact English command against your real bundled model — failed before the
fix (`FileNotFoundError` one directory too high), succeeded after.

**Deleted `backend/src/production_lipsync/`** — a second, divergent copy of
the same package that `pyproject.toml` never actually installs (confirmed:
its `cli_generate.py` had already drifted from the live copy). It was a
trap: editing it — the natural thing to do since `src/` layout is the
standard modern convention — would silently do nothing. One copy now.

**`backend/config/languages.json`** — `piper_model`/`piper_config` pointed
at `models/piper/en/...`; the model that's actually bundled lives at
`models/piper_voices/en/...`. Also `mfa_dictionary`/`mfa_acoustic_model`
said `english_us_arpa`, but the README (and `languages.backup.json`, and
`tools/install_english_models_windows.ps1`) all say to download
`english_mfa` — two different real MFA models. Aligned the config to what
the docs actually tell you to download. Same two fixes applied to
`languages.backup.json`, `tools/install_windows.ps1`,
`tools/install_english_models_windows.ps1`, `tools/run_english_example.ps1`,
and `README_START_HERE.md` so nothing points at the wrong path anymore.
Verified: ran the pipeline with *no* `--piper-model`/`--piper-config`
override at all, relying purely on the config default — succeeded.

**`backend/production_lipsync/cli_generate.py`** — `--skip-align` couldn't
work. `align_dir` was built with `ensure_empty_dir(...)` *unconditionally*,
which wipes the folder — including any existing TextGrid — before the
`--skip-align` check ever looks for one. Found this empirically: placed a
TextGrid, ran with `--skip-align`, watched it get deleted out from under
itself. Now `align_dir` only gets wiped when alignment is actually about to
run; `--skip-align` uses the non-destructive `ensure_dir`, matching how
`--skip-tts`/`audio_dir` already worked correctly.

## Serious (ran fine, produced wrong output)

**`backend/production_lipsync/smoothing.py`** — the actual lip-sync bug.
`end += vowel_extra` (vowel dominance) skipped the overlap check entirely
when the current frame was a vowel, and even the non-vowel clamp could
still overlap when `next_start < start + min_hold`. I built a realistic
TextGrid ("hello this" — HH, IY1, Z, DH, AH0) and ran it through your real
`smooth_frames()`, then simulated `ProductionLipSyncPlayer.ApplyFrameForTime()`'s
cursor logic against the output:

```
Before fix: 2 of 9 frames never displayed (SZ_SH_CH "Z", DENTAL_TDN "DH" —
            both fully swallowed by the extended E_WIDE frame before them)
After fix:  0 of 9 frames skipped, 0 overlapping pairs
```

The fix makes the "never overlap the next frame" rule unconditional —
applies to every viseme type, and to the two rest-insertion branches too
(both were using the *raw* MFA end instead of the frame's own *adjusted*
end, which could let an inserted silence-frame overlap the frame right
before it). `min_hold`/`vowel_extra` are now "hold this long if there's
room," never "hold this long regardless."

**`backend/production_lipsync/quality_report.py`** — added the check that
would have caught this automatically: `qa_report.json` now reports
`overlappingFramePairs` and adds a warning if it's nonzero.

## Documented, not changed (didn't want to guess at a design call)

**`indic_viseme_mapper.py`** — `MEDIUM_OPEN`/`BIG_OPEN` (2 of your 18
sprites) are still never produced by `unit_to_viseme()`. Left unwired —
turning them on means picking a trigger (stress? loudness? something else?)
that changes animation output, and I don't have a spec for what you
actually want there. Added a comment so it's a documented gap, not a silent
one. Tell me the intended trigger and I'll wire it up.

**`normalizer.py`** — `split_sentences()` is still unused; long text still
goes to TTS/MFA as one utterance. Wiring it in means chunking the corpus
into multiple `.lab`/`.wav` pairs and reconciling timestamps across MFA
runs — a bigger structural change than a fix, and every example in your
README is a single sentence anyway. Commented for visibility; say the word
if you want this built out.

**`indic_viseme_mapper.py`** — `SIL`/`SP`/`SPN`/`PAU` entries in `roman_map`
are unreachable (silence intervals get filtered out one step earlier, in
`textgrid_parser.py`). Harmless, left in place as a defensive default,
commented so it's not mistaken for an oversight.

## Not touched

Windows-only toolchain (Miniconda `.exe`, `piper.exe`, `.dll` runtime,
`.ps1` scripts) — that's a packaging/deployment question for whenever you
port this to the Linux server your original architecture diagram describes,
not something to fix inside "same flow."
