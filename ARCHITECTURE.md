# ARCHITECTURE.md

## Shape

```
                 storyboard.json  ──validate()──►  every stage reads it, none writes it
                        │
     ┌──────────────────┼────────────────────┬─────────────────────┐
     ▼                  ▼                    ▼                     ▼
 narration.py      keyframes.py         kaggle/music (GPU)    (optional Wan clips)
 Gemini TTS        Cloudflare FLUX       ACE-Step 1.5          outputs/clips/
 outputs/narration outputs/keyframes     outputs/music
     │  manifest.json  │ manifest.json        │ candidate_N.wav
     └────────┬────────┴──────────────────────┘
              ▼
   common.timeline()  ── narration length sets each shot's length
              ▼
   radio_cut.py (user test 1)      assemble.py → outputs/final/film_9x16.mp4, film_16x9.mp4
```

## The contract

`storyboard.json` is the single source of truth: meta (title, language, fps, formats), style (style block, negative list, voice), **references** (bowl, family, home, each with a fixed description reused verbatim), 8–12 **shots** (beat, reason, shot size, minimum length, keyframe prompt/refs/seed, motion, narration + English subtitle), **music** (caption, bpm, key, seeds, cues, ducking), and the **end card**.

`schema/storyboard.schema.json` (JSON Schema 2020-12, `additionalProperties: false` everywhere) plus `validate.py` cross-field checks run before every stage: unknown reference ids, duplicate ids, subtitle lines over 48 characters or 2 lines, music cues pointing at missing shots, and a minimum film length over 90 s. A broken contract fails in milliseconds instead of after GPU time. `tests/` exercises these rules.

## Caching: only what changed is regenerated

Each stage computes `input_hash(...)` (SHA-256 of a canonical JSON of its inputs) and stores it in its manifest next to the output path.

| Stage | Hash covers | Consequence |
|---|---|---|
| Narration | voice, style instruction, text (model is excluded, see below) | edit one line → one TTS call |
| Reference image | model, full prompt, seed, size | edit the bowl → bowl regenerates |
| Shot keyframe | model, full prompt, seed, size, **hashes of the references it uses** | edit the bowl → every bowl shot regenerates automatically; edit one shot → only that shot |
| Shot clip (assembly) | keyframe hash, motion, duration, format, title overlay | new narration timing → only affected clips re-render |

The narration hash leaves out the model on purpose: a fallback model can fill in when the primary is rate-limited, and `--unify` re-generates exactly the lines whose recorded model differs from the primary, so the film has one voice (FAILURES F05).

A cache hit is still logged (`"cache_hit": true`), so `runs.jsonl` shows both what was generated and what was reused.

## Timeline

`common.timeline()` sets each shot's length to `max(min_duration_s, narration + 0.5 s lead + 0.8 s tail)`. Picture is cut to the voice, as professionals do. Assembly joins clips with 0.5 s dissolves whose start is exactly the next shot's start, so narration, subtitles and picture stay in sync. The same timeline drives the radio cut, so user test 1 heard the final timing.

## Failure handling

| Failure | Where | Handling |
|---|---|---|
| Transient errors, 429, 5xx | `common.retry` | exponential backoff |
| Permanent errors (HTTP 400) | `common.PermanentError` | never retried (no wasted quota) |
| TTS per-minute rate limit | `narration._tts` | 20 s spacing; on 429 wait 65 s on the **same** model; then fall back; a request a model rejects (400) skips to the next model |
| SDK retry loops that hang | `narration._call_with_timeout` | 45 s timeout in a daemon thread → treated as quota |
| Image model failure | `keyframes._generate` | fall back to FLUX.1 schnell (text only), logged with its model name |
| Missing Wan clip | `assemble._shot_clip` | pan-and-zoom over the keyframe |
| Missing music | `assemble._music_source` | placeholder drone, logged as such |
| Missing Ethiopic font | `assemble` | warning; Amharic overlay skipped, English kept |
| Windows paths in FFmpeg filters | `assemble._ff` | FFmpeg runs from the repo root with relative paths; manifests store `/` paths |
| Review aids (contact sheet) | `keyframes.contact_sheet` | wrapped so they can never break a stage |

## Secrets and reproducibility

Keys live only in `.env` (git-ignored; `.env.example` lists the names). Seeds for every image and music candidate are in the storyboard, not in code. Generated files are kept in `outputs/` so a clean clone can rebuild the film from cache, and `python -m pipeline.run` regenerates anything missing.
