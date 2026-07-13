from __future__ import annotations

import regex as re
from num2words import num2words

LANGS = {"en", "ta", "ml", "hi", "te", "kn"}

# Production hook: replace this with a stronger per-language number/symbol normalizer later.
# Important production rule: the text returned here is the exact text sent to TTS and MFA.
COMMON_SYMBOL_REPLACEMENTS = {
    "%": " percent ",
    "+": " plus ",
    "=": " equals ",
    "@": " at ",
}

EN_SYMBOL_REPLACEMENTS = {
    "&": " and ",
    "₹": " rupees ",
    "#": " number ",
}

INDIC_SYMBOL_REPLACEMENTS = {
    "&": " and ",
    "₹": " rupees ",
}

ZERO_WIDTH_RE = re.compile(r"[\u200b\u200c\u200d\ufeff]")
MULTISPACE = re.compile(r"\s+")

# --- Number -> words expansion (English only for now) ---
# Runs BEFORE the crude symbol replacements above and before the
# Latin/digit-only character filter, so it can still see "$"/"%"/":"
# attached to their numbers to tell what kind of number it is. This is the
# real fix for the "5:15" -> "5 15" bug: MFA was getting bare numeral
# tokens with no dictionary pronunciation, producing "spn" (unknown
# pronunciation) blocks. Converting to real words here means MFA never
# sees a bare digit at all for the cases this covers.
#
# Known gaps, deliberately out of scope for this pass (will still produce
# spn if they occur -- that's what the SPN->UH_MISC fallback in
# indic_viseme_mapper.py is for):
#   - 24-hour times (17:30) say the hour as a plain number ("seventeen
#     thirty"), not converted to 12-hour + am/pm.
#   - Digits glued to letters (COVID19, Round2) aren't touched -- the \b
#     word-boundary regexes below don't split inside a single token, and
#     there's no reliable way to guess the right pronunciation there.
#   - Ranges (10-15), fractions (1/2), ordinals (3rd, 1st) aren't expanded.
_CURRENCY_RE = re.compile(r"\$\s?(\d+)(?:\.(\d{1,2}))?")
_PERCENT_RE = re.compile(r"(\d+(?:\.\d+)?)\s?%")
_TIME_RE = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)\s?([AaPp]\.?[Mm]\.?)?\b")
_DECIMAL_RE = re.compile(r"\b(\d+)\.(\d+)\b")
_INTEGER_RE = re.compile(r"\b\d+\b")


def _say_int(n: int) -> str:
    return num2words(n)


def _expand_currency(m: re.Match) -> str:
    dollars = int(m.group(1))
    cents = m.group(2)
    word = f"{_say_int(dollars)} {'dollar' if dollars == 1 else 'dollars'}"
    if cents:
        cents_val = int(cents.ljust(2, "0"))
        if cents_val > 0:
            word += f" and {_say_int(cents_val)} {'cent' if cents_val == 1 else 'cents'}"
    return word


def _expand_percent(m: re.Match) -> str:
    num_str = m.group(1)
    if "." in num_str:
        whole, frac = num_str.split(".")
        word = f"{_say_int(int(whole))} point " + " ".join(_say_int(int(d)) for d in frac)
    else:
        word = _say_int(int(num_str))
    return f"{word} percent"


def _expand_time(m: re.Match) -> str:
    hour = int(m.group(1))
    minute = int(m.group(2))
    ampm = m.group(3)
    hour_word = _say_int(hour if hour != 0 else 12)
    if minute == 0:
        word = f"{hour_word} o'clock"
    elif minute < 10:
        word = f"{hour_word} oh {_say_int(minute)}"
    else:
        word = f"{hour_word} {_say_int(minute)}"
    if ampm:
        word += f" {ampm.replace('.', '').lower()}"
    return word


def _expand_decimal(m: re.Match) -> str:
    whole = _say_int(int(m.group(1)))
    frac_word = " ".join(_say_int(int(d)) for d in m.group(2))
    return f"{whole} point {frac_word}"


def _expand_integer(m: re.Match) -> str:
    return _say_int(int(m.group(0)))


def expand_numbers_to_words(text: str) -> str:
    """Order matters: each pattern's trigger character ($ % : .) is
    consumed before the generic bare-integer pattern would otherwise catch
    part of it."""
    text = _CURRENCY_RE.sub(_expand_currency, text)
    text = _PERCENT_RE.sub(_expand_percent, text)
    text = _TIME_RE.sub(_expand_time, text)
    text = _DECIMAL_RE.sub(_expand_decimal, text)
    text = _INTEGER_RE.sub(_expand_integer, text)
    return text


def normalize_for_speech(raw_text: str, lang: str) -> str:
    if lang not in LANGS:
        raise ValueError(f"Unsupported language '{lang}'. Use one of {sorted(LANGS)}")

    text = raw_text.strip()
    text = ZERO_WIDTH_RE.sub("", text)

    if lang == "en":
        text = expand_numbers_to_words(text)

    replacements = dict(COMMON_SYMBOL_REPLACEMENTS)
    replacements.update(EN_SYMBOL_REPLACEMENTS if lang == "en" else INDIC_SYMBOL_REPLACEMENTS)
    for src, dst in replacements.items():
        text = text.replace(src, dst)

    if lang == "en":
        # MFA English dictionary works best with normal English words and punctuation.
        text = text.replace("’", "'").replace("“", '"').replace("”", '"')
        # Keep apostrophes inside words, remove unsupported decorative punctuation.
        text = re.sub(r"[^\p{Latin}\p{N}\s.!?,;'\-]", " ", text)
    else:
        # Keep sentence punctuation because it helps TTS prosody.
        # Remove repeated punctuation that can confuse alignment.
        text = re.sub(r"([.!?।]){2,}", r"\1", text)

    text = MULTISPACE.sub(" ", text).strip()
    if not text:
        raise ValueError("Text became empty after normalization.")
    return text


def split_sentences(text: str) -> list[str]:
    # Alignment is better sentence-by-sentence.
    # NOTE: not currently called anywhere in cli_generate.py -- the full
    # input text is sent to TTS/MFA as a single utterance regardless of
    # length. Wiring this in means chunking the corpus into multiple .lab/
    # .wav pairs, running MFA per chunk, and reconciling timestamps/
    # concatenating audio across chunks -- a bigger structural change than
    # a bug fix, left out of this pass. Fine for the short single-sentence
    # test commands in this README; worth revisiting before feeding it
    # multi-sentence paragraphs.
    chunks = re.split(r"(?<=[.!?।])\s+", text.strip())
    return [c.strip() for c in chunks if c.strip()]
