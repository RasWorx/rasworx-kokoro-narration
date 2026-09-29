"""Turn .txt / .md files in input/ into .mp3 narration in output/ using Kokoro-82M.

Usage (from C:\\Github\\kokoro):
    .venv\\Scripts\\python generate.py                  # every new/changed file in input/
    .venv\\Scripts\\python generate.py input\\story.md   # one specific file
    .venv\\Scripts\\python generate.py --voice bm_george --speed 0.95 --force
    .venv\\Scripts\\python generate.py --voice voices\\my_blend.pt --accent b   # saved voice blend
"""

import argparse
import re
import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parent
INPUT_DIR = ROOT / "input"
OUTPUT_DIR = ROOT / "output"
SAMPLE_RATE = 24000
EXTENSIONS = {".txt", ".md", ".markdown"}
DEFAULT_VOICE = "af_kore"
LANG_CODES = "abefhijpz"  # Kokoro language codes; j and z need extra packages (misaki[ja], misaki[zh])


def sentence(line: str) -> str:
    """Make sure a heading or list item ends with punctuation so it is spoken as a sentence."""
    spoken = re.sub(r"\[([^\]]+)\]\([^)]*\)$", r"\1", line)  # judge by the word, not trailing pronunciation markup
    return line if spoken[-1] in ".!?:;,\"')" else line + "."


def markdown_to_speech(text: str) -> str:
    """Strip Markdown syntax so only speakable prose remains."""
    text = re.sub(r"^---\n.*?\n---\n", "", text, flags=re.S)  # YAML front matter
    text = re.sub(r"```.*?```", "", text, flags=re.S)  # fenced code blocks
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)  # HTML comments
    text = re.sub(r"<[^>]+>", "", text)  # HTML tags
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)  # images
    # links -> link text, but keep Kokoro pronunciation markup: [word](/phonemes/), [word](-1), [123](#a#)
    text = re.sub(r"\[([^\]]+)\]\((?!/[^/)]+/\)|#[^)]*#\)|[-+]?\d+(?:\.\d+)?\))[^)]*\)", r"\1", text)
    text = re.sub(r"\[\[([^\]|]+\|)?([^\]]+)\]\]", r"\2", text)  # [[wikilinks]]
    text = re.sub(r"`([^`]*)`", r"\1", text)  # inline code
    # Line-anchored patterns use [ \t] (not \s) so they never swallow blank lines.
    text = re.sub(r"^[ \t]*([-*_][ \t]*){3,}$", "", text, flags=re.M)  # horizontal rules
    text = re.sub(  # headings become their own short sentence
        r"^[ \t]{0,3}#{1,6}[ \t]*(.+?)[ \t]*#*[ \t]*$",
        lambda m: "\n" + sentence(m.group(1)) + "\n",
        text,
        flags=re.M,
    )
    text = re.sub(r"^[ \t]*>[ \t]?", "", text, flags=re.M)  # blockquotes
    text = re.sub(  # list items: drop the marker, end each item as a sentence
        r"^[ \t]*(?:[-*+]|\d+[.)])[ \t]+(.+?)[ \t]*$",
        lambda m: sentence(m.group(1)),
        text,
        flags=re.M,
    )
    text = re.sub(r"^[ \t]*\|?[ \t:|-]+\|[ \t:|-]*$", "", text, flags=re.M)  # table separators
    text = text.replace("|", ", ")
    text = re.sub(r"(?<!\w)(\*\*|__|\*|_|~~)(?=\S)(.+?)(?<=\S)\1(?!\w)", r"\2", text)  # bold / italic / strike
    return text


def paragraphs_of(text: str) -> list[str]:
    paras = [" ".join(p.split()) for p in re.split(r"\n\s*\n", text)]
    return [p for p in paras if p]


def load_text(path: Path) -> str:
    text = path.read_text(encoding="utf-8-sig")
    if path.suffix.lower() in {".md", ".markdown"}:
        text = markdown_to_speech(text)
    return text


def pending_files(force: bool) -> list[Path]:
    files = sorted(p for p in INPUT_DIR.iterdir() if p.is_file() and p.suffix.lower() in EXTENSIONS)
    if force:
        return files
    todo = []
    for p in files:
        out = OUTPUT_DIR / f"{p.stem}.mp3"
        if not out.exists() or out.stat().st_mtime < p.stat().st_mtime:
            todo.append(p)
    return todo


