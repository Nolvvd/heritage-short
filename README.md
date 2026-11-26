# Around One Bowl (በአንድ ሳህን ዙሪያ)

An 85-second Amharic short film about my family's Eid al-Fitr mornings: waking each other before dawn, sitting on the floor around one bowl of genfo, racing for the butter in the middle, making dua, and walking to the stadium for prayer. It is generated end to end by a small, reproducible pipeline from one file, `storyboard.json`.

**Watch:** [vertical 9:16](https://youtube.com/shorts/q2Oz-x5BJ0c) · [horizontal 16:9](https://youtu.be/lCcljUvVNNM) (unlisted, AI-labelled) · [pipeline walkthrough](https://youtu.be/1GrMu0Rhi8w) · [post on X](https://x.com/VvdNole/status/2125986257159205304)

**Output:** `outputs/final/film_9x16.mp4` (vertical) and `outputs/final/film_16x9.mp4` (horizontal), each with Amharic narration, burned-in English subtitles, an original score ducked under the voice, and an AI-disclosure end card.

## Run it

```bash
git clone <this repo> && cd heritage-short
python -m venv .venv && source .venv/bin/activate     # Windows Git Bash: source .venv/Scripts/activate
pip install -r requirements.txt                       # plus FFmpeg on your PATH
cp .env.example .env                                  # add GEMINI_API_KEY, CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_API_TOKEN
python -m pipeline.run                                # the whole film (or: make film)
```

`python -m pipeline.run --draft` renders a half-resolution preview. With the committed `outputs/`, every stage is a cache hit and the film rebuilds in about a minute without any API calls.

**Music** is generated on a Kaggle GPU (`kaggle/music_acestep.ipynb`, ACE-Step 1.5) and imported with `python -m pipeline.import_music music_outputs.zip`; the chosen candidate is set in `storyboard.json → music.chosen`.

## Change one shot, regenerate only that shot

Edit a narration line or keyframe prompt in `storyboard.json`, then run `python -m pipeline.run` again. Each stage hashes its inputs; only the changed shot makes a new model call, which `runs.jsonl` shows (one new line with `"cache_hit": false`, the rest `true`).

```bash
python -m pipeline.narration --only s07        # one line
python -m pipeline.keyframes --only s06 --seed 1306   # try another seed without overwriting
```

## Stages

| Stage | Script | Model / tool | Runs on | Output |
|---|---|---|---|---|
| Contract | `pipeline/validate.py` | JSON Schema + cross-field checks | local | fails fast on a broken storyboard |
| Narration | `pipeline/narration.py` | Gemini 3.8 Flash-Lite TTS (fallback: Flash TTS) | Gemini API, free tier | `outputs/narration/sNN.wav` |
| Radio cut | `pipeline/radio_cut.py` | FFmpeg | local | narration + placeholder music on black (user test 1) |
| Keyframes | `pipeline/keyframes.py` | FLUX.2 [klein] 4B (fallback: FLUX.1 [schnell]) | Cloudflare Workers AI | 3 references, then 11 shots conditioned on them |
| Music | `kaggle/music_acestep.ipynb` | ACE-Step 1.5 turbo, 3 seeded candidates | Kaggle GPU | `outputs/music/candidate_N.wav` |
| Motion + edit | `pipeline/assemble.py` | FFmpeg: pan-and-zoom, dissolves, ducking, loudness, subtitles, end card | local | `outputs/final/*.mp4` |

Every model call is one line in `runs.jsonl`: stage, model, shot, parameters, seed, latency, status, cache hit, list-price cost.

## Cost

About **$0.10 at list prices** for everything generated so far, all of it covered by free tiers; see [COSTS.md](COSTS.md). The binding constraints were the Gemini TTS rate limit (about 5 calls per minute per model) and Kaggle setup time, not money.

## Repository

```
storyboard.json        the contract: shots, prompts, seeds, narration, music cues
schema/                JSON Schema, validated before every stage
pipeline/              one script per stage + run.py (all stages)
kaggle/                GPU notebooks (music)
tests/                 python -m unittest discover tests  (no network needed)
outputs/               every generated file, kept for inspection
runs.jsonl             one line per model call
DESIGN.md              audience, intent, shot reasons, user tests and what they changed
ARCHITECTURE.md        contracts, caching, failure handling
EXPERIMENTS.md         hypothesis -> change -> result
FAILURES.md            what broke, what I tried, what fixed it
COSTS.md               latency, GPU minutes, list-price equivalent
ETHICS.md              consent, licences, labelling, cultural respect
```

Made with AI. All characters are fictional; the tradition is my family's, shared with my parents' consent.
