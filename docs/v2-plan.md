# Plan: UI v2 and open-source release

Status: **built** (2026-09-29). Release (commit, repo, push) waits for the user's go. Follows `docs\ui-plan.md` (v1, built).

## Decisions agreed

| Topic | Decision |
|---|---|
| Settings file | `settings.json` in the project folder, git-ignored. Missing or corrupt file falls back to defaults. |
| Clear button | Wipes file path, paste text, name, script check, progress and status. Keeps the loaded model. **Keeps** Mood / Voice / Speed / Pause. |
| File list placement | Right-hand panel. Window becomes wider (about 1100x640 minimum); form stays left. |
| License | MIT, `LICENSE` file. |
| Repo | Public, org RasWorx (verify with `gh org list`), name `rasworx-kokoro-narration` (spelling corrected from "naration"). |
| Public content | Exclude personal scripts in `input\`, all `output\` MP3s and `output\previews\`. Keep `input\sample.md`. Keep `AGENTS.md` / `CLAUDE.md` but strip personal hardware and personal rules. `requirements.txt` IS committed; "ignore requirements" means ignore installed packages (`.venv\`). |

## Work items

1. **Persist settings.** `load_settings()` / `save_settings()` in `ui.py`, JSON with mood, voice, speed, pause. Load in `App.__init__` inside the `applying_mood` guard so traces do not flip Mood to Custom. Validate ranges on load. Save in `_on_close`.
2. **Clear button** in the header (right side, `Page.TButton`). Resets file_var, name_var, paste text, `name_touched`, lint state (bump `lint_seq`), progress, status (back to "Ready ..."), mode to File. Disabled while converting.
3. **Folder buttons.** "Open Output Folder" (opens `output\`, always enabled; creates the folder if missing) and "Open Input Folder" (opens `input\`). Play stays tied to the last MP3.
4. **Warnings popup.** Clicking the count or summary text (and a "View" link) opens a brand-styled `Toplevel` with a read-only text list. Replaces the inline box and the Show/Hide toggle. Only clickable when warnings exist.
5. **Output file browser** (right panel). `ttk.Treeview`, multi-select, columns Name / Length / Date (length read via `soundfile.info`, cached). Lists `output\*.mp3` and `*.wav`, excludes `previews\`. Buttons: Play selected (first selected, double-click also plays), Delete selected (confirm dialog lists the file names, default No), Refresh. Auto-refresh after each conversion and on start.
6. **Linter path.** `LINTER` looks at `.agents\skills\tts-output\scripts\check_tts_script.py` first, then the global `%USERPROFILE%\.claude\skills\...` path.
7. **Split theme.** Move palette and `apply_theme` / `dark_title_bar` to `ui_theme.py` to keep `ui.py` manageable.
8. **Setup.** `requirements.txt` (kokoro, soundfile, numpy; pinned to tested versions) with torch installed separately from the cu128 index. `setup.bat` + `setup.ps1`: install `uv` if missing, create `.venv` (Python 3.12) in the current folder, install torch cu128 then requirements, create `input\` and `output\`, create a desktop shortcut to `ui.bat` with `images\favicon.ico`, and recreate the `.claude\skills` junctions for both skills.
9. **Git files.** `.gitignore` (`.venv/`, `__pycache__/`, `.handoff/`, `ui.log`, `settings.json`, `output/*` except `.gitkeep`, `input/*` except `sample.md`), `LICENSE`, `output\.gitkeep`.
10. **README.md.** Researched first (defuddle / WebSearch, plus the `ofx-conv` README for house style). Tool, not app. Logo via `<picture>` so the white "RasWor" text is visible on light themes. Sections: description, features, requirements, install (states that setup installs into the folder it is run from), window usage, CLI usage, writing tips, the two skills (`kokoro-help`, `tts-output`; how to install `tts-output` globally or upload to claude.ai / chatgpt.com), troubleshooting, license and credits (Kokoro-82M is Apache-2.0, weights downloaded not committed; Montserrat recommended).
11. **Docs.** Update `AGENTS.md` (new features, setup) and `kokoro-help` skill line. Strip personal content from the public copy.
12. **Release** (needs explicit go at the time): `git init`, first commit, `gh repo create RasWorx/rasworx-kokoro-narration --public`, push.

## Layout sketch

```
┌ Kokoro narration ───────────────────────────────────────────────────────┐
│ [logo]                                   [Clear]   Kokoro narration     │
│ ┌ form card (as v1) ──────────────────┐ ┌ Output files ───────────────┐ │
│ │ Input / Paste / Name / Mood / Voice │ │ Name          Length  Date  │ │
│ │ Script check: 2,140 words, 3 warnings│ │ ep-01.mp3     14.1m   09-29 │ │
│ └─────────────────────────────────────┘ │ ...                         │ │
│ [CONVERT][Cancel][███████░░] para 4/8    │ [Play][Delete][Refresh]     │ │
│ Status line                              └─────────────────────────────┘ │
│ [Play] [Open Input Folder] [Open Output Folder]                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## Order of work

Items 1-7 (UI) then verify with screenshots, then `simplify` on `ui.py`; then 8-9, 10-11; then item 12 after a final confirmation.

## Verification

1. `.venv\Scripts\python.exe -c "import ui"`.
2. Scripted UI test (patched dialogs, `INPUT_DIR` / `OUTPUT_DIR` redirected to `output\previews\`, screenshots via `drive-screen`): settings round trip incl. corrupt file, Clear, popup, file list refresh, delete confirm listing, Open buttons.
3. Run `setup.bat` into a scratch folder copy; check `.venv`, shortcut and a CLI render.
4. `git status` review of what would be committed before the first commit.
