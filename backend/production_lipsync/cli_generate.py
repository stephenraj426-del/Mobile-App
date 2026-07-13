from __future__ import annotations

import argparse
from pathlib import Path

from .audio_tools import read_wav_duration_seconds
from .file_utils import copy_file, ensure_empty_dir, ensure_dir, load_json, resolve_backend_path, save_json, sha1_text
from .indic_viseme_mapper import map_units_to_frames
from .mfa_aligner import MfaAligner
from .normalizer import normalize_for_speech
from .piper_tts import PiperTTS
from .quality_report import build_qa_report
from .smoothing import smooth_frames
from .textgrid_parser import parse_textgrid_intervals


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate TTS audio + 21-sprite lip-sync JSON for English and Indic languages.")
    p.add_argument("--lang", required=True, choices=["en", "ta", "ml", "hi", "te", "kn"])
    p.add_argument("--text", required=True, help="Text the avatar should speak.")
    p.add_argument("--tts-engine", default="auto", choices=["auto", "piper", "indicf5"], help="Default: piper for en, indicf5 for Indian languages.")
    p.add_argument("--ref-audio", default=None, help="IndicF5 reference voice WAV path. Required for indicf5.")
    p.add_argument("--ref-text", default=None, help="Exact transcript of the IndicF5 reference voice WAV. Required for indicf5.")
    p.add_argument("--piper-bin", default="piper", help="Piper executable path/name for English TTS.")
    p.add_argument("--speed", type=float, default=None, help="Piper length_scale: >1.0 slower (e.g. 1.2 = 20% slower), <1.0 faster. Default: Piper's own default speed.")
    p.add_argument("--piper-model", default=None, help="Optional Piper .onnx voice model path. Overrides config/languages.json.")
    p.add_argument("--piper-config", default=None, help="Optional Piper .onnx.json config path. Overrides config/languages.json.")
    p.add_argument("--job-id", default=None, help="Output job id. Defaults to hash of language/text/voice.")
    p.add_argument("--device", default=None, help="Optional torch device for IndicF5, e.g. cuda or cpu.")
    p.add_argument("--mfa-bin", default="mfa")
    p.add_argument("--skip-tts", action="store_true", help="Use an existing WAV at runs/<job>/audio/avatar.wav.")
    p.add_argument("--skip-align", action="store_true", help="Use an existing TextGrid at runs/<job>/align/aligned.TextGrid.")
    p.add_argument("--num-jobs", type=int, default=None, help="MFA parallel jobs.")
    return p.parse_args()


def _selected_tts_engine(args: argparse.Namespace, lang_entry: dict) -> str:
    if args.tts_engine != "auto":
        return args.tts_engine
    return str(lang_entry.get("tts_engine", "indicf5"))


def _run_tts(
    *,
    engine: str,
    args: argparse.Namespace,
    lang_entry: dict,
    normalized_text: str,
    avatar_wav: Path,
    sample_rate: int,
) -> None:
    if engine == "piper":
        piper_model = args.piper_model or lang_entry.get("piper_model")
        piper_config = args.piper_config or lang_entry.get("piper_config")
        if not piper_model:
            raise ValueError("Piper model path is missing. Set --piper-model or config/languages.json piper_model.")
        print("[3/6] Running Piper English TTS...")
        tts = PiperTTS(args.piper_bin)
        tts.validate_available()
        tts.synthesize_to_wav(
            text=normalized_text,
            model_path=resolve_backend_path(piper_model),
            config_path=resolve_backend_path(piper_config) if piper_config else None,
            output_wav=avatar_wav,
            length_scale=args.speed,
        )
        return

    if engine == "indicf5":
        if not args.ref_audio or not args.ref_text:
            raise ValueError("IndicF5 requires --ref-audio and --ref-text. English normally uses --tts-engine piper.")
        # Lazy import keeps English/Piper usable even if IndicF5 dependencies are not installed yet.
        from .indic_f5_tts import IndicF5TTS

        print("[3/6] Running IndicF5 TTS...")
        tts = IndicF5TTS(device=args.device)
        tts.synthesize_to_wav(
            text=normalized_text,
            ref_audio_path=resolve_backend_path(args.ref_audio),
            ref_text=args.ref_text,
            output_wav=avatar_wav,
            sample_rate=sample_rate,
        )
        return

    raise ValueError(f"Unsupported TTS engine: {engine}")


