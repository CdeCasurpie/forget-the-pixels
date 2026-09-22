"""Street-overhang envelope, Z-offset wrapper and front-edge classification."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import numpy as np
from shapely.geometry import LineString, Polygon, box

from domain.architecture import (
    BuildingProgram,
    BuildingSpecificationV4,
    MassSpec,
    ParcelContext,
    SitePlan,
)
from modeling.geometry_constraints import outward_normal, projection_envelope
from modeling.grammar import (
    ZOffsetMeshBuilder,
    _is_front_edge,
    generate_v4_mesh,
    street_envelope,
)
from modeling.mesh_builder import MeshBuilder
from modeling.validation import validate_mesh

LOT = ((-5.0, -10.0), (5.0, -10.0), (5.0, 10.0), (-5.0, 10.0), (-5.0, -10.0))


def build_spec(footprint=None, floors=4, finish="premium", fronts=(0,),
               language="balcony_apartments"):
    """A lot whose family guarantees balconies, so envelope reach is testable."""
    levels = tuple(float(i * 2.8) for i in range(floors + 1))
    mass = MassSpec(
        id="main",
        footprint=footprint or LOT,
        base_z=0.0,
        roof_z=floors * 2.8,
        floor_levels=levels,
        role="tower",
        roof_spec=None,
    )
    return BuildingSpecificationV4(
        context=ParcelContext(polygon=LOT, explicit_fronts=fronts),
        program=BuildingProgram(
            use="residential",
            occupancy="medium",
            placement="flush",
            architectural_language=language,
            finish_profile=finish,
            maintenance="average",
            construction_state="completed",
            seed=7,
            primary_color=(0.85, 0.84, 0.78),
            side_wall_finish="raw",
            has_fence=False,
            fence_type="none",
        ),
        site_plan=SitePlan(
            masses=(mass,),
            free_space=(),
            access_nodes=(),
            boundaries=(),
            exclusion_zones=(),
        ),
        facades=(),
        components=(),
        seed=7,
    )


class EnvelopeTests(unittest.TestCase):
    def test_apron_only_grows_in_front_of_declared_street_edges(self):
        parcel = Polygon(LOT)
        envelope = projection_envelope(parcel, [LineString([LOT[0], LOT[1]])], 1.35)
        self.assertTrue(envelope.covers(parcel))
        self.assertTrue(envelope.covers(box(-2, -11.0, 2, -10.0)))  # over the street
        self.assertFalse(envelope.covers(box(-2, 10.0, 2, 11.0)))  # over the rear
        self.assertFalse(envelope.covers(box(5.0, -2, 6.0, 2)))  # over a party wall

    def test_envelope_without_fronts_or_overhang_is_the_parcel(self):
        parcel = Polygon(LOT)
        self.assertTrue(projection_envelope(parcel, [], 1.35).equals(parcel))
        front = [LineString([LOT[0], LOT[1]])]
        self.assertTrue(projection_envelope(parcel, front, 0.0).equals(parcel))

    def test_outward_normal_points_away_from_the_interior(self):
        parcel = Polygon(LOT)
        _, normal, length = outward_normal(parcel, LOT[0], LOT[1])
        np.testing.assert_allclose(normal, [0.0, -1.0], atol=1e-9)
        self.assertAlmostEqual(length, 10.0)
        self.assertEqual(outward_normal(parcel, (0, 0), (0, 0))[0], None)

    def test_structural_mass_stays_in_the_parcel_while_trim_may_overhang(self):
        parcel = Polygon(LOT)
        builder = MeshBuilder(parcel, envelope=box(-5, -12, 5, 10))
        self.assertIs(builder.limit_for("wall"), parcel)
        self.assertIsNot(builder.limit_for("balcony_slab"), parcel)
        self.assertIs(builder.limit_for("balcony_slab", "parcel"), parcel)
        with self.assertRaises(ValueError):
            builder.limit_for("wall", "somewhere_else")

    def test_default_envelope_is_the_parcel(self):
        parcel = Polygon(LOT)
        builder = MeshBuilder(parcel)
        self.assertIs(builder.limit_for("balcony_slab"), parcel)


class ZOffsetTests(unittest.TestCase):
    def setUp(self):
        self.builder = MeshBuilder(box(-20, -20, 20, 20))
        self.wrapped = ZOffsetMeshBuilder(self.builder, 10.0)

    def z_range(self, start):
        z = np.asarray(self.builder.vertices)[start:, 2]
        return float(z.min()), float(z.max())

    def test_every_primitive_is_lifted(self):
        a, t, n = np.array([0.0, 0.0]), np.array([1.0, 0.0]), np.array([0.0, -1.0])
        mark = len(self.builder.vertices)
        self.wrapped.box(a, t, n, 0, 1, 0.0, 1.0, 0.0, 0.5, "plaster", "wall")
        self.assertEqual(self.z_range(mark), (10.0, 11.0))

        mark = len(self.builder.vertices)
        self.wrapped.solid(box(1, 1, 2, 2), 0.0, 1.0, "plaster", "wall")
        self.assertEqual(self.z_range(mark), (10.0, 11.0))

        mark = len(self.builder.vertices)
        self.wrapped.foliage((6.0, 6.0, 0.5), (0.4, 0.4, 0.4), np.random.default_rng(1))
        low, high = self.z_range(mark)
        self.assertGreater(low, 10.0)
        self.assertLess(high, 11.0)

    def test_height_fields_are_lifted_too(self):
        mark = len(self.builder.vertices)
        self.wrapped.solid(
            box(3, 3, 4, 4), lambda x, y: 0.0, lambda x, y: 1.0, "plaster", "wall"
        )
        self.assertEqual(self.z_range(mark), (10.0, 11.0))


class FrontEdgeTests(unittest.TestCase):
    def setUp(self):
        self.spec = build_spec()

    def test_inset_masses_keep_their_street_frontage(self):
        south = np.array([0.0, -1.0])
        for inset in (0.0, 0.1, 0.5, 2.0, 8.0):
            with self.subTest(inset=inset):
                self.assertTrue(
                    _is_front_edge(
                        south,
                        self.spec,
                        (-5.0 + inset, -10.0 + inset),
                        (5.0 - inset, -10.0 + inset),
                    )
                )

    def test_rear_and_party_walls_are_not_fronts(self):
        self.assertFalse(
            _is_front_edge(np.array([0.0, 1.0]), self.spec, (-5, 10), (5, 10))
        )
        self.assertFalse(
            _is_front_edge(np.array([1.0, 0.0]), self.spec, (5, -5), (5, 5))
        )

    def test_segmented_fronts_within_tolerance_still_count(self):
        skew = np.array([0.35, -0.94])
        self.assertTrue(_is_front_edge(skew, self.spec, (-2, -10), (2, -10)))
        steep = np.array([0.8, -0.6])
        self.assertFalse(_is_front_edge(steep, self.spec, (-2, -10), (2, -10)))

    def test_missing_fronts_fall_back_to_the_legacy_rule(self):
        spec = build_spec(fronts=())
        self.assertTrue(_is_front_edge(np.array([0.0, -1.0]), spec, (-5, -10), (5, -10)))
        self.assertFalse(_is_front_edge(np.array([0.0, 1.0]), spec, (-5, 10), (5, 10)))


class BalconyReachTests(unittest.TestCase):
    def test_balconies_are_emitted_and_overhang_the_sidewalk(self):
        spec = build_spec()
        mesh = generate_v4_mesh(spec)
        names = {part["name"] for part in mesh.parts}
        self.assertIn("balcony_slab", names)
        self.assertIn("balcony_handrail", names)

        slab = next(p for p in mesh.parts if p["name"] == "balcony_slab")
        faces = mesh.faces[slab["face_start"] : slab["face_start"] + slab["face_count"]]
        self.assertLess(mesh.vertices[faces, 1].min(), -10.0)

    def test_mesh_fits_the_envelope_and_walls_stay_in_the_parcel(self):
        spec = build_spec()
        mesh = generate_v4_mesh(spec)
        report = validate_mesh(
            mesh, Polygon(LOT), envelope=street_envelope(spec.context)
        )
        self.assertEqual(report["envelope_test"], "passed")

        wall = next(p for p in mesh.parts if p["name"] == "wall")
        faces = mesh.faces[wall["face_start"] : wall["face_start"] + wall["face_count"]]
        self.assertGreaterEqual(mesh.vertices[faces, 1].min(), -10.0 - 1e-6)


if __name__ == "__main__":
    unittest.main()
