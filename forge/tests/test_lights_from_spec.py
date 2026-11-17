"""The 'reference' look-dev rig comes from spec.lightingFromPhoto when the spec measured one.

The factory used to emit one fixed template rig per mode (warm key 0xffcf8a, strong hemisphere) and
only copied lightingFromPhoto into userData, so a lighting-pass decision written into the spec never
reached the render. Measured on an enamel mug: reference body falloff 230/178/150 (lit/mid/shaded)
rendered as 234/227/222 with the template, 221/164/156 with the spec's measured rig.
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

MEASURED = [
    {"id": "key", "type": "directional", "position": [-5.0, 1.8, 4.0], "intensity": 2.7, "color": "#EEF3FA",
     "castShadow": True},
    {"id": "fill", "type": "hemisphere", "skyColor": "#D9E2EA", "groundColor": "#5A4436", "intensity": 0.35},
    {"id": "rim", "type": "directional", "position": [3.0, 2.0, -4.0], "intensity": 0.35},
    {"id": "tone", "toneMapping": "ACESFilmic", "exposure": 0.9},
]
PROSE = [
    {"id": "key", "type": "directional", "direction": "upper-front-left", "intensity": 2.2},
    {"id": "fill", "type": "hemisphere", "intensity": 0.6},
    {"id": "tone", "toneMapping": "ACESFilmic"},
]


def _factory(lighting) -> str:
    tmp = Path(tempfile.mkdtemp())
    out = tmp / "spec.json"
    subprocess.run([sys.executable, str(SCRIPTS / "stage2_spec" / "new_sculpt_spec.py"), "Mug", "--out", str(out)],
                   check=True, capture_output=True, text=True)
    spec = json.loads(out.read_text())
    spec["lightingFromPhoto"] = lighting
    return generator.generate(spec, "blockout")


class LightsFromSpec(unittest.TestCase):
    def test_measured_rig_is_emitted_for_reference_mode(self):
        ts = _factory(MEASURED)
        self.assertIn("const photoRig: Array<Record<string, any>> = ", ts)
        self.assertIn("if (mode === 'reference' && photoRig.length > 0) {", ts)
        self.assertIn("-5.0, 1.8, 4.0", ts)
        self.assertIn('"#EEF3FA"', ts)
        self.assertIn("rigSource = 'lightingFromPhoto'", ts)
        # the template rig still exists for neutral / grazing review modes
        self.assertIn("mode === 'grazing' ? 4.2", ts)

    def test_exposure_reaches_the_renderer(self):
        self.assertIn("renderer.toneMappingExposure = 0.9;", _factory(MEASURED))

    def test_prose_only_lighting_keeps_the_template(self):
        """Negative control: the starter spec's descriptive entries change nothing."""
        ts = _factory(PROSE)
        self.assertNotIn("const photoRig", ts)
        self.assertNotIn("toneMappingExposure", ts)
        self.assertIn("mode === 'reference' ? 0xffcf8a", ts)

    def test_rig_parsing(self):
        rig = generator.photo_light_rig(MEASURED)
        self.assertEqual([light["type"] for light in rig], ["directional", "hemisphere", "directional"])
        self.assertEqual(rig[2]["color"], "#ffffff")  # missing colour defaults to white
        self.assertTrue(rig[0]["castShadow"])
        self.assertEqual(generator.photo_light_rig(PROSE), [])
        # a hemisphere alone is not a rig: no key light was measured
        self.assertEqual(generator.photo_light_rig([MEASURED[1]]), [])
        self.assertEqual(generator.photo_light_rig([{"type": "directional", "position": [1, "x", 2], "intensity": 1}]), [])
        self.assertIsNone(generator.photo_tone_exposure(PROSE))


if __name__ == "__main__":
    unittest.main()
