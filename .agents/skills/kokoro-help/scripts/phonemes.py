"""Show how Kokoro will read text: the phonemes it generates for each chunk, without making audio.

Use it to find mispronunciations, badly read numbers/abbreviations, and to check custom
pronunciation syntax before rendering a long file.

Run from the project root with the project venv:
    .venv\\Scripts\\python .agents\\skills\\kokoro-help\\scripts\\phonemes.py "It cost $12.50 on 3/4/2026."
    .venv\\Scripts\\python .agents\\skills\\kokoro-help\\scripts\\phonemes.py --file input\\episode-01.md
    .venv\\Scripts\\python .agents\\skills\\kokoro-help\\scripts\\phonemes.py --british "Schedule the tomato harvest."
    .venv\\Scripts\\python .agents\\skills\\kokoro-help\\scripts\\phonemes.py --file input\\episode-01.md --words

A .md file goes through generate.py's Markdown cleaning first, exactly as it would during generation.
--words lists each word with its phonemes and flags words that got no phonemes (they would be silent).
"""

import argparse
import os
import sys
from pathlib import Path

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # Windows consoles default to cp1252, which cannot print IPA


def project_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "generate.py").exists():
            return parent
    return Path.cwd()


def main() -> int:
    parser = argparse.ArgumentParser(description="Print Kokoro phonemes for text or a file")
    parser.add_argument("text", nargs="?", help="text to phonemize")
    parser.add_argument("--file", type=Path, help=".txt or .md file (Markdown is cleaned like generate.py does)")
    parser.add_argument("--british", action="store_true", help="use British English G2P (b* voices)")
    parser.add_argument("--words", action="store_true", help="list every word with its phonemes")
    args = parser.parse_args()
    if not args.text and not args.file:
        parser.error("give some text or --file")

    root = project_root()
    sys.dont_write_bytecode = True  # importing generate.py must not leave __pycache__ in the project
    sys.path.insert(0, str(root))
    from generate import load_text, paragraphs_of

    paras = paragraphs_of(load_text(args.file.resolve())) if args.file else [args.text]

    from kokoro import KPipeline

    pipeline = KPipeline(lang_code="b" if args.british else "a", repo_id="hexgrad/Kokoro-82M", model=False)
    silent = []
    for i, para in enumerate(paras, 1):
        for r in pipeline(para, split_pattern=None):
            print(f"[{i}] {r.graphemes}\n    {r.phonemes}  ({len(r.phonemes)}/510 phonemes)\n")
            for t in r.tokens or []:
                if args.words and t.text.strip():
                    print(f"      {t.text:<20} {t.phonemes or '<none>'}")
                if not t.phonemes and any(c.isalnum() for c in t.text):
                    silent.append(t.text)
    if silent:
        print("Words with no phonemes (will be skipped when spoken):", ", ".join(sorted(set(silent))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
