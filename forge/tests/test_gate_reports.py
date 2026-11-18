"""A failing blocking gate must block `continue`, not just be described as blocking.

The off-axis gates (turntable_gate, self_intersection, attachment_anchor) exit 1 on failure and
SKILL.md says a failure "blocks continue", but nothing carried their verdict into the review: an
unattended character run recorded `continue` over a failing self-intersection report on five
passes. append_review now takes `--gate-report [name=]path.json`, records the verdict on the review,
refuses `continue` over a failing one, and a spec can require named reports on every visual continue.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[2]
SCRIPTS = SKILL / "forge"
sys.path.insert(0, str(SCRIPTS / "_shared"))
sys.path.insert(0, str(SCRIPTS / "stage4_review"))

import append_review  # noqa: E402


def run(*args) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, *map(str, args)], capture_output=True, text=True)


class GateVerdictTests(unittest.TestCase):
    def test_reads_each_gate_shape(self):
        self.assertTrue(append_review.gate_report_verdict({"passed": True}))
        self.assertFalse(append_review.gate_report_verdict({"passed": False}))
        self.assertFalse(append_review.gate_report_verdict({"selfIntersecting": True}))
        self.assertTrue(append_review.gate_report_verdict({"selfIntersecting": False}))
        self.assertTrue(append_review.gate_report_verdict({"verdict": "PASS"}))
        self.assertFalse(append_review.gate_report_verdict({"verdict": "fail"}))
        self.assertIsNone(append_review.gate_report_verdict({"something": 1}))

    def test_error_is_a_failure_even_with_clean_flag(self):
        self.assertFalse(append_review.gate_report_verdict({"error": "unreadable mesh", "selfIntersecting": False}))


class AppendReviewGateTests(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.spec = self.dir / "spec.json"
        r = run(SCRIPTS / "stage2_spec" / "new_sculpt_spec.py", "Bust", "--out", self.spec)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.fail_report = self.dir / "self-intersection.json"
        self.fail_report.write_text(json.dumps({"selfIntersecting": True, "meshes": []}))
        self.pass_report = self.dir / "turntable.json"
        self.pass_report.write_text(json.dumps({"passed": True}))

    def review(self, action: str, *extra) -> subprocess.CompletedProcess:
        # optimization-pass is the non-visual pass, so no screenshot evidence is needed to reach the gate check
        return run(SCRIPTS / "stage4_review" / "append_review.py", self.spec, "--pass-id", "optimization-pass",
                   "--force-out-of-order", "--fidelity", "0.8", "--action", action,
                   "--summary", "test", *extra, "--in-place")

    def history(self) -> list:
        return json.loads(self.spec.read_text(encoding="utf-8")).get("reviewHistory", [])

    def test_failing_report_blocks_continue(self):
        r = self.review("continue", "--gate-report", f"self-intersection={self.fail_report}")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("blocking gate failed", r.stderr)
        self.assertEqual(self.history(), [])

    def test_failing_report_is_recorded_on_refine(self):
        r = self.review("refine-code", "--gate-report", f"self-intersection={self.fail_report}")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.history()[-1]["gateReports"][0], {
            "gate": "self-intersection", "path": str(self.fail_report), "passed": False})

    def test_passing_report_allows_continue_and_name_defaults_to_stem(self):
        r = self.review("continue", "--gate-report", str(self.pass_report))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.history()[-1]["gateReports"][0]["gate"], "turntable")

    def test_unrecognised_report_is_refused(self):
        junk = self.dir / "junk.json"
        junk.write_text(json.dumps({"hello": "world"}))
        r = self.review("refine-code", "--gate-report", str(junk))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("no recognisable verdict", r.stderr)

    def test_hand_written_continue_over_failing_gate_does_not_complete_the_pass(self):
        entry = {"passId": "optimization-pass", "action": "continue",
                 "gateReports": [{"gate": "self-intersection", "passed": False}]}
        self.assertFalse(append_review.review_completes_pass({}, entry, "optimization-pass"))
        entry["gateReports"][0]["passed"] = True
        self.assertTrue(append_review.review_completes_pass({}, entry, "optimization-pass"))

    def test_required_gate_reports_are_enforced_on_visual_continue(self):
        spec = json.loads(self.spec.read_text(encoding="utf-8"))
        spec.setdefault("selfCorrectLoop", {}).setdefault("visualAcceptance", {})["requiredGateReports"] = [
            "turntable", "self-intersection"]
        self.spec.write_text(json.dumps(spec), encoding="utf-8")
        render = self.dir / "render.png"
        render.write_bytes(b"\x89PNG\r\n\x1a\n")
        r = run(SCRIPTS / "stage4_review" / "append_review.py", self.spec, "--pass-id", "blockout",
                "--fidelity", "0.9", "--action", "continue", "--summary", "t",
                "--render-screenshot", render, "--comparison-image", render, "--map-stripped-render", render,
                "--ai-vision-score", "0.95", "--gate-report", f"turntable={self.pass_report}", "--in-place")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("self-intersection", r.stderr)


if __name__ == "__main__":
    unittest.main()
