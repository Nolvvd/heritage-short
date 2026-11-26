"""Radio cut: narration over a placeholder drone, ducked, on black, with subtitles.

This is the cheap prototype for user test 1. Shot lengths come from the
measured narration, so the same timeline later drives the picture edit.

Usage: python -m pipeline.radio_cut
"""
import subprocess
import time

from pipeline.common import (OUTPUTS, ROOT, log_call, read_manifest, repo_path,
                             timeline, write_manifest, write_srt)
from pipeline.narration import MANIFEST
from pipeline.validate import validate

OUT = OUTPUTS / "radio_cut"


def run() -> None:
    sb = validate()
    narr = read_manifest(MANIFEST)
    if not narr:
        raise SystemExit("no narration yet: run `make narration` first")
    rows = timeline(sb, narr)
    total = rows[-1]["start"] + rows[-1]["duration"] + sb["end_card"]["duration_s"]
    OUT.mkdir(parents=True, exist_ok=True)
    write_manifest(OUT / "timeline.json", {"total_s": round(total, 2), "shots": rows})
    srt = OUT / "radio_cut.srt"
    write_srt(rows, narr, srt)

    d = sb["music"]["duck"]
    inputs, chains, labels = [], [], []
    for i, r in enumerate(x for x in rows if x["narration"]):
        inputs += ["-i", str(repo_path(r["narration"]))]
        ms = int((r["start"] + 0.5) * 1000)
        chains.append(f"[{i}:a]aresample=48000,aformat=channel_layouts=mono,adelay={ms}[n{i}]")
        labels.append(f"[n{i}]")
    n = len(labels)
    # Placeholder music: a soft D-minor drone (D, F, A), clearly temporary.
    drone = (f"sine=f=146.83:d={total}[d1];sine=f=174.61:d={total}[d2];"
             f"sine=f=220:d={total}[d3];"
             f"[d1][d2][d3]amix=inputs=3,volume=0.25,aresample=48000,"
             f"afade=t=in:d=3,afade=t=out:st={total - 4}:d=4[music]")
    graph = ";".join(chains) + ";" + "".join(labels) + \
        f"amix=inputs={n}:normalize=0,apad=whole_dur={total},asplit=2[voice][key];" + \
        drone + ";" + \
        f"[music][key]sidechaincompress=threshold={d['threshold']}:ratio={d['ratio']}:" \
        f"attack={d['attack_ms']}:release={d['release_ms']}[ducked];" + \
        "[voice][ducked]amix=inputs=2:normalize=0,loudnorm=I=-14:TP=-1:LRA=11[aout]"

    out = OUT / "radio_cut.mp4"
    sub_style = "FontName=DejaVu Sans,FontSize=9,Outline=1,MarginV=50"
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *inputs,
           "-f", "lavfi", "-i", f"color=c=black:s=1080x1920:r={sb['meta']['fps']}:d={total}",
           "-filter_complex", graph + f";[{n}:v]subtitles={srt.relative_to(ROOT).as_posix()}:force_style='{sub_style}'[vout]",
           "-map", "[vout]", "-map", "[aout]", "-t", f"{total}",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "28", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "160k", str(out)]
    t0 = time.time()
    subprocess.run(cmd, check=True, cwd=ROOT)  # relative srt path: Windows drive colons break filter syntax
    log_call("radio_cut", "ffmpeg", None, {"total_s": total, "shots": len(rows)},
             None, time.time() - t0, "ok", output=str(out.relative_to(ROOT)))
    print(f"radio cut: {out} ({total:.1f}s)")
    if not 60 <= total <= 90:
        print(f"WARNING: {total:.1f}s is outside 60-90s; trim narration or min_duration_s")


if __name__ == "__main__":
    run()
