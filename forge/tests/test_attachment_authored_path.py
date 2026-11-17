"""An attached tube/curve-sweep keeps its authored path instead of becoming an endpoint cylinder.

`tube` and `curve-sweep` are ATTACHMENT_PRIMITIVES. With an attachment block the generator used to
build `new THREE.CylinderGeometry(...)` between attachment.localStart and localEnd and drop the
authored `tubePath` / `curveSweep`. A handle requires an attachment, and a constant-section
`tapered-sweep` is refused by strict-quality, so a curved, constant-section loop with two roots on
one parent (a mug handle) could not be generated at all: it shipped as a short vertical bar.
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
sys.path.insert(0, str(SCRIPTS / "stage2_spec"))
sys.path.insert(0, str(SCRIPTS / "stage3_build"))

import generate_threejs_factory as generator  # noqa: E402

HANDLE_PATH = [[0.48, 0.74, 0.0], [0.70, 0.73, 0.0], [0.83, 0.55, 0.0], [0.80, 0.30, 0.0],
               [0.62, 0.19, 0.0], [0.48, 0.12, 0.0]]
ATTACHMENT = {"parentSocket": "wall", "localStart": [0.48, 0.74, 0.0], "localEnd": [0.48, 0.12, 0.0],
              "contactType": "embed", "embedDepth": 0.02, "gapTolerance": 0.004}


def _spec(tmp: Path, primitive: str, descriptor: dict) -> dict:
    out = tmp / "spec.json"
    subprocess.run([sys.executable, str(SCRIPTS / "stage2_spec" / "new_sculpt_spec.py"), "Mug",
                    "--out", str(out)], check=True, capture_output=True, text=True)
    spec = json.loads(out.read_text())
    root = spec["componentTree"][0]
    handle = json.loads(json.dumps(root))
    handle.update({"id": "handle", "name": "Handle", "role": "handle", "parent": root["id"],
                   "primitive": primitive, "attachment": dict(ATTACHMENT),
                   "transform": {"position": [0, 0, 0], "rotation": [0, 0, 0], "scale": [1, 1, 1]}})
    handle["geometryDescriptor"] = dict(handle.get("geometryDescriptor") or {}, **descriptor)
    spec["componentTree"].append(handle)
    return spec


def _handle_block(ts: str) -> str:
    # from the handle's endpoint binding (emitted just before its pivot) to its mesh registration
    start = ts.index("const endpoint_handle_")
    return ts[start:ts.index('meshes["handle"]', start)]


# The factory always emits `endpoint ? new THREE.CylinderGeometry(...) : <authored geometry>`;
# which branch runs is decided by the endpoint binding: makeAttachmentEndpoint(null) -> authored.
AUTHORED = "makeAttachmentEndpoint(null)"
ENDPOINT = "makeAttachmentEndpoint(attachment_handle_"


class AttachedAuthoredPath(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def test_attached_tube_with_path_builds_the_path(self):
        spec = _spec(self.tmp, "tube", {"tubePath": {"points": HANDLE_PATH, "radius": 0.03}})
        block = _handle_block(generator.generate(spec, "blockout"))
        self.assertIn(AUTHORED, block)
        self.assertNotIn(ENDPOINT, block)
        self.assertIn("buildTubeGeometry({\"points\": [[0.48, 0.74, 0.0], [0.7, 0.73, 0.0], [0.83, 0.55", block)

    def test_attached_curve_sweep_with_spine_builds_the_sweep(self):
        sweep = {"spine": HANDLE_PATH,
                 "crossSection": {"points": [[-0.03, -0.03], [0.03, -0.03], [0.03, 0.03], [-0.03, 0.03]]},
                 "closed": False}
        block = _handle_block(generator.generate(_spec(self.tmp, "curve-sweep", {"curveSweep": sweep}),
                                                 "blockout"))
        self.assertIn("buildCurveSweepGeometry(", block)
        self.assertIn(AUTHORED, block)
        self.assertNotIn(ENDPOINT, block)

    def test_attached_tube_without_path_keeps_the_endpoint_cylinder(self):
        """Negative control: a limb authored only by its endpoints still gets the endpoint cylinder."""
        spec = _spec(self.tmp, "tube", {})
        spec["componentTree"][-1]["geometryDescriptor"].pop("tubePath", None)
        block = _handle_block(generator.generate(spec, "blockout"))
        self.assertIn(ENDPOINT, block)
        self.assertNotIn(AUTHORED, block)

    def test_has_authored_path_needs_two_points(self):
        self.assertTrue(generator.has_authored_path("tube", {"tubePath": {"points": HANDLE_PATH[:2]}}))
        self.assertFalse(generator.has_authored_path("tube", {"tubePath": {"points": HANDLE_PATH[:1]}}))
        self.assertFalse(generator.has_authored_path("tube", {}))
        self.assertFalse(generator.has_authored_path("capsule", {"tubePath": {"points": HANDLE_PATH}}))


if __name__ == "__main__":
    unittest.main()
