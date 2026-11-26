# ETHICS.md

## 1. Consent

| Person | Appears? | Voiced? | Consent | Recorded |
|---|---|---|---|---|
| Me (Nole Mohammed), author and the narrator "I" | No (fictional characters only) | No: a stock Gemini TTS voice ("Charon"), not a clone of my voice | I wrote and approve every narration line | 2026-11-26 |
| My family (the tradition belongs to them) | No | No | My parents agreed on 2026-11-26 that our Eid genfo tradition may be shared in a public film (their words, translated: "it would be great to share"). They are not depicted or voiced. Method: in person (I live with them) | 2026-11-26 |

**No real person's face, likeness or voice is generated.** Every person on screen, including the children, is a fictional, non-identifiable AI character described only by clothing. Faces are kept turned away or out of focus. No photographs of real relatives were sent to any model. No voice cloning was used.

### Photorealism decision (2026-11-26)
The first family reference came out so realistic that it "looks like a real family rather than a generated one" (my own reaction). I chose to keep the photorealistic look for the film's warmth, with these safeguards: the family is generated from text only (no photos of anyone as input; seed and prompt in `runs.jsonl`); in the film's shots faces stay turned away, partly hidden or out of focus; the end card says all characters are fictional; and the platform's AI label is switched on. The considered alternative was a painterly "memory" style that is obviously not real footage.

## 2. Private data

Free API tiers may use submitted data to train models. Prompts therefore contain no real names, addresses, neighbourhood names or photos. Only generic descriptions ("a modest Addis Ababa living room") are sent.

## 3. Licences

| Component | Used for | Licence / terms | Commercial use of output |
|---|---|---|---|
| Gemini 3.8 Flash (Google AI Studio, free tier) | Script help, translation | Gemini API Additional Terms | Allowed per terms; free-tier data may be used by Google |
| Gemini 3.8 Flash TTS | Narration | Gemini API Additional Terms; output carries SynthID | Allowed per terms |
| FLUX.1 schnell / FLUX.2 klein **4B** (Cloudflare Workers AI) | Keyframes | Apache 2.0 (the FLUX.2 klein 9B is non-commercial and is **not** used) | Yes |
| Wan 2.2 TI2V-5B | Moving shots | Apache 2.0 | Yes |
| ACE-Step 1.5 | Score | MIT; trained on licensed, royalty-free and synthetic data | Yes |
| FFmpeg | Assembly | LGPL/GPL (tool only; doesn't affect output) | n/a |

No third-party photos, music or footage are used. Reference images found while brainstorming were deliberately **not** used.

## 4. Labelling

- An end card in Amharic and English: "Made with AI. All characters are fictional. Based on my family's Eid al-Fitr tradition."
- The platform's AI-content disclosure is switched on when posting.
- SynthID and other provenance metadata are left intact: no re-encoding steps strip them on purpose, and no watermark removal.

## 5. Cultural and religious respect

- The film presents **my family's** tradition, not a rule for all Ethiopian Muslims.
- The dua is shown calmly, with no generated Arabic script or Quran pages. Generated text is often garbled, and that would be disrespectful.
- The stadium prayer is shown as a distant, generic crowd. No real worshippers are depicted.
- A family member reviews the near-final cut for accuracy and respect before publishing.