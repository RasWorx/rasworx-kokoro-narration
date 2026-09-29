# Kokoro Python API (kokoro 0.9.4) and voice blending

Read this when the user wants something `generate.py` cannot do from its command line: weighted voice blends, different voices per section, word timestamps, a custom script, or when you need to explain how `generate.py` works inside. All code below was run successfully in this project's `.venv` (torch 2.11 cu128, RTX 5050).

## Contents

1. How generate.py drives Kokoro
2. KPipeline constructor and call
3. Result objects and timestamps
4. Voice blending (three verified methods)
5. Sharing one model across accents
6. Patterns for custom scripts

## 1. How generate.py drives Kokoro

- Builds one `KPipeline(lang_code=..., repo_id="hexgrad/Kokoro-82M", device=...)`. `--accent a|b` picks the G2P; without it, `accent_of()` uses the first letter of the first voice (or of a `.pt` file's name), falling back to `a`.
- Splits text into paragraphs on blank lines, calls `pipeline(para, voice=..., speed=..., split_pattern=None)` per paragraph, and appends `--pause` seconds of silence after each one.
- `split_pattern=None` means a whole paragraph goes to misaki at once; misaki then chunks internally at ≤510 phonemes, preferring sentence ends (`!.?…`), then `:;`, then `,—`. So long paragraphs are safe.
- Audio is float32 at **24 000 Hz mono**, written with `soundfile` as MP3 (falls back to WAV).
- `resolve_voice()` turns every `.pt` part of `--voice` into an absolute path (as given, else relative to the project root) and exits with `Voice file not found` otherwise. So `--voice af_heart,af_bella`, `--voice voices\blend.pt` and even `--voice af_heart,voices\blend.pt` all work from the command line.
- Markdown cleaning keeps misaki pronunciation markup (`[w](/…/)`, `[w](-1)`, `[n](#a#)`) and strips ordinary links; see `pronunciation.md` section 3.

## 2. KPipeline

```python
from kokoro import KPipeline, KModel

pipeline = KPipeline(
    lang_code="a",                   # 'a' US English, 'b' UK English; aliases 'en-us', 'en-gb' also accepted
    repo_id="hexgrad/Kokoro-82M",    # pass it explicitly or kokoro prints a warning
    device="cuda",                   # 'cuda', 'cpu', or None (auto). 'cuda' without CUDA raises
    model=True,                      # True = load a model, False = phonemes only ("quiet"), or pass a KModel
    trf=False,                       # True = spaCy transformer tagger for G2P (slower, rarely needed)
)

for result in pipeline(
    text,                            # str or list[str]
    voice="af_heart",                # ID, "id1,id2" blend, path to .pt, or a torch tensor
    speed=1.0,                       # float, or callable(len_phonemes) -> float
    split_pattern=r"\n+",            # default; None = no pre-splitting
):
    audio = result.audio             # torch.FloatTensor on the model's device, or None
```

- Other lang codes: `e` Spanish, `f` French, `h` Hindi, `i` Italian, `p` Brazilian Portuguese (espeak-ng G2P, no smart chunking), `j` Japanese (`pip install misaki[ja]`), `z` Mandarin (`pip install misaki[zh]`). This project only installs English support.
- `speed` as a callable receives the phoneme count of the chunk, e.g. `speed=lambda n: 0.9 if n < 50 else 1.0` slows down short lines.
- `pipeline.generate_from_tokens("phoneme string", voice=...)` speaks raw misaki phonemes (≤510 chars) – useful for testing a pronunciation.

## 3. Result objects and timestamps

Each yielded `KPipeline.Result` has `graphemes` (text chunk), `phonemes`, `tokens` (English only: list of misaki `MToken`), `audio`, `pred_dur`, `text_index`. For English, tokens get `start_ts` / `end_ts` in seconds relative to that chunk – enough to build rough subtitles:

```python
offset = 0.0
for r in pipeline(text, voice="af_heart"):
    for t in r.tokens or []:
        if t.start_ts is not None:
            print(f"{offset + t.start_ts:7.2f}-{offset + t.end_ts:7.2f}  {t.text}")
    offset += len(r.audio) / 24000
```

(generate.py inserts paragraph pauses, so add `pause` to `offset` per paragraph if mirroring its output.)

## 4. Voice blending

A voicepack is a tensor of shape `[510, 1, 256]` (one style vector per phoneme-length). Blends are averages of these tensors.

**a) Equal blend – works straight from the command line**
```
.venv\Scripts\python generate.py input\ep.md --voice af_heart,af_bella --force
```
`load_voice` splits on commas and takes the mean.

**b) Weighted blend by repetition – also works from the command line**
Repeating a name weights it: `af_heart,af_heart,af_bella` = 2/3 heart + 1/3 bella (verified numerically identical to `(2*heart + bella)/3`). `af_heart,af_heart,af_heart,af_bella` = 75/25.
```
.venv\Scripts\python generate.py input\ep.md --voice af_heart,af_heart,af_bella --force
```

**c) Arbitrary weights – tensor or saved .pt**
```python
import torch
from kokoro import KPipeline
p = KPipeline(lang_code="a", repo_id="hexgrad/Kokoro-82M", device="cuda")
mix = 0.7 * p.load_voice("af_heart") + 0.3 * p.load_voice("af_bella")   # CPU tensors
for r in p(text, voice=mix): ...                                           # use directly
torch.save(mix, "voices/af_heart70_bella30.pt")                            # or save it
for r in p(text, voice="voices/af_heart70_bella30.pt"): ...                 # and load by path
```
Create `voices\` first. Then render with `generate.py --voice voices\af_heart70_bella30.pt`. Name blend files starting with the accent letter (`af_…`, `bm_…`) so the right accent is picked automatically, or pass `--accent`. Keep weights summing to 1. Pass the tensor while it is on the CPU (`load_voice` only recognises CPU float tensors; the pipeline moves it to the GPU itself).

Blending tips: mix voices of the same accent and gender for a natural result; cross-gender blends give androgynous voices; cross-accent blends (`af_*` + `bf_*`) work but the accent follows the pipeline's `lang_code`. Always audition with `scripts/preview_voices.py`, which accepts all three forms.

## 5. One model, several accents

The model is language-agnostic; only G2P differs. Load the model once and share it:

```python
model = KModel(repo_id="hexgrad/Kokoro-82M").to("cuda").eval()
us = KPipeline(lang_code="a", repo_id="hexgrad/Kokoro-82M", model=model)
uk = KPipeline(lang_code="b", repo_id="hexgrad/Kokoro-82M", model=model)
```

## 6. Patterns for custom scripts

- Put one-off scripts in the scratchpad or a new file; do not rewrite `generate.py` unless the user asks. If a feature is wanted permanently (e.g. per-section voices), propose a small, backwards-compatible `generate.py` change that keeps the `input\` → `output\` workflow and existing flags.
- Reuse the project's text handling: `sys.path.insert(0, project_root)` then `from generate import load_text, paragraphs_of, write_mp3, resolve_voice, accent_of, SAMPLE_RATE`. Set `sys.dont_write_bytecode = True` first so no `__pycache__` appears in the project.
- Collect `r.audio.cpu().numpy()` chunks and `np.concatenate` them; insert `np.zeros(int(24000 * seconds), dtype=np.float32)` for silence.
- Two-voice dialogue: prefix lines like `A: ...` / `B: ...`, map prefixes to voices, render each line with its voice, join with short silences.
- Always run with `.venv\Scripts\python.exe`, never the system Python 3.14.
