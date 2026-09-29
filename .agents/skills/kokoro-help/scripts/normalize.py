"""Make Kokoro MP3s louder and consistent (Kokoro output is quiet, about -26 dBFS RMS).

Writes a new file next to each input named <name>-loud.mp3; the original is never changed.

Run from the project root with the project venv:
    .venv\\Scripts\\python .agents\\skills\\kokoro-help\\scripts\\normalize.py output\\episode-01.mp3
    .venv\\Scripts\\python .agents\\skills\\kokoro-help\\scripts\\normalize.py output\\*.mp3 --target -18

RMS normalisation (measured on speech only, not true LUFS but close for one voice) followed by a
soft limiter so the few loud peaks are rounded off smoothly instead of clipping.
Default target -16 dBFS RMS approximates podcast loudness; peaks never exceed -1 dBFS.
"""

import argparse
import glob
import sys
from pathlib import Path

import numpy as np
import soundfile as sf


def db(x: float) -> float:
    return 20 * np.log10(max(x, 1e-9))


def soft_limit(x: np.ndarray, ceiling: float) -> np.ndarray:
    """Leave samples below the knee untouched; squash the rest smoothly towards the ceiling."""
    knee = ceiling * 0.5  # 6 dB below the ceiling
    mag = np.abs(x)
    over = mag > knee
    squashed = knee + (ceiling - knee) * np.tanh((mag[over] - knee) / (ceiling - knee))
    y = x.copy()
    y[over] = np.sign(x[over]) * squashed
    return y


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalise MP3/WAV loudness")
    parser.add_argument("files", nargs="+", help="MP3/WAV files (wildcards allowed)")
    parser.add_argument("--target", type=float, default=-16.0, help="target RMS in dBFS (default -16)")
    parser.add_argument("--ceiling", type=float, default=-1.0, help="maximum peak in dBFS (default -1)")
    args = parser.parse_args()

    paths = [Path(p) for pattern in args.files for p in (glob.glob(pattern) or [pattern])]
    for path in paths:
        if path.stem.endswith("-loud"):
            continue
        audio, rate = sf.read(path, dtype="float32")
        speech = audio[np.abs(audio) > 1e-3]  # ignore paragraph silences when measuring
        rms = float(np.sqrt(np.mean(speech**2))) if speech.size else 0.0
        peak = float(np.max(np.abs(audio))) if audio.size else 0.0
        gain = min(10 ** ((args.target - db(rms)) / 20), 10.0)  # at most +20 dB
        result = soft_limit(audio * gain, 10 ** (args.ceiling / 20))
        new_speech = result[np.abs(result) > 1e-3]
        new_rms = float(np.sqrt(np.mean(new_speech**2))) if new_speech.size else 0.0
        out = path.with_name(f"{path.stem}-loud{path.suffix}")
        sf.write(out, result, rate, format=path.suffix.lstrip(".").upper())
        print(f"{path.name}: RMS {db(rms):.1f} dBFS, peak {db(peak):.1f} dBFS, gain {db(gain):+.1f} dB -> {out.name} "
              f"(RMS {db(new_rms):.1f}, peak {db(float(np.max(np.abs(result)))):.1f})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
