---
name: kokoro-help
description: Expert help for this local Kokoro-82M text-to-speech project on Windows 11 (generate.py, input\ and output\ folders, .venv). Use it whenever the user wants to change or compare voices, blend voices, adjust speed or pauses, fix mispronounced words, names, numbers or abbreviations, write or tidy a narration script so it sounds good, generate or regenerate an MP3, understand generate.py options, script Kokoro from Python, or troubleshoot errors such as CUDA/GPU not used, espeak, Hugging Face downloads, symlink warnings, Unicode console errors or MP3 export. Trigger even when the user does not say "Kokoro" but talks about narration, TTS, voiceover, "the voice", "make it slower", "it says X wrong", or MP3s in this folder.
---

# Kokoro help

This folder is an offline narration tool: scripts in `input\` (`.txt`, `.md`) become MP3s in `output\` via `generate.py`, using Kokoro-82M on the RTX 5050. `AGENTS.md` in the project root is the user-facing manual; this skill adds the deeper knowledge needed to change voices and parameters well and to fix problems.

There is also a desktop window, `ui.bat` / `ui.py` (see `AGENTS.md`, "Using the window"; theme in `ui_theme.py`, settings remembered in `settings.json`, `setup.bat` installs everything). It imports its cleaning, `synthesize()` and MP3 export from `generate.py`, so changes there apply to both; its errors go to `ui.log`. It also has a Preview button (plays the opening of a script without saving), drag and drop, and a Pronunciations editor. The version number is in `version.py` (`generate.py --version`).

## Ground rules (why they matter)

- **Run Python only via `.venv\Scripts\python.exe`.** The system Python is 3.14, which Kokoro does not support, and it lacks the CUDA 12.8 PyTorch build that Blackwell GPUs need.
- **Keep the workflow stable:** `input\` → `generate.py` → `output\`, same names, same flags. The user relies on double-clicking `generate.bat`.
- **Never delete or rewrite files in `input\` or `output\` unless asked.** Previews go to `output\previews\`, which `generate.py` ignores.
- **Do not edit `generate.py` on your own initiative.** When a request needs a code change (e.g. different voices per section, dialogue, subtitles), explain the limitation, propose the small change, and make it only if the user agrees. For one-off needs, write a separate script instead.
- **An unchanged input is skipped.** After changing only voice/speed/pause, pass `--force` or name the file, otherwise nothing is regenerated.

## Quick reference: generate.py

```
.venv\Scripts\python generate.py [files...] [--voice ID] [--speed N] [--pause SECONDS] [--force] [--cpu]
```

| Want | Do |
|---|---|
| Different voice | `--voice bm_george` (first letter sets accent: `a` US, `b` UK) |
| Slower / faster | `--speed 0.9` / `--speed 1.1`. 0.9–1.05 sounds most natural for narration; below ~0.8 or above ~1.2 tends to slur (no hard limit) |
| Longer gaps between paragraphs | `--pause 0.8` (default 0.4 s) |
| Re-render after changing settings | add `--force`, or name the file: `generate.py input\ep.md --voice af_bella` |
| Equal blend of two voices | `--voice af_heart,af_bella` |
| Weighted blend (2:1) | `--voice af_heart,af_heart,af_bella` (repeating a name weights it) |
| Saved voice blend (`.pt`) | `--voice voices\my_blend.pt` (path as given or relative to the project); accent from the file name's first letter, else American – override with `--accent b` |
| Force accent | `--accent a` / `--accent b` (default: first letter of the voice) |
| No GPU / CUDA error | `--cpu` (slower but works) |
| Double-click with options | `generate.bat --voice am_michael --speed 0.95` |
| Old volume (no loudness boost) | `--no-normalize`. Loudness normalisation to about -16 dBFS RMS is on by default in both the CLI and the window |
| MP3 still too quiet or too loud | `.venv\Scripts\python .agents\skills\kokoro-help\scripts
ormalize.py output\ep.mp3` (writes `ep-loud.mp3`, about podcast loudness) |

Blend strings contain commas, and PowerShell treats an unquoted `a,b` as an array, so quote them when giving PowerShell commands: `--voice "bm_george,bm_george,bm_fable"`. No spaces around the commas. The first voice's letter sets the accent. Naming a file on the command line always regenerates it (and overwrites its MP3 in `output\`), so mention that when it matters.

Settings are not saved anywhere: each run uses the defaults (`af_kore`, 1.0, 0.4) unless flags are given. If the user wants a new permanent default, that means changing `DEFAULT_VOICE` or the argparse defaults in `generate.py` (ask first), or putting the flags in their own `.bat`.

## Choosing a voice

The user works in **US English only** and chose **`af_kore`** (Kore) as the project default – keep it unless they ask to change it, and suggest American (`a*`) voices first. The agreed fallback, if they report problems with Kore (artefacts, flat or odd delivery), is `af_heart`: offer to switch `DEFAULT_VOICE` in `generate.py` and update `AGENTS.md`. If they want other options: `af_heart` (best rated overall), `af_bella` (warm, expressive), `af_nicole` (soft, close-mic), `am_michael`/`am_fenrir` (US male), `bf_emma` (UK female), `bm_george`/`bm_fable` (UK male). Grades and the full list with notes are in `references/voices.md` – read it when recommending or comparing voices.

Match the voice to the script's language; the first letter of the voice picks the language rules. Working here: English (`a`, `b`, best quality), Spanish `e`, French `f`, Hindi `h`, Italian `i`, Brazilian Portuguese `p` (verified). Japanese `j` and Mandarin `z` need `misaki[ja]` / `misaki[zh]`, which are not installed. No Afrikaans or other South African languages. See `references/voices.md` for voices per language.

**Let the user hear before committing a 20-minute render.** Render the same passage in several candidates:

```
.venv\Scripts\python .agents\skills\kokoro-help\scripts\preview_voices.py --voices af_heart af_bella bm_george "af_heart,af_heart,af_bella"
.venv\Scripts\python .agents\skills\kokoro-help\scripts\preview_voices.py --text-file input\episode-01.md --voices af_heart am_michael --speeds 0.9 1.0
```

Files land in `output\previews\` named like `bm_george@0.9.mp3`. First use of a voice downloads its ~0.5 MB voicepack from Hugging Face (internet needed once; then cached).

## Fixing pronunciation and script problems

0. **Fix a word for every script:** add `word = respelling` or `word = /IPA/` to `pronunciations.txt` (or the window's Pronunciations button). `generate.py` applies it after Markdown cleaning (`prepare_text()`), so it works in `.txt` and `.md`, for whole words in any case. `phonemes.py --file` goes through the same code, so it shows the dictionary's effect.
1. Find out what Kokoro "hears":
   ```
   .venv\Scripts\python .agents\skills\kokoro-help\scripts\phonemes.py --file input\episode-01.md --words
   ```
   It applies the same Markdown cleaning as `generate.py`, shows phonemes per chunk, and lists words that got no phonemes (they would be silently skipped).
2. Fix in the script text, preferring plain-English respelling (works everywhere). Spell out dates like `3/4/2026`, phone numbers, version numbers, 4-digit non-year numbers (Kokoro reads `1500` as "fifteen hundred"), and rand amounts (`R100` is read "ar one hundred"; write "one hundred rand"). `St.` is always "saint".
3. For exact control use misaki's inline syntax `[Kokoro](/kˈOkəɹO/)`, stress tweaks `[word](-1)` / `[word](+2)` and number flags `[150](#a#)`. They work in both `.txt` and `.md` (`generate.py` strips ordinary links but keeps this markup). Text aliases like `[Kokoro](ko ko ro)` are not supported by misaki at all. Always confirm with `phonemes.py`, because an override can land on the wrong word in rare cases (e.g. a single-letter link followed by a full stop).

Details, the verified number/abbreviation behaviour table, stress control (`[word](-1)`, `[word](+2)`), number flags and the phoneme alphabet are in `references/pronunciation.md`. Read it before editing a script for pronunciation.

When writing a new narration script for the user, follow `AGENTS.md` "Writing scripts that sound good": blank line between paragraphs, spoken-style punctuation, no tables/code, numbers and symbols spelled out when ambiguous, ~150 words per minute. Then run `generate.py` for that file only.

## Custom Python work

For things the CLI cannot do – arbitrary blend weights or `.pt` voicepacks, different voices per section or dialogue, word timestamps/subtitles, speed that varies with sentence length – read `references/python-api.md`. It documents `KPipeline` as installed here (kokoro 0.9.4), how `generate.py` uses it, and verified blending code.

## Troubleshooting

Read `references/windows-troubleshooting.md` for symptoms and fixes: GPU not used, CUDA/Blackwell errors, Hugging Face download/offline/symlink messages, espeak fallback, `UnicodeEncodeError` on IPA, MP3 export failing, and the harmless warnings Kokoro prints on every run. Quick health check:

```
.venv\Scripts\python -c "import torch, kokoro; print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

Expected: `2.11.0+cu128 True NVIDIA GeForce RTX 5050 Laptop GPU` (or similar). `False` means the GPU is not being used.

## Limits worth telling the user

- 54 fixed voices, no voice cloning, no SSML, no emotion or emphasis control beyond punctuation, paragraph breaks and subtle stress markers. Delivery is even and documentary-like.
- If they need more expression or their own voice, the researched next step is Chatterbox-Turbo in a separate folder and venv (see `AGENTS.md`), not changes here.
