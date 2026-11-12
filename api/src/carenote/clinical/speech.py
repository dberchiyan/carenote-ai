"""How nurses speak numbers and corrections. Shared by the rule-based extractor and the review
hints, so both read dictation the same way."""

import re

from carenote.clinical.numbers import ONES, TENS

_WORD_VALUES = {w: i for i, w in enumerate(ONES)} | {w: 10 * i for i, w in enumerate(TENS) if w}
_NUM_WORD = "|".join(sorted([*_WORD_VALUES, "hundred", "thousand"], key=len, reverse=True))
NUMBER_WORDS = re.compile(
    rf"\b(?:{_NUM_WORD})(?:(?:[\s-]+(?:and[\s-]+)?|[\s-]+point[\s-]+)(?:{_NUM_WORD}))*\b",
    re.IGNORECASE,
)


def _parse_int(words: list[str]) -> int:
    current = 0
    total = 0
    for word in words:
        if word == "hundred":
            current = (current or 1) * 100
        elif word == "thousand":
            total += (current or 1) * 1000
            current = 0
        else:
            v = _WORD_VALUES[word]
            if v < 10:
                if (current % 100 >= 20 and current % 10 == 0) or (
                    current >= 100 and current % 100 == 0
                ):
                    current += v
                elif current == 0:
                    current = v
                else:
                    current = current * 10 + v
            elif 1 <= current <= 9:  # colloquial "one fifty" -> 150
                current = current * 100 + v
            else:
                current += v
    return total + current


def words_to_number(phrase: str) -> str:
    words = [w for w in re.split(r"[\s-]+", phrase.lower()) if w and w != "and"]
    if "point" in words:
        i = words.index("point")
        whole = _parse_int(words[:i]) if words[:i] else 0
        return f"{whole}." + "".join(str(_WORD_VALUES[w]) for w in words[i + 1 :])
    return str(_parse_int(words))


def spoken_to_digits(text: str) -> str:
    """Turn "thirty-seven point nine" into "37.9"; other text is unchanged."""
    return NUMBER_WORDS.sub(lambda m: words_to_number(m.group(0)), text)


# A spoken self-correction marker ("sorry, I mean", "correction", "scratch that"). A bare
# "no"/"sorry" only counts when followed by a comma, so "no chest pain" is not a correction.
CORRECTION_MARKER = (
    r"(?:no,?\s*sorry|sorry,?\s*i\s+mean|no\s+wait|correction|i\s+mean|scratch\s+that"
    r"|let\s+me\s+correct\s+that|sorry(?=\s*,)|no(?=\s*,))"
)
SPOKEN_VALUE = r"\d+(?:\.\d+)?(?:\s*(?:/|over)\s*\d+(?:\.\d+)?)?"
