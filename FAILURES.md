# FAILURES.md

What broke, what I tried, what fixed it.

## F01: Dummy timing ran over 90 s (2026-11-26)
- **What broke:** a pipeline dry run with placeholder audio (assuming about 0.45 s per Amharic word plus 1.3 s padding per shot) produced a 95.5 s radio cut, over the 60–90 s limit.
- **What I did:** added a warning to `radio_cut.py`. The real fix waits on measured TTS durations: if the real voice is also too long, cut words from the narration (not speed up the voice) and lower `min_duration_s` on the silent-heavy shots.
- **Status:** open until the real narration is measured.

## F02: TTS read the style instruction aloud (2026-11-26)
- **What broke:** the first narration run produced 134.2 s of audio for 96 Amharic words (0.72 words/s). Line s10 was 18.4 s for 13 words.
- **Evidence:** listening to the v1 files, several start with about 10 s of the English instruction "Speak Amharic as a young man, calm…" spoken aloud before the Amharic line.
- **Cause:** I had prepended the style instruction ("Speak Amharic as a young man…") to the text. The Gemini TTS docs say the `text` field is a verbatim transcript, so the instruction was spoken.
- **Fix:** moved the style into a `speech_metadata` annotation on the text item and bumped the cache key to `narration-v2`, so every line regenerates once. v1 audio kept in `outputs/narration_v1/` for comparison.
- **Lesson:** read the API contract for "what is spoken" vs "what steers". The 2× length was the clue.

## F03: 429 Too Many Requests on Gemini TTS free tier (2026-11-26)
- **What broke:** after ~10 back-to-back TTS calls, s11 got `429 Too Many Requests`. The SDK's internal retry kept sleeping; I interrupted it.
- **What worked:** a re-run resumed from cache. Only s11 was generated, because s01–s10 were cache hits. That's the caching doing its job.
- **Fix:** an 8 s minimum interval between TTS calls, plus a slower backoff (20 s base) in `pipeline/narration.py`.

## F04: Daily TTS quota exhausted (2026-11-26)
- **What broke:** after the fix in F02, the first call of the re-run returned 429 immediately, even with 8 s spacing. The ~13 calls of the first run (with retries) seem to have used up the free daily quota for `gemini-3.8-flash-tts`. The SDK then retried silently for minutes, so it looked frozen.
- **What I did:** added a `--model` override and per-line progress output. Tested `gemini-3.8-flash-lite-tts`, which also supports Amharic, on one line first (`--only s01`) before spending quota on all 11.
- **Result:** Flash-Lite TTS worked on s01 (6.5 s, 1.70 words/s, only Amharic, sounded good to me), so it became the primary model.
- **Correction (see F05):** the limit was not daily. `flash-tts` worked again ~15 min later.
- **Lesson:** on a free tier, test one line before batch runs, and never regenerate everything to fix one line.

## F05: The TTS limit is per-minute, and the fallback broke voice consistency (2026-11-26)
- **Observed:** with Flash-Lite as primary, s02–s05 succeeded, then s06 got 429 (about 5 calls in a minute). The stage fell back to `flash-tts`, which had "failed" at 03:52 but worked at 04:08, and made s06–s07. At s08 it hit 429 too, then fell to `gemini-2.5-flash-preview-tts`, which returned **400: "Speech annotations are not supported"**.
- **Diagnosis:** (1) the limit is per minute per model (~4–5 calls), not daily. My F04 guess was wrong. (2) Switching models mid-film gives lines in different voices, which is worse for the film than waiting a minute. (3) The 2.5 TTS model doesn't accept `speech_metadata`, and putting the style in the text gets it read aloud (F02), so it can't serve as a fallback.
- **Fix:** 20 s spacing between calls; on 429, wait 65 s and retry the **same** model before falling back; a 400 skips that model instead of crashing; 2.5 removed from `fallback_models`; new `--unify` flag regenerates any line made by a fallback model. Tested all four paths against a fake client before running for real.
- **Lesson:** a fallback that changes the output (here, the voice) trades availability for consistency. For a film, consistency wins, so wait first and switch last.

## F06: Contact sheet crashed FFmpeg on Windows (2026-11-26)
- **What broke:** `drawtext` labels on the contact sheet failed with "Fontconfig error: Cannot load default config file" and exit code 3221225477 (access violation) on the Windows gyan.dev FFmpeg build. The stage itself kept going, because the contact sheet is wrapped so a review aid can't break generation.
- **Fix:** removed the text labels; tiles follow storyboard order. Lesson: avoid font-dependent filters unless a font file is passed explicitly. The end card and titles in assembly will pass `fontfile=` directly.

