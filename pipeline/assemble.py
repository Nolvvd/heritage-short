"""Stage: assembly. Pictures + narration + score -> both aspect ratios.

Everything here is deterministic FFmpeg, driven by storyboard.json and the
manifests of the earlier stages:

  1. one clip per shot and format: a Wan clip from outputs/clips/<id>.mp4 if
     it exists, otherwise a slow pan-and-zoom (Ken Burns) over the keyframe.
     Cached by the hash of (keyframe hash, motion, duration, format, overlay).
  2. an end card (Amharic + English) saying the film was made with AI.
  3. clips joined with short dissolves, timed to the narration timeline.
  4. narration placed per shot, score ducked under it (sidechaincompress),
     loudness normalised to about -14 LUFS / -1.5 dBTP, subtitles burned in.

Usage: python -m pipeline.assemble [--format 9:16|16:9] [--draft]
"""
import argparse
import shutil
import subprocess
import time
from pathlib import Path

from pipeline.common import (NARRATION_LEAD_S, OUTPUTS, ROOT, input_hash, log_call,
                             read_manifest, repo_path, timeline, write_manifest, write_srt)
from pipeline.keyframes import MANIFEST as KF_MANIFEST
from pipeline.narration import MANIFEST as NARR_MANIFEST
from pipeline.validate import validate

OUT = OUTPUTS / "final"
WORK = OUTPUTS / "assemble"
CLIPS_IN = OUTPUTS / "clips"          # optional Wan clips, <shot id>.mp4
MUSIC_DIR = OUTPUTS / "music"
XFADE_S = 0.5
FORMATS = {"9:16": (1080, 1920, "film_9x16"), "16:9": (1920, 1080, "film_16x9")}
DRAFT = {"9:16": (540, 960), "16:9": (960, 540)}

ETHIOPIC_FONTS = [
    ROOT / "fonts" / "NotoSansEthiopic-Regular.ttf",
    Path("C:/Windows/Fonts/nyala.ttf"), Path("C:/Windows/Fonts/ebrima.ttf"),
    Path("/usr/share/fonts/truetype/noto/NotoSansEthiopic-Regular.ttf"),
    Path("/usr/share/fonts/opentype/noto/NotoSansEthiopic-Regular.ttf"),
    Path("/usr/share/fonts/truetype/abyssinica/AbyssinicaSIL-Regular.ttf"),
]
LATIN_FONTS = [
    ROOT / "fonts" / "NotoSans-Regular.ttf",
    Path("C:/Windows/Fonts/arial.ttf"), Path("C:/Windows/Fonts/segoeui.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
]


def _ff(args: list, what: str) -> None:
    """Run ffmpeg from the repo root so every path in a filter is relative.
    Windows drive letters (C:) break FFmpeg filter syntax (FAILURES.md)."""
    r = subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *args],
                       cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg failed ({what}): {r.stderr.strip()[-600:]}")


def _rel(p: Path) -> str:
    return p.resolve().relative_to(ROOT).as_posix()


def _font(candidates: list, name: str) -> str | None:
    """Copy the first available font into the work dir and return a relative path."""
    for c in candidates:
        if c.exists():
            dst = WORK / "fonts" / f"{name}{c.suffix.lower()}"
            dst.parent.mkdir(parents=True, exist_ok=True)
            if not dst.exists() or dst.stat().st_size != c.stat().st_size:
                shutil.copyfile(c, dst)
            return _rel(dst)
    return None


def _textfile(text: str, name: str) -> str:
    p = WORK / "text" / f"{name}.txt"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return _rel(p)


def _drawtext(font: str, textfile: str, size: int, y: str, fade_in: float = 0.0,
              start: float = 0.0) -> str:
    alpha = (f":alpha='if(lt(t,{start}),0,min(1,(t-{start})/{fade_in}))'" if fade_in else "")
    return (f"drawtext=fontfile={font}:textfile={textfile}:fontsize={size}:fontcolor=white:"
            f"x=(w-text_w)/2:y={y}:shadowcolor=black@0.7:shadowx=2:shadowy=2{alpha}")


