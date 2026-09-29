# Pronunciation and text preparation

Kokoro turns text into phonemes with **misaki** (its own G2P library), then speaks the phonemes. Almost every "it said that wrong" problem is a text-to-phoneme problem, so check phonemes first:

```
.venv\Scripts\python .agents\skills\kokoro-help\scripts\phonemes.py "The text that sounds wrong."
.venv\Scripts\python .agents\skills\kokoro-help\scripts\phonemes.py --file input\episode-01.md --words
```

Everything below was checked against the installed kokoro 0.9.4 / misaki 0.9.4 in this project's `.venv`.

## Contents

1. How misaki reads things by default (numbers, symbols, abbreviations)
2. Fixing pronunciation: rewriting vs. inline phoneme overrides
3. How generate.py treats this markup in `.md` files
4. Stress control
5. Number flags
6. The phoneme alphabet
7. Pauses and rhythm

## 1. Default reading behaviour (verified)

| Input | Spoken as | Verdict |
|---|---|---|
| `$12.50` | "twelve dollars and fifty cents" | good |
| `45%` | "forty-five percent" | good |
| `2026`, `1984` | "twenty twenty-six", "nineteen eighty-four" | good (years) |
| `1990s`, `1st`, `3rd` | "nineteen nineties", "first", "third" | good |
| `1,234,567` | "one million two hundred thirty-four thousand..." | good |
| `150 people` | "one hundred fifty people" | fine; `[150](#a#)` gives "a hundred fifty" |
| `1500 people` | "fifteen hundred people" | **any 4-digit number is read as a year** |
| `3/4/2026` | "three four twenty twenty-six" | **bad** – write "March fourth, twenty twenty-six" |
| `555-1234` | "five hundred fifty-five, twelve thirty-four" | **bad** – write "five five five, one two three four" |
| `Version 2.0` | "version two" | **drops ".0"** – write "version two point oh" |
| `10:30am` | "ten thirty A M" | acceptable; "ten thirty in the morning" is smoother |
| `Dr. Smith` | "doctor Smith" | good |
| `St. John`, `James St.` | "saint." then a stop | **bad** – `St.` is always "saint", even for street; write "Saint John", "James Street" |
| `e.g.`, `etc.`, `Mr.` | "ee gee", "et cetera", "mister" | write "for example" instead of e.g. |
| `$5.50`, `£3`, `€10` | dollars and cents, pounds, euros | good |
| `R100`, `ZAR 50` | "ar one hundred", "Z A R fifty" | **bad** – South African rand is not supported; write "one hundred rand" |
| `082 555 1234` | "eighty-two five hundred fifty-five twelve thirty-four" | **bad** – write digits as words |
| `7:30 pm` | "seven thirty P M" | fine; colon adds a tiny pause |
| `NASA`, `SQL` | "nasa", "sequel" | known acronyms read as words |
| `API`, `MP3` | "A P I", "M P three" | spelled out |
| `&`, `+`, `@` | "and", "plus", "at" | good |
| made-up words | espeak-ng fallback guess | check them |

Rule of thumb for narration scripts: **spell out** dates, phone numbers, version numbers, codes, 4-digit non-year quantities, and Latin abbreviations. Leave simple money, percentages, years, ordinals and ordinary counts as digits.

## 2. Fixing a mispronounced word

Try in this order:

1. **Respell it phonetically in plain English** – works in both `.txt` and `.md`, zero risk. `Nguyen` → `Win`, `Hermione` → `Her-my-oh-nee`, `Siobhan` → `Shiv-awn`. Hyphenated pieces each get their own stress (verified: `Koh-koh-roh` → `kˈOkˈOɹˈO`, slightly choppy), so prefer a respelling that reads as one natural word, and check the result with `phonemes.py`.
2. **Inline phoneme override** (misaki Markdown-link syntax) – exact control:
   ```
   [Kokoro](/kˈOkəɹO/) is a text to speech model.
   I [read](/ɹˈɛd/) that book yesterday.
   ```
   The text inside `[...]` is what shows in the transcript; the IPA-style string between slashes is spoken. Use misaki's alphabet (section 6), and copy phonemes from `phonemes.py --words` output of a similar word as a starting point.

Verified: `Kokoro` alone → `kəkˈɔɹO` (wrong stress); `[Kokoro](/kˈOkəɹO/)` → `kˈOkəɹO`.

## 3. How generate.py treats this markup in `.md` files

`generate.py` cleans Markdown before speaking and turns ordinary links `[text](url)` into `text`. It deliberately **keeps** misaki markup, so overrides work in `.md` and `.txt` alike:

