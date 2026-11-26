"""Stage: keyframes. References first, then one still per shot conditioned on them.

Model: FLUX.2 [klein] 4B on Cloudflare Workers AI (Apache 2.0), with
FLUX.1 [schnell] as a prompt-only fallback.

Images are square (1536x1536) with the subject centred, so the same frame
crops to both 9:16 (864x1536) and 16:9 (1536x864) in assembly.

Caching: a shot's hash covers its full prompt, seed, size, model AND the
hashes of the reference images it uses. Change the bowl reference and every
bowl shot regenerates; change one shot prompt and only that shot does.

Usage:
  python -m pipeline.keyframes --refs-only        # step 1: approve references
  python -m pipeline.keyframes                    # step 2: all shots
  python -m pipeline.keyframes --only s06 --seed 1306   # try another seed
"""
import argparse
import base64
import os
import subprocess
import time

import requests

from pipeline.common import (OUTPUTS, ROOT, PermanentError, input_hash, load_env,
                             log_call, read_manifest, repo_path, retry, write_manifest)
from pipeline.validate import validate

OUT = OUTPUTS / "keyframes"
MANIFEST = OUT / "manifest.json"
SIZE = 1536
PRIMARY = "@cf/black-forest-labs/flux-2-klein-4b"
FALLBACK = "@cf/black-forest-labs/flux-1-schnell"
TILE_PRICE_USD = 0.000287     # per output 512x512 tile, klein 4B list price
INPUT_TILE_PRICE_USD = 0.000059
API = "https://api.cloudflare.com/client/v4/accounts/{acct}/ai/run/{model}"


class ModelError(PermanentError):
    pass


def _ext(data: bytes) -> str:
    return ".png" if data[:8] == b"\x89PNG\r\n\x1a\n" else ".jpg"


def _decode(resp: requests.Response) -> bytes:
    if resp.status_code == 429:
        raise RuntimeError("429 rate limited")
    if resp.status_code >= 500:
        raise RuntimeError(f"{resp.status_code} server error")
    if resp.status_code >= 400:
        raise ModelError(f"{resp.status_code}: {resp.text[:300]}")
    if resp.headers.get("content-type", "").startswith("image/"):
        return resp.content
    body = resp.json()
    if not body.get("success", True):
        raise ModelError(str(body.get("errors"))[:300])
    return base64.b64decode(body["result"]["image"])


@retry(attempts=3, base_delay=10)
def _klein(acct: str, token: str, prompt: str, seed: int, refs: list) -> bytes:
    files = {"prompt": (None, prompt), "width": (None, str(SIZE)),
             "height": (None, str(SIZE)), "seed": (None, str(seed))}
    for i, p in enumerate(refs[:4]):
        files[f"input_image_{i}"] = (p.name, p.read_bytes(), "image/jpeg")
    r = requests.post(API.format(acct=acct, model=PRIMARY), files=files,
                      headers={"Authorization": f"Bearer {token}"}, timeout=120)
    return _decode(r)


@retry(attempts=3, base_delay=10)
def _schnell(acct: str, token: str, prompt: str, seed: int) -> bytes:
    r = requests.post(API.format(acct=acct, model=FALLBACK),
                      json={"prompt": prompt[:2048], "steps": 8, "seed": seed},
                      headers={"Authorization": f"Bearer {token}"}, timeout=120)
    return _decode(r)


def _small_copy(src, dst) -> None:
    """References are sent at <=512 px, as the API requires."""
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src),
                    "-vf", "scale=512:512:force_original_aspect_ratio=decrease",
                    "-q:v", "3", str(dst)], check=True)


def _ref_prompt(sb: dict, ref: dict) -> str:
    return f"{ref['prompt']}. {sb['style']['style_block']}. Avoid: {sb['style']['negative']}"


def _shot_prompt(sb: dict, shot: dict, refs_by_id: dict) -> str:
    used = shot["keyframe"]["refs"]
    lines = [shot["keyframe"]["prompt"] + "."]
    for i, rid in enumerate(used[:4]):
        lines.append(f"Image {i} shows {refs_by_id[rid]['description']}; keep it exactly the same.")
    for rid in used[4:] + shot["keyframe"].get("text_refs", []):
        lines.append(f"Featuring {refs_by_id[rid]['description']}.")
    lines.append(f"Centred composition, the main subject in the middle of the frame. {sb['style']['style_block']}.")
    lines.append(f"Avoid: {sb['style']['negative']}.")
    return " ".join(lines)