def _kenburns_vf(w: int, h: int, frames: int, kb: dict, fps: int, crop: str) -> str:
    zf, zt = kb.get("zoom_from", 1.0), kb.get("zoom_to", 1.08)
    pan = kb.get("pan", "none")
    n = max(frames - 1, 1)
    z = f"{zf}+({zt}-{zf})*on/{n}"
    if pan != "none":                      # leave room to move
        z = f"max(1.08,{z})"
    cx, cy = "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    x = {"left": f"(iw-iw/zoom)*(1-on/{n})", "right": f"(iw-iw/zoom)*on/{n}"}.get(pan, cx)
    y = {"up": f"(ih-ih/zoom)*(1-on/{n})", "down": f"(ih-ih/zoom)*on/{n}"}.get(pan, cy)
    # Upscale 2x before zoompan so the slow movement doesn't judder.
    return (f"{crop},scale={w * 2}:{h * 2}:flags=lanczos,"
            f"zoompan=z='{z}':x='{x}':y='{y}':d={frames}:s={w}x{h}:fps={fps},"
            f"setsar=1,format=yuv420p")


def _shot_clip(sb, shot, row, kf_entry, fmt, w, h, fonts, cache, force) -> Path:
    fps = sb["meta"]["fps"]
    length = row["duration"] + XFADE_S          # overlap that the dissolve eats
    frames = round(length * fps)
    motion = shot["motion"]
    wan = CLIPS_IN / f"{shot['id']}.mp4"
    use_wan = motion["mode"] == "wan" and wan.exists()
    overlay = shot.get("title_overlay", "")
    key = f"{fmt}:{shot['id']}"
    h_in = input_hash("shot-clip-v1", kf_entry["hash"], motion, round(length, 3), fmt, w, h,
                      overlay, use_wan, wan.stat().st_mtime if use_wan else None)
    out = WORK / fmt.replace(":", "x") / f"{shot['id']}.mp4"
    if not force and cache.get(key) == h_in and out.exists():
        return out
    out.parent.mkdir(parents=True, exist_ok=True)

    crop = "crop=ih*9/16:ih" if w < h else "crop=iw:iw*9/16"
    if use_wan:
        src = ["-i", _rel(wan)]
        vf = (f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps={fps},"
              f"tpad=stop_mode=clone:stop_duration={length},setsar=1,format=yuv420p")
    else:
        kb = motion.get("kenburns", {"zoom_from": 1.0, "zoom_to": 1.08, "pan": "none"})
        src = ["-loop", "1", "-framerate", str(fps), "-i", _rel(repo_path(kf_entry["path"]))]
        vf = _kenburns_vf(w, h, frames, kb, fps, crop)

    if overlay and fonts["latin"]:
        am, en = (overlay.split(" — ") + [""])[:2]
        fs = int(h * (0.045 if w < h else 0.06))
        if fonts["ethiopic"]:
            vf += "," + _drawtext(fonts["ethiopic"], _textfile(am, f"title_am_{shot['id']}"), fs,
                                  "h*0.40", fade_in=1.2, start=length * 0.35)
        vf += "," + _drawtext(fonts["latin"], _textfile(en, f"title_en_{shot['id']}"), int(fs * 0.6),
                              f"h*0.40+{int(fs * 1.5)}", fade_in=1.2, start=length * 0.35)

    _ff([*src, "-vf", vf, "-frames:v", str(frames), "-r", str(fps), "-an",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", _rel(out)],
        f"shot {shot['id']} {fmt}")
    cache[key] = h_in
    return out


def _end_card(sb, fmt, w, h, fonts, fps) -> Path:
    ec = sb["end_card"]
    out = WORK / fmt.replace(":", "x") / "end_card.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)
    fs = int(h * (0.026 if w < h else 0.04))
    vf = []
    lines_en = ec["text_en"].split("\n")
    y0 = 0.45
    if ec.get("text_am") and fonts["ethiopic"]:
        am = ec["text_am"].split("\n")
        for i, line in enumerate(am):   # one drawtext per line: long lines overflow 9:16
            vf.append(_drawtext(fonts["ethiopic"], _textfile(line, f"end_am_{i}"), int(fs * 0.9),
                                f"h*{y0}-{(len(am) - i) * int(fs * 1.6) + int(fs * 0.8)}"))
    for i, line in enumerate(lines_en):
        vf.append(_drawtext(fonts["latin"], _textfile(line, f"end_en_{i}"), fs,
                            f"h*{y0}+{i * int(fs * 1.6)}"))
    d = ec["duration_s"]
    vf.append(f"fade=t=in:st=0:d=0.6,fade=t=out:st={d - 0.8}:d=0.8,format=yuv420p")
    _ff(["-f", "lavfi", "-i", f"color=c=black:s={w}x{h}:r={fps}:d={d}",
         "-vf", ",".join(vf), "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
         _rel(out)], f"end card {fmt}")
    return out


def _music_source(sb) -> Path | None:
    chosen = sb["music"].get("chosen")
    if chosen is None:
        return None
    for ext in (".wav", ".mp3", ".flac"):
        p = MUSIC_DIR / f"candidate_{chosen}{ext}"
        if p.exists():
            return p
    return None


def _audio_graph(sb, rows, total, first_input: int, music: Path | None) -> tuple[list, str]:
    """Narration placed per shot + score (or placeholder drone) ducked under it."""
    inputs, chains, labels = [], [], []
    k = first_input
    for r in rows:
        if not r["narration"]:
            continue
        inputs += ["-i", _rel(repo_path(r["narration"]))]
        ms = int((r["start"] + NARRATION_LEAD_S) * 1000)
        chains.append(f"[{k}:a]aresample=48000,aformat=channel_layouts=mono,adelay={ms}[n{k}]")
        labels.append(f"[n{k}]")
        k += 1
    voice = ";".join(chains) + ";" + "".join(labels) + \
        f"amix=inputs={len(labels)}:normalize=0,apad=whole_dur={total},asplit=2[voice][key]"
    fade_out = f"afade=t=out:st={total - 4}:d=4"
    if music:
        inputs += ["-i", _rel(music)]
        mus = (f"[{k}:a]aresample=48000,aformat=channel_layouts=stereo,atrim=0:{total},"
               f"apad=whole_dur={total},volume=0.55,afade=t=in:d=2,{fade_out}[music]")
    else:  # placeholder until the ACE-Step score is chosen
        mus = (f"sine=f=146.83:d={total}[d1];sine=f=174.61:d={total}[d2];sine=f=220:d={total}[d3];"
               f"[d1][d2][d3]amix=inputs=3,volume=0.25,aresample=48000,"
               f"aformat=channel_layouts=stereo,afade=t=in:d=3,{fade_out}[music]")
    d = sb["music"]["duck"]
    graph = (f"{voice};{mus};"
             f"[voice]aformat=channel_layouts=stereo[voice2];"
             f"[music][key]sidechaincompress=threshold={d['threshold']}:ratio={d['ratio']}:"
             f"attack={d['attack_ms']}:release={d['release_ms']}[ducked];"
             f"[voice2][ducked]amix=inputs=2:normalize=0,"
             f"loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000[aout]")
    return inputs, graph


def render(sb, fmt: str, draft: bool, force: bool) -> Path:
    w, h, name = FORMATS[fmt]
    if draft:
        w, h = DRAFT[fmt]
        name += "_draft"
    fps = sb["meta"]["fps"]
    narr = read_manifest(NARR_MANIFEST)
    kf = read_manifest(KF_MANIFEST)
    missing = [s["id"] for s in sb["shots"] if s["id"] not in kf]
    if missing:
        raise SystemExit(f"keyframes missing for {missing}: run `python -m pipeline.keyframes`")
    rows = timeline(sb, narr)
    card = sb["end_card"]["duration_s"]
    total = round(rows[-1]["start"] + rows[-1]["duration"] + card, 2)

    fonts = {"latin": _font(LATIN_FONTS, "latin"), "ethiopic": _font(ETHIOPIC_FONTS, "ethiopic")}
    if not fonts["ethiopic"]:
        print("WARNING: no Ethiopic font found; Amharic title/end-card text skipped. "
              "Put NotoSansEthiopic-Regular.ttf in fonts/ to fix.")
    cache_path = WORK / "clip_cache.json"
    cache = read_manifest(cache_path)

    t0 = time.time()
    clips = []
    for s, r in zip(sb["shots"], rows):
        t = time.time()
        clips.append(_shot_clip(sb, s, r, kf[s["id"]], fmt, w, h, fonts, cache, force))
        write_manifest(cache_path, cache)
        print(f"  {fmt} {s['id']}: {r['duration']:.1f}s ({time.time() - t:.1f}s)", flush=True)
    clips.append(_end_card(sb, fmt, w, h, fonts, fps))

    # Dissolves: transition k starts exactly where shot k+1 starts on the timeline,
    # so picture and narration stay in sync (each clip carries XFADE_S of overlap).
    vin = sum((["-i", _rel(c)] for c in clips), [])
    starts = [r["start"] for r in rows] + [total - card]
    chain, prev = [], "[0:v]"
    for i in range(1, len(clips)):
        lbl = f"[x{i}]" if i < len(clips) - 1 else "[vcat]"
        chain.append(f"{prev}[{i}:v]xfade=transition=fade:duration={XFADE_S}:"
                     f"offset={starts[i]:.3f}{lbl}")
        prev = lbl

    srt = OUT / f"{name}.srt"
    write_srt(rows, narr, srt)
    sub_size = 9 if w < h else 15
    vfinal = (f"[vcat]fade=t=in:st=0:d=1,subtitles={_rel(srt)}:"
              f"force_style='FontName=Arial,FontSize={sub_size},Outline=1,MarginV={40 if w < h else 25}'"
              f",format=yuv420p[vout]")
    music = _music_source(sb)
    ain, agraph = _audio_graph(sb, rows, total, len(clips), music)
    out = OUT / f"{name}.mp4"
    _ff([*vin, *ain, "-filter_complex", ";".join(chain) + ";" + vfinal + ";" + agraph,
         "-map", "[vout]", "-map", "[aout]", "-t", f"{total}", "-r", str(fps),
         "-c:v", "libx264", "-preset", "veryfast" if draft else "medium", "-crf", "20",
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
         _rel(out)], f"final {fmt}")
    log_call("assemble", "ffmpeg", None,
             {"format": fmt, "size": f"{w}x{h}", "total_s": total, "draft": draft,
              "music": _rel(music) if music else "placeholder-drone",
              "wan_clips": [s["id"] for s in sb["shots"] if (CLIPS_IN / f"{s['id']}.mp4").exists()]},
             None, time.time() - t0, "ok", output=_rel(out))
    print(f"{fmt}: {_rel(out)} ({total:.1f}s, {time.time() - t0:.0f}s to render)")
    if not 60 <= total <= 90:
        print(f"WARNING: {total:.1f}s is outside 60-90s")
    return out


def run(fmt: str | None = None, draft: bool = False, force: bool = False) -> None:
    sb = validate()
    OUT.mkdir(parents=True, exist_ok=True)
    for f in ([fmt] if fmt else sb["meta"]["formats"]):
        render(sb, f, draft, force)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--format", choices=list(FORMATS))
    ap.add_argument("--draft", action="store_true", help="half resolution, fast, for checking")
    ap.add_argument("--force", action="store_true", help="re-render all shot clips")
    a = ap.parse_args()
    run(a.format, a.draft, a.force)
