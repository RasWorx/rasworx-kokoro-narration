# Windows 11 setup notes and troubleshooting

This project: Windows 11 Pro, Python 3.12 venv made by `uv` (no `pip` inside), torch 2.11.0+cu128, kokoro 0.9.4, misaki 0.9.4, espeakng-loader 0.2.4, spaCy 3.8 + en_core_web_sm 3.8.0, soundfile 0.14 (libsndfile 1.2.2), NVIDIA RTX 5050 Laptop GPU (Blackwell, sm_120).

## Contents

1. Health check
2. Harmless messages you will see
3. GPU / CUDA problems
4. Hugging Face downloads, cache and offline use
5. espeak-ng and out-of-dictionary words
6. spaCy model missing
7. Console Unicode errors
8. MP3 export and loudness
9. Rebuilding the environment
10. Python version

## 1. Health check

```
.venv\Scripts\python -c "import torch, kokoro, soundfile; print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_name(0), torch.cuda.get_device_capability(0), soundfile.__libsndfile_version__)"
```
Good: `2.11.0+cu128 True NVIDIA GeForce RTX 5050 Laptop GPU (12, 0) 1.2.2`.

`generate.py` prints `Loading Kokoro on cuda ...` when the GPU is used; `on cpu` means it fell back (it silently uses the CPU when CUDA is unavailable).

## 2. Harmless messages (ignore unless something else fails)

- `UserWarning: dropout option adds dropout after all but last recurrent layer ... num_layers=1` – from the model's LSTM; harmless.
- `FutureWarning: torch.nn.utils.weight_norm is deprecated` – harmless.
- `Warning: You are sending unauthenticated requests to the HF Hub` – harmless; no token is needed for this public model.
- `To support symlinks on Windows, you either need to activate Developer Mode or to run Python as an administrator` – the Hugging Face cache stores real copies instead of symlinks; works fine, uses slightly more disk. It is printed when a file is newly downloaded (first run, first use of a voice); already-cached files skip that code path, so if it appears on *every* run, something is being re-downloaded each time. Silence with `setx HF_HUB_DISABLE_SYMLINKS_WARNING 1` (new terminals) or turn on Windows Developer Mode.
- `WARNING: Defaulting repo_id to hexgrad/Kokoro-82M` – only appears in scripts that omit `repo_id=`; pass `repo_id="hexgrad/Kokoro-82M"`.
- `words count mismatch on X% of the lines` – phonemizer/espeak warning, mostly with non-English languages; harmless.

Kokoro disables its own loguru warnings by default (truncation, language mismatch, espeak fallback disabled). When debugging, turn them on at the top of a script: `from loguru import logger; logger.enable("kokoro")`.

## 3. GPU / CUDA problems

| Symptom | Cause | Fix |
|---|---|---|
| `torch.cuda.is_available()` is `False`, `Loading Kokoro on cpu` | CPU-only torch wheel installed, or driver problem | Reinstall torch from the cu128 index (section 9); update the NVIDIA driver; check `nvidia-smi` |
| `CUDA error: no kernel image is available for execution on the device` / `sm_120 is not compatible with the current PyTorch installation` | torch built for older CUDA (cu126 or earlier) cannot run on Blackwell | Needs torch ≥ 2.7 **cu128** or newer build |
| `RuntimeError: CUDA requested but not available` | script passed `device="cuda"` without a working GPU | Use `--cpu` or fix the torch install |
| `CUDA out of memory` | another app (game, Ollama, Chatterbox) holding VRAM | Close it; Kokoro itself needs well under 1 GB of the 8 GB. Or use `--cpu` |
| `+cu128` build but `is_available()` is `False` on this laptop | Windows is not exposing the NVIDIA GPU: Lenovo Vantage / BIOS set to integrated-GPU-only (Hybrid off, battery saver), driver crash, or `CUDA_VISIBLE_DEVICES` set to empty/`-1` | Plug in, set GPU mode to Hybrid or dGPU in Lenovo Vantage, check Device Manager and `nvidia-smi`, clear `CUDA_VISIBLE_DEVICES` |
| Very slow even though GPU is found | laptop on battery / power-saving mode, or iGPU in use | Plug in, set Windows power mode to Best performance |

Expected speed on the RTX 5050: a 12–13 minute clip in about 15 seconds. On CPU, several times slower (still usable).

## 4. Hugging Face downloads, cache and offline use