## F07: Reference sheet merged two characters (2026-11-26)
- **What broke:** the family reference asked for five people but showed six: the grandmother wore the mother's pale green dress (the mother was missing) and there were two boys instead of one.
- **Why it matters:** every shot is conditioned on this image, so the error would spread to all family shots.
- **Fix:** rewrote the prompt as a numbered costume list ("exactly five people … only one boy and one girl"). **Result:** the same seed now gives exactly five people: father, mother, grandmother, one boy, one girl.

## F08: The "Ethiopian" family didn't look Ethiopian (2026-11-26)
- **What broke:** the family reference (and all shots using it) looked Middle Eastern rather than Ethiopian. I confirmed this myself as part of the audience. The prompt said "Ethiopian Muslim family", but the model seems to lean on "Muslim + jalabiya + kufi" more than on "Ethiopian".
- **Why it matters:** for an Ethiopian audience, wrong-looking faces break the "I remember mornings like that" feeling immediately.
- **Fix:** made it explicit in both the reference prompt and the description reused in every shot: "Ethiopian (Habesha) … warm brown skin and East African Habesha features". The family reference was regenerated with the same seed first, approved, then the dependent shots, which regenerate automatically because their cache key includes the reference hash.
- **Result (attempt 1, group-level "Habesha"):** partial. The father and boy looked Ethiopian, but the mother, grandmother and girl still looked lighter-skinned and Middle Eastern. The model applied the group adjective unevenly.
- **Attempt 2:** "Habesha … brown skin" on **each** numbered person, same seed. **Result:** father, boy, girl and grandmother now read as Ethiopian; the mother still reads lighter and somewhat Middle Eastern. **Accepted:** she is seen mostly from behind or side-on in the film (s04, s07, s09), and the remaining time was better spent on music and testing. A residual model bias, worth noting: the model's default image of a "Muslim family in jalabiya" pulls away from East African faces.

## F09: A stale file copy silently undid a fix (2026-11-26)
- **What broke:** after I updated the family prompt to "Ethiopian (Habesha)", regenerating gave the *same* family. The image's timestamp and `runs.jsonl` showed no new call had been made. The `storyboard.json` on disk didn't contain the change: the agent's file-sync step had copied a cached older snapshot of the file it had just written, twice.
- **How it was found:** comparing checksums of every repository file on the laptop against the agent's copies, instead of trusting a "written" confirmation.
- **Fix:** write each sync to a fresh path, wait a few seconds, then verify the file on disk (size, plus reading the changed field back) before running anything.
- **Lesson:** a cache key on *inputs* protected us (no wrong images were generated, because the prompt hash hadn't changed), but "it says written" is not proof. Verify the artifact.

## F10: Kaggle notebook crashed on the music settings (2026-11-26)
- **What broke:** cell 1 of `kaggle/music_acestep.ipynb` raised `NameError: name 'true' is not defined`. The music block was copied from `storyboard.json` as raw JSON into Python source, and JSON's `true` is not Python's `True`.
- **Fix:** the cell now parses the block with `json.loads(...)`, so it stays a verbatim copy of the storyboard contract. Tested by executing the cell locally.
- **Lesson:** when moving the contract between environments, parse it; don't paste it as code.

## F11: Kaggle's Python is newer than ACE-Step allows (2026-11-26)
- **What broke:** `ModuleNotFoundError: loguru` in the music notebook. The real cause was hidden by my quiet install (`pip -q … | tail -3`). Re-running the install verbosely showed `Package 'ace-step' requires a different Python: 3.13.16 not in '<3.13,>=3.11'`: Kaggle's kernel had moved to Python 3.13.
- **Fix:** notebook v2 no longer installs ACE-Step into the kernel. It uses ACE-Step's own documented setup (`uv sync`, which provisions Python 3.12 inside the repo) and runs generation as a script (`gen.py`) via `uv run`. The storyboard's music block is passed as a JSON file.
- **Lessons:** (1) never silence an install step; the first error is the real one. (2) The brief warned that "some of what we write here [will] be out of date": here not the model but the *platform* moved. Pinning the runtime the tool declares beats fighting the host's.

## F12: Kaggle's plotting setting leaked into the isolated environment (2026-11-26)
- **What broke:** with v2 of the notebook, `uv sync` worked (95 s), but `gen.py` crashed before any audio: `ValueError: Key backend: 'module://matplotlib_inline.backend_inline' is not a valid value for backend`. The `music_outputs.zip` held only `session.json`.
- **Cause:** Kaggle's Jupyter sets `MPLBACKEND` to its inline backend. The `uv run` subprocess inherits the variable, but `matplotlib-inline` doesn't exist in ACE-Step's own `.venv`, so importing matplotlib fails.
- **Fix:** `MPLBACKEND=Agg uv run python gen.py` (a headless backend that always exists). Only cells 3–4 re-run; the environment from cell 2 is reused.
- **Lesson:** isolating the Python version (F11) isn't full isolation: environment variables cross the boundary too.