def _generate(kind, key, prompt, seed, refs, h, manifest, creds, allow_fallback=True):
    acct, token = creds
    t0 = time.time()
    model = PRIMARY
    try:
        data = _klein(acct, token, prompt, seed, refs)
    except Exception as e:  # noqa: BLE001
        log_call("keyframes", PRIMARY, key, {"prompt": prompt, "refs": [p.name for p in refs]},
                 seed, time.time() - t0, "error", error=str(e))
        if not allow_fallback:
            raise
        print(f"{key}: klein failed ({str(e)[:80]}), falling back to schnell (no references)")
        model, t0 = FALLBACK, time.time()
        data = _schnell(acct, token, prompt, seed)
    path = OUT / ("refs" if kind == "ref" else "shots") / f"{key}{_ext(data)}"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    latency = time.time() - t0
    tiles = (SIZE // 512) ** 2 if model == PRIMARY else 4
    cost = tiles * TILE_PRICE_USD + (len(refs) * INPUT_TILE_PRICE_USD if model == PRIMARY else 0)
    rel = path.relative_to(ROOT).as_posix()
    manifest[key] = {"hash": h, "path": rel, "model": model, "seed": seed}
    write_manifest(MANIFEST, manifest)
    log_call("keyframes", model, key, {"prompt": prompt, "size": SIZE,
             "refs": [p.name for p in refs]}, seed, latency, "ok",
             cost_usd=round(cost, 5), output=rel)
    print(f"{key}: {model.split('/')[-1]} seed={seed} {latency:.1f}s -> {rel}")
    return path


def contact_sheet(manifest: dict, ids: list) -> None:
    paths = [repo_path(manifest[i]["path"]) for i in ids if i in manifest]
    if not paths:
        return
    cols = 4
    rows = (len(paths) + cols - 1) // cols
    inputs = sum((["-i", str(p)] for p in paths), [])
    # No drawtext labels: Windows FFmpeg builds often lack a fontconfig file (FAILURES.md F06).
    # Tiles are in storyboard order, left to right, top to bottom.
    labels = "".join(f"[{i}:v]scale=384:384[v{i}];" for i in range(len(paths)))
    layout = "|".join(f"{(i % cols) * 384}_{(i // cols) * 384}" for i in range(len(paths)))
    graph = labels + "".join(f"[v{i}]" for i in range(len(paths))) + \
        f"xstack=inputs={len(paths)}:layout={layout}:fill=black[out]" if len(paths) > 1 \
        else labels.rstrip(";").replace(f"[v0]", "[out]")
    out = OUT / "contact_sheet.jpg"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", graph,
                    "-map", "[out]", "-frames:v", "1", "-q:v", "3", str(out)], check=True)
    print(f"contact sheet: {out.relative_to(ROOT)} ({rows} rows)")


def run(refs_only=False, only=None, seed_override=None, force=False) -> dict:
    sb = validate()
    load_env()
    creds = (os.environ["CLOUDFLARE_ACCOUNT_ID"], os.environ["CLOUDFLARE_API_TOKEN"])
    manifest = read_manifest(MANIFEST)
    refs_by_id = {r["id"]: r for r in sb["references"]}

    # 1. References (text only). Their hashes feed every shot that uses them.
    ref_hash = {}
    for r in sb["references"]:
        key = f"ref_{r['id']}"
        prompt = _ref_prompt(sb, r)
        h = input_hash("keyframe-ref", PRIMARY, prompt, r["seed"], SIZE)
        ref_hash[r["id"]] = h
        entry = manifest.get(key, {})
        if not force and entry.get("hash") == h and repo_path(entry["path"]).exists():
            print(f"{key}: cached")
            continue
        p = _generate("ref", key, prompt, r["seed"], [], h, manifest, creds)
        _small_copy(p, OUT / "refs" / f"{key}_512.jpg")
    if refs_only:
        try:
            contact_sheet(manifest, [f"ref_{r['id']}" for r in sb["references"]])
        except Exception as e:  # noqa: BLE001
            print(f"(contact sheet skipped: {e})")
        return manifest

    # 2. Shots, conditioned on their references.
    for s in sb["shots"]:
        sid = s["id"]
        if only and sid != only:
            continue
        seed = seed_override if (seed_override is not None and only) else s["keyframe"]["seed"]
        prompt = _shot_prompt(sb, s, refs_by_id)
        ref_files = [OUT / "refs" / f"ref_{rid}_512.jpg" for rid in s["keyframe"]["refs"][:4]]
        h = input_hash("keyframe-shot", PRIMARY, prompt, seed, SIZE,
                       [ref_hash[rid] for rid in s["keyframe"]["refs"]])
        entry = manifest.get(sid, {})
        if not force and entry.get("hash") == h and repo_path(entry["path"]).exists():
            print(f"{sid}: cached")
            log_call("keyframes", entry.get("model", PRIMARY), sid, {}, seed, 0.0, "ok",
                     cache_hit=True, output=entry["path"])
            continue
        key = f"{sid}_seed{seed}" if seed != s["keyframe"]["seed"] else sid  # seed trials don't overwrite
        _generate("shot", key, prompt, seed, ref_files, h, manifest, creds)

    try:
        contact_sheet(manifest, [s["id"] for s in sb["shots"]])
    except Exception as e:  # noqa: BLE001 - a review aid must never break the stage
        print(f"(contact sheet skipped: {e})")
    return manifest


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--refs-only", action="store_true", help="generate only the reference sheet")
    ap.add_argument("--only", help="one shot id, e.g. s06")
    ap.add_argument("--seed", type=int, help="with --only: try a different seed (then copy it into storyboard.json)")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    run(a.refs_only, a.only, a.seed, a.force)
