"""Perimeter treatment, entrance steps and front-garden planting."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import numpy as np
from shapely.affinity import rotate, translate
from shapely.geometry import Polygon

from domain.architecture import BuildingProgram, MassSpec, ParcelContext, SitePlan
from modeling.boundaries import generate_boundaries
from modeling.mesh_builder import MeshBuilder
from modeling.site import build_site

LOT = Polygon([(-5, -10), (5, -10), (5, 10), (-5, 10)])
BUILT = Polygon([(-5, -6), (5, -6), (5, 10), (-5, 10)])  # set back 4 m from the street


def context_for(lot=LOT, fronts=(0,)):
    return ParcelContext(
        polygon=tuple((float(x), float(y)) for x, y in lot.exterior.coords),
        explicit_fronts=tuple(fronts),
    )


def program_for(fence="reja", has_fence=True):
    return BuildingProgram(
        use="residential",
        occupancy="medium",
        placement="front_setback",
        architectural_language="quiet_house",
        finish_profile="standard",
        maintenance="average",
        construction_state="completed",
        seed=7,
        front_setback=4.0,
        has_fence=has_fence,
        fence_type=fence,
    )


def plan_for(built=BUILT):
    return SitePlan(
        masses=(
            MassSpec(
                id="main_0",
                footprint=tuple((float(x), float(y)) for x, y in built.exterior.coords),
                base_z=0.0,
                roof_z=5.6,
                floor_levels=(0.0, 2.8, 5.6),
                role="main",
                roof_spec=None,
            ),
        ),
        free_space=(),
        access_nodes=(),
        boundaries=(),
        exclusion_zones=(),
    )


def entrance_at(x=-0.6, width=1.2):
    return {
        "origin": np.array([x, -6.0]),
        "tangent": np.array([1.0, 0.0]),
        "normal": np.array([0.0, -1.0]),
        "width": width,
        "base_z": 0.0,
    }


class BoundaryTests(unittest.TestCase):
    def test_street_frontage_comes_from_declared_edges_not_from_coordinates(self):
        # Same lot, moved far from the origin and rotated: the front edge is
        # still edge 0, which a y-near-zero test would have missed entirely.
        moved = rotate(translate(LOT, xoff=600.0, yoff=-250.0), 41, origin="centroid")
        boundaries = generate_boundaries(
            context_for(moved), program_for(), plan_for(
                rotate(translate(BUILT, xoff=600.0, yoff=-250.0), 41,
                       origin=translate(LOT, xoff=600.0, yoff=-250.0).centroid)
            )
        )
        street = [b for b in boundaries if b.is_street]
        self.assertEqual(len(street), 1)
        self.assertIsNotNone(street[0].gate_u)

    def test_edges_already_built_on_get_no_fence(self):
        flush = generate_boundaries(context_for(), program_for(), plan_for(LOT))
        self.assertEqual(flush, [])

    def test_a_long_frontage_also_gets_a_vehicle_gate(self):
        street = [
            b
            for b in generate_boundaries(context_for(), program_for(), plan_for())
            if b.is_street
        ]
        self.assertIsNotNone(street[0].garage_u)
        self.assertGreater(street[0].garage_width, 2.0)

    def test_fences_can_be_switched_off(self):
        self.assertEqual(
            generate_boundaries(context_for(), program_for(has_fence=False), plan_for()),
            [],
        )

    def test_party_edges_get_a_blind_wall_where_no_building_stands(self):
        kinds = {
            b.kind
            for b in generate_boundaries(context_for(), program_for(), plan_for())
            if not b.is_street
        }
        self.assertEqual(kinds, {"solid_wall"})


class SiteBuildTests(unittest.TestCase):
    def build(self, fence="reja", entrances=None):
        builder = MeshBuilder(LOT, envelope=LOT.buffer(1.2))
        planted = build_site(
            builder, context_for(), program_for(fence), plan_for(),
            entrances if entrances is not None else [entrance_at()],
            np.random.default_rng(7),
        )
        return builder.finish(), planted

    def test_a_fence_carries_its_base_bars_cap_and_gates(self):
        mesh, _ = self.build()
        names = {part["name"] for part in mesh.parts}
        self.assertIn("boundary_base", names)
        self.assertIn("fence_bar", names)
        self.assertIn("boundary_cap", names)
        self.assertIn("pedestrian_gate", names)

    def test_each_fence_style_builds(self):
        for style in ("reja", "concreto_bajo", "ladrillos", "concreto"):
            with self.subTest(style=style):
                mesh, _ = self.build(style)
                self.assertGreater(len(mesh.faces), 0)

    def test_doors_get_steps_and_keep_their_approach_clear(self):
        mesh, planted = self.build()
        names = {part["name"] for part in mesh.parts}
        self.assertIn("entrance_step", names)
        self.assertGreater(planted, 0)

        door = entrance_at()
        corridor = Polygon([
            (door["origin"][0] - 0.3, -10.0),
            (door["origin"][0] + door["width"] + 0.3, -10.0),
            (door["origin"][0] + door["width"] + 0.3, -6.0),
            (door["origin"][0] - 0.3, -6.0),
        ])
        for part in mesh.parts:
            if part["name"] != "planting_soil":
                continue
            faces = mesh.faces[part["face_start"]: part["face_start"] + part["face_count"]]
            centre = mesh.vertices[faces].reshape(-1, 3)[:, :2].mean(axis=0)
            self.assertFalse(
                corridor.contains(Polygon(
                    [(centre[0], centre[1]), (centre[0] + 1e-6, centre[1]),
                     (centre[0], centre[1] + 1e-6)]
                ).centroid),
                "planting blocks the door",
            )

    def test_planting_is_skipped_when_there_is_no_garden_left(self):
        builder = MeshBuilder(LOT, envelope=LOT.buffer(1.2))
        planted = build_site(
            builder, context_for(), program_for(), plan_for(LOT), [],
            np.random.default_rng(7),
        )
        self.assertEqual(planted, 0)


if __name__ == "__main__":
    unittest.main()
