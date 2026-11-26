# DESIGN.md: Around One Bowl (በአንድ ሳህን ዙሪያ)

Written on 2026-11-26, before any image, video or music was generated.

## Brief

**Audience.** Ethiopian Muslims who spend Eid away from home, such as university students in dorms and relatives in the diaspora, plus my own family. They will mostly watch on a phone, vertically, after the film is forwarded on Telegram, WhatsApp or TikTok.

**Intent.** At the end, the viewer should feel *"I remember mornings like that"*, a quiet, warm homesickness. They should not come away feeling they learned about an Ethiopian custom. The film is a memory, not an explanation.

**Define (how might we).** How might we help someone far from home feel, for 85 seconds, that they are sitting on the floor of their family's house again on Eid al-Fitr morning?

**Constraints.** 60–90 s, Amharic narration with English subtitles, about 22 hours to make it, free GPU quota (Kaggle T4), no real faces.

## Empathise: what the story owner told me (before generating)

My family's real routine, collected in conversation, replaced several early ideas:

| Early idea | What actually happens | Change to the storyboard |
|---|---|---|
| Family members phone each other after midnight | We wake each other in person, around ከሌሊቱ 11 ሰዓት (5 AM) | Phone shot removed; s02 is a hand waking a sleeper |
| A formal family breakfast | Everyone sits on the floor; children run around excitedly | s03 added (children running); s06 is on the floor mat |
| "Eid" in general | It is Eid al-Fitr: we eat genfo *before* prayer | Narration opens with "Ramadan is over" |
| Ending on the stadium | The bowl is what I'll remember | s11 returns to the empty bowl |
| A sunrise finale | We leave while it is still dark | No sunrise sky in any shot; the stadium is shown at blue hour |

## Ideate: options considered

1. **Explainer:** a narrator describes the Ethiopian Eid genfo tradition. Rejected: it informs but doesn't move the viewer, and it risks presenting one family's habit as a rule for everyone.
2. **Day-in-the-life:** realistic coverage from waking to prayer. Rejected: too many places and people for AI consistency.
3. **Memory piece centred on one object (chosen):** one family, one room, one bowl that keeps returning. This fits the intent, and it fits what the models can keep consistent.

## Visual rules

- **The bowl is the golden reference.** It is one cream-white enamel bowl with a blue rim. It never appears as multiple bowls or separate plates.
- **Hands, backs and soft focus instead of faces.** Faces drift between shots, and a memory is blurry anyway.
- **Colour:** midnight blue outside and amber inside. Morning light appears only in the last shot.
- **No text is generated inside images.** Title, subtitles and end card are added in code.
- **The dua is shown still and respectfully,** with no generated scripture.

## Shot reasons

| Shot | Beat | Why it exists |
|---|---|---|
| s01 | House asleep | Sets the time and place; the night is part of the memory |
| s02 | We wake each other | The ritual starts with people, not alarms |
| s03 | Children running | The energy of the morning, not posed |
| s04 | Getting ready, laying the mat | Waiting for each other; sets up where the bowl goes |
| s05 | The genfo arrives | Introduces the bowl in close-up |
| s06 | Family around one bowl (wide) | The signature image; proves there is one bowl |
| s07 | Many hands, one bowl | "Together" without faces |
| s08 | Dua | The turn from excitement to calm |
| s09 | Leaving in the dark | Our Eid as part of a city waking |
| s10 | Stadium | The reflection: this is what Eid has always been |
| s11 | The empty bowl | The bowl is the memory, so the film ends on it |

## Self-review of the radio cut (before test 1)

- **5.8 s of silence between s06 and s07.** The rule "shot length = max(min_duration, narration + padding)" gave s06 (the family-around-the-bowl wide shot) a 9 s minimum but only 3.2 s of speech. A held pause on the signature image was intended, with the score swelling there, but 5.8 s of near-silence over a placeholder drone feels like a dropout. **Change:** s06 `min_duration_s` 9 → 6.5, which leaves about 2.8 s of held silence. Film 86.7 s → about 84.2 s.

## User test 1: radio cut (narration over placeholder music, black screen)

*Plan:* send the radio cut to at least 3 people from the audience: family members, AAU friends who spend Eid in the dorm, and a relative abroad. Ask them:
1. In one sentence, what was this about?
2. Which line stayed with you?
3. Was anything unclear or mispronounced?
4. Did it feel like a memory or like an explanation?

Run on 2026-11-26 with three people from the core audience: family members who shared these Eid mornings, including one who now lives on his own.

| # | Who (relation, not name) | Situation | What they said |
|---|---|---|---|
| 1 | Elder brother | Lives on his own now (away from the family home) | Story clear; it is about "the Eid morning we guys used to have" |
| 2 | Elder sister | Lives with the family | Nothing unclear or mispronounced; it felt like a **memory**, not an explanation |
| 3 | Younger brother | Lives with the family | Didn't think about it much, but said it is "one of the most important things we used to do" |

Shared answers across the group: the story is clear ("the Eid morning we used to have"), nothing unclear or mispronounced, it felt like a **memory**, and they said it was great but asked to **"add something funny about it"**.

**Insights**
- The intent landed: every answer frames it as *our* memory, not a cultural explainer. Keep the memory framing; don't add explanation.
- The Amharic TTS was understood with no pronunciation complaints, so Gemini Flash-Lite TTS stays.
- The film is all tenderness and no laughter, but real Eid mornings at home are noisy and funny. The testers' request names a real gap.

**What changed because of test 1**
- Asked the story owner (me) what the funny moment actually is, rather than inventing one: **everyone races for the butter and berbere in the middle of the genfo**.
- **s07** rewritten: the narration now ends with "…ሁሉም ግን መሃል ላይ ወዳለው ቅቤ ይሽቀዳደማል" ("…but everyone races for the butter in the middle"), with a playful style instruction for that line only; the keyframe now shows all the hands racing to the butter pool, a child's hand first.
- Placement reason: the laugh comes right before the dua (s08), so the shift from noise to stillness is bigger.
- Only s07's narration and keyframe regenerate (cache), as `runs.jsonl` shows.

## User test 2: near-final cut

| # | Who | What they said | Action |
|---|---|---|---|
| 1 | | | |
| 2 | | | |
| 3 | | | |

**What changed because of test 2:** _(fill in)_
