# Kokoro formatting evidence

This is the research behind the `tts-output` rules, gathered on 2026-09-29. It covers Kokoro-82M 0.9.4 with misaki and the US voices `af_kore` and `af_heart`, rendered on the GPU at speed 1.0. The findings are sorted by how much to trust them:

- **Verified in code**: read from the Kokoro or misaki source code, or stated by the maintainer (hexgrad).
- **Measured locally**: rendered and measured in `C:\Github\kokoro`. The WAV files are in `output\previews\format-tests\`.
- **Anecdotal**: reports from users or blog claims that have not been checked.

## Contents
1. [How Kokoro chooses delivery](#1-how-kokoro-chooses-delivery)
2. [Punctuation](#2-punctuation)
3. [Capitals, emphasis and markup](#3-capitals-emphasis-and-markup)
4. [Chunk and sentence length](#4-chunk-and-sentence-length)
5. [Text bugs to avoid](#5-text-bugs-to-avoid)
6. [Voices](#6-voices)
7. [Wrapper ecosystem](#7-wrapper-ecosystem)
8. [Folklore that does not hold up](#8-folklore-that-does-not-hold-up)
9. [General writing-for-audio guidance](#9-general-writing-for-audio-guidance)
10. [Open questions](#10-open-questions)

## 1. How Kokoro chooses delivery

- **Verified in code.** The model cannot produce emotion on request. hexgrad: "Kokoro has not yet seen 'sad' or 'angry' in training, therefore it cannot produce these at inference, and SSML syntax does not cover that flaw." Sources: https://github.com/hexgrad/kokoro/issues/36 and https://github.com/hexgrad/kokoro/issues/89
- **Verified in code.** The training data was "mostly long-form reading and narration, not conversation". Source: https://huggingface.co/hexgrad/kLegacy/blob/main/v0.19/README.md
- **Verified in code.** The voice style is chosen only from two things: the voice name and the length of the utterance.
  - In the code this is `model(ps, pack[len(ps)-1], speed)`.
  - hexgrad: "the punctuation texture `.?!` or the text sentiment are not yet being used". He adds that averaging the styles "may explain why the voices are somewhat flat-sounding".
  - Sources: https://pypi.org/project/kokoro/0.2.1/ and https://github.com/hexgrad/kokoro/blob/main/kokoro/pipeline.py
- **Verified in code.** The only official intonation advice is to try punctuation `;:,.!?—…"()“”` or the stress marks `ˈ` and `ˌ`. This comes from the demo Space. Source: https://huggingface.co/spaces/hexgrad/Kokoro-TTS/blob/main/app.py

## 2. Punctuation

- **Verified in code.** Only these punctuation marks reach the model: `; : , . ! ? — … " ( ) “ ”`.
  - misaki turns straight quotes into curly `“ ”`, and turns a standalone `-` or `–` into `—`.
  - Every other symbol is dropped.
  - Sources: https://huggingface.co/hexgrad/Kokoro-82M/blob/main/config.json and https://github.com/hexgrad/misaki/blob/main/misaki/en.py
- **Measured locally.** A spaced ` -- ` is dropped completely. The phonemes show a double space and no `—`, so there is no pause.
  - `Wait - then` and `Wait – then` both become `—`.
  - `...` is kept as `...`, and `…` is kept as `…`.
- **Measured locally (the previous session).** Pause lengths on `af_heart`:

  | Text | Pause |
  |---|---|
  | No punctuation | about 0.04 s |
  | Comma | about 0.18 s |
  | `—` or `…` | about 0.2 s |
  | `.` `:` `;` `...` | about 0.22–0.25 s |
  | Stacked punctuation | adds almost nothing |

  An ellipsis inside a sentence added about 0.15 s compared with no punctuation.
- **Measured locally.** Test sentence: "The results came back this morning" ending in `.`, `!` or `?`.
  - The audio does change: the RMS difference was 0.07–0.09, against 0.006–0.008 run-to-run noise.
  - The pitch contour at the end of the sentence does not change. On Kore the last 10 pitch frames were the same within 2 Hz for `.`, `!` and `?`.
  - On Heart, `!` and `?` give almost identical contours. Both fall, from 222 Hz to 145 Hz.
  - `!!` is the same as `!`.
- **Measured locally.** Questions:
  - On Kore, "Did the results come back this morning?" falls to the bottom of the voice's range, exactly like the same words ending in `.`.
  - Tag questions (", right?") don't rise either.
  - On Heart, a yes/no question may rise slightly at the very end. This is ambiguous, because the pitch tracker may have made an octave error, so judge it by ear.
  - Users report the same: https://github.com/hexgrad/kokoro/issues/78, /issues/264 (with audio), /issues/194, /issues/215; https://github.com/remsky/Kokoro-FastAPI/issues/286 and /305; https://github.com/thewh1teagle/kokoro-onnx/issues/59
