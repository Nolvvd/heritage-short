# COSTS.md

Measured from `runs.jsonl` (89 lines on 2026-11-26, 00:25–11:43 UTC, before the music run), plus the Kaggle session log. Everything ran on free tiers; list prices show what it would cost at scale.

## Per stage

| Stage | Model | Calls (ok / cached / failed) | Latency, median (max) | Compute | List-price equivalent |
|---|---|---|---|---|---|
| Narration | Gemini 3.8 Flash TTS | 13 / 18 / 3 quota | 7.5 s (54.7 s incl. waits) | API | $9.00 per 1M audio tokens |
| Narration | Gemini 3.8 Flash-Lite TTS | 12 / 6 / 3 quota + 1 error | 8.4 s (49.4 s incl. waits) | API | $6.00 per 1M audio tokens |
| Keyframes | FLUX.2 [klein] 4B, 1536×1536 | 25 / 4 / 0 | 10.8 s (25.7 s) | API | **$0.066** (logged per call: 9 output tiles × $0.000287 + input reference tiles) |
| Music | ACE-Step 1.5 turbo, 3 × 90 s | 3 / 0 / 0 (after 2 failed sessions: F11, F12) | 8.2 s (11.3 s) | Kaggle Tesla T4: 0.46 GPU-min generating; the session was 17.6 min in all (install 95 s, model load 45 s, weight download), peak 7.8 GB | $0 (open weights, MIT) |
| Radio cut | FFmpeg | 3 | 7.8 s | laptop CPU | $0 |
| Assembly, draft 9:16 | FFmpeg | 1 | 15 s | laptop CPU | $0 |

**Narration list-price estimate:** about 210 s of audio generated in total (the 134 s first attempt that read its instructions aloud, the 58 s fixed version, and re-takes). At roughly 25 audio tokens per second (an assumption, not measured), that's about 5,000 output tokens, so **about $0.04** even at the Flash TTS rate. Text input is negligible.

**Total so far: about $0.10 at list prices, $0 actually paid.**

## Where the time went

| | Time |
|---|---|
| Kaggle music session (successful) | 1,057 s total: `uv sync` 95 s, model load 45 s, weights download + generation the rest; plus two failed attempts (F11, F12) |
| TTS rate-limit waiting | most of the narration wall time: 20 s spacing + 65 s cool-downs |
| One full keyframe pass (11 shots) | about 2 min |
| Full-resolution assembly, both formats | _(fill after final render)_ |

## Free-tier limits actually met

- **Gemini TTS:** about 4–5 requests per minute per model, counted separately for Flash and Flash-Lite (F03–F05). Not a daily cap, as I first assumed.
- **Cloudflare Workers AI:** about 40 images at 1536² used without hitting the daily allowance.
- **Kaggle:** a phone-verified account is needed for internet; Python 3.13 kernel (F11).

## Frontier comparison

Not done: no access to the paid frontier lane (Omni Flash, Nano Banana, Lyria 3.5).
