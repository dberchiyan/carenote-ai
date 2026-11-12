"""Numbers to English words, the way a nurse might say them."""

from carenote.clinical.numbers import ONES, TENS

_ONES, _TENS = ONES, TENS


def _below_100(n: int) -> str:
    if n < 20:
        return _ONES[n]
    tens, ones = divmod(n, 10)
    return _TENS[tens] + (f"-{_ONES[ones]}" if ones else "")


def int_to_words(n: int, colloquial: bool = False) -> str:
    """0..9999. colloquial=True says 150 as 'one fifty' (common for vitals)."""
    if n < 0:
        return "minus " + int_to_words(-n, colloquial)
    if n < 100:
        return _below_100(n)
    if n < 1000:
        hundreds, rest = divmod(n, 100)
        if colloquial and rest >= 10:
            return f"{_ONES[hundreds]} {_below_100(rest)}"
        if rest == 0:
            return f"{_ONES[hundreds]} hundred"
        return f"{_ONES[hundreds]} hundred {'and ' if colloquial else ''}{_below_100(rest)}"
    thousands, rest = divmod(n, 1000)
    return f"{_below_100(thousands)} thousand" + (f" {int_to_words(rest)}" if rest else "")


def number_to_words(text: str, colloquial: bool = False) -> str:
    """'37.8' -> 'thirty-seven point eight'; '150' -> 'one hundred fifty' (or 'one fifty')."""
    whole, _, frac = text.partition(".")
    words = int_to_words(int(whole), colloquial)
    if frac:
        words += " point " + " ".join(_ONES[int(d)] for d in frac)
    return words
