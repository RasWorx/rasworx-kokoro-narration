# Plan: Markdown preview in the paste box (v4)

Status: **built** (2026-09-30), approved with Preview as the default view, File mode rendered too. Follows `docs\v3-plan.md` (built).

## Problem

Pasting Markdown into the Paste tab shows the raw syntax (`# Heading`, `**bold**`, `> quote`, `---`). It is hard to read, and it hides what will actually be spoken.

## Proposal

The big text box gets two views when the pasted text looks like Markdown:

| View | What it shows | Editable |
|---|---|---|
| **Preview** (default after a paste of Markdown) | Rendered text: headings sized and bold, bold and italic applied, block quotes indented with a bar, list bullets, horizontal rules as a thin line, links as their text | No |
| **Edit** | The raw text, as today | Yes |

- A small segmented control **Preview | Edit** sits beside Browse in the input row (built there, not over the text, so it never covers it). Click **Edit** to change the text; click **Preview** to render again. Ctrl+E toggles.
- "Looks like Markdown": the text has a line starting with `#`, `>`, `-`/`*`/`1.` list markers, or contains `**`, `__`, or `[text](url)`. Plain text never switches views.
- The file mode preview (Browse) renders too, since that box is already read-only.
- Only the display changes. `generate.py`, the saved `input\<name>.md`, the name suggestion, Preview audio and the script check all keep using the raw text.
- No new dependency: a small renderer built on `tkinter.Text` tags (about 80 lines in a new `md_preview.py`), covering headings 1 to 6, bold, italic, inline code, block quotes, lists, rules, links, and Kokoro's `[word](/ipa/)` markup shown as the plain word.
- Not covered: tables, images, nested lists deeper than two levels. They show as plain text (the linter already tells the user to keep tables out of narration).

## Files touched

`ui.py` (view toggle, wiring), new `md_preview.py` (renderer, unit-testable without a window), `ui_theme.py` (tag fonts and colours), `README.md`, `AGENTS.md`, `CHANGELOG.md`. Not `generate.py`.

## Decisions for you

1. Default view after pasting Markdown: **Preview** (recommended) or stay on Edit?
2. Also render the read-only File-mode box? Recommended: yes.
3. Ship as **1.2.0** together with the copy button and the linter/skill changes already in `CHANGELOG.md` (Unreleased).

## Test plan

Renderer unit tests on the sample and on a script with every construct; scratch-folder window harness: paste Markdown, assert Preview shows and raw text is unchanged, toggle, edit, convert reads the raw text; screenshot from a scratch folder (never the real `output\`).
