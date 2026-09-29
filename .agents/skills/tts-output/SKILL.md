---
name: tts-output
description: >-
  Write or rewrite text so a text-to-speech engine (tuned for Kokoro-82M, US
  English) reads it naturally and with the intended tone: calm, warm, serious,
  excited, urgent, sad. Produces a speech-ready .md/.txt narration script,
  checks it with a bundled linter, and fixes what the linter flags. Invoked by
  the user only, e.g. "/tts-output 15-minute narration about X" or
  "/tts-output input\draft.md".
argument-hint: "Topic to narrate, or a file to turn into a speech-ready script (optionally: length, mood, voice)"
disable-model-invocation: true
---

# TTS output

Turn a topic, notes, or an existing document into a script that sounds natural when a TTS engine reads it aloud. The rules below are tuned for **Kokoro-82M** with US English voices (tested on `af_kore` and `af_heart`), but the writing principles transfer to any neural TTS.

The single most important fact: **Kokoro has no emotion control.** Its author says the model "has not yet seen 'sad' or 'angry' in training". The voice style is chosen only from the voice name and the length of each chunk of text, never from punctuation or meaning. So tone must be carried by **the words, the sentence shapes, the paragraph lengths, the pauses, the speed and the voice choice**. Punctuation shapes rhythm, not feeling. Evidence and sources are in `references/kokoro-evidence.md`; read it when the user asks why, or before telling them that a trick does or does not work.

## Workflow

