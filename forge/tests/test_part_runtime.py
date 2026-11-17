"""The factory ships the assembly runtime (parts / partOf / pick / explode / manifest) and an
environment binder, instead of every run hand-writing them.

geometry_patterns.md makes "explodable AND clickable from one definition of a part" a build
requirement, but the generator only exposed nodes/meshes; both unattended reconstructions
(mug, hammer) re-implemented explode + pick + the part manifest in a factory patch. Both also hit
three r163+ ignoring material.envMapIntensity without a per-material envMap.
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


def _spec(detail_flag: bool) -> dict:
    tmp = Path(tempfile.mkdtemp())
    out = tmp / "spec.json"
    subprocess.run([sys.executable, str(SCRIPTS / "stage2_spec" / "new_sculpt_spec.py"), "Mug", "--out", str(out)],
                   check=True, capture_output=True, text=True)
    spec = json.loads(out.read_text())
    root = spec["componentTree"][0]
    detail = json.loads(json.dumps(root))
    detail.update({"id": "print", "name": "Print", "role": "decal", "parent": root["id"], "primitive": "box",
                   "transform": {"position": [0, 0, 0.5], "rotation": [0, 0, 0], "scale": [0.3, 0.3, 0.01]}})
    if detail_flag:
        detail["explodeWithParent"] = True
    spec["componentTree"].append(detail)
    return spec


class PartRuntime(unittest.TestCase):
    def test_runtime_is_attached_to_the_model(self):
        ts = generator.generate(_spec(True), "blockout")
        self.assertIn("function attachPartRuntime(root: THREE.Object3D, rt: ProceduralModelRuntime)", ts)
        self.assertIn("root.userData.sculptRuntime = attachPartRuntime(root, { nodes, meshes, sockets, colliders, destructionGroups });", ts)
        for member in ("parts?: string[];", "partOf?:", "pick?:", "explode?:", "manifest?:"):
            self.assertIn(member, ts)

    def test_explode_scales_offsets_not_a_uniform_push(self):
        ts = generator.generate(_spec(True), "blockout")
        self.assertIn("const away = centreOf(rt.meshes[id]).sub(modelCentre);", ts)
        self.assertIn("away.multiplyScalar(amount)", ts)

    def test_component_flag_marks_the_mesh_as_surface_detail(self):
        ts = generator.generate(_spec(True), "blockout")
        self.assertEqual(ts.count(".userData.explodeWithParent = true;"), 1)

    def test_no_flag_no_detail(self):
        """Negative control: without the flag no mesh is marked as surface detail."""
        self.assertNotIn(".userData.explodeWithParent = true;", generator.generate(_spec(False), "blockout"))

    def test_environment_binder_is_exported(self):
        ts = generator.generate(_spec(False), "blockout")
        self.assertIn("export function bindMugEnvironment(", ts)
        self.assertIn("pbr.envMapIntensity *= environmentIntensity;", ts)
        self.assertIn("pbr.envMapIntensity === 1", ts)  # defaults stay on scene.environment


if __name__ == "__main__":
    unittest.main()
