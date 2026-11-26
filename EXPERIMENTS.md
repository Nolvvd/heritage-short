# EXPERIMENTS.md

Each entry: hypothesis → change (one thing at a time) → result → decision.

## E01: Subtitle size on a vertical frame (2026-11-26)
- **Hypothesis:** at the default-ish FontSize=13, two-line English subtitles will fit a 1080×1920 frame.
- **Change:** rendered the radio cut with dummy narration and inspected frames at 5 s and 37 s.
- **Result:** at size 13, "Ramadan is over. It is five in the morning," wrapped onto **3 lines**, breaking the 2-line rule. At FontSize=9 with MarginV=50, every subtitle stays on its authored 2 lines, inside the lower safe area.
- **Decision:** FontSize=9. The validator also enforces ≤48 characters per line and ≤2 lines, and it already rejected s11's 52-character line.

## E02: Gemini TTS for Amharic: speed, model and style placement (2026-11-26)
- **Hypothesis:** at about 2 words/s, 96 Amharic words fit in roughly 50 s of speech.
- **Change:** generated all 11 lines with `gemini-3.8-flash-lite-tts`, voice Charon, style passed as `speech_metadata` (v2), vs v1 where style was prepended to the text.
- **Result:** v1 = 134.2 s (0.72 words/s; the instruction was spoken, F02). v2 = **58.2 s, 1.65 words/s**, only Amharic. Amharic words are long (agglutinative), so words/s is lower than the English rule of thumb of 2–2.5. Per-line latency 4–8 s when not rate-limited.
- **Decision:** Flash-Lite TTS as primary; plan Amharic narration at about 1.6 words/s.

## E03: Narration-driven timeline vs fixed minimums (2026-11-26)
- **Hypothesis:** letting the narration set shot length (`max(min_duration, speech + 1.3 s)`) gives natural pacing.
- **Result:** most shots ended with 0.8–2.9 s of breathing room, but s06 had 5.3 s after its line (plus a 0.5 s lead into s07), which I heard as a dropout when watching the radio cut.
- **Change:** s06 minimum 9 → 6.5 s, one parameter changed; regenerating the radio cut made **no** new TTS calls (all 11 lines cache hits).
- **Decision:** keep the rule; the minimums are creative choices, reviewed by ear.

## E04: Describing genfo so the model draws it correctly (2026-11-26)
- **Hypothesis:** "a smooth mound of thick golden-brown barley genfo, a well in the centre holding butter and berbere" is enough for FLUX to draw real genfo.
- **Result (seed 1101):** the bowl itself was right, but the genfo looked rough, not like real genfo. Real genfo is served as a smooth, glossy ring with a deep red pool of niter kibbeh and berbere in the centre (checked against a reference photo; not used as model input).
- **Change:** one variable, the genfo wording: "a smooth glossy ring … shaped like a wide doughnut … perfectly smooth and shiny … deep hollow … dark red pool". Same seed.
- **Result:** the genfo is now a smooth, glossy ring with a dark red pool in the centre, recognisably genfo (my judgement as a native). The bowl was unchanged. Same seed, one variable changed, so the wording made the difference.

## E05: Image reference vs text reference for characters (2026-11-26)
- **Observation (first full keyframe run):** every shot conditioned on the family reference image (a front-facing lineup) copied that lineup. s03 (children running away), s04 (mother laying the mat) and s09 (family walking away) all came out as the whole family **standing in a row facing the camera**, with faces fully visible. Shots whose action differed strongly (s05 hands, s07 hands, s08 dua) were fine.
- **Hypothesis:** the reference image carries pose and framing, not just identity. For "from behind" shots, describing the costumes in text instead of passing the image will give the intended action while keeping the clothing consistent.
- **Change:** new `keyframe.text_refs` field. s03 and s09 use the family as text only, and s04 uses no family reference at all. The prompts add "seen from behind … faces not visible". Seeds unchanged.
- **Result:** yes. s03 now shows the boy and girl running away from camera, s04 the mother from behind laying the mat, s09 the family walking away down the street, all with the same clothing colours (white jalabiya, pale green dress, pink headscarf) from the text description alone. Shots that kept the image reference (s06, s07, s08) held identity and clothing best.
- **Decision:** image references for identity-heavy shots; text references when the pose must differ from the reference sheet.

## E06: Choosing the score from three ACE-Step candidates (2026-11-26)
- **Setup:** ACE-Step 1.5 turbo on a Kaggle T4, one caption (tizita-feel krar, masinko, felt piano, string pad, no drums), 70 BPM, D minor, 90 s, instrumental, **three fixed seeds** (3001–3003). Each took 8–11 s to generate (0.14–0.19 GPU-minutes); peak GPU memory was 7.8 GB, so it fits a T4 comfortably.
- **Hypothesis:** with the same caption, the seeds will differ mostly in arrangement, and the best candidate is the one whose loudness shape matches the cue plan (quiet opening, swell at the bowl, near-silence at the dua, theme at the stadium, fade at the end), not just the one that sounds nicest alone.
- **Listening (me, at low volume):** all three are nostalgic and peaceful, have no vocals despite the 8-language-capable model, and none is busy or loud. By ear alone I couldn't separate them.
- **Measurement:** short-term loudness (EBU R128) in 6 s windows, compared with the cue times from the timeline:

| | 0–30 s | 30–42 s | 48–56 s (dua) | 60–72 s | 78–90 s | Integrated / range |
|---|---|---|---|---|---|---|
| cand 0 (3001) | −23 → −19 | swell to −15 | −15 | **peak −13** | fade −21 | −16.8 LUFS / 14.1 LU |
| cand 1 (3002) | builds to −13 | **peak −11** | −12 | fading from 66 s | −29 | −14.8 / 17.2 |
| cand 2 (3003) | jump at 12 s | **dip** at 30 s | **peak −11** | fading | −30 | −16.6 / 16.4 |

- **Result:** only candidate 0 follows the arc: its swell lands on the bowl, its peak on the stadium, and it fades under the last line. Candidate 2 peaks exactly on the dua, the moment that should be quietest. None has a real dip for the dua; ducking (threshold 0.02, ratio 6) lowers the score under every line anyway.
- **Decision:** `music.chosen = 0`. Lesson: when the ear can't separate candidates, measuring them against the edit's timeline can. That's the "spotting session" done with numbers.
