"""Bring the Kaggle music run back into the repo.

Unpacks music_outputs.zip (from kaggle/music_acestep.ipynb) into outputs/music/,
and appends its log lines to runs.jsonl so every model call stays in one log.

Usage: python -m pipeline.import_music path/to/music_outputs.zip
Then listen to outputs/music/candidate_*.wav, set "chosen" in storyboard.json.
"""
import json
import sys
import zipfile
from pathlib import Path

from pipeline.common import OUTPUTS, RUNS

OUT = OUTPUTS / "music"


def run(zip_path: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as z:
        for name in z.namelist():
            base = Path(name).name
            if base.startswith("candidate_") or base in ("runs_music.jsonl", "session.json"):
                (OUT / base).write_bytes(z.read(name))
                print("extracted", base)
    log = OUT / "runs_music.jsonl"
    if log.exists():
        seen = RUNS.read_text(encoding="utf-8") if RUNS.exists() else ""
        new = [l for l in log.read_text(encoding="utf-8").splitlines() if l and l not in seen]
        with RUNS.open("a", encoding="utf-8") as f:
            for l in new:
                f.write(l + "\n")
        print(f"appended {len(new)} music calls to runs.jsonl")
    if (OUT / "session.json").exists():
        print("session:", json.loads((OUT / "session.json").read_text()))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    run(sys.argv[1])
