"""High-recall surface signals, never proof of intentional obfuscation.

Offsets are zero-based Python Unicode code-point offsets into unchanged raw_text.
No dictionary, language, keyword or signal is used to discard collected text.
"""
import re
import unicodedata as ud


ANNOTATION_TYPES = {
    "space_insertion": "A word is deliberately split using spaces.",
    "space_deletion_word_merging": "Separate words are deliberately joined.",
    "punctuation_insertion": "Extra punctuation/symbols appear within a word.",
    "symbol_masking": "A symbol hides one or several characters.",
    "character_substitution": "One character is replaced by another.",
    "character_deletion": "Characters are omitted.",
    "character_insertion": "Extra characters are added.",
    "character_transposition": "Character order is changed.",
    "character_repetition": "Characters are repeated to distort a word.",
    "phonetic_spelling_variant": "A pronunciation/spelling variant conceals a word.",
    "grapheme_diacritic_manipulation": "Bengali marks or conjuncts are altered.",
    "number_rebus_leetspeak": "Numbers stand for letters, syllables or words.",
    "mixed_script": "Different scripts are mixed to conceal a word.",
    "homoglyph": "Similar-looking characters from different scripts are used.",
    "romanized_bangla": "Bangla is represented using Latin letters to conceal it.",
    "zero_width_format_manipulation": "Invisible formatting characters disrupt text.",
    "unusual_whitespace": "Special whitespace changes word representation.",
    "emoji_substitution": "An emoji stands for a character, syllable or word.",
    "abbreviation": "A shortened form or initials conceal an expression.",
    "semantic_euphemism_codeword": "Meaning is concealed by a substitute expression.",
    "image_visual_text": "Obfuscation is rendered within an image.",
    "other_unknown": "An unlisted/new type; explain it in annotation_notes.",
}


def is_letter_or_mark(c):
    return ud.category(c)[0] in "LM"


def scripts_present(text):
    found = set()
    for c in text:
        if not is_letter_or_mark(c):
            continue
        name = ud.name(c, "")
        script = next((s for s in ("BENGALI", "LATIN", "CYRILLIC", "GREEK", "ARABIC", "DEVANAGARI")
                       if s in name), "OTHER")
        found.add(script.lower())
    return sorted(found)


def analyze(text):
    signals = []

    def add(kind, start, end, reason):
        signals.append({"signal": kind, "start": start, "end": end,
                        "surface": text[start:end], "reason": reason})

    for i, c in enumerate(text):
        if ud.category(c) == "Cf":
            add("format_character_present", i, i + 1,
                ud.name(c, "UNNAMED") + "; may be legitimate Bengali shaping")
        elif c.isspace() and c not in " \n\r\t":
            add("unusual_whitespace_present", i, i + 1, ud.name(c, "UNNAMED"))
        cp = ord(c)
        if 0x1F000 <= cp <= 0x1FAFF or 0x2600 <= cp <= 0x27BF:
            add("emoji_or_pictograph_present", i, i + 1,
                "Presence alone does not establish substitution or abuse")

    # Include spacing around separators, including slash-separated Bengali words.
    for m in re.finditer(r"[ \t]*[*/\\|_@#$!~.·•…-]+[ \t]*", text):
        if (m.start() > 0 and m.end() < len(text) and
                is_letter_or_mark(text[m.start() - 1]) and is_letter_or_mark(text[m.end()])):
            add("internal_symbol_candidate", m.start(), m.end(),
                "Could be punctuation, an insertion or a masked character")

    for m in re.finditer(r"\S+", text):
        token = m.group()
        scripts = scripts_present(token)
        if len([s for s in scripts if s != "other"]) > 1:
            add("mixed_script_token", m.start(), m.end(),
                "Script mixing may also be ordinary code-switching")
        if "latin" in scripts:
            add("latin_text_present", m.start(), m.end(),
                "Could be English, romanized Bangla or something else")
        if any(c.isdigit() for c in token) and any(is_letter_or_mark(c) for c in token):
            add("number_letter_mixture", m.start(), m.end(),
                "Could be a rebus or an ordinary numeric expression")

    for m in re.finditer(r"([^\W\d_])\1{2,}", text):
        add("repeated_character_candidate", m.start(), m.end(),
            "May be emphasis or character repetition")

    # Weak evidence only: short normal words also match this pattern.
    fragments = []
    def flush_fragments():
        if len(fragments) >= 2:
            add("short_spaced_fragments_candidate", fragments[0].start(), fragments[-1].end(),
                "Low confidence; ordinary separate words also match")
        fragments.clear()
    for m in re.finditer(r"\S+", text):
        token = m.group()
        short = all(is_letter_or_mark(c) for c in token) and 1 <= sum(ud.category(c).startswith('L') for c in token) <= 2
        if not short:
            flush_fragments()
            continue
        if fragments and not re.fullmatch(r'[ \t]+', text[fragments[-1].end():m.start()]):
            flush_fragments()
        fragments.append(m)
    flush_fragments()

    for i in range(1, len(text)):
        if text[i] == text[i - 1] and ud.category(text[i]).startswith("M"):
            add("repeated_mark_candidate", i - 1, i + 1,
                "Repeated combining mark; inspect the grapheme manually")

    return {
        "scripts_present": scripts_present(text),
        "nfc_would_change_text": ud.normalize("NFC", text) != text,
        "signals": signals,
        "has_surface_signals": bool(signals),
        "human_label": "unreviewed",
        "normalized_text": "",
        "confirmed_types": [],
        "annotation_notes": "",
    }
