# RasWorx Kokoro Narration

Manual for people and coding agents working in this repository. The public overview and install steps are in `README.md`; this file is the working reference.

## Purpose

A local, offline text-to-speech tool built on [Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M). It turns written scripts (plain text or Markdown) into natural-sounding MP3 narration, typically **10 to 20 minutes long**, without any cloud service, API key, or per-character cost.

Kokoro is small (82M parameters, about 330 MB), fast on a consumer GPU, Apache-2.0 licensed (commercial use is fine), and among the best-rated open-weight TTS models. Its limits: 54 fixed voices, no voice cloning, and a fairly even, documentary-style delivery rather than dramatic acting. This project is MIT licensed (see `LICENSE`).

## How to use it

1. **Put the script in `input\`** as a `.txt` or `.md` file, e.g. `input\episode-01.md`.
2. **Run the generator** from the project folder:
   ```
   .venv\Scripts\python generate.py
   ```
   or double-click `generate.bat`.
3. **Collect the MP3 from `output\`**. The file keeps the input's name: `input\episode-01.md` becomes `output\episode-01.mp3`.

Running with no arguments converts every file in `input\` that has no MP3 yet, or whose text was edited after its MP3 was made. Unchanged files are skipped, so it is safe to run repeatedly.

**Speed:** on the development GPU (RTX 5050 Laptop) a 12.6 minute clip took about 15 seconds. On `--cpu` expect several times slower.

`input\sample.md` is a short demo script (its MP3 is `output\sample.mp3`); delete both whenever you like.

## Using the window (`ui.bat`)

Double-click `ui.bat` (or the desktop shortcut made by `setup.bat`) to open the narration window (RasWorx dark style, starts maximized). It runs `.venv\Scripts\pythonw.exe ui.py`, so no console window stays open, and it reuses `generate.py` for cleaning, synthesis and MP3 export, so the audio is identical to the CLI.

- **Version:** `version.py` is the single source (semantic versioning). It shows in the window title and header and in `generate.py --version`. `CHANGELOG.md` records each release; a release is also tagged `v<version>` in git.
- **Input:** choose **File** and Browse (or drag a script onto the window; needs `tkinterdnd2`) to a `.txt` / `.md` / `.markdown` script (read where it is, never changed; the box shows a read-only preview), or choose **Paste** and paste plain text or Markdown. Markdown (headings, `>` quotes, lists, `**bold**`, links, rules) is shown as a rendered, read-only preview (`md_preview.py`); a **Preview | Edit** switch beside Browse (Ctrl+E) flips to the raw text. Pasting Markdown into an empty box opens in Preview; typing never flips the view. Only the display changes: conversion, the script check and the saved `.md` use the raw text. Pasted text is saved as `input\<name>.md` first, so `generate.py` can re-render it later. The name defaults to the first heading or first five words; letters, digits, `-` and `_` only.
- **Output:** always `output\<name>.mp3`. If the input or output file already exists, the window asks before overwriting.
- **Mood** presets fill Voice, Speed and Pause (still editable; editing switches back to Custom). **Voice** lists the US voices and also accepts a typed blend such as `af_heart,af_bella`. Speed 0.70 to 1.30, Pause 0 to 3 s.
- **Preview** renders the opening of the script (about 300 characters, cut at a sentence end) with the current Voice, Speed and loudness setting and plays it from memory (nothing is written to disk). Click again to stop. It is disabled while converting.
- **Normalize loudness** (checkbox, default on) raises the speech to about -16 dBFS RMS with a soft limiter under -1 dBFS (`normalize_loudness()` in `generate.py`). The CLI does the same unless `--no-normalize` is given.
- **Pronunciations** opens an editor for `pronunciations.txt` (git-ignored, personal to each install). Format: `word = respelling` or `word = /IPA/`, `#` notes. `generate.py` applies it to every script after Markdown cleaning (`prepare_text()`), for whole words in any case, and leaves existing `[word](/ipa/)` markup alone. The CLI uses the same file.
- **Settings are remembered:** Mood, Voice, Speed, Pause and Normalize loudness are saved to `settings.json` (git-ignored) when the window closes and restored on the next start. A missing or corrupt file means defaults.
- **Clear** (top right) returns the input, script check, progress and status to the just-opened state. It keeps the loaded model and the settings.
- **Keyboard:** Ctrl+Enter convert, Ctrl+O browse, Ctrl+P preview, Ctrl+E Preview/Edit, Ctrl+L clear, Esc cancel, F5 refresh files.
- **Script check** (a green / amber / red chip) runs the `tts-output` linter (`.agents\skills\tts-output`, or a copy in `%USERPROFILE%\.claude\skills`) when a file is picked and on Convert. Click the chip or **View** to open the list of warnings; **Copy to Clipboard** in that popup copies the summary and every warning, ready to paste into a coding-agent chat when tuning a script or the skill. Warnings never block conversion. Short headings and paragraphs are grouped into one warning each, listing their line numbers.
- **Output files** (right panel) lists the MP3/WAV files in `output\` (not `previews\`). **Play selected** (or double-click) plays the first selected file; the file just made is selected after a conversion. **Delete selected** deletes the selected files after a confirmation that lists them; it is the only place the tools delete anything in `output\`, and only on the user's click.
- **Input folder** and **Output folder** (top of the Output files panel) open `input\` and `output\` in Explorer.
- The model loads in the background when the window opens (status "Ready (model on cuda)"). **Cancel** stops at the next paragraph and writes no MP3.
- Errors and Kokoro's own messages go to `ui.log` in this folder.

## Folder layout

| Path | What it is |
|---|---|
| `input\` | Drop `.txt`, `.md`, or `.markdown` scripts here. Files are never moved or modified. |
| `output\` | Generated `.mp3` files land here, named after the input file. |
| `generate.py` | The conversion script. |
| `generate.bat` | Double-click shortcut; passes any arguments through to `generate.py`. |
| `ui.py` | The desktop window (tkinter). Imports its conversion code from `generate.py`. |
| `ui_theme.py` | RasWorx palette, ttk styles and dark title bar used by `ui.py`. |
| `md_preview.py` | Small Markdown renderer for the paste box preview (tk.Text tags, no dependencies). |
| `ui.bat` | Double-click shortcut that opens the window without a console. |
| `settings.json` | Saved Mood / Voice / Speed / Pause / Normalize loudness. Created by the window, git-ignored. |
| `pronunciations.txt` | Your pronunciation dictionary. Created by the Pronunciations editor, git-ignored. |
| `version.py`, `CHANGELOG.md` | The release number (one source of truth) and what changed in each release. |
| `setup.bat`, `setup.ps1` | One-step install into the folder they are run from: `.venv`, torch (CUDA 12.8), `requirements.txt`, desktop shortcut, skill links. |
| `requirements.txt` | Pinned Python packages (torch is installed separately by `setup.ps1`). |
| `README.md`, `LICENSE` | Public description of the tool and the MIT licence. |
| `docs\` | Design plans for each release (`v3-plan.md` is the template for the next). |
| `.agents\skills\` | The two agent skills (`kokoro-help`, `tts-output`); `setup.bat` links them into `.claude\skills`. |
| `assets\`, `images\` | RasWorx logo and window icon (`assets\`), and README images (`images\`). |
| `ui.log` | Log written by the window (errors, Kokoro warnings, saved files). Safe to delete. |
| `.venv\` | Python 3.12 virtual environment (Kokoro does not support Python 3.13+). Do not use a newer system Python. |

Personal content stays out of git: `input\*` (except `sample.md`), `output\*`, `settings.json`, `pronunciations.txt`, `ui.log`, `.handoff\`, `.venv\` and `.claude\skills\` are all in `.gitignore`.

## Options

```
.venv\Scripts\python generate.py [files...] [--voice ID] [--accent a|b] [--speed N] [--pause SECONDS] [--force] [--cpu] [--no-normalize] [--version]
```

| Option | Default | Meaning |
|---|---|---|
| `files` | all pending in `input\` | Convert only these files, e.g. `input\intro.md`. |
| `--voice` | `af_kore` | Voice ID (see below), a blend such as `af_heart,af_bella` (repeat a name to weight it), or a saved `.pt` voice file. The first letter of the voice (or `.pt` file name) sets the accent: `a` American, `b` British. |
| `--accent` | from voice | Force the language/accent code (`a`, `b`, `e`, `f`, `h`, `i`, `p`, `j`, `z`). Useful for `.pt` files whose name does not start with a language letter. |
| `--speed` | `1.0` | `0.9` slower and calmer, `1.1` faster. |
| `--pause` | `0.4` | Seconds of silence inserted between paragraphs. |
| `--force` | off | Regenerate even if the MP3 is already up to date. |
| `--cpu` | off | Run on the CPU instead of the GPU (slower, but works without CUDA). |
| `--no-normalize` | off | Skip loudness normalisation (default: speech is raised to about -16 dBFS RMS). |
| `--version` | | Print the version and exit. |

Examples:
```
.venv\Scripts\python generate.py input\chapter-3.md --voice bm_george --speed 0.95
.venv\Scripts\python generate.py --force --voice af_bella
generate.bat --voice am_michael
.venv\Scripts\python generate.py --voice "bm_george,bm_george,bm_fable" --force
.venv\Scripts\python generate.py --voice voices\my_blend.pt --accent b --force
```

## Voices

The project targets **US English**, and the default voice is **`af_kore`** (Kore). Use American (`a*`) voices unless asked otherwise. If Kore gives quality problems, the fallback is `af_heart`: change `DEFAULT_VOICE` in `generate.py` and these docs.

The best-rated English voices, roughly in quality order:

- **American female:** `af_kore` (default), `af_heart` (best rated overall), `af_bella`, `af_nicole`, `af_aoede`, `af_sarah`
- **American male:** `am_michael`, `am_fenrir`, `am_puck`
- **British female:** `bf_emma`, `bf_isabella`
- **British male:** `bm_george`, `bm_fable`

Full list and quality grades: <https://huggingface.co/hexgrad/Kokoro-82M/blob/main/VOICES.md>. Use a voice that matches the script's language. English (`a*`, `b*`) is the best supported. Spanish (`e*`), French (`f*`), Hindi (`h*`), Italian (`i*`) and Brazilian Portuguese (`p*`) also work in this setup, with simpler pronunciation rules. Japanese (`j*`) and Mandarin (`z*`) need extra packages that are not installed. Afrikaans and other South African languages are not supported, so a quotation in one of them is read with English rules and comes out garbled. Write scripts in English only: translate any Afrikaans text (a Bible verse, a proverb) into English and leave the original out.

## Writing scripts that sound good

- **Separate paragraphs with a blank line.** Each paragraph is spoken in one flow, followed by a short pause (`--pause`). Very long paragraphs are split at sentence boundaries automatically.
- **Write paragraphs of 20 to 60 words. Never write one sentence per paragraph.** Every paragraph, and every heading (it is spoken as its own paragraph), is one chunk for the model, and chunks under about 8 words sound clipped. Join a list of short parallel lines into one paragraph; fold "Amen" or "Thanks for listening" into the paragraph before it; open with one spoken sentence rather than a stack of short headings.
- **Markdown is cleaned before speaking:** headings are read as short sentences; bold/italic markers, link URLs (the link text is kept), images, code blocks, HTML, horizontal rules (`---`) and YAML front matter are removed; list items are read as separate sentences (a full stop is added if missing). Keep tables and code out of narration scripts; they do not read well aloud.
- **Punctuation drives rhythm.** Commas give short breaths, full stops give longer ones. Use them deliberately.
- **Spell out things that should be read a specific way:** dates, decimals, phone numbers, abbreviations, symbols, unusual names, and any `chapter:verse` reference (`Proverbs 6:10` is read "six, ten"; write "Proverbs chapter six, verse ten"). Small numbers and years (`30`, `1983`) are read correctly. If a word is mispronounced, rewrite it phonetically, add it to `pronunciations.txt`, or give Kokoro the exact sounds with `[Kokoro](/kˈOkəɹO/)` (works in `.md` and `.txt`; stress tweaks like `[really](+2)` also work). The `kokoro-help` skill has the details and a phoneme checker.
- As a rough guide, ~150 words is about 1 minute of audio, so a 10 to 20 minute clip is ~1,500 to 3,000 words.
- The `tts-output` skill (`.agents\skills\tts-output`) writes and lints scripts for you; its linter (`scripts\check_tts_script.py`) is also what the window's Script check runs.

## Environment and setup details

- **Reference hardware:** developed on an NVIDIA RTX 5050 Laptop GPU (8 GB, Blackwell, compute capability 12.0). Any CUDA GPU or the CPU (`--cpu`, `setup.bat -Cpu`) also works.
- **PyTorch** is the CUDA 12.8 build (`cu128`), which Blackwell GPUs (RTX 50 series) require. A CPU-only or older-CUDA build will not use such a GPU.
- **Model weights** download from Hugging Face on first run and are cached in `%USERPROFILE%\.cache\huggingface`. Each voice (~0.5 MB) downloads the first time it is used, so try new voices while online; after that everything runs offline.
- **MP3 encoding** uses `soundfile` (libsndfile). If MP3 export ever fails, the script writes a `.wav` instead and says so.
- Kokoro does not run through Ollama; it runs directly in Python on PyTorch.

Run `setup.bat` to build (or rebuild) the environment in this folder. It does the following, which can also be done by hand (requires `uv`):
```
uv venv --python 3.12 .venv
uv pip install --python .venv\Scripts\python.exe torch --index-url https://download.pytorch.org/whl/cu128
uv pip install --python .venv\Scripts\python.exe -r requirements.txt
```

## Instructions for agents working in this repository

- For any request about voices, speed, pauses, pronunciation, narration scripts, generating MP3s, loudness or Kokoro errors, load the `kokoro-help` skill first (`.agents\skills\kokoro-help`, linked into `.claude\skills`). It has the tested voice data, pronunciation rules, helper scripts and Windows fixes.
- The `tts-output` skill is meant to be invoked by the person using the project (it sets `disable-model-invocation`). Agents may run its linter script, `.agents\skills\tts-output\scripts\check_tts_script.py`, without invoking the skill.
- The workflow is: drop scripts in `input\`, run `generate.py`, collect the MP3 from `output\`. Keep that workflow and those folder names stable; a change to them is a major version.
- Never delete or rewrite files in `input\` or `output\` unless the person asks. The window's **Delete selected** button is the only code path that deletes output files.
- Always run Python through `.venv\Scripts\python.exe`, never a system Python.
- When asked for a narration, write the script as a `.md` file in `input\` following the "Writing scripts that sound good" rules, lint it, then run `generate.py` for that file.
- Do not change `generate.py` on your own initiative: propose the change and wait for agreement. Do not commit, tag, push or release without being asked.
- Keep personal content (scripts, MP3s, `pronunciations.txt`, `settings.json`) out of commits, screenshots and docs. This is a public repository.
- For a new feature, write a short plan in `docs\` first (use `docs\v3-plan.md` as the template). For a release, bump `version.py`, add a `CHANGELOG.md` section, update `README.md` and this file if behaviour changed, then tag `v<version>`.
- If quality needs more expression or voice cloning, Kokoro cannot do it. The researched next step is Chatterbox-Turbo (MIT, ~6 GB VRAM, clones a voice from 10 to 20 seconds of clean audio); set it up in a separate folder and venv rather than changing this one.
