"""Fast tests: no network, no GPU. Run: python -m unittest discover tests"""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from pipeline import common, keyframes
from pipeline.validate import StoryboardError, validate

ROOT = Path(__file__).resolve().parent.parent
SB = json.loads((ROOT / "storyboard.json").read_text(encoding="utf-8"))


def _validate_dict(sb: dict) -> dict:
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(sb, f, ensure_ascii=False)
    return validate(f.name)


class Contract(unittest.TestCase):
    def test_storyboard_is_valid(self):
        self.assertGreaterEqual(len(validate()["shots"]), 8)

    def test_rejects_unknown_reference(self):
        sb = copy.deepcopy(SB)
        sb["shots"][0]["keyframe"]["refs"] = ["no_such_ref"]
        with self.assertRaises(StoryboardError):
            _validate_dict(sb)

    def test_rejects_long_subtitle_line(self):
        sb = copy.deepcopy(SB)
        sb["shots"][0]["narration"]["subtitle_en"] = "x" * 60
        with self.assertRaises(StoryboardError):
            _validate_dict(sb)

    def test_rejects_film_over_90s(self):
        sb = copy.deepcopy(SB)
        for s in sb["shots"]:
            s["min_duration_s"] = 12
        with self.assertRaises(StoryboardError):
            _validate_dict(sb)


class Caching(unittest.TestCase):
    def test_hash_is_stable_and_sensitive(self):
        a = common.input_hash("x", {"b": 1, "a": 2}, "ፊደል")
        self.assertEqual(a, common.input_hash("x", {"a": 2, "b": 1}, "ፊደል"))
        self.assertNotEqual(a, common.input_hash("x", {"a": 2, "b": 1}, "ፊደላት"))

    def test_shot_prompt_changes_only_that_shot(self):
        refs = {r["id"]: r for r in SB["references"]}
        before = [keyframes._shot_prompt(SB, s, refs) for s in SB["shots"]]
        sb = copy.deepcopy(SB)
        sb["shots"][2]["keyframe"]["prompt"] += " softly"
        after = [keyframes._shot_prompt(sb, s, refs) for s in sb["shots"]]
        changed = [i for i, (x, y) in enumerate(zip(before, after)) if x != y]
        self.assertEqual(changed, [2])

    def test_reference_text_is_reused_verbatim(self):
        refs = {r["id"]: r for r in SB["references"]}
        for s in SB["shots"]:
            p = keyframes._shot_prompt(SB, s, refs)
            for rid in s["keyframe"]["refs"] + s["keyframe"].get("text_refs", []):
                self.assertIn(refs[rid]["description"], p)

    def test_windows_manifest_paths_are_portable(self):
        self.assertEqual(common.repo_path(r"outputs\narration\s01.wav"),
                         common.ROOT / "outputs/narration/s01.wav")


class Timeline(unittest.TestCase):
    def test_narration_sets_length_with_minimum(self):
        narr = {s["id"]: {"duration_s": 2.0, "path": "x"} for s in SB["shots"]}
        narr[SB["shots"][0]["id"]]["duration_s"] = 20.0
        rows = common.timeline(SB, narr)
        self.assertAlmostEqual(rows[0]["duration"], 20.0 + common.NARRATION_LEAD_S + common.NARRATION_TAIL_S)
        self.assertEqual(rows[1]["duration"], SB["shots"][1]["min_duration_s"])
        for a, b in zip(rows, rows[1:]):
            self.assertAlmostEqual(a["start"] + a["duration"], b["start"], places=2)

    def test_srt_is_well_formed(self):
        narr = {s["id"]: {"duration_s": 3.0, "path": "x"} for s in SB["shots"]}
        rows = common.timeline(SB, narr)
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "t.srt"
            common.write_srt(rows, narr, p)
            blocks = p.read_text(encoding="utf-8").strip().split("\n\n")
        self.assertEqual(len(blocks), len(SB["shots"]))
        self.assertIn("-->", blocks[0])


if __name__ == "__main__":
    unittest.main()
