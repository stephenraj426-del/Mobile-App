from __future__ import annotations

import unicodedata

import regex as re

from .schema import AlignedUnit, VisemeFrame

# 21-sprite profile, matching the actual bundled art
# (Unity_FullFrame_Sequences222: FRAME_<NN>_<NAME>_<0-4>.png, 5 frames each).
# Replaces the earlier 18-category placeholder scheme -- these are real
# asset names, not aspirational ones, so every index here has art behind it.
VISEME_TO_INDEX = {
    "REST_CLOSED": 0,
    "AA_WIDE": 1,
    "EE_NARROW": 2,
    "OO_ROUND": 3,
    "UH_MISC": 4,
    "M_B_P": 5,
    "F_V": 6,
    "TH": 7,
    "L_D_T": 8,
    "SH_CH": 9,
    "K_G": 10,
    "S_Z": 11,
    "I_NEAR_EE": 12,
    "O_HALF_OPEN": 13,
    "AW_VOWEL": 14,
    "N_CONSONANT": 15,
    "UR_VOWEL": 16,
    "W_SOUND": 17,
    "H_BREATH": 18,
    "AE_SHORT": 19,
    "ERR_MODIFIER": 20,
}

# Starting defaults -- reasonable jaw/scale guesses per category, same spirit
# as the old scheme's numbers where the category is a close analog. Tune
# these against your actual sprites; nothing else in the pipeline depends
# on the exact values, only on every VISEME_TO_INDEX key having an entry.
DEFAULT_JAW = {
    "REST_CLOSED": 0.00,
    "AA_WIDE": 0.86,
    "EE_NARROW": 0.42,
    "OO_ROUND": 0.28,
    "UH_MISC": 0.35,
    "M_B_P": 0.00,
    "F_V": 0.18,
    "TH": 0.20,
    "L_D_T": 0.28,
    "SH_CH": 0.22,
    "K_G": 0.32,
    "S_Z": 0.15,
    "I_NEAR_EE": 0.20,
    "O_HALF_OPEN": 0.55,
    "AW_VOWEL": 0.65,
    "N_CONSONANT": 0.25,
    "UR_VOWEL": 0.35,
    "W_SOUND": 0.20,
    "H_BREATH": 0.22,
    "AE_SHORT": 0.55,
    "ERR_MODIFIER": 0.28,
}

DEFAULT_SCALE = {
    "REST_CLOSED": (1.00, 1.00),
    "AA_WIDE": (1.00, 1.18),
    "EE_NARROW": (1.18, 0.92),
    "OO_ROUND": (0.72, 0.85),
    "UH_MISC": (1.00, 1.00),
    "M_B_P": (0.98, 0.96),
    "F_V": (0.96, 0.98),
    "TH": (1.00, 0.95),
    "L_D_T": (1.02, 0.98),
    "SH_CH": (0.85, 0.92),
    "K_G": (1.00, 1.02),
    "S_Z": (1.05, 0.90),
    "I_NEAR_EE": (1.10, 0.85),
    "O_HALF_OPEN": (0.85, 1.00),
    "AW_VOWEL": (0.90, 1.05),
    "N_CONSONANT": (1.00, 1.00),
    "UR_VOWEL": (0.90, 0.95),
    "W_SOUND": (0.65, 0.85),
    "H_BREATH": (1.00, 1.00),
    "AE_SHORT": (1.05, 1.05),
    "ERR_MODIFIER": (0.85, 0.95),
}

# Independent vowels + dependent vowel signs for Brahmic scripts.
VOWEL_SIGNS_A = set("ாाాಾാ")
VOWEL_SIGNS_E = set("ிீெேைिீेैిీెేైಿೀೆೇೈിീെேൈ")
VOWEL_SIGNS_U = set("ுூुूుూುೂುൂ")
VOWEL_SIGNS_O = set("ொோௌोौొోౌೊೋೌൊോൗ")

# Independent vowels by script.
A_VOWELS = set("அஆअआఅఆಅಆഅആ")
E_VOWELS = set("இஈஎஏऋइईएఇఈఎఏಇಈಎಏഇഈഎഏ")
U_VOWELS = set("உஊउऊఉఊಉಊഉഊ")
O_VOWELS = set("ஒஓஔओऔఒఓఔಒಓಔഒഓഔ")
AI_VOWELS = set("ஐऐఐಐഐ")


