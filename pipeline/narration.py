"""Stage: narration. One WAV per shot from Gemini TTS, cached by input hash.

Changing one narration line regenerates only that line's audio.

Usage: python -m pipeline.narration [--only s03] [--force]
"""
import argparse
import base64
import io
import os
import threading
import time
import wave

from pipeline.common import (OUTPUTS, audio_duration, input_hash, load_env,
                             log_call, read_manifest, write_manifest)
from pipeline.validate import validate

OUT = OUTPUTS / "narration"
MANIFEST = OUT / "manifest.json"
PCM_RATE = 24000  # Gemini TTS returns 24 kHz, 16-bit mono PCM when not already WAV


def _to_wav(data: bytes) -> bytes:
    if data[:4] == b"RIFF":
        return data
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(PCM_RATE)
        w.writeframes(data)
    return buf.getvalue()


MIN_INTERVAL_S = 20.0    # free tier: ~4-5 TTS calls per minute per model (FAILURES.md F05)
QUOTA_COOLDOWN_S = 65.0  # per-minute limit: wait it out on the same model before switching
CALL_TIMEOUT_S = 45.0    # the SDK retries 429s silently for minutes; give up sooner
_last_call = [0.0]


class QuotaError(RuntimeError):
    pass


def _call_with_timeout(fn, timeout: float):
    """Run fn in a daemon thread so a stuck SDK retry loop can't freeze the stage."""
    box = {}

    def target():
        try:
            box["ok"] = fn()
        except Exception as e:  # noqa: BLE001
            box["err"] = e
    t = threading.Thread(target=target, daemon=True)
    t.start()
    t.join(timeout)
    if t.is_alive():
        raise QuotaError(f"no response in {timeout:.0f}s (likely 429 retry loop)")
    if "err" in box:
        e = box["err"]
        if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e) or "quota" in str(e).lower():
            raise QuotaError(str(e)) from e
        raise e
    return box["ok"]


def _tts_once(client, model: str, voice: str, text: str, style: str) -> bytes:
    wait = MIN_INTERVAL_S - (time.time() - _last_call[0])
    if wait > 0:
        time.sleep(wait)
    _last_call[0] = time.time()

    def call():
        # The text field is a verbatim transcript: style goes in speech_metadata,
        # otherwise the model reads the instruction aloud (see FAILURES.md F02).
        inter = client.interactions.create(
            model=model,
            input=[{"type": "user_input", "content": [{
                "type": "text", "text": text,
                "annotations": [{"type": "speech_metadata", "style": style}],
            }]}],
            response_format={"type": "audio"},
            generation_config={"speech_config": [{"voice": voice}]},
        )
        return base64.b64decode(inter.output_audio.data)
    return _call_with_timeout(call, CALL_TIMEOUT_S)


def _tts(client, models: list[str], exhausted: set, voice: str, text: str,
         style: str, sid: str) -> tuple[bytes, str]:
    """Try each model in order; a model that hits quota is skipped for the rest of the run."""
    last = None
    for m in models:
        if m in exhausted:
            continue
        print(f"{sid}: generating with {m} ...", flush=True)
        t0 = time.time()
        for attempt in (1, 2):
            try:
                return _tts_once(client, m, voice, text, style), m
            except QuotaError as e:
                last = e
                log_call("narration", m, sid, {"voice": voice}, None, time.time() - t0,
                         "quota", error=str(e), attempt=attempt)
                if attempt == 1:
                    print(f"{sid}: {m} rate-limited, waiting {QUOTA_COOLDOWN_S:.0f}s "
                          f"to keep the same voice ...", flush=True)
                    time.sleep(QUOTA_COOLDOWN_S)
                    t0 = time.time()
            except Exception as e:  # e.g. 400: model doesn't support speech annotations
                last = e
                log_call("narration", m, sid, {"voice": voice}, None, time.time() - t0,
                         "unsupported", error=str(e))
                print(f"{sid}: {m} rejected the request ({str(e)[:80]}) -> next model",
                      flush=True)
                break
        exhausted.add(m)
        print(f"{sid}: giving up on {m} for this run", flush=True)
    raise SystemExit(f"no TTS model could produce audio ({', '.join(models)}); last error: {last}")


def run(only: str | None = None, force: bool = False, model: str | None = None,
        unify: bool = False) -> dict:
    sb = validate()
    v = dict(sb["style"]["voice"])
    models = [model] if model else [v["model"], *v.get("fallback_models", [])]
    exhausted: set = set()
    manifest = read_manifest(MANIFEST)
    OUT.mkdir(parents=True, exist_ok=True)
    client = None

    for s in sb["shots"]:
        sid, text = s["id"], s["narration"]["text"].strip()
        if only and sid != only:
            continue
        if not text:
            manifest.pop(sid, None)
            continue
        style = s["narration"].get("style_instruction", v["style_instruction"])
        h = input_hash("narration-v2", v["voice_name"], style, text)  # model may fall back
        path = OUT / f"{sid}.wav"
        params = {"voice": v["voice_name"], "style": style, "text": text}

        wrong_model = unify and manifest.get(sid, {}).get("model") not in (None, models[0])
        if not force and not wrong_model and manifest.get(sid, {}).get("hash") == h and path.exists():
            print(f"{sid}: cached")
            log_call("narration", manifest[sid].get("model", v["model"]), sid, params, None, 0.0, "ok",
                     cache_hit=True, output=path.relative_to(OUTPUTS.parent).as_posix())
            continue

        if client is None:
            load_env()
            from google import genai
            client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

        t0 = time.time()
        try:
            raw, used = _tts(client, models, exhausted, v["voice_name"], text, style, sid)
            audio = _to_wav(raw)
        except SystemExit:
            write_manifest(MANIFEST, manifest)
            raise
        except Exception as e:  # logged, then the stage stops
            log_call("narration", models[0], sid, params, None, time.time() - t0,
                     "error", error=str(e))
            raise
        path.write_bytes(audio)
        dur = audio_duration(path)
        manifest[sid] = {"hash": h, "model": used, "path": path.relative_to(OUTPUTS.parent).as_posix(),
                         "duration_s": round(dur, 3), "words": len(text.split())}
        write_manifest(MANIFEST, manifest)
        log_call("narration", used, sid, params, None, time.time() - t0, "ok",
                 output=manifest[sid]["path"], audio_s=round(dur, 3),
                 chars=len(text))
        print(f"{sid}: {dur:.1f}s with {used} ({time.time() - t0:.1f}s)")

    write_manifest(MANIFEST, manifest)
    total = sum(m["duration_s"] for m in manifest.values())
    words = sum(m["words"] for m in manifest.values())
    print(f"narration total {total:.1f}s, {words} words, {words / total:.2f} words/s")
    used = {m.get("model") for m in manifest.values()}
    if len(used) > 1:
        print(f"WARNING: lines come from different models {sorted(used, key=str)}; voices may not "
              f"match. Run again with --unify")
    return manifest


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="regenerate a single shot id, e.g. s03")
    ap.add_argument("--force", action="store_true", help="ignore the cache")
    ap.add_argument("--model", help="use only this model (no fallback) for this run")
    ap.add_argument("--unify", action="store_true",
                    help="regenerate lines made by a fallback model, so every line has one voice")
    a = ap.parse_args()
    run(a.only, a.force, a.model, a.unify)