- **Anecdotal.** `!`, a closing `"` and opening quotes take up real time in the audio.
  - One user measured a breathy tail after `!"` and `."`, and the next word starting early inside an opening quote.
  - Source: https://github.com/hexgrad/kokoro/issues/365
- **Anecdotal.** Parentheses and a sentence-final "etc." give no pause. Source: https://github.com/remsky/Kokoro-FastAPI/issues/308

## 3. Capitals, emphasis and markup

- **Verified in code.** How misaki treats capitals (`cap_stresses = (0.5, 2)`):
  - A capitalised word gets stress 0.5.
  - An ALL-CAPS word gets stress 2, which only adds stress to a word that has none.
  - An ALL-CAPS word tagged as a proper noun can be spelled out letter by letter.
- **Measured locally.** `THIS` gives exactly the same phonemes as `[this](+2)`, and the audio is identical. `The IT team` became "I T". `It was NOT fine` only stressed "not".
- **Verified in code.** Stress markers work like this:

  | Marker | Effect |
  |---|---|
  | `[word](-2)` | Removes all stress |
  | `(-1)` | Demotes primary stress to secondary |
  | `(0.5)` or `(1)` on an unstressed word | Adds secondary stress |
  | `(1)` or more on a word with only secondary stress | Promotes it to primary |
  | `(2)` on an unstressed word | Adds primary stress |
  | Any marker on a word that already has primary stress | Nothing changes |

  Source: `apply_stress` in https://github.com/hexgrad/misaki/blob/main/misaki/en.py
- **Anecdotal, but consistent.** The audible effect of stress markers is "very subtle… for some sentences it's basically unnoticeable". Sources: https://github.com/hexgrad/kokoro/issues/170 and https://github.com/remsky/Kokoro-FastAPI/issues/319
- **Verified in code.** Markdown handling:
  - misaki has no italic or bold markup.
  - `generate.py` strips `*`, `_` and `**` before speaking.
  - Asterisks left in the text can be read aloud: https://github.com/hexgrad/kokoro/issues/217
- **Verified in code.** Kokoro-FastAPI handles SSML like this: `<emphasis>` and `say-as` are stripped, and `prosody` pitch and volume are ignored. The emotion tags that some blogs recommend (`[whisper]`, `(excited)`) do nothing.

## 4. Chunk and sentence length

- **Verified in code.** The author's guidance on length:
  - Voices do badly on very short utterances, under about 10–20 tokens.
  - They rush on long ones, over about 400 tokens.
  - The sweet spot is about 100–200 tokens.
  - Source: https://huggingface.co/hexgrad/Kokoro-82M/blob/main/VOICES.md
- **Verified in code.** How text is split into chunks:
  - `generate.py` passes each paragraph whole (`split_pattern=None`).
  - KPipeline only splits a chunk once it passes 510 phonemes. It prefers to split at `!.?…`, then at `:;`, then at `,—`.
- **Measured locally.** English text has roughly 1.05 phonemes per character, measured on `input\sample.md`. So 100–200 phonemes is about 100–200 characters, or 17–35 words. The 510-phoneme limit is about 85 words.
- **Measured locally.** Speaking rate against chunk length:

  | Voice | Long sentence (227 phonemes) | Short sentences (202) | Fragments (79) |
  |---|---|---|---|
  | Kore | 16.7 ph/s | 16.2 ph/s | 16.1 ph/s |
  | Heart | 17.4 ph/s | 16.4 ph/s | 15.4 ph/s |

  Longer chunks are spoken faster. The effect is clearer on Heart.
- **Verified in code.** Kokoro-FastAPI aims for chunks of 175–250 tokens, with a hard maximum of 450. Its README says long chunks sound "rushed" and that "artifacts in intonation can increase with smaller chunks". Source: https://github.com/remsky/Kokoro-FastAPI
- **Anecdotal.** Single words often come out wrong, for example "six" as "ah-six-ah". The fix is to embed the word in a longer sentence. Source: https://news.ycombinator.com/item?id=48821576

## 5. Text bugs to avoid

- **Measured locally.** Curly apostrophes:
  - `the man’s.` becomes `mˈæn”ˈɛs`, read as "man-ESS".
  - The straight `'` gives the correct `mˈænz`.
  - Source for the bug: https://github.com/hexgrad/misaki/issues/100
  - The same issue reports that `wasn’t` can be read as "was". The local test read it correctly, but use straight apostrophes anyway.
