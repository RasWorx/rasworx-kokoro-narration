"""Lint a narration script (.md or .txt) for text-to-speech, tuned for Kokoro-82M.

Usage:
    python check_tts_script.py script.md [more.md ...] [--wpm 150] [--quiet]

Standard library only. Kokoro speaks each paragraph (text between blank lines)
as one chunk, so checks are reported per paragraph with its first line number:
paragraphs too short (clipped) or too long (rushed / auto-split), curly
apostrophes, " -- ", ALL CAPS, digits, symbols, abbreviations, emotion tags,
HTML/SSML, emoji, Markdown emphasis, tables, code and URLs.
Exit code 1 when any WARN is reported, 0 when clean (notes do not count).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

MIN_WORDS = 8  # below this a chunk sounds clipped (author: < 10-20 tokens is bad)
SOFT_MAX_WORDS = 60  # ~350 characters, upper end of the comfortable range
MAX_CHARS = 480  # ~510 phonemes: Kokoro splits or rushes beyond this

# Kokoro's own markup: [word](/phonemes/), [word](+2), [123](#a#). Kept as its word before checks.
KOKORO_MARKUP = re.compile(r"\[([^\]]+)\]\((?:/[^/)]+/|[-+]?\d+(?:\.\d+)?|#[^)]*#)\)")
MD_LINK = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
MD_EMPHASIS = re.compile(r"(?<!\w)(\*\*|__|\*|_)(?=\S)(.+?)(?<=\S)\1(?!\w)")
URL = re.compile(r"https?://[^\s)]+|www\.[^\s)]+")
ACRONYMS = {
    "AI", "API", "ATM", "BBC", "BMW", "CEO", "CFO", "CPU", "CTO", "DNA", "EU", "FAQ", "FBI",
    "GPS", "GPU", "HR", "ID", "IQ", "IT", "MP3", "NASA", "NATO", "NBA", "NFL", "OK", "PC",
    "PDF", "RSVP", "SMS", "SUV", "TV", "UK", "UN", "US", "USA", "USB", "VIP", "WHO",
}
ABBREVIATIONS = re.compile(
    r"(?<!\w)(e\.g\.|i\.e\.|etc\.|vs\.?|approx\.|Dr\.|Mr\.|Mrs\.|Ms\.|St\.|Prof\.|No\.|Fig\.|cf\.|a\.m\.|p\.m\.|(?:Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sept?|Oct|Nov|Dec)\.)",
    re.I,
)
SYMBOLS = re.compile(r"[%&$€£¥@#/+=<>~^\\*_]")
_MOODS = r"whisper\w*|excited|laugh\w*|sigh\w*|sad|angry|happy|calm|softly|shout\w*|pause[^\]\)]*"
EMOTION_TAG = re.compile(rf"\[(?:{_MOODS})\]|\((?:{_MOODS})\)", re.I)
HTML_TAG = re.compile(r"</?[A-Za-z][^>]*>")
EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿]")


def blocks(text: str):
    """Yield (line, kind, text): kind is 'heading', 'text' or 'code'. Skips YAML front matter."""
    lines = text.splitlines()
    i = 0
    if lines and lines[0].strip() == "---":
        for j in range(1, len(lines)):
            if lines[j].strip() == "---":
                i = j + 1
                break
    buf: list[str] = []
    start = 0
    in_code = False
    is_list = False
    for n in range(i, len(lines)):
        s = lines[n].strip()
        if s.startswith("```"):
            if buf:
                yield start, "text", " ".join(buf)
                buf = []
            if not in_code:
                yield n + 1, "code", ""
            in_code = not in_code
        elif in_code:
            continue
        elif not s:
            if buf:
                yield start, "text", " ".join(buf)
                buf = []
        elif re.match(r"^#{1,6}\s", s):
            if buf:
                yield start, "text", " ".join(buf)
                buf = []
            yield n + 1, "heading", re.sub(r"^#{1,6}\s*|\s*#*$", "", s)
        else:
            if not buf:
                start = n + 1
                is_list = bool(re.match(r"^(?:[-*+]|\d+[.)])\s", s))
            if is_list and not buf:
                buf.append("- ")  # keep one marker so the list note still fires
            buf.append(re.sub(r"^(?:[-*+>]|\d+[.)])\s+", "", s))  # drop list/quote markers per line
    if buf:
        yield start, "text", " ".join(buf)


def listed(items) -> str:
    return ", ".join(dict.fromkeys(items))


def check(path: Path, wpm: int, quiet: bool) -> int:
    raw = path.read_text(encoding="utf-8-sig")
    warnings: list[tuple[int, str]] = []
    notes: list[tuple[int, str]] = []
    sizes: list[int] = []

    for line, kind, para in blocks(raw):
        warn = lambda msg: warnings.append((line, msg))  # noqa: E731
        note = lambda msg: notes.append((line, msg))  # noqa: E731
        if kind == "code":
            warn("code block: removed before speaking; keep code out of narration")
            continue
        if para.count("|") >= 2:
            warn("table: tables read badly aloud; rewrite as sentences")
            continue
        if para.startswith("- "):
            note("list: each item is spoken as its own sentence; consider rewriting as prose")
            para = para[2:]

        # What generate.py would actually speak: keep Kokoro markup's word and link text, drop list markers.
        spoken = KOKORO_MARKUP.sub(r"\1", para)
        spoken = MD_LINK.sub(r"\1", spoken)
        for url in URL.findall(spoken):
            warn(f"URL {url}: say where to find it in words, or drop it")
        spoken = URL.sub("", spoken)
        for m in MD_EMPHASIS.finditer(spoken):
            note(f"emphasis {m.group(0)} is stripped; put the emphasis in the words or word order")
        plain = MD_EMPHASIS.sub(r"\2", spoken).strip()

        words = re.findall(r"[A-Za-z0-9][A-Za-z0-9'’-]*", plain)
        wc, cc = len(words), len(plain)
        sizes.append(wc)
        label = "heading" if kind == "heading" else "paragraph"
        if wc < MIN_WORDS:
            warn(f"{label} of {wc} words ({plain[:50]!r}): too short, sounds clipped; "
                 "make it a full spoken sentence (8+ words) or merge it into the next paragraph")
        elif cc > MAX_CHARS:
            warn(f"paragraph of {wc} words / {cc} chars: over ~480 chars gets rushed or auto-split; "
                 "break it into two paragraphs at a natural turn")
        elif wc > SOFT_MAX_WORDS:
            note(f"paragraph of {wc} words: fine, but 20-60 words is the sweet spot")

        if "’" in plain or "‘" in plain:
            warn("curly apostrophe/quote: use straight ' (misaki misreads e.g. man’s. as 'man-ESS')")
        if "--" in plain:
            warn("'--' is silently dropped (no pause); use — or ' - '")
        if re.search(r"\.\s\.\s\.", plain):
            warn("'. . .' is read as separate marks; use ... or …")
        if re.search(r"[!?]{2,}", plain):
            note("stacked !/? adds nothing in Kokoro; one mark is enough")
        caps = [w for w in re.findall(r"\b[A-Z][A-Z0-9]+\b", plain) if w not in ACRONYMS]
        if caps:
            warn(f"ALL CAPS {listed(caps)}: gives no extra emphasis and may be spelled out; "
                 "use normal case (keep caps for real acronyms)")
        digits = [d.rstrip(".,:/-") for d in re.findall(r"(?<![A-Za-z])\d[\d,.:/-]*", plain)]
        if digits:
            warn(f"digits {listed(digits)}: spell out how each should be said "
                 "(e.g. 'twenty twenty-six', 'three point five', 'forty-seven dollars')")
        abbrs = ABBREVIATIONS.findall(plain)
        if abbrs:
            warn(f"abbreviations {listed(abbrs)}: write them out ('for example', 'Doctor', 'et cetera')")
        tags = EMOTION_TAG.findall(para)
        if tags:
            warn(f"tags {listed(tags)}: Kokoro has no emotion or pause tags; they are read aloud or ignored")
        if HTML_TAG.search(para):
            warn("HTML/SSML tag: stripped or ignored by Kokoro")
        if EMOJI.search(plain):
            warn("emoji: remove it; it is dropped or read oddly")
        syms = SYMBOLS.findall(EMOTION_TAG.sub("", plain))
        if syms:
            warn(f"symbols {' '.join(dict.fromkeys(syms))}: write them as words ('percent', 'and', 'dollars')")
        if "(" in plain:
            note("parentheses give no clear pause; consider commas or a separate sentence")

    total = sum(sizes)
    median = sorted(sizes)[len(sizes) // 2] if sizes else 0
    print(f"{path}: {total} words, ~{total / wpm:.1f} min at {wpm} wpm, "
          f"{len(sizes)} spoken paragraphs, median {median} words each")
    for ln, msg in sorted(warnings, key=lambda x: x[0]):
        print(f"  WARN line {ln}: {msg}")
    if not quiet:
        for ln, msg in sorted(notes, key=lambda x: x[0]):
            print(f"  note line {ln}: {msg}")
    print(f"{len(warnings)} warnings, {len(notes)} notes")
    return 1 if warnings else 0


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+", type=Path)
    ap.add_argument("--wpm", type=int, default=150, help="words per minute for the length estimate (default 150)")
    ap.add_argument("--quiet", action="store_true", help="show warnings only, not notes")
    args = ap.parse_args()
    rc = 0
    for f in args.files:
        rc |= check(f, args.wpm, args.quiet)
    return rc


if __name__ == "__main__":
    sys.exit(main())