1. **Pin down the brief** from the arguments and conversation: source (topic, notes, or file), target length, mood, audience, and output location. Ask only about what you cannot infer. Defaults: about 150 words per minute of audio, a documentary tone, and a `.md` file.
2. **Choose where the file goes.**
   - In the Kokoro project (`C:\Github\kokoro`, with `generate.py` and `input\`), write to `input\<name>.md` and follow that project's `AGENTS.md` and `kokoro-help` skill to render it. Never overwrite an existing file in `input\` or `output\` without asking.
   - Elsewhere, write where the user says, or next to the source file as `<name>.tts.md`.
   - When rewriting an existing document, write a new file and leave the original untouched.
3. **Write for the ear** using the rules below.
4. **Lint it**, then fix every warning that matters and re-run until clean:
   ```
   python "%USERPROFILE%\.claude\skills\tts-output\scripts\check_tts_script.py" path\to\script.md
   ```
   In bash, the path is `"$USERPROFILE/.claude/skills/tts-output/scripts/check_tts_script.py"`. It uses only the Python standard library, so any Python 3.9+ works. In the Kokoro project, use `.venv\Scripts\python.exe`, not the system Python. Exit code 1 means warnings remain. Treat a warning as a strong hint, not a law: an acronym the linter doesn't know, or a deliberate short closing line, can stay if you judge it right. Say so in the report.
5. **Render if asked, or if you are in the Kokoro project and the user wants audio.** Use `generate.py <file>` and the `--speed`/`--pause`/`--voice` from the mood recipe. For a first listen, render a short excerpt to `output\previews\`.
6. **Report briefly**: the file path, word count and estimated minutes, the recommended voice/speed/pause flags, and any lines the user should check by ear (names, questions, rare words).

## Writing rules (verified unless marked)

**Paragraphs are the unit of delivery.** `generate.py` sends each paragraph (text between blank lines) to the model as one chunk. The author's sweet spot is 100–200 phonemes per chunk. Very short chunks sound clipped. Chunks near the 510-phoneme limit sound rushed, and anything longer is split automatically at a sentence end. One phoneme is roughly one character.
- Aim for **20–60 words (about 120–350 characters) per paragraph**. Stay under about 80 words (about 480 characters) so no paragraph gets split mid-thought.
- **Never leave a paragraph under about 8 words.** That includes headings, which are spoken as their own paragraph. Turn a heading into a full spoken sentence ("Part two: what went wrong at the plant.") or fold it into the next paragraph. Short fragments are fine **inside** a longer paragraph, because the whole paragraph is one chunk.
- Measured: longer chunks are spoken slightly faster. Heart went from 15.4 to 17.4 phonemes per second between short and long chunks.

**Punctuation sets pauses, not emotion.** Measured on `af_heart` at speed 1.0:
- A comma pauses about 0.18 s. `—` or `…` pause about 0.2 s. `.` `:` `;` pause about 0.22–0.25 s. Stacking marks (`!!`, `?!`, `. . .`) adds nothing.
- `!` and `?` barely change delivery. On Kore they are indistinguishable from `.`, and `!` and `?` sound almost the same on Heart. **Kore's pitch never rises at the end of a question**, even "Did the results come back?" So make questions obvious from the words ("Did it work? Here is the answer."), and don't rely on intonation.
- The only long, reliable pause is a **paragraph break** (default 0.4 s; set with `--pause`). Use a new paragraph for a dramatic beat, a topic change, or to let a point land.
- Dashes: write `—`, or ` - ` with spaces (converted to `—`). **` -- ` is silently dropped**, so no pause happens.

**Things that do nothing, or backfire:**
- ALL CAPS gives no extra loudness or emotion, only a small stress change. Short caps words may be spelled out ("IT" became "I T"). Keep caps for real acronyms.
- `*italics*` and `**bold**` are stripped. Emotion tags (`[excited]`, `(whispers)`), SSML, and emoji do nothing or get read aloud.
- Stress markers `[word](+2)` are barely audible and only affect short, unstressed words. Use them for pronunciation fixes, not emphasis.
- Curly apostrophes can break words: `man’s.` at the end of a phrase is read "man-ESS" (misaki bug). **Use straight apostrophes `'` and straight quotes.**
- Parentheses reach the model but give no clear pause. Rewrite asides as comma-bounded clauses or their own sentence.

**Make the words carry the tone.** A human reader would act. Kokoro won't, so write the emotion in:
- Name the feeling plainly when it matters: "This part is hard to hear." "And then, finally, good news."
- Put emphasis in **word order**. The stressed idea goes at the end of the sentence, or into a short sentence after a long one: "They checked every sensor. Every single one."
- Use contractions and everyday words. Write it the way you would say it, then read it in your head at speaking pace.
- Vary sentence length. Long, flowing sentences sound calm and steady; runs of short sentences sound urgent. Avoid four or more clauses chained with commas.
- For quoted speech, put the speaker and their state **before** the line: "She paused, and her voice dropped. 'You're leaving?'"
- Interjections ("Oh,", "Well,", "Hmm.") are read as words. They can add a conversational feel, but this is untested for emotion, so use them sparingly.

**Spell out anything ambiguous**, because Kokoro guesses:
- Numbers and dates: "twenty twenty-six", "three point five", "March fourth".
- Currency and units: "forty-seven dollars", "one hundred rand", "ten kilobytes".
- Symbols and abbreviations: "and" not `&`, "percent" not `%`, "for example" not `e.g.`, "Doctor" not `Dr.`, "et cetera" not `etc.`
- Kokoro reads a 4-digit number that isn't a year as a year ("1500" becomes "fifteen hundred"). `St.` is always "saint".
- For a word that still sounds wrong, respell it phonetically or use Kokoro's `[word](/phonemes/)` syntax. In the Kokoro project, the `kokoro-help` skill has the phoneme checker.

**Keep out of narration**: tables, code, URLs, footnote markers, bullet-point fragments (turn lists into sentences), and "see above" or "as shown below".

## Mood recipes

Speed and pause are `generate.py` flags (`--speed`, `--pause`). Sentence shape is how you write. These are starting points: suggest a short preview before a long render.

| Mood | Writing | `--speed` | `--pause` | Voice notes |
|---|---|---|---|---|
| Calm, documentary (default) | Medium to long sentences, 2–3 per paragraph, gentle transitions | 0.95–1.0 | 0.4–0.5 | `af_kore` (user default) or `af_heart` |
| Warm, reassuring | "You" and "we", contractions, softer words, longer sentences | 0.9–0.95 | 0.5–0.6 | `af_heart`, `af_bella`, or a Heart+Bella blend |
| Serious, sad, reflective | Plain words, shorter paragraphs, a new paragraph before key lines | 0.85–0.9 | 0.7–1.0 | `af_heart`; slower speed does most of the work |
| Excited, upbeat | Short punchy sentences grouped **inside** 30–50 word paragraphs, active verbs, "and then" momentum | 1.05–1.1 | 0.3 | `af_heart` or `af_bella`; Kore stays even |
| Urgent, tense | Fragments inside a paragraph ("Three years. Two leaders. No money."), present tense | 1.05 | 0.3, then a single paragraph break for the reveal | Any |
| Meditation, sleep | Long soft sentences, repetition, many short paragraphs of 20+ words | 0.8–0.85 | 1.5–3.0 | `af_heart`, `af_nicole` |

Voice matters more than any punctuation trick. The official grades are `af_heart` A, `af_bella` A-, and `af_kore` C+. Kore is the user's chosen default and delivers evenly; if a script needs more warmth or energy, suggest a Heart or Bella preview rather than more exclamation marks. If real acting, whispering or voice cloning is needed, Kokoro can't do it; the researched next step is Chatterbox-Turbo.

## Example

Before (reads badly):
> ## Results
> The results were AMAZING!!! (Better than expected -- see Table 2.) Revenue rose 23% to $4.5M in Q3 2025.

After (speech-ready):
> Now for the part everyone was waiting for: the results.
>
> They were better than anyone expected. In the third quarter of twenty twenty-five, revenue rose by twenty-three percent, to four and a half million dollars. For a team this small, that's remarkable.

What changed and why: the one-word heading became a full sentence, so it isn't clipped. Caps and `!!!` were dropped because they add nothing. The aside was turned into its own sentence. `--` was removed because it is silently dropped. Figures and the quarter were spelled out. The emotion ("remarkable") is now in the words.

## Other engines

The writing rules (paragraph sizing, words carrying tone, spelled-out numbers, no markup) transfer to any neural TTS. The "does nothing" list is Kokoro-specific. Engines such as Azure, Polly and Google do support SSML, and some (ElevenLabs v3) support audio tags. If the user targets one of those, use that engine's own controls and say which parts of this skill don't apply.
