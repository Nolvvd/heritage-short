"""Validate storyboard.json against the schema plus cross-field rules.

Every other stage calls validate() before doing any work, so a broken
contract fails fast instead of wasting GPU time.

Usage: python -m pipeline.validate [storyboard.json]
"""
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = ROOT / "schema" / "storyboard.schema.json"


class StoryboardError(ValueError):
    pass


def _semantic_checks(sb: dict) -> list[str]:
    errors = []
    ref_ids = {r["id"] for r in sb["references"]}
    shot_ids = [s["id"] for s in sb["shots"]]

    if len(ref_ids) != len(sb["references"]):
        errors.append("duplicate reference ids")
    if len(set(shot_ids)) != len(shot_ids):
        errors.append("duplicate shot ids")

    for s in sb["shots"]:
        for r in s["keyframe"]["refs"] + s["keyframe"].get("text_refs", []):
            if r not in ref_ids:
                errors.append(f"{s['id']}: unknown reference '{r}'")
        for line in s["narration"]["subtitle_en"].split("\n"):
            if len(line) > 48:
                errors.append(f"{s['id']}: subtitle line over 48 chars: '{line}'")
        if s["narration"]["subtitle_en"].count("\n") > 1:
            errors.append(f"{s['id']}: subtitle has more than two lines")

    for c in sb["music"]["cues"]:
        if c["at_shot"] not in shot_ids:
            errors.append(f"music cue points at unknown shot '{c['at_shot']}'")

    seeds = sb["music"].get("seeds", [])
    if seeds and len(seeds) != sb["music"]["candidates"]:
        errors.append("music.seeds length must equal music.candidates")

    minimum = sum(s["min_duration_s"] for s in sb["shots"]) + sb["end_card"]["duration_s"]
    if minimum > 90:
        errors.append(f"minimum film length {minimum:.1f}s exceeds 90s")
    return errors


def validate(path: Path | str = ROOT / "storyboard.json") -> dict:
    sb = json.loads(Path(path).read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    errors = [
        f"{'/'.join(map(str, e.absolute_path)) or '<root>'}: {e.message}"
        for e in Draft202012Validator(schema).iter_errors(sb)
    ]
    if not errors:
        errors = _semantic_checks(sb)
    if errors:
        raise StoryboardError("storyboard invalid:\n  " + "\n  ".join(errors))
    return sb


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else ROOT / "storyboard.json"
    try:
        sb = validate(target)
    except StoryboardError as e:
        print(e, file=sys.stderr)
        sys.exit(1)
    total = sum(s["min_duration_s"] for s in sb["shots"]) + sb["end_card"]["duration_s"]
    print(f"OK: {len(sb['shots'])} shots, minimum length {total:.0f}s")
