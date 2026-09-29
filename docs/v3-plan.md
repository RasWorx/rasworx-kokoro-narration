# Plan: version number and UI/UX pass (v3)

Status: **built** (2026-09-29), approved with version 1.1.0 and all three features (A, B, C). Committed locally; push, tag and release wait for the user's go. Follows `docs\v2-plan.md` (built, published).

## Research used

- Design direction: `frontend-design` skill, translated to tkinter. Direction is **refined utilitarian**: keep the RasWorx dark palette, add restraint, clear hierarchy and one memorable detail (a drop zone with a live state), not decoration.
- Desktop guidance (Microsoft Fluent / Windows app guidelines, UX pattern references): one visually dominant primary action; empty states carry one clear action; drag and drop needs a visible drop target, drag-over state and a non-drag alternative; show shortcuts on the controls; keep focus visible and in a logical order; immediate feedback for every action; errors say what to do next.
- Baseline screenshot taken from the running v2 window (maximized, 1270x693 client).

## Task 1: version number

| Topic | Proposal |
|---|---|
| Source of truth | New `version.py` with `__version__ = "1.0.0"`. `ui.py`, `generate.py`, `setup.ps1` and docs read it (setup and docs by text, the rest by import). |
| First version | `1.0.0` (the published release). Semver: patch = fixes, minor = features, major = workflow or folder changes. |
| In the window | Small muted `v1.0.0` in the header under the subtitle, and in the title bar: `Kokoro narration 1.0.0`. |
| CLI | `generate.py --version` prints `kokoro-narration 1.0.0`. **Needs your OK** (touches `generate.py`). |
| Changelog | New `CHANGELOG.md` (Keep a Changelog format): 1.0.0 = first release, 1.1.0 = this UI pass. |
| Git | Tag `v1.0.0` on the existing first commit `6a5ffd3`; the UI pass ships as `1.1.0` with tag `v1.1.0`. |
| GitHub release | Optional `gh release create`. **Outward-facing: only on your explicit go.** |

Open question: ship the UI pass as `1.1.0` (recommended) or fold everything into `1.0.0`?

## Task 2: UI/UX changes

Problems seen in the baseline: the wide card has a huge empty paste box and a small form; the file list is cramped and truncates names; the file list has a bright white focus frame; Play, folder buttons and progress sit loose under the cards; no drag and drop; no shortcuts; Convert explains itself only via the status line.

Proposed changes (each is independent, so you can strike any):

1. **Layout rebalance.** Left column fixed to a comfortable form width (about 620 px), right file panel takes the remaining width. Fixes the truncated names and the empty stretch. Wide windows no longer stretch the form.
2. **Drop zone in the input area.** The text box doubles as a drop target for `.txt` / `.md` / `.markdown`. Empty state text inside it: "Drop a script here, click Browse, or switch to Paste". Border turns blue while a file is dragged over. Needs `tkinterdnd2` (new pinned dependency, installed by `setup.ps1`); if it is missing the app runs without drop and the hint changes. **New dependency: needs your OK.**
3. **Input mode as a segmented control.** File / Paste as two joined buttons instead of radio buttons; Browse sits beside the path field. The name row is the same in both.
4. **One action bar.** Convert (primary), Cancel, progress bar and "para 4/8" on one row inside the left card's footer. The status line moves directly under it and gets a small state dot (busy, ready, error) so colour is not the only signal.
5. **Play and folders join the file panel.** Panel header gets the two folder buttons as small link buttons ("Input folder", "Output folder"). Panel footer keeps Play selected / Delete selected / Refresh. "Play" for the last MP3 is dropped because the newest file is selected and highlighted after each conversion.
6. **File list polish.** Columns Name (stretch) / Length / Date with shorter date (`29 Sep 21:50`), full-name tooltip on hover, newest row selected after conversion, remove the white focus frame (`highlightthickness=0`, palette focus colour), empty state row "No MP3s yet".
7. **Keyboard.** `Ctrl+Enter` convert, `Ctrl+O` browse, `Ctrl+L` clear (Clear uses `Esc` no), `Esc` cancels a running conversion, `F5` refresh files. Shortcut hints shown on button tooltips ("Convert  Ctrl+Enter"). Sensible tab order; visible blue focus ring on buttons.
8. **Convert guidance.** While the model loads, Convert shows "LOADING MODEL..." (disabled) with the first-run note "first start can take about a minute" in the status line, then flips to "CONVERT". Removes the silent disabled state.
9. **Clearer script check.** Show it as a coloured chip: green "0 warnings", amber "3 warnings  View". Same popup as now.
10. **Small type and spacing pass** in `ui_theme.py`: 8 px spacing scale, section labels a little brighter (contrast 4.5:1 against the card), card corner separation via 1 px border colour, heading weight for the title.

Out of scope: light theme, settings dialog, batch conversion, menus.

## Suggested new features (pick up to three)

Research: comparable local TTS/audiobook tools ([audiobookifier](https://pypi.org/project/audiobookifier/), TTSMate, ReadSpeaker speechMaker Studio, [PyKokoro](https://pykokoro.readthedocs.io/)) converge on the same value-adders: voice preview, pronunciation dictionary, loudness normalisation, chapter markers, batch queue.

| # | Feature | Why it adds value here | Effort / touches |
|---|---|---|---|
| A | **Preview button.** Renders the first paragraph (about 15 s) with the current Voice / Speed / Pause into `output\previews\` and plays it. | Today the only way to test a mood is a full render (up to a minute for 20 min). Preview makes Mood / Speed / Pause tuning instant. Reuses the loaded model. | Small. `ui.py` only. |
| B | **Pronunciation dictionary.** `pronunciations.txt` (`word = respelling` or `word = /IPA/`), applied to the text before synthesis, plus a small "Pronunciations" editor window. | Fixes a word once for every future script instead of editing each one. Complements the existing `[word](/ipa/)` inline syntax. | Medium. Needs a hook in `generate.py` (shared by CLI and window), so it needs your OK. |
| C | **Loudness normalisation option.** "Normalise loudness" checkbox (default on), using the existing `normalize.py` logic to about -16 LUFS on export. | Output volume becomes consistent across episodes and phone/car playback; removes the manual post-step in the kokoro-help skill. | Small to medium. Export step in `generate.py`, so it needs your OK. |

Runners-up, not proposed now: chapter markers (M4B from headings), SRT subtitles from word timestamps, a batch queue for several files.

## Files touched

`version.py` (new), `CHANGELOG.md` (new), `ui.py`, `ui_theme.py`, `generate.py` (`--version` only, with OK), `requirements.txt` and `setup.ps1` (tkinterdnd2, with OK), `README.md`, `AGENTS.md`, `docs\v3-plan.md`.

## Order of work

1. Approval of this plan (strike or keep each numbered item; answer the three open questions).
2. `version.py`, window version label, `--version`, `CHANGELOG.md`.
3. Theme and layout changes (1, 3, 4, 5, 6, 10), then drop zone (2), then keyboard and guidance (7, 8, 9).
4. Scripted test in a scratch folder (patched dialogs, redirected `INPUT_DIR` / `OUTPUT_DIR` / `SETTINGS_FILE`) plus screenshots of the real window; `simplify` and `code-review` on `ui.py`.
5. Update `README.md` and `AGENTS.md`. Commit locally. **Push, tag and release only after your go.**

## Open questions

1. Ship as `1.1.0` with tag `v1.0.0` on the first commit, or a single `1.0.0`?
2. OK to add `tkinterdnd2` for drag and drop?
3. OK to add `--version` to `generate.py`?