def _chars(*names: str) -> set[str]:
    """Build a character set from official Unicode names via
    unicodedata.lookup(), instead of hand-typed Unicode literals. A typo in
    a name here raises KeyError immediately (caught by the self-test at the
    bottom of this module); a typo in a hand-typed literal glyph would
    silently produce a subtly wrong or missing character with no error at
    all, which is what caused real mapping bugs during development."""
    return {unicodedata.lookup(n) for n in names}


# Consonant visual groups across Tamil, Malayalam, Hindi, Telugu, Kannada.
# Split more finely than the old 18-scheme did, to match the 21-scheme's
# extra English-oriented categories. Two real consequences of that split,
# worth knowing:
#  - Dental (त/द/த/...) and retroflex (ट/ड/ட/...) stops now land in the
#    SAME bucket (L_D_T) -- the 21-scheme has no separate retroflex viseme
#    the way the 18-scheme's RETRO_TDN did, so that distinction is lost
#    visually. Same for dental vs retroflex nasals -> N_CONSONANT.
#  - Tamil/Malayalam RRA (ற/റ) used to be folded in with retroflex T/D/N
#    (a rough approximation); it's phonetically an r-sound, so it's grouped
#    with R_SET -> ERR_MODIFIER now, which is more accurate, not less.
MBP = _chars(
    "DEVANAGARI LETTER PA", "DEVANAGARI LETTER BA", "DEVANAGARI LETTER BHA", "DEVANAGARI LETTER MA",
    "TAMIL LETTER PA", "TAMIL LETTER MA", "TAMIL SIGN ANUSVARA", "TAMIL SIGN VIRAMA",
    "TELUGU LETTER PA", "TELUGU LETTER BA", "TELUGU LETTER BHA", "TELUGU LETTER MA", "TELUGU SIGN ANUSVARA",
    "KANNADA LETTER PA", "KANNADA LETTER BA", "KANNADA LETTER BHA", "KANNADA LETTER MA",
    "KANNADA SIGN ANUSVARA", "KANNADA SIGN VIRAMA",
    "MALAYALAM LETTER PA", "MALAYALAM LETTER BA", "MALAYALAM LETTER BHA", "MALAYALAM LETTER MA",
    "MALAYALAM SIGN ANUSVARA",
)
FVW = _chars(
    "DEVANAGARI LETTER VA", "TAMIL LETTER VA", "TELUGU LETTER VA", "KANNADA LETTER VA", "MALAYALAM LETTER VA",
    "BENGALI LETTER RA WITH LOWER DIAGONAL",
)
DENTAL_STOP = _chars(
    "DEVANAGARI LETTER TA", "DEVANAGARI LETTER DA", "DEVANAGARI LETTER TTA", "DEVANAGARI LETTER DDA",
    "TAMIL LETTER TA", "TAMIL LETTER TTA",
    "TELUGU LETTER TA", "TELUGU LETTER THA", "TELUGU LETTER DA", "TELUGU LETTER DHA",
    "TELUGU LETTER TTA", "TELUGU LETTER TTHA", "TELUGU LETTER DDA",
    "KANNADA LETTER TA", "KANNADA LETTER THA", "KANNADA LETTER DA", "KANNADA LETTER DHA",
    "KANNADA LETTER TTA", "KANNADA LETTER TTHA", "KANNADA LETTER DDA", "KANNADA LETTER DDHA",
    "MALAYALAM LETTER TA", "MALAYALAM LETTER THA", "MALAYALAM LETTER DA", "MALAYALAM LETTER DHA",
    "MALAYALAM LETTER TTA", "MALAYALAM LETTER DDA",
)
NASAL_ALL = _chars(
    "DEVANAGARI LETTER NA", "DEVANAGARI LETTER NNA",
    "TAMIL LETTER NA", "TAMIL LETTER NNNA", "TAMIL LETTER NNA",
    "TELUGU LETTER NA", "TELUGU LETTER NNA",
    "KANNADA LETTER NA", "KANNADA LETTER NNA",
    "MALAYALAM LETTER NA", "MALAYALAM LETTER NNA",
)
KG = _chars(
    "DEVANAGARI LETTER KA", "DEVANAGARI LETTER KHA", "DEVANAGARI LETTER GA",
    "TAMIL LETTER KA", "TAMIL LETTER NGA",
    "TELUGU LETTER KA", "TELUGU LETTER KHA", "TELUGU LETTER GA", "TELUGU LETTER GHA", "TELUGU LETTER NGA",
    "KANNADA LETTER KA", "KANNADA LETTER KHA", "KANNADA LETTER GA", "KANNADA LETTER GHA",
    "MALAYALAM LETTER KA", "MALAYALAM LETTER KHA", "MALAYALAM LETTER GA", "MALAYALAM LETTER GHA",
    "MALAYALAM LETTER NGA",
)
# ca/cha/ja/sha/ssa (affricates + sh) -- split out of the old combined
# SZSHCH bucket. Plain s (S_SET) and h (HA_SET) now get their own buckets
# since the 21-scheme separates S_Z from SH_CH and has a dedicated H_BREATH.
SZSHCH = _chars(
    "DEVANAGARI LETTER CA", "DEVANAGARI LETTER JA", "DEVANAGARI LETTER SHA", "DEVANAGARI LETTER SSA",
    "TAMIL LETTER CA", "TAMIL LETTER JA", "TAMIL LETTER SSA",
    "TELUGU LETTER CA", "TELUGU LETTER CHA", "TELUGU LETTER JA", "TELUGU LETTER SHA", "TELUGU LETTER SSA",
    "KANNADA LETTER CA", "KANNADA LETTER CHA", "KANNADA LETTER JA", "KANNADA LETTER SHA", "KANNADA LETTER SSA",
    "MALAYALAM LETTER CA", "MALAYALAM LETTER JA", "MALAYALAM LETTER SHA", "MALAYALAM LETTER SSA",
)
S_SET = _chars(
    "DEVANAGARI LETTER SA", "TAMIL LETTER SA", "TELUGU LETTER SA", "KANNADA LETTER SA", "MALAYALAM LETTER SA",
)
HA_SET = _chars(
    "DEVANAGARI LETTER HA", "TAMIL LETTER HA", "TELUGU LETTER HA", "KANNADA LETTER HA", "MALAYALAM LETTER HA",
)
L_SET = _chars(
    "DEVANAGARI LETTER LA", "DEVANAGARI LETTER LLA",
    "TAMIL LETTER LA", "TAMIL LETTER LLA",
    "TELUGU LETTER LA", "TELUGU LETTER LLA",
    "KANNADA LETTER LA", "KANNADA LETTER LLA",
    "MALAYALAM LETTER LA", "MALAYALAM LETTER LLA",
)
R_SET = _chars(
    "DEVANAGARI LETTER RA", "DEVANAGARI LETTER RRA",
    "TAMIL LETTER RA", "TAMIL LETTER RRA",
    "TELUGU LETTER RA", "TELUGU LETTER RRA",
    "KANNADA LETTER RA", "KANNADA LETTER RRA",
    "MALAYALAM LETTER RA", "MALAYALAM LETTER RRA",
)
Y_SET = _chars(
    "DEVANAGARI LETTER YA", "TAMIL LETTER YA", "TELUGU LETTER YA", "KANNADA LETTER YA", "MALAYALAM LETTER YA",
)

