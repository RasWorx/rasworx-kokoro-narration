# Plan: simple desktop UI for text-to-MP3

Status: **built** (2026-09-29). `ui.py`, `ui.bat` and `assets\` exist, `generate.synthesize()` has `progress` / `stop`, and the verification steps below passed. Change after approval: the window uses the RasWorx brand style (dark palette, `#046FCC`, Montserrat, logo from `assets\`). Overwrite prompts are Yes / No dialogs (tkinter cannot relabel them Overwrite / Cancel).

## Decisions agreed

| Topic | Decision |
|---|---|
| Technology | `tkinter` + `ttk` desktop window. Already in `.venv`, no new installs, fully offline. |
| Input modes | 1. Pick a `.txt` / `.md` / `.markdown` file. 2. Paste plain text or Markdown. |
| Pasted text | Saved as `input\<name>.md` first, then converted to `output\<name>.mp3`. Keeps the `input\` to `output\` workflow, so `generate.py` can re-render it later. |
| Picked file | Read where it is, never copied or changed. MP3 goes to `output\<file stem>.mp3`. |
| Extras in v1 | Script linter warnings (from `tts-output`) and mood presets. No preview render. |

## New files (nothing existing is changed, except the docs listed at the end)

- `ui.py`: the window and the worker thread. Imports `load_text`, `markdown_to_speech`, `paragraphs_of`, `write_mp3`, `resolve_voice`, `accent_of`, `SAMPLE_RATE`, `INPUT_DIR`, `OUTPUT_DIR`, `DEFAULT_VOICE` from `generate.py`.
- `ui.bat`: double-click launcher. Runs `.venv\Scripts\pythonw.exe ui.py` so no console window stays open.

## Window layout

```
┌ Kokoro narration ──────────────────────────────── _ □ x ┐
│ Input   (•) File  [C:\...\episode-02.md      ] [Browse] │
│         ( ) Paste                                       │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ paste text here (enabled in Paste mode)             │ │
│ └─────────────────────────────────────────────────────┘ │
│ Name    [episode-02          ]  -> output\episode-02.mp3│
│ Mood    [Custom ▾]                                      │
│ Voice   [af_kore ▾]  Speed [1.00]  Pause [0.40] s       │
│ Script check: 2,140 words, ~14.3 min, 3 warnings  [▸]   │
│   WARN line 12: paragraph has 5 words (sounds clipped)  │
│ [ Convert ]  [ Cancel ]  [██████████░░░░] para 42/60    │
│ Saved output\episode-02.mp3 (14.1 min in 16 s)          │
│ [ Play ]  [ Open folder ]                               │
└─────────────────────────────────────────────────────────┘
```

## Behaviour

**Input**
- File mode: Browse opens a file dialog (starts in `input\`, filters `.txt .md .markdown`). The Name field shows the file stem and is read-only.
- Paste mode: the text box is enabled. Name defaults to a slug of the first heading, or of the first five words (e.g. `why-the-plant-failed`), and can be edited. Allowed characters: letters, digits, `-`, `_`.

**Overwrite protection** (the rule "never rewrite files in `input\` or `output\` unless asked")
- If `input\<name>.md` already exists in Paste mode, ask: Overwrite / Cancel.
- If `output\<name>.mp3` already exists, ask: Overwrite / Cancel. Clicking Overwrite counts as the user asking.

**Voice, speed, pause**
- Voice: editable dropdown with US voices only, in quality order: `af_kore` (default), `af_heart`, `af_bella`, `af_nicole`, `af_aoede`, `af_sarah`, `am_michael`, `am_fenrir`, `am_puck`. Typing a blend such as `af_heart,af_bella` also works.
- Speed: spinbox, 0.70 to 1.30, step 0.05, default 1.00.
- Pause: spinbox, 0.0 to 3.0 s, step 0.1, default 0.4.
- Settings are not saved between sessions, same as `generate.py`.

**Mood presets** (from the `tts-output` mood table, midpoints). Picking one fills Voice, Speed and Pause, which stay editable. Editing any of them switches the dropdown back to Custom.

| Preset | Voice | Speed | Pause |
|---|---|---|---|
| Custom (default) | `af_kore` | 1.00 | 0.4 |
| Calm, documentary | `af_kore` | 0.95 | 0.45 |
| Warm, reassuring | `af_heart` | 0.92 | 0.55 |
| Serious, reflective | `af_heart` | 0.88 | 0.8 |
| Excited, upbeat | `af_heart` | 1.08 | 0.3 |
| Urgent, tense | keep current | 1.05 | 0.3 |
| Meditation, sleep | `af_heart` | 0.82 | 2.0 |

**Script check (linter)**
- Runs `%USERPROFILE%\.claude\skills\tts-output\scripts\check_tts_script.py --quiet` as a subprocess through `.venv\Scripts\python.exe`, when a file is picked and when Convert is clicked. For pasted text it checks a temporary copy in `%TEMP%`.
- Shows the summary line (words, estimated minutes, warning count). The warnings are listed in a collapsible box.
- Warnings never block conversion. If the linter file is missing, the check row is hidden.

**Conversion**
- The Kokoro model loads in a background thread when the window opens. The status line shows "Loading model on cuda..." and then "Ready". The model stays loaded, so later conversions only pay the synthesis time.
- One `KPipeline` for accent `a` (US only). A new pipeline is created only if a typed voice needs another accent.
- Convert runs in a worker thread, so the window stays responsive. Progress (paragraph n of N) is sent back through a queue and polled with `root.after`.
- Cancel stops at the next paragraph boundary. No MP3 is written.
- Convert is disabled while the model loads or a conversion runs.
- GPU is used when available, otherwise CPU, and the status line says which.

**After conversion**
- The status shows the output path, audio minutes and seconds taken. If MP3 export failed and a WAV was written, it says so.
- Play opens the MP3 in the default player (`os.startfile`). Open folder runs `explorer /select,` on the file.

**Errors**
- Errors show in the status line and a message box. They are also written to `ui.log` in the project folder, because `pythonw.exe` has no console. Kokoro's own warnings also go to `ui.log`.

## Progress reporting (decided: option A)

`generate.synthesize()` prints progress to the console and offers no callback. The user chose **A** on 2026-09-29. The options were:

- **A (recommended):** add an optional `progress=None` argument to `synthesize()` in `generate.py`. It is called as `progress(i, total)` for each paragraph, and a `stop` check lets Cancel work. The CLI behaves exactly the same. About 5 changed lines. Needs your OK, because `generate.py` is only changed with agreement.
- **B:** `ui.py` has its own copy of the 10-line synthesis loop. `generate.py` stays untouched, but the loop is duplicated.

## Docs to update after build

- `AGENTS.md`: a "Using the window (`ui.bat`)" section, and `ui.py` / `ui.bat` added to the folder layout table.
- `.agents\skills\kokoro-help\SKILL.md`: one line saying the UI exists and reuses `generate.py`.

## Verification

1. Import check: `.venv\Scripts\python.exe -c "import ui"` with no errors.
2. Headless test of the worker: convert a 2-paragraph pasted text to `output\previews\ui-test.mp3`, and confirm the file plays and has the expected length.
3. Launch `ui.bat` and take a screenshot. Test both modes, the overwrite prompt, Cancel, Play and Open folder.
4. If option A is chosen, confirm the CLI still works: call `generate.synthesize()` from Python on `input\sample.md` with no `progress` argument and write the result to `output\previews\`, so real outputs are not touched.
