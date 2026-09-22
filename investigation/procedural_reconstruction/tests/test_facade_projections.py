"""The facade projection vocabulary: every kind builds, and stays in bounds."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import numpy as np
from shapely.geometry import Polygon, box

from domain.models import FacadeProjection
from modeling.grammar import projection
from modeling.mesh_builder import MeshBuilder
from modeling.prefabs_facade import FACADE_PROJECTIONS, LEGACY_KINDS

# Facade running along +X at y = 0, outward normal pointing to -Y.
ORIGIN = np.array([0.0, 0.0])
TANGENT = np.array([1.0, 0.0])
NORMAL = np.array([0.0, -1.0])
PARCEL = box(-2.0, -0.01, 12.0, 14.0)
ENVELOPE = box(-2.0, -2.0, 12.0, 14.0)

# Dimensions that make architectural sense for each kind.
FIXTURES = {
    "panel": dict(v_m=3.0, width_m=4.0, height_m=0.6, depth_m=0.10),
    "frame": dict(v_m=3.0, width_m=4.0, height_m=2.4, depth_m=0.14,
                  border_width_m=0.16),
    "ledge": dict(v_m=3.2, width_m=2.2, height_m=0.09, depth_m=0.18),
    "canopy": dict(v_m=2.6, width_m=1.8, height_m=0.12, depth_m=0.45),
    "curved_canopy": dict(v_m=2.6, width_m=2.6, height_m=0.14, depth_m=0.55),
    "cornice": dict(v_m=8.2, width_m=7.0, height_m=0.34, depth_m=0.30),
    "sill_band": dict(v_m=3.4, width_m=7.0, height_m=0.10, depth_m=0.14),
    "pilaster": dict(u_m=0.4, v_m=0.0, width_m=0.34, height_m=8.4, depth_m=0.10),
    "balcony": dict(v_m=3.2, width_m=2.4, height_m=1.05, depth_m=0.95),
    "gallery": dict(v_m=3.0, width_m=7.0, height_m=2.5, depth_m=1.15),
    "awning": dict(v_m=2.7, width_m=3.6, height_m=0.42, depth_m=1.10),
    "bay_window": dict(v_m=3.1, width_m=2.2, height_m=2.3, depth_m=0.65),
    "eave": dict(v_m=8.2, width_m=7.0, height_m=0.30, depth_m=0.55),
    "shutter": dict(u_m=2.0, v_m=3.4, width_m=1.3, height_m=1.5, depth_m=0.05,
                    border_width_m=0.34),
    "downpipe": dict(u_m=6.6, v_m=0.2, width_m=0.12, height_m=8.0, depth_m=0.10),
    "sign_box": dict(v_m=2.9, width_m=3.0, height_m=0.55, depth_m=0.12,
                     label="TIENDA"),
}

# Semantics each kind must contribute, so a silent no-op cannot pass.
REQUIRED = {
    "panel": "facade_projection_panel",
    "frame": "facade_projection_frame",
    "ledge": "facade_projection_ledge",
    "canopy": "facade_projection_canopy",
    "curved_canopy": "facade_projection_curved_canopy",
    "cornice": "cornice_step",
    "sill_band": "sill_band",
    "pilaster": "pilaster",
    "balcony": "balcony_slab",
    "gallery": "gallery_post",
    "awning": "awning",
    "bay_window": "bay_window_wall",
    "eave": "rafter_tail",
    "shutter": "shutter_slat",
    "downpipe": "downpipe",
    "sign_box": "sign_box",
}


def feature_for(kind, **overrides):
    fields = dict(u_m=1.0, v_m=3.0, width_m=3.0, height_m=0.5, depth_m=0.3,
                  material_slot="stone", border_width_m=0.18, label="")
    fields.update(FIXTURES.get(kind, {}))
    fields.update(overrides)
    return FacadeProjection(kind=kind, **fields)


def build(kind, *, parcel=PARCEL, envelope=ENVELOPE, **overrides):
    builder = MeshBuilder(parcel, envelope=envelope)
    projection(builder, ORIGIN, TANGENT, NORMAL, feature_for(kind, **overrides))
    return builder.finish()


class VocabularyTests(unittest.TestCase):
    def test_every_kind_builds_its_characteristic_geometry(self):
        for kind in FACADE_PROJECTIONS:
            with self.subTest(kind=kind):
                mesh = build(kind)
                self.assertGreater(len(mesh.faces), 0, f"{kind} emitted nothing")
                names = {part["name"] for part in mesh.parts}
                self.assertIn(REQUIRED[kind], names)

    def test_the_legacy_kinds_keep_their_part_names(self):
        for kind in LEGACY_KINDS:
            with self.subTest(kind=kind):
                names = {part["name"] for part in build(kind).parts}
                self.assertIn(f"facade_projection_{kind}", names)

    def test_unknown_kinds_and_impossible_dimensions_are_rejected(self):
        with self.assertRaises(ValueError):
            build("flying_buttress")
        for bad in ({"width_m": 0.0}, {"height_m": -1.0}, {"depth_m": 0.0}):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    build("ledge", **bad)
        with self.assertRaises(ValueError):
            build("frame", border_width_m=0.0)


class ProjectionReachTests(unittest.TestCase):
    def test_cantilevers_reach_past_the_lot_line_into_the_envelope(self):
        for kind in ("balcony", "gallery", "awning", "bay_window", "eave"):
            with self.subTest(kind=kind):
                mesh = build(kind)
                self.assertLess(
                    mesh.vertices[:, 1].min(), -0.3,
                    f"{kind} did not reach over the pavement",
                )

    def test_a_cantilever_is_dropped_when_there_is_no_room_for_it(self):
        tight = box(-2.0, -0.01, 12.0, 14.0)
        for kind in ("balcony", "gallery", "bay_window"):
            with self.subTest(kind=kind):
                mesh = build(kind, parcel=tight, envelope=tight)
                names = {part["name"] for part in mesh.parts}
                self.assertNotIn(REQUIRED[kind], names)

    def test_a_sign_panel_still_carries_its_lettering(self):
        names = {part["name"] for part in build("panel", label="TIENDA").parts}
        self.assertIn("sign_letter", names)

    def test_a_sign_box_letters_itself_exactly_once(self):
        lettered = [p for p in build("sign_box").parts if p["name"] == "sign_letter"]
        self.assertTrue(lettered)
        # The dispatcher must not letter it a second time on top of the builder.
        strokes_per_letter = 25  # upper bound for the 3x5 glyph grid
        self.assertLessEqual(len(lettered), len("TIENDA") * strokes_per_letter)
        plain = build("sign_box", label="")
        self.assertNotIn("sign_letter", {p["name"] for p in plain.parts})


class BalustradeTests(unittest.TestCase):
    def test_railing_styles_produce_distinct_geometry(self):
        counts = {}
        for style in ("bars", "balusters", "solid"):
            mesh = build("balcony", label=style)
            names = {part["name"] for part in mesh.parts}
            counts[style] = len(mesh.faces)
            if style == "bars":
                self.assertIn("balcony_bar", names)
            else:
                self.assertIn("balustrade", names)
        self.assertEqual(len(set(counts.values())), 3)


if __name__ == "__main__":
    unittest.main()