VIRAMA = set("்्్್്")
COMBINING_MARK_RE = re.compile(r"\p{Mark}+")

# english_mfa's real IPA phone inventory. Entries marked VERIFIED came
# directly from a real `mfa align` run against real audio -- not assumed.
# Everything else is extrapolated from standard English IPA for phones that
# specific test sentence didn't happen to use (no th/v/w/etc. in it). If a
# later run flags an unrecognized phone, it belongs in this table, not in
# roman_map below (which is ARPABET, not what english_mfa speaks).
IPA_MAP = {
    # --- VERIFIED against real MFA output ---
    "a": "AA_WIDE",
    "aw": "AW_VOWEL",
    "c": "K_G",            # voiceless palatal stop -- allophone of k/t before front vowels
    "d": "L_D_T",
    "d̪": "L_D_T",          # dental d -- see module docstring note; visually same as d/t externally
    "eː": "AE_SHORT",
    "h": "H_BREATH",
    "i": "EE_NARROW",
    "iː": "EE_NARROW",     # long ee (FLEECE) -- was missing entirely; confirmed
                            # via real data, "meeting"/"sync" both use this and
                            # were silently falling through to UH_MISC before.
    "j": "UH_MISC",         # y-glide
    "k": "K_G",
    "l": "L_D_T",
    "n": "N_CONSONANT",
    "p": "M_B_P",
    "s": "S_Z",
    "tʃ": "SH_CH",
    "z": "S_Z",
    "ŋ": "N_CONSONANT",
    "ɔ": "O_HALF_OPEN",
    "ɖ": "L_D_T",           # retroflex d -- visually same as d/t externally
    "ə": "UH_MISC",
    "əw": "OO_ROUND",       # GOAT vowel realized as schwa+w
    "ɛ": "EE_NARROW",
    "ɪ": "I_NEAR_EE",
    "ɹ": "ERR_MODIFIER",    # the actual IPA symbol english_mfa uses for English "r"
    "ʃ": "SH_CH",
    "ʈ": "L_D_T",           # retroflex t -- visually same as d/t externally
    "ʎ": "L_D_T",           # palatal lateral -- allophone of l

    # --- not yet seen in a real run, extrapolated from standard English IPA ---
    "b": "M_B_P", "t": "L_D_T", "g": "K_G",
    "f": "F_V", "v": "F_V", "w": "W_SOUND",
    "θ": "TH", "ð": "TH",
    "ʒ": "SH_CH", "dʒ": "SH_CH",
    "m": "M_B_P", "r": "ERR_MODIFIER",
    "u": "OO_ROUND", "uː": "OO_ROUND", "ʊ": "OO_ROUND",
    "ʌ": "UH_MISC", "æ": "AE_SHORT",
    "ɑ": "AA_WIDE", "ɑː": "AA_WIDE", "ɒ": "O_HALF_OPEN",
    "ɜ": "UR_VOWEL", "ɜː": "UR_VOWEL", "ɚ": "UR_VOWEL",
    "aɪ": "AW_VOWEL", "aj": "AW_VOWEL", "ɔɪ": "AW_VOWEL", "ɔj": "AW_VOWEL",  # aj/ɔj: alternate
                            # diphthong-offglide notation (j instead of ɪ) --
                            # confirmed via real data, "five" uses this exact
                            # form and was silently falling through to UH_MISC.
                            # ɔj not yet observed directly but follows the same
                            # pattern as aj/əw, which both are confirmed real.
    "oʊ": "OO_ROUND", "oː": "OO_ROUND",
    "ɪə": "I_NEAR_EE", "eə": "EE_NARROW", "ʊə": "OO_ROUND",
}

