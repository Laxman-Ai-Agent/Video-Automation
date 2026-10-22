"""Telugu text helpers (standard library only). A grapheme cluster is what a reader sees as one letter: a consonant with its vowel sign,
a conjunct (consonant + virama + consonant, e.g. క్ష, స్త్ర), anusvara/visarga. Splitting or wrapping must never cut inside one."""
import unicodedata

VIRAMA = "్"
JOINERS = ("‍", "‌")        # ZWJ, ZWNJ
TELUGU = range(0x0C00, 0x0C80)


def graphemes(text: str) -> list[str]:
    out: list[str] = []
    for ch in text:
        if out and (unicodedata.category(ch) in ("Mn", "Mc", "Me") or ch in JOINERS
                    or (out[-1][-1] in (VIRAMA, "‍") and unicodedata.category(ch) == "Lo")):
            out[-1] += ch                       # a sign, a joiner, or the consonant after a virama belongs to the previous cluster
        else:
            out.append(ch)
    return out


def glen(text: str) -> int:
    return len(graphemes(text))


def has_telugu(text: str) -> bool:
    return any(ord(c) in TELUGU for c in text)


def wrap(text: str, max_units: int) -> list[str]:
    """Lines of at most max_units grapheme clusters. Breaks at spaces; a single word longer than a line is cut BETWEEN clusters, never inside one."""
    lines: list[str] = []
    cur = ""
    for word in text.split():
        pieces = [word]
        if glen(word) > max_units:
            g = graphemes(word)
            pieces = ["".join(g[i:i + max_units]) for i in range(0, len(g), max_units)]
        for piece in pieces:
            if cur and glen(cur) + 1 + glen(piece) > max_units:
                lines.append(cur)
                cur = piece
            else:
                cur = f"{cur} {piece}" if cur else piece
    if cur:
        lines.append(cur)
    return lines