- `[word](/phonemes/)` – kept (a single `/…/` segment with no inner slash; a relative link like `[page](/docs/page/)` is still treated as a link)
- `[word](-1)`, `[word](+2)`, `[word](0.5)` – kept
- `[123](#a#)` – kept
- anything else, e.g. `[site](https://…)`, `[x](./a.md)` – reduced to its text

A list item or heading that ends with an override still gets its automatic full stop. `phonemes.py --file` applies the same cleaning, so what it shows is what will be spoken.

Known misaki quirk: an override is matched to words by position, and spaCy occasionally merges a link word with the next punctuation (seen with a single letter: `[v](0.5).`). Every later override in that paragraph then shifts by one word. If `phonemes.py` shows an override on the wrong word, rephrase or add a space before the punctuation.

## 4. Stress control

Put a number in the link target to adjust a word's stress (works for dictionary words):

| Syntax | Effect |
|---|---|
| `[word](-1)` | demote stress one level (primary → secondary) – de-emphasise |
| `[word](-2)` | remove stress entirely |
| `[word](+1)` / `[word](1)` | promote stress (add or raise) |
| `[word](+2)` / `[word](2)` | force primary stress – emphasise |
| `[word](0)`, `[word](0.5)`, `[word](-0.5)` | add secondary stress if the word has none |

Verified: `I [really](-1) mean it` → `ɹˌiᵊli` (secondary); `[really](+2)` → `ɹˈiᵊli` (primary); `[read](-2)` → `ɹɛd`. Stress can also change which dictionary pronunciation is chosen (`[read](0.5)` gave `ɹˈid`), so always check with `phonemes.py`. The audible effect is subtle; do not expect acted emphasis.

**Not supported:** text aliases such as `[Kokoro](ko ko ro)`. In misaki 0.9.4 anything in the parentheses that is not `/phonemes/`, `#flags#` or a number is silently dropped and only the bracketed word is read. Write respellings directly in the text instead.

## 5. Number flags

`[number](#flags#)` changes how a number is expanded. Flags (can combine):

- `a` – "a hundred" instead of "one hundred": `[150](#a#)` → "a hundred fifty"
- `n` – insert "and" British-style: `[101](#n#)` → "one hundred and one"
- `&` – keep num2words' own "and"

## 6. misaki English phoneme alphabet (cheat sheet)

misaki uses IPA plus a few single-letter shortcuts for diphthongs:

| Symbol | Sound | Example |
|---|---|---|
| `A` | eɪ | great `ɡɹˈAt` |
| `I` | aɪ | file `fˈIl` |
| `O` | oʊ (US) | go `ɡˈO` |
| `Q` | əʊ (UK "go") | British voices |
| `W` | aʊ | cloud `klˈWd` |
| `Y` | ɔɪ | voice `vˈYs` |
| `ʤ`, `ʧ` | j, ch | John `ʤˈɑn`, March `mˈɑɹʧ` |
| `T` | American flap t | better `bˈɛTəɹ` |
| `ᵊ` | reduced schwa | people `pˈipᵊl` |
| `ˈ` / `ˌ` | primary / secondary stress, placed before the stressed vowel's syllable | |
| `ɹ` | English r | |

Full list: <https://github.com/hexgrad/misaki/blob/main/EN_PHONES.md>. American and British G2P give different phonemes (`--british` in `phonemes.py`), so craft overrides for the accent you will use.

## 7. Pauses and rhythm

- **Paragraph pause** – blank line between paragraphs; `generate.py --pause` sets the silence (default 0.4 s). This is the only pause length you can set exactly.
- Inside a paragraph, punctuation pauses are short and fairly similar (measured on af_heart at speed 1.0): no punctuation ≈ 0.04 s, comma ≈ 0.18 s, `—` or `…` ≈ 0.2 s, full stop / colon / semicolon / `...` ≈ 0.22–0.25 s. Lower speed stretches them 10–20%.
- Stacking punctuation (`..`, `!!`, `,,`) adds almost nothing and can sound odd. A spaced hyphen ` - ` is not reliably treated as a dash; use `—`.
- A heading in `.md` becomes its own short paragraph, so it gets a pause before and after.
- The only reliable way to get a long pause is silence between segments, which is what paragraph breaks + `--pause` do. Want a longer beat mid-section? Start a new paragraph. Want a dramatic pause? End a paragraph and raise `--pause`, or put the key line in its own paragraph.
- There is no SSML (`<break>`, `<emphasis>`, `<prosody>`); tags are stripped from `.md` and would be read or garbled in `.txt`.
- Very short inputs (one or two words alone) can sound clipped or rushed; give headings and one-liners a full sentence where possible.
