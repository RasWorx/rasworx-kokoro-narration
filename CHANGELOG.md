# Changelog

All notable changes to RasWorx Kokoro Narration. The version number lives in `version.py` and follows [semantic versioning](https://semver.org/): patch for fixes, minor for new features, major for changes to the `input\` to `generate.py` to `output\` workflow or its folder names.

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