_VOWEL_VISEMES = {
    "AA_WIDE", "EE_NARROW", "OO_ROUND", "UH_MISC",
    "I_NEAR_EE", "O_HALF_OPEN", "AW_VOWEL", "UR_VOWEL", "AE_SHORT",
}


def _lookup_ipa(phone: str) -> str | None:
    """Look up a phone in IPA_MAP, retrying with modifier letters (Unicode
    category Lm -- palatalization ʲ, aspiration ʰ, labialization ʷ, etc.)
    stripped if the phone isn't found as typed. Handles secondary-
    articulation variants MFA emits that aren't literally in the table
    (e.g. "fʲ") without needing a separate entry for every marked variant
    of every phone."""
    if phone in IPA_MAP:
        return IPA_MAP[phone]
    stripped = "".join(c for c in phone if unicodedata.category(c) != "Lm")
    if stripped and stripped != phone:
        return IPA_MAP.get(stripped)
    return None



def map_units_to_frames(units: list[AlignedUnit], lang: str) -> list[VisemeFrame]:
    frames: list[VisemeFrame] = []
    for unit in units:
        viseme = unit_to_viseme(unit.label, lang)
        idx = VISEME_TO_INDEX[viseme]
        sx, sy = DEFAULT_SCALE[viseme]
        frames.append(
            VisemeFrame(
                time=round(unit.start, 4),
                end=round(unit.end, 4),
                unit=unit.label,
                viseme=viseme,
                spriteIndex=idx,
                jawOpen=DEFAULT_JAW[viseme],
                mouthScaleX=sx,
                mouthScaleY=sy,
                confidence=1.0,
            )
        )
    return frames


