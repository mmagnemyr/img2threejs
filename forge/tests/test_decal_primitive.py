"""`primitive: "decal"` projects reference pixels onto another component (three DecalGeometry).

Projection-first is the skill's biggest fidelity lever (SKILL.md 2c), but the generator had no way
to put a photo crop on a built surface: both unattended runs hand-wrote decal shells (a mug's
print; a hammer's stamp, scuff and logo) in factory patches.
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
from validate_sculpt_spec import validate_decal  # noqa: E402

DECAL = {"target": "root", "position": [0, 0.5, 0.5], "orientation": [0, 0, 0], "size": [0.4, 0.4, 0.3],
         "texture": "projection/print.png", "alphaTest": 0.5}


def _spec(decal_first: bool = False, decal: dict | None = None) -> dict:
    tmp = Path(tempfile.mkdtemp())
    out = tmp / "spec.json"
    subprocess.run([sys.executable, str(SCRIPTS / "stage2_spec" / "new_sculpt_spec.py"), "Mug", "--out", str(out)],
                   check=True, capture_output=True, text=True)
    spec = json.loads(out.read_text())
    root = spec["componentTree"][0]
    d = json.loads(json.dumps(root))
    d.update({"id": "print", "name": "Print", "role": "decal", "parent": root["id"], "primitive": "decal",
              "topologyClass": "surface-relief"})
    d["geometryDescriptor"] = {"decal": dict(decal or DECAL)}
    if decal_first:
        spec["componentTree"].insert(0, d)
    else:
        spec["componentTree"].append(d)
    return spec


class DecalValidation(unittest.TestCase):
    def _errors(self, decal: dict, ids=("root", "print")) -> list[str]:
        errors: list[str] = []
        validate_decal({"id": "print", "geometryDescriptor": {"decal": decal}}, set(ids), errors)
        return errors

    def test_valid_decal(self):
        self.assertEqual(self._errors(DECAL), [])

    def test_target_must_exist_and_not_be_self(self):
        self.assertTrue(any("target" in e for e in self._errors(dict(DECAL, target="lid"))))
        self.assertTrue(any("itself" in e for e in self._errors(dict(DECAL, target="print"))))

    def test_geometry_fields(self):
        self.assertTrue(any("size values must be > 0" in e for e in self._errors(dict(DECAL, size=[0.4, 0, 0.3]))))
        self.assertTrue(any("position" in e for e in self._errors(dict(DECAL, position=[0, 1]))))
        self.assertTrue(any("texture" in e for e in self._errors(dict(DECAL, texture=" "))))
        self.assertTrue(any("alphaTest" in e for e in self._errors(dict(DECAL, alphaTest=2))))

    def test_missing_descriptor(self):
        errors: list[str] = []
        validate_decal({"id": "print", "geometryDescriptor": {}}, {"root", "print"}, errors)
        self.assertTrue(any("geometryDescriptor.decal" in e for e in errors))


class DecalGeneration(unittest.TestCase):
    def test_decal_is_projected_onto_its_target(self):
        ts = generator.generate(_spec(), "blockout")
        self.assertIn("import { DecalGeometry } from 'three/examples/jsm/geometries/DecalGeometry.js';", ts)
        self.assertIn('Target = meshes["root"];', ts)
        self.assertIn("new THREE.Vector3(0.4, 0.4, 0.3)", ts)
        self.assertIn('TextureLoader().load("projection/print.png")', ts)
        self.assertIn("Target.matrixWorld).invert()", ts)
        self.assertRegex(ts, r"decal_print_\d+\.userData\.explodeWithParent = true;")

    def test_decal_listed_before_its_target_is_still_emitted_after_it(self):
        ts = generator.generate(_spec(decal_first=True), "blockout")
        self.assertLess(ts.index('meshes["root"] = '), ts.index('Target = meshes["root"];'))

    def test_no_decal_no_import(self):
        """Negative control: a spec without decals does not import DecalGeometry."""
        spec = _spec()
        spec["componentTree"] = [c for c in spec["componentTree"] if c.get("primitive") != "decal"]
        self.assertNotIn("DecalGeometry", generator.generate(spec, "blockout"))


if __name__ == "__main__":
    unittest.main()
