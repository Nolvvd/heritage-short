"""One command for the whole film: python -m pipeline.run

validate -> narration -> keyframes -> radio cut -> assembly (both formats).
Every stage is cached by the hash of its inputs, so a re-run after editing one
shot in storyboard.json regenerates only that shot (see runs.jsonl).

Music and optional Wan clips come from Kaggle (kaggle/*.ipynb); assembly uses
them when present in outputs/music/ and outputs/clips/, else placeholders.
"""
import argparse
import time

from pipeline import assemble, keyframes, narration, radio_cut
from pipeline.validate import validate


def main(draft: bool = False) -> None:
    t0 = time.time()
    print("== validate"); validate()
    print("== narration"); narration.run()
    print("== keyframes"); keyframes.run()
    print("== radio cut"); radio_cut.run()
    print("== assembly"); assemble.run(draft=draft)
    print(f"== done in {time.time() - t0:.0f}s; outputs/final/")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--draft", action="store_true", help="half-resolution preview")
    main(ap.parse_args().draft)
