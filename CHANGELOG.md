# Changelog

All notable changes to RasWorx Kokoro Narration. The version number lives in `version.py` and follows [semantic versioning](https://semver.org/): patch for fixes, minor for new features, major for changes to the `input\` to `generate.py` to `output\` workflow or its folder names.

## 1.2.0 - 2026-09-30

### Added
- **Markdown preview.** Pasted or loaded Markdown is shown rendered (headings, bold, italic, quotes, lists, rules, links) instead of raw syntax. A **Preview | Edit** switch beside Browse (Ctrl+E) shows the raw text for editing. Pasting Markdown into an empty box opens in Preview. New `md_preview.py`; conversion still uses the raw text.
- **Copy to Clipboard** in the script check warnings popup: copies the summary and every warning, ready to paste into a chat when tuning a script or the `tts-output` skill.
- Linter checks for `chapter:verse` references (read "six, ten") and for text in another language (a US voice garbles it).

### Changed
- The script check groups short headings and short paragraphs into one warning each (with their line numbers) instead of one warning per line; `--detail` restores one line each. Small numbers and years are now only a note.
- `tts-output` and `kokoro-help` skills: new "Structure traps" guidance (one sentence per paragraph, stacked headings, bold-only lines, closings, scripture references, foreign-language quotes) and a fourth eval.
- `AGENTS.md` rewritten for a public repository.

### Fixed
- The linter no longer reports horizontal rules (`---`) as empty paragraphs with a false "`--` is dropped" warning; `generate.py` already strips them.

## 1.1.0 - 2026-09-29

### Added
- **Version number.** Shown in the window title and header, printed by `generate.py --version`, defined once in `version.py`.
- **Preview.** Hear the opening of a script (about 15 seconds) with the current voice, speed and loudness setting, without saving anything. Click again to stop.
- **Pronunciation dictionary.** `pronunciations.txt` holds `word = respelling` or `word = /IPA/` entries that apply to every conversion and preview, from the window or the command line. Edit it from the **Pronunciations** button.
- **Loudness normalisation.** Output is raised to about podcast level (-16 dBFS RMS, peaks under -1 dBFS) so episodes play at a steady volume. On by default; untick **Normalize loudness** in the window or pass `--no-normalize` on the command line.
- **Drag and drop.** Drop a `.txt`, `.md` or `.markdown` script on the window. Adds the `tkinterdnd2` package.
- **Keyboard shortcuts.** Ctrl+Enter convert, Ctrl+O browse, Ctrl+P preview, Ctrl+L clear, Esc cancel, F5 refresh the file list.
- The picked file is now previewed read-only in the window.

### Changed
- Window layout: two equal columns, a File / Paste segmented control, the convert bar and status inside the form card, and the folder buttons moved into the Output files panel.
- The newest MP3 is selected in the file list after each conversion (this replaces the separate Play button), names show in full on hover, and the list has an empty state.
- Script check is a coloured chip: green for no warnings, amber for warnings, red if the check failed.
- Convert reads "LOADING MODEL..." until the model is ready, and the status line says the first start can take about a minute.
- **Behaviour change:** MP3s are louder than before because loudness normalisation is on by default. Use `--no-normalize` (or untick the box) for the old volume.
- The Normalize loudness choice is remembered with the other settings.

## 1.0.0 - 2026-09-29

First release: `generate.py` command line, the desktop window with moods, voice blends, script check, output file list and Clear, `setup.bat` one-step install, the `kokoro-help` and `tts-output` skills.
