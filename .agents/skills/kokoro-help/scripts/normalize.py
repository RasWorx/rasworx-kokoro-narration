r"""Make Kokoro MP3s louder and consistent (Kokoro output is quiet, about -26 dBFS RMS).

Since v1.1.0 generate.py and the window already do this by default, so use this script only on MP3s made
with --no-normalize (or before 1.1.0). Running it on an already normalised file changes almost nothing.

Writes a new file next to each input named <name>-loud.mp3; the original is never changed.

Run from the project root with the project venv:
    .venv\Scripts\python .agents\skills\kokoro-help\scripts\normalize.py output\episode-01.mp3
    .venv\Scripts\python .agents\skills\kokoro-help\scripts\normalize.py output\*.mp3 --target -18

Uses generate.normalize_loudness: RMS normalisation (measured on speech only, not true LUFS but close for
one voice) followed by a soft limiter. Default target -16 dBFS RMS approximates podcast loudness; peaks
never exceed -1 dBFS.
"""

import argparse
import glob
import sys
from pathlib import Path

import numpy as np
import soundfile as sf


def project_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "generate.py").exists():
            return parent
    return Path.cwd()


sys.dont_write_bytecode = True  # importing generate.py must not leave __pycache__ in the project
sys.path.insert(0, str(project_root()))
from generate import LOUDNESS_TARGET, PEAK_CEILING, normalize_loudness  # noqa: E402


def db(x: float) -> float:
    return 20 * np.log10(max(x, 1e-9))


def speech_rms(audio: np.ndarray) -> float:
    speech = audio[np.abs(audio) > 1e-3]  # ignore paragraph silences
    return float(np.sqrt(np.mean(speech**2))) if speech.size else 0.0


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalise MP3/WAV loudness")
    parser.add_argument("files", nargs="+", help="MP3/WAV files (wildcards allowed)")
    parser.add_argument("--target", type=float, default=LOUDNESS_TARGET,
                        help=f"target RMS in dBFS (default {LOUDNESS_TARGET:g})")
    parser.add_argument("--ceiling", type=float, default=PEAK_CEILING,
                        help=f"maximum peak in dBFS (default {PEAK_CEILING:g})")
    args = parser.parse_args()

    paths = [Path(p) for pattern in args.files for p in (glob.glob(pattern) or [pattern])]
    for path in paths:
        if path.stem.endswith("-loud"):
            continue
        audio, rate = sf.read(path, dtype="float32")
        result = normalize_loudness(audio, args.target, args.ceiling)
        out = path.with_name(f"{path.stem}-loud{path.suffix}")
        sf.write(out, result, rate, format=path.suffix.lstrip(".").upper())
        peak_in, peak_out = float(np.max(np.abs(audio))) if audio.size else 0.0, float(np.max(np.abs(result))) if result.size else 0.0
        print(f"{path.name}: RMS {db(speech_rms(audio)):.1f} dBFS, peak {db(peak_in):.1f} dBFS "
              f"-> {out.name} (RMS {db(speech_rms(result)):.1f}, peak {db(peak_out):.1f})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
