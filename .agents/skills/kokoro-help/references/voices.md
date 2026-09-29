# Kokoro-82M v1.0 voices

Source: <https://huggingface.co/hexgrad/Kokoro-82M/blob/main/VOICES.md> (model v1.0, `kokoro-v1_0.pth`, 54 voices). Voice IDs are `<lang><gender>_<name>`: first letter = language/accent, second = `f` female / `m` male.

**Grades.** "Target" rates the quality of the voice's reference audio. "Data" is how much training audio the voice had: HH = 10–100 hours, H = 1–10 hours, MM = 10–100 minutes, M = 1–10 minutes. "Overall" combines them. More data generally means a steadier voice over a long narration.

## American English (`a*`, use with `lang_code='a'`)

| Voice | Gender | Target | Data | Overall | Notes |
|---|---|---|---|---|---|
| **af_heart** | F | – | – | **A** | Flagship. Warm and clear; best rated overall |
| **af_bella** | F | A | HH | **A-** | Warmer, slightly more expressive; excellent for long narration |
| af_nicole | F | B | HH | B- | Soft, breathy, close-mic "headphones" style; calm/ASMR feel |
| af_aoede | F | B | H | C+ | |
| **af_kore** | F | B | H | C+ | **Project default** (user's choice) |
| af_sarah | F | B | H | C+ | |
| af_alloy | F | B | MM | C | |
| af_nova | F | B | MM | C | |
| af_sky | F | B | M | C- | Little data; can wobble |
| af_jessica | F | C | MM | D | |
| af_river | F | C | MM | D | |
| **am_michael** | M | B | H | C+ | Best US male for narration |
| am_fenrir | M | B | H | C+ | Deeper |
| am_puck | M | B | H | C+ | Lighter, livelier |
| am_echo | M | C | MM | D | |
| am_eric | M | C | MM | D | |
| am_liam | M | C | MM | D | |
| am_onyx | M | C | MM | D | |
| am_santa | M | C | M | D- | Novelty |
| am_adam | M | D | H | F+ | Avoid |

## British English (`b*`, use with `lang_code='b'`)

| Voice | Gender | Target | Data | Overall | Notes |
|---|---|---|---|---|---|
| **bf_emma** | F | B | HH | B- | Best British voice; steady over long text |
| bf_isabella | F | B | MM | C | |
| bf_alice | F | C | MM | D | |
| bf_lily | F | C | MM | D | |
| **bm_george** | M | B | MM | C | Mature, documentary tone |
| **bm_fable** | M | B | MM | C | Storytelling tone |
| bm_lewis | M | C | H | D+ | |
| bm_daniel | M | C | MM | D | |

The "Notes" descriptions of character are informal listening impressions, not official; always audition with `scripts/preview_voices.py`.

## Other languages

| Code | Language | Voices | Needs |
|---|---|---|---|
| `j` | Japanese | jf_alpha (C+), jf_gongitsune, jf_nezumi, jf_tebukuro, jm_kumo | `misaki[ja]` |
| `z` | Mandarin | zf_xiaobei, zf_xiaoni, zf_xiaoxiao, zf_xiaoyi, zm_yunjian, zm_yunxi, zm_yunxia, zm_yunyang (all D) | `misaki[zh]` |
| `e` | Spanish | ef_dora, em_alex, em_santa | espeak-ng (bundled) |
| `f` | French | ff_siwis (B-) | espeak-ng |
| `h` | Hindi | hf_alpha, hf_beta, hm_omega, hm_psi (C) | espeak-ng |
| `i` | Italian | if_sara, im_nicola (C) | espeak-ng |
| `p` | Brazilian Portuguese | pf_dora, pm_alex, pm_santa | espeak-ng |

Status in this project (checked 2026-09-29): Spanish, French, Hindi, Italian and Brazilian Portuguese work out of the box, because the espeak-ng they rely on is bundled with the venv (`espeakng-loader`). `ef_dora` and `ff_siwis` were rendered successfully. Japanese fails with `No module named 'pyopenjtalk'` and Mandarin with `No module named 'ordered_set'`. To add them, run `uv pip install --python .venv\Scripts\python.exe "misaki[ja]"` (or `"misaki[zh]"`); this has not been tested here. Only install them if the user asks.

Use them with `generate.py` exactly like English: `--voice ef_dora` picks Spanish automatically, or pass `--accent e` for a `.pt` file. Notes:
- The espeak languages use simpler rule-based pronunciation, no dictionary, and no `[word](/phonemes/)` or stress overrides. Numbers are handled by espeak.
- Their chunking is basic: about 400 characters, split at `.!?`. A single very long sentence can be cut at 510 phonemes, so keep sentences moderate.
- Afrikaans, isiZulu, isiXhosa and other South African languages are not supported by Kokoro at all.

## Picking a voice: practical guidance

- **Default narration:** `af_kore` (project default). Top-graded alternatives: `af_heart`, `af_bella`.
- **Calm, intimate, meditation, bedtime:** `af_nicole` at `--speed 0.9`, or `af_heart` at 0.9 with `--pause 0.7`.
- **Male narrator:** `am_michael` (US) or `bm_george` (UK). Male voices are graded lower than the top female voices; blending can smooth them, e.g. `am_michael,am_fenrir`.
- **British:** `bf_emma` is the safest; `bm_fable` for stories.
- **Avoid D/F voices for 10–20 minute pieces**: artefacts that are fine in a sentence become tiring over a long clip.
- **Length sweet spot:** voices perform best on chunks of roughly 100–200 phonemes; very short lines (under ~20 phonemes) can sound clipped, and chunks near the 510 limit can sound rushed. Normal paragraphs are fine; avoid one-word paragraphs.

## Blends

Blending averages voicepacks, producing a new, consistent voice:

- `af_heart,af_bella` – 50/50, a popular richer female voice.
- `af_heart,af_heart,af_bella` – 67/33 (repeat a name to weight it).
- `am_michael,am_fenrir` – fuller male voice.
- `af_heart,am_michael` – androgynous; usually not what people want.
- Mixing `a*` with `b*` works, but the accent/pronunciation follows the pipeline language (the first voice's letter in `generate.py`, or `--accent`).

Arbitrary weights (e.g. 70/30 exactly) and saving a blend as a `.pt` file are covered in `python-api.md`.