- **Measured locally.** ` -- ` disappears, as described in section 2.
- **Verified in code.** A mid-sentence stray pause usually means the phonemizer produced something odd. Check the phonemes, then rephrase or respell. Source: https://github.com/thewh1teagle/kokoro-onnx/issues/11

## 6. Voices

- **Verified in code.** The official grades reflect the quality and amount of training data, not how expressive a voice is:

  | Voice | Grade |
  |---|---|
  | `af_heart` | A |
  | `af_bella` | A- |
  | `af_kore`, `af_nicole`, `af_aoede`, `af_sarah`, `af_nova` | C to C+ |
  | Best US male voices: `am_michael`, `am_fenrir`, `am_puck` | C+ |

  Source: https://huggingface.co/hexgrad/Kokoro-82M/blob/main/VOICES.md
- **Measured locally.** Kore sits lower and is flatter. Its median pitch is about 162 Hz against Heart's 204 Hz, and it reacts less to punctuation than Heart does.
- **Anecdotal.** Suggested voices by mood:
  - Heart: warm, emotional
  - Bella: warm, long-form
  - Nova: energetic
  - Puck: playful
  - A Heart and Bella blend "for energetic yet warm narration"
  - Sources: https://deapi.ai/blog/kokoro-tts-guide-how-to-control-41-voices-with-nothing-but-punctuation and https://github.com/GeekyGhost/ComfyUI-Geeky-Kokoro-TTS
- **Anecdotal.** Users on Hacker News find the male voices noticeably weaker than the female ones.

## 7. Wrapper ecosystem

- **Kokoro-FastAPI** rewrites text before speaking:
  - Converts `--` to `—`, curly quotes to straight, and "1-5" to "1 to 5".
  - Reads symbols as words.
  - Lowercases long ALL-CAPS words.
  - Expands Dr., Mr. and Ms.
  - Supports inline `[pause:1.5s]`.
  - Source: https://github.com/remsky/Kokoro-FastAPI
- **pdf-narrator** replaces dashes and semicolons with commas, removes footnote markers and page numbers, and adds a full stop to lines of more than 3 words. Source: https://github.com/mateogon/pdf-narrator
- **abogen** expands contractions by default, converts Roman numerals to words, and lowercases all-caps text inside quotes. Source: https://github.com/denizsafak/abogen
- **Kokoro-TTS-Pause** renders phrases separately and joins them with exact silences: 7 s after a chapter title, 2–3 s for drama, and speed 0.85 for meditation. Source: https://github.com/ibuhs/Kokoro-TTS-Pause
- **Anecdotal.** Adding 0.5–0.8 s of silence between batches made long text sound more natural. Source: https://github.com/thewh1teagle/kokoro-onnx/issues/84

## 8. Folklore that does not hold up

These claims come from blogs such as deapi.ai and kokoroweb.app. None of them came with tests:

| Claim | What the evidence shows |
|---|---|
| "`?` rises on yes/no questions" | No rise on Kore; contradicted by several GitHub reports |
| "`!` adds energy" | No measurable pitch change on Kore; small change on Heart |
| "`…` gives a 0.5–1 s falling pause" | Measured about 0.2 s |
| Emotion tags, emoji and `say-as` | Stripped or read aloud |

## 9. General writing-for-audio guidance

These points come from sources outside Kokoro. They still apply without SSML.

- Write the way you speak, with short and simple sentences and no jargon. Sources: https://learn.microsoft.com/en-us/style-guide/top-10-tips-style-voice and https://blog.videate.io/7-best-practices-writing-for-text-to-speech-voices
- Use contractions and vary sentence length, averaging around 8–10 words. Source: https://theelearningcoach.com/elearning_design/the-art-of-writing-great-voice-over-scripts/
- Sentence shape sets the pace. Long sentences sound steady, and fragments sound urgent or hesitant. Put the emotion in the words themselves. Spell out numbers and abbreviations. Source: https://elevenlabs.io/docs/best-practices/prompting
- Say who is speaking before the line, don't rely on formatting, and reintroduce characters who have been absent for a while. Source: https://www.audible.com/blog/writing-for-audio
- Page-style paragraphs run together when heard, so keep each speaking turn short. Source: https://developers.google.com/assistant/conversation-design/scale-your-design

## 10. Open questions

- Whether interjections ("Oh!", "Hmm.") change perceived emotion. They are phonemized fine, but nobody has tested this.
- Whether Heart really gives yes/no questions a slight rise.
- Whether a lower `--speed` reads as "sadder" or just slower. This is plausible, but only the meditation examples support it.