def main() -> None:
    args = parse_args()
    backend_root = Path(__file__).resolve().parents[1]
    lang_cfg = load_json(backend_root / "config" / "languages.json")
    sprite_cfg = load_json(backend_root / "config" / "sprite_profile_21.json")
    if args.lang not in lang_cfg:
        raise ValueError(f"Language '{args.lang}' not found in config/languages.json")

    lang_entry = lang_cfg[args.lang]
    engine = _selected_tts_engine(args, lang_entry)
    normalized_text = normalize_for_speech(args.text, args.lang)
    voice_seed = args.piper_model or args.ref_audio or lang_entry.get("piper_model", "")
    job_seed = f"{args.lang}|{engine}|{normalized_text}|{voice_seed}|{args.ref_text or ''}"
    job_id = args.job_id or sha1_text(job_seed)[:12]

    run_dir = ensure_dir(backend_root / "runs" / job_id)
    audio_dir = ensure_dir(run_dir / "audio")
    corpus_dir = ensure_empty_dir(run_dir / "corpus")
    # NOTE: previously always ensure_empty_dir(...), which wiped out any
    # existing TextGrid before the --skip-align check below ever got to look
    # for it -- --skip-align could never actually find a TextGrid to reuse.
    align_dir = ensure_dir(run_dir / "align") if args.skip_align else ensure_empty_dir(run_dir / "align")
    lipsync_dir = ensure_dir(run_dir / "lipsync")

    avatar_wav = audio_dir / "avatar.wav"
    lab_file = corpus_dir / "utt_0001.lab"
    corpus_wav = corpus_dir / "utt_0001.wav"

    print(f"[1/6] Job: {job_id}")
    print(f"[2/6] Language: {args.lang} | TTS engine: {engine}")
    print(f"[2/6] Normalized text: {normalized_text}")

    if args.skip_tts:
        if not avatar_wav.exists():
            raise FileNotFoundError(f"--skip-tts was used, but WAV is missing: {avatar_wav}")
    else:
        _run_tts(
            engine=engine,
            args=args,
            lang_entry=lang_entry,
            normalized_text=normalized_text,
            avatar_wav=avatar_wav,
            sample_rate=int(lang_entry.get("sample_rate", 24000)),
        )

    duration = read_wav_duration_seconds(avatar_wav)
    lab_file.write_text(normalized_text + "\n", encoding="utf-8")
    copy_file(avatar_wav, corpus_wav)

    tg_output = align_dir / "aligned.TextGrid"
    if args.skip_align:
        if not tg_output.exists():
            raise FileNotFoundError(f"--skip-align was used, but TextGrid is missing: {tg_output}")
    else:
        print("[4/6] Running MFA forced alignment...")
        dictionary_value = lang_entry["mfa_dictionary"]
        acoustic_value = lang_entry["mfa_acoustic_model"]
        dictionary_path = resolve_backend_path(dictionary_value) if any(x in str(dictionary_value) for x in ("/", "\\")) else dictionary_value
        acoustic_path = resolve_backend_path(acoustic_value) if any(x in str(acoustic_value) for x in ("/", "\\")) else acoustic_value
        aligner = MfaAligner(args.mfa_bin)
        aligner.validate_available()
        produced_tg = aligner.align(
            corpus_dir=corpus_dir,
            dictionary_path=dictionary_path,
            acoustic_model_path=acoustic_path,
            output_dir=align_dir,
            clean=True,
            overwrite=True,
            num_jobs=args.num_jobs,
        )
        # Normalize the filename for the Unity export process.
        copy_file(produced_tg, tg_output)

    print("[5/6] Building 21-sprite lipsync JSON...")
    units = parse_textgrid_intervals(tg_output)
    raw_frames = map_units_to_frames(units, args.lang)
    s = sprite_cfg.get("smoothing", {})
    frames = smooth_frames(
        raw_frames,
        duration=duration,
        anticipation_ms=int(s.get("anticipationMs", 42)),
        minimum_hold_ms=int(s.get("minimumHoldMs", 48)),
        silence_close_after_ms=int(s.get("silenceCloseAfterMs", 70)),
        vowel_dominance_ms=int(s.get("vowelDominanceMs", 55)),
        max_frame_gap_ms=int(s.get("maxFrameGapMs", 80)),
    )

    lipsync = {
        "version": "1.1",
        "source": f"{engine} + MFA + 21-sprite-viseme-map",
        "language": args.lang,
        "audioFile": "avatar.wav",
        "duration": round(duration, 4),
        "rawText": args.text,
        "normalizedText": normalized_text,
        "spriteProfile": "21-universal-en-indic",
        "frames": [f.to_json() for f in frames],
    }
    save_json(lipsync_dir / "lipsync.json", lipsync)

    qa = build_qa_report(args.text, normalized_text, args.lang, duration, units, frames)
    save_json(lipsync_dir / "qa_report.json", qa)

    print("[6/6] DONE")
    print(f"Audio:       {avatar_wav}")
    print(f"TextGrid:    {tg_output}")
    print(f"LipSync JSON:{lipsync_dir / 'lipsync.json'}")
    print(f"QA report:   {lipsync_dir / 'qa_report.json'}")
    if qa["warnings"]:
        print("Warnings:")
        for w in qa["warnings"]:
            print(f"  - {w}")


if __name__ == "__main__":
    main()
