"""Render the same short text in several Kokoro voices so they can be compared by ear.

Run from the project root with the project venv:
    .venv\\Scripts\\python .agents\\skills\\kokoro-help\\scripts\\preview_voices.py
    .venv\\Scripts\\python .agents\\skills\\kokoro-help\\scripts\\preview_voices.py --voices af_heart bm_george "af_heart,af_bella"
    .venv\\Scripts\\python .agents\\skills\\kokoro-help\\scripts\\preview_voices.py --text-file input\\episode-01.md --speeds 0.9 1.0

Writes one MP3 per voice/speed to output\\previews\\ (never touches other files in output\\).
Voices may be single IDs, comma blends ("af_heart,af_bella"), or paths to .pt voicepacks.
American (a*) and British (b*) voices can be mixed in one run; one pipeline is built per accent.
"""

import argparse
import os
import re
import sys
from pathlib import Path

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

DEFAULT_TEXT = (
    "Welcome back. In today's episode we look at how a small idea, repeated every day, "
    "can quietly change everything. Let's begin with a simple question: what would you do "
    "with one extra hour?"
)
DEFAULT_VOICES = ["af_kore", "af_heart", "af_bella", "af_nicole", "am_michael", "am_fenrir", "bf_emma", "bm_george", "bm_fable"]
SAMPLE_RATE = 24000


def project_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "generate.py").exists():
            return parent
    return Path.cwd()


def lang_of(voice: str) -> str:
    """Accent letter for a voice spec: first letter of the (first) voice ID; .pt files default to American."""
    first = voice.split(",")[0]
    if first.endswith(".pt"):
        name = Path(first).stem
        return name[0] if name[:1] in ("a", "b") else "a"
    return first[0]


def safe_name(voice: str, speed: float) -> str:
    base = ",".join(Path(v).stem for v in voice.split(","))
    base = re.sub(r"[^A-Za-z0-9_,.-]+", "_", base).replace(",", "+")
    return f"{base}@{speed:g}.mp3"


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare Kokoro voices on the same text")
    parser.add_argument("--voices", nargs="+", default=DEFAULT_VOICES, help="voice IDs, comma blends, or .pt paths")
    parser.add_argument("--text", help="text to speak (default: a short narration sample)")
    parser.add_argument("--text-file", type=Path, help="take the first ~600 characters of this .txt/.md file")
    parser.add_argument("--speeds", nargs="+", type=float, default=[1.0], help="one or more speeds, e.g. 0.9 1.0")
    parser.add_argument("--cpu", action="store_true", help="run on CPU instead of the GPU")
    args = parser.parse_args()

    root = project_root()
    sys.dont_write_bytecode = True  # importing generate.py must not leave __pycache__ in the project
    sys.path.insert(0, str(root))
    text = args.text or DEFAULT_TEXT
    if args.text_file:
        from generate import load_text  # reuse the project's Markdown cleaning

        text = " ".join(load_text(args.text_file.resolve()).split())[:600]
        text = text[: text.rfind(".") + 1] or text

    import numpy as np
    import soundfile as sf
    import torch
    from kokoro import KModel, KPipeline

    device = "cpu" if args.cpu or not torch.cuda.is_available() else "cuda"
    model = KModel(repo_id="hexgrad/Kokoro-82M").to(device).eval()
    pipelines: dict[str, KPipeline] = {}
    out_dir = root / "output" / "previews"
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Device {device}. Text: {text[:80]}{'...' if len(text) > 80 else ''}")
    for voice in args.voices:
        lang = lang_of(voice)
        if lang not in pipelines:
            pipelines[lang] = KPipeline(lang_code=lang, repo_id="hexgrad/Kokoro-82M", model=model)
        for speed in args.speeds:
            chunks = [r.audio.cpu().numpy() for r in pipelines[lang](text, voice=voice, speed=speed) if r.audio is not None]
            audio = np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.float32)
            path = out_dir / safe_name(voice, speed)
            sf.write(path, audio, SAMPLE_RATE, format="MP3")
            print(f"  {voice:<28} speed {speed:<4g} {len(audio) / SAMPLE_RATE:5.1f}s -> {path.relative_to(root)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