- Cache: `%USERPROFILE%\.cache\huggingface\hub\models--hexgrad--Kokoro-82M\` – `config.json`, `kokoro-v1_0.pth` (312 MB) and `voices\<id>.pt` (~0.5 MB each).
- **Voices download lazily**: a voice is fetched the first time it is used. Initially only `af_heart` was cached. A new voice on a machine without internet fails with a connection / `LocalEntryNotFoundError`. Fix: go online once, or pre-fetch all English voices while online:
  ```
  .venv\Scripts\python -c "from huggingface_hub import snapshot_download; snapshot_download('hexgrad/Kokoro-82M', allow_patterns=['voices/a*.pt','voices/b*.pt'])"
  ```
  or with the Hugging Face CLI that ships in the venv: `.venv\Scripts\hf download hexgrad/Kokoro-82M --include "voices/*"` (all languages, ~28 MB).
- Fully offline, faster start (no HTTP check): `set HF_HUB_OFFLINE=1` before running. Errors if something was never downloaded.
- Move the cache (e.g. to another drive): set `HF_HOME` (or `HF_HUB_CACHE`) as a user environment variable. Environment variables must be set before Python imports `huggingface_hub`, so set them in the shell or a `.bat`, not halfway through a script.
- Corrupt download (`safetensors`/`torch.load` errors, truncated file): delete the `models--hexgrad--Kokoro-82M` folder and run again online.

## 5. espeak-ng and out-of-dictionary words

- No system espeak-ng install is needed. misaki uses the `espeakng-loader` package, which bundles `espeak-ng.dll` and its data inside the venv. Old guides that say to install the espeak-ng `.msi` or set `PHONEMIZER_ESPEAK_LIBRARY` / `PHONEMIZER_ESPEAK_PATH` are from older versions.
- espeak is only the fallback for English words misaki's dictionaries do not know (names, made-up words). If it fails to load, those words are **silently skipped**. Symptom: a name missing from the audio. Check with `scripts/phonemes.py --words` (it lists words with no phonemes) and enable kokoro logging to see `EspeakFallback not Enabled`.
- Fallback guesses for unusual names are often wrong (e.g. South African place names like Gqeberha). Respell or use a `/phoneme/` override (see `pronunciation.md`).

## 6. spaCy model missing

misaki needs `en_core_web_sm` (installed). If it goes missing, misaki tries `spacy.cli.download`, which calls `pip` – and this uv-made venv has no pip, so it fails. Reinstall with uv:
```
uv pip install --python .venv\Scripts\python.exe https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl
```

## 7. Console Unicode errors

`UnicodeEncodeError: 'charmap' codec can't encode character 'ə'` when printing phonemes: Windows consoles default to cp1252. Run with `set PYTHONUTF8=1` (or `PYTHONIOENCODING=utf-8`), or call `sys.stdout.reconfigure(encoding="utf-8")` in the script. `scripts/phonemes.py` already does this. Scripts containing IPA should be saved as UTF-8; `generate.py` reads input files as UTF-8 (with or without BOM). Files saved as ANSI/cp1252 by old editors can turn quotes and dashes into garbage – re-save as UTF-8.

## 8. MP3 export and loudness

- MP3 writing uses libsndfile ≥ 1.1 (bundled 1.2.2 has MP3 support). If it ever fails, `generate.py` writes `.wav` and prints `MP3 export failed (...)`. Fix by reinstalling `soundfile` (`uv pip install --python .venv\Scripts\python.exe --reinstall soundfile`).
- Output is 24 kHz mono. Bitrate is libsndfile's default VBR; fine for speech.
- **Kokoro output is quiet** (about −26 dBFS RMS, peaks ~0.4) compared with podcasts (about −16 LUFS). If the user says the MP3 is too quiet, use `scripts/normalize.py` (writes a new `*-loud.mp3`, never overwrites) or, if ffmpeg is installed (`winget install Gyan.FFmpeg`; not installed on this machine), `ffmpeg -i in.mp3 -af loudnorm=I=-16:TP=-1.5:LRA=11 out.mp3`.
- A file locked by a media player: `PermissionError` / `LibsndfileError: Error opening ... for writing` when regenerating. Close the player and rerun.

## 9. Rebuilding the environment

From the project root, with `uv` installed:
```
uv venv --python 3.12 .venv
uv pip install --python .venv\Scripts\python.exe torch --index-url https://download.pytorch.org/whl/cu128
uv pip install --python .venv\Scripts\python.exe kokoro soundfile
```
Order matters: install the cu128 torch first so `kokoro` does not pull a CPU-only torch from PyPI. If torch was replaced by a CPU build, rerun the torch line with `--reinstall`.

## 10. Python version

Kokoro/misaki require Python 3.10–3.12. The system Python here is 3.14 – running `python generate.py` with it fails on import. Always use `.venv\Scripts\python` or `generate.bat`.

## Alternatives if this setup is not enough

- **Kokoro-FastAPI** (Docker, OpenAI-compatible `POST /v1/audio/speech` on port 8880, web UI at `/web`, weighted mixes like `af_bella(2)+af_sky(1)`): `docker run --gpus all -p 8880:8880 ghcr.io/remsky/kokoro-fastapi-gpu:latest-cu128` (cu128 image for RTX 50-series). Useful for other apps to call Kokoro; not needed for the file workflow.
- **kokoro-onnx**: ONNX Runtime version without PyTorch; smaller install, mostly for CPU or other platforms.
- **Chatterbox-Turbo**: for voice cloning and more expressive delivery (separate folder and venv; see `AGENTS.md`).