def synthesize(pipeline, text: str, voice: str, speed: float, pause: float,
               progress=None, stop=None) -> np.ndarray | None:
    """progress(i, total) replaces the console output; stop() returning True cancels (returns None)."""
    silence = np.zeros(int(SAMPLE_RATE * pause), dtype=np.float32)
    paras = paragraphs_of(text)
    chunks = []
    for i, para in enumerate(paras, 1):
        if stop and stop():
            return None
        if progress:
            progress(i, len(paras))
        else:
            print(f"  paragraph {i}/{len(paras)}", end="\r", flush=True)
        for result in pipeline(para, voice=voice, speed=speed, split_pattern=None):
            if result.audio is not None:
                chunks.append(result.audio.cpu().numpy().astype(np.float32))
        chunks.append(silence)
    if not progress:
        print()
    return np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.float32)


def write_mp3(audio: np.ndarray, path: Path) -> Path:
    try:
        sf.write(path, audio, SAMPLE_RATE, format="MP3")
        return path
    except Exception as exc:  # libsndfile without MP3 support
        wav = path.with_suffix(".wav")
        print(f"  MP3 export failed ({exc}); writing WAV instead")
        sf.write(wav, audio, SAMPLE_RATE)
        return wav


def resolve_voice(voice: str) -> str:
    """Turn any .pt part of a voice spec into an absolute path (tried as given, then relative to this folder)."""
    parts = []
    for part in voice.split(","):
        if part.lower().endswith(".pt"):
            path = Path(part)
            if not path.exists() and (ROOT / part).exists():
                path = ROOT / part
            if not path.exists():
                raise SystemExit(f"Voice file not found: {part}")
            part = str(path.resolve())
        parts.append(part)
    return ",".join(parts)


def accent_of(voice: str) -> str:
    """Language code from the first letter of the first voice ID (or .pt file name); American if unknown."""
    first = voice.split(",")[0]
    name = Path(first).stem if first.lower().endswith(".pt") else first
    return name[0].lower() if name[:1].lower() in LANG_CODES else "a"


def main() -> int:
    parser = argparse.ArgumentParser(description="Kokoro text/markdown -> mp3")
    parser.add_argument("files", nargs="*", type=Path, help="specific files (default: all pending in input/)")
    parser.add_argument("--voice", default=DEFAULT_VOICE,
                        help=f"voice id, blend like af_heart,af_bella, or a .pt voice file (default {DEFAULT_VOICE})")
    parser.add_argument("--accent", choices=list(LANG_CODES),
                        help="language/accent: a US English, b UK English, e Spanish, f French, h Hindi, "
                             "i Italian, p Brazilian Portuguese, j Japanese, z Mandarin (default: from the voice name)")
    parser.add_argument("--speed", type=float, default=1.0, help="speaking speed, e.g. 0.9 slower, 1.1 faster")
    parser.add_argument("--pause", type=float, default=0.4, help="seconds of silence between paragraphs")
    parser.add_argument("--force", action="store_true", help="regenerate even if the mp3 is up to date")
    parser.add_argument("--cpu", action="store_true", help="run on CPU instead of the GPU")
    args = parser.parse_args()

    voice = resolve_voice(args.voice)
    INPUT_DIR.mkdir(exist_ok=True)
    OUTPUT_DIR.mkdir(exist_ok=True)
    files = [f.resolve() for f in args.files] if args.files else pending_files(args.force)
    if not files:
        print(f"Nothing to do. Put .txt or .md files in {INPUT_DIR}")
        return 0

    import torch
    from kokoro import KPipeline

    device = "cpu" if args.cpu or not torch.cuda.is_available() else "cuda"
    lang_code = args.accent or accent_of(args.voice)
    print(f"Loading Kokoro on {device} (voice {args.voice}, accent {lang_code}, speed {args.speed})")
    pipeline = KPipeline(lang_code=lang_code, repo_id="hexgrad/Kokoro-82M", device=device)

    for path in files:
        print(f"{path.name}")
        text = load_text(path)
        start = time.perf_counter()
        audio = synthesize(pipeline, text, voice, args.speed, args.pause)
        out = write_mp3(audio, OUTPUT_DIR / f"{path.stem}.mp3")
        minutes = len(audio) / SAMPLE_RATE / 60
        print(f"  -> {out}  ({minutes:.1f} min audio in {time.perf_counter() - start:.0f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
