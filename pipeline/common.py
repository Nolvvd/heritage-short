"""Shared helpers: run logging, content-hash caching, retries, timeline."""
import functools
import hashlib
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUTS = ROOT / "outputs"
RUNS = ROOT / "runs.jsonl"

NARRATION_LEAD_S = 0.5   # silence before a line starts inside its shot
NARRATION_TAIL_S = 0.8   # breathing room after a line ends


def repo_path(p: str) -> Path:
    """Manifest paths are repo-relative; accept Windows backslashes from older runs."""
    return ROOT / p.replace("\\", "/")


def load_env() -> None:
    """Load KEY=VALUE pairs from .env (never committed) into os.environ."""
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def input_hash(*parts) -> str:
    """Stable hash of a stage's inputs. Same inputs -> same hash -> cache hit."""
    blob = json.dumps(parts, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]


def log_call(stage: str, model: str, shot: str | None, params: dict, seed,
             latency_s: float, status: str, cost_usd: float = 0.0,
             cache_hit: bool = False, output: str | None = None,
             error: str | None = None, **extra) -> None:
    """Append one line per model call (or cache hit) to runs.jsonl."""
    rec = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "stage": stage, "model": model, "shot": shot, "params": params,
        "seed": seed, "latency_s": round(latency_s, 3), "status": status,
        "cache_hit": cache_hit, "cost_usd": cost_usd, "output": output,
    }
    if error:
        rec["error"] = error[:500]
    rec.update(extra)
    with RUNS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


class PermanentError(RuntimeError):
    """A request that will fail the same way every time (e.g. HTTP 400): never retried."""


def retry(attempts: int = 3, base_delay: float = 4.0):
    """Retry with exponential backoff; for quota (429) and transient errors."""
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*a, **kw):
            for i in range(attempts):
                try:
                    return fn(*a, **kw)
                except PermanentError:
                    raise
                except Exception as e:  # noqa: BLE001 - re-raised on last attempt
                    if i == attempts - 1:
                        raise
                    delay = base_delay * (2 ** i)
                    print(f"  retry {i + 1}/{attempts - 1} in {delay:.0f}s: {e}")
                    time.sleep(delay)
        return wrapper
    return deco


def read_manifest(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_manifest(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def audio_duration(path: Path) -> float:
    if path.suffix.lower() == ".wav":  # no ffprobe needed for WAV
        import wave
        with wave.open(str(path), "rb") as w:
            return w.getnframes() / w.getframerate()
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def timeline(sb: dict, narration_manifest: dict) -> list[dict]:
    """Shot start/length. The narration sets the length (cut picture to voice)."""
    t, rows = 0.0, []
    for s in sb["shots"]:
        n = narration_manifest.get(s["id"], {})
        need = n.get("duration_s", 0) + NARRATION_LEAD_S + NARRATION_TAIL_S if n else 0
        dur = round(max(s["min_duration_s"], need), 2)
        rows.append({"id": s["id"], "start": round(t, 2), "duration": dur,
                     "narration": n.get("path"), "subtitle": s["narration"]["subtitle_en"]})
        t += dur
    return rows


def _srt_time(sec: float) -> str:
    ms = int(round(sec * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def write_srt(rows: list[dict], narration_manifest: dict, path: Path) -> None:
    lines = []
    for i, r in enumerate(rows, 1):
        start = r["start"] + NARRATION_LEAD_S
        speech = narration_manifest.get(r["id"], {}).get("duration_s", r["duration"] - 1)
        end = min(r["start"] + r["duration"], start + speech + 0.3)
        lines += [str(i), f"{_srt_time(start)} --> {_srt_time(end)}", r["subtitle"], ""]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