def unit_to_viseme(label: str, lang: str) -> str:
    s = label.strip()
    if not s:
        return "REST_CLOSED"

    # english_mfa's acoustic model outputs IPA, not ARPABET -- confirmed
    # against a real MFA run (2026-07, en, "Hello, how are you today? This
    # is a production lip sync check."), which is where the phones marked
    # VERIFIED below came from. Checked before any case-folding: IPA symbols
    # aren't ASCII letters, so .upper() doesn't mean anything useful for
    # them (and str.upper() silently no-ops on most of them anyway, which
    # is exactly how this got missed the first time -- it didn't error, it
    # just never matched, and fell through to a generic fallback).
    if s in IPA_MAP:
        return IPA_MAP[s]

    # MFA sometimes emits a combined phone label joined by "+" for
    # coarticulated/palatalized sequences (confirmed with real data: "meeting"
    # produced one interval labeled "mʲ+iː+tʲ" -- palatalized m + long ee +
    # palatalized t -- as a single 180ms unit instead of three). Split and
    # look up each component (stripping modifier letters like ʲ/ʰ/ʷ, Unicode
    # category Lm, if the exact marked form isn't in IPA_MAP); a vowel among
    # the components wins since it's visually dominant, otherwise use the
    # first consonant that resolves. This was previously falling through
    # silently to the generic UH_MISC fallback for the whole combined span.
    if "+" in s:
        sub_visemes = [v for v in (_lookup_ipa(p.strip()) for p in s.split("+")) if v]
        if sub_visemes:
            for v in sub_visemes:
                if v in _VOWEL_VISEMES:
                    return v
            return sub_visemes[0]

    # A single phone with a secondary-articulation marker not literally in
    # IPA_MAP (e.g. a palatalized consonant not seen in testing yet) --
    # strip modifier letters and retry before falling through further.
    stripped_result = _lookup_ipa(s)
    if stripped_result:
        return stripped_result

    # MFA/IndicMFA labels can also be graphemes, grapheme clusters,
    # romanized labels, or ARPABET phones like AH0, IY1, CH, TH -- kept as a
    # fallback for other acoustic models (e.g. english_us_arpa, which IS
    # ARPABET) or manually typed romanized test input.
    upper_raw = s.upper()
    upper = re.sub(r"\d", "", upper_raw)  # remove English stress marks: AH0 -> AH
    upper = upper.strip(".:-_ ")

    roman_map = {
        # SIL/SP are unreachable in practice -- textgrid_parser._filter_units()
        # already drops them before they get here; real silence gap-filling
        # happens entirely in smoothing.py's own gap-detection instead.
        # SPN is different and NOT filtered upstream -- confirmed with a real
        # MFA run (bare numeral tokens "5"/"15" produced a 770ms spn block
        # that reached this mapping and originally became dead silence-mouth
        # during audible speech; see the SPN case below for the fix).
        "SIL": "REST_CLOSED", "SP": "REST_CLOSED",
        "SPN": "UH_MISC",  # MFA's "speech, no pronunciation known" marker --
                            # something IS being said here, just not
                            # recognized (e.g. bare numerals, OOV words).
                            # REST_CLOSED would look like silence during
                            # audible speech; a generic open mouth is closer
                            # to correct than a closed one.
        "PAU": "REST_CLOSED", "": "REST_CLOSED",

        # Indian romanized/common labels
        "A": "AA_WIDE", "AA": "AA_WIDE",
        "I": "EE_NARROW", "II": "EE_NARROW", "E": "EE_NARROW", "EE": "EE_NARROW",
        "U": "OO_ROUND", "UU": "OO_ROUND", "OO": "OO_ROUND", "O": "OO_ROUND",
        "AI": "AW_VOWEL", "AU": "OO_ROUND",

        # English ARPABET vowels
        "AH": "AA_WIDE", "AY": "AW_VOWEL",
        "EH": "EE_NARROW", "EY": "AE_SHORT",
        "IH": "I_NEAR_EE", "IY": "EE_NARROW",
        "AO": "O_HALF_OPEN", "OW": "OO_ROUND", "OY": "O_HALF_OPEN",
        "UH": "UH_MISC", "UW": "OO_ROUND",
        "AE": "AE_SHORT", "AW": "AW_VOWEL",
        "ER": "UR_VOWEL", "AX": "UH_MISC",

        # Bilabial/lip closure
        "M": "M_B_P", "B": "M_B_P", "P": "M_B_P",

        # Labiodental (F/V) vs labio-velar glide (W) -- own sprite now.
        "V": "F_V", "F": "F_V", "W": "W_SOUND",

        # Dental/alveolar stops vs nasal -- own sprite now (old scheme
        # lumped T/D/N together; N_CONSONANT is a separate viseme here).
        "T": "L_D_T", "D": "L_D_T", "TH": "TH", "DH": "TH",
        "N": "N_CONSONANT", "NG": "N_CONSONANT",
        "TT": "L_D_T", "DD": "L_D_T", "NN": "N_CONSONANT",

        # Back consonants
        "K": "K_G", "G": "K_G",

        # Affricates/sh vs plain s/z -- split into two sprites now.
        "SH": "SH_CH", "ZH": "SH_CH", "CH": "SH_CH", "J": "SH_CH", "JH": "SH_CH",
        "S": "S_Z", "Z": "S_Z",

        "L": "L_D_T", "R": "ERR_MODIFIER",
        "Y": "UH_MISC", "HH": "H_BREATH",
    }
    if upper in roman_map:
        return roman_map[upper]

    # Dependent vowel sign dominates visual vowel shape.
    chars = list(s)
    if any(c in VOWEL_SIGNS_A for c in chars):
        return "AA_WIDE"
    if any(c in VOWEL_SIGNS_E for c in chars):
        # ஐ/ai gets a slightly wider mouth when present.
        if any(c in "ைैైೈൈ" for c in chars):
            return "AW_VOWEL"
        return "EE_NARROW"
    if any(c in VOWEL_SIGNS_U for c in chars):
        return "OO_ROUND"
    if any(c in VOWEL_SIGNS_O for c in chars):
        return "OO_ROUND"

    # Independent vowels.
    if any(c in AI_VOWELS for c in chars):
        return "AW_VOWEL"
    if any(c in A_VOWELS for c in chars):
        return "AA_WIDE"
    if any(c in E_VOWELS for c in chars):
        return "EE_NARROW"
    if any(c in U_VOWELS for c in chars):
        return "OO_ROUND"
    if any(c in O_VOWELS for c in chars):
        return "OO_ROUND"

    # Consonants.
    if any(c in MBP for c in chars):
        return "M_B_P"
    if any(c in FVW for c in chars):
        return "F_V"
    if any(c in NASAL_ALL for c in chars):
        return "N_CONSONANT"
    if any(c in DENTAL_STOP for c in chars):
        return "L_D_T"
    if any(c in KG for c in chars):
        return "K_G"
    if any(c in HA_SET for c in chars):
        return "H_BREATH"
    if any(c in S_SET for c in chars):
        return "S_Z"
    if any(c in SZSHCH for c in chars):
        return "SH_CH"
    if any(c in L_SET for c in chars):
        return "L_D_T"
    if any(c in R_SET for c in chars):
        return "ERR_MODIFIER"
    if any(c in Y_SET for c in chars):
        return "UH_MISC"

    # Fallback: unknown character with a visible sound. UH_MISC is the closest
    # analog to the old scheme's SMALL_OPEN fallback -- a neutral, modestly
    # open mouth. REST_CLOSED would be wrong here: it implies silence, and
    # this branch only runs for a character that IS actually being spoken,
    # just not one any rule above recognized.
    return "UH_MISC"
