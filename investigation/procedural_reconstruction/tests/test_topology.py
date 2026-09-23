"""Component topology invariants: shared indices from construction.

Every primitive must emit closed, connected, 2-manifold components with
coherently oriented faces. No post-hoc welding is allowed to achieve this;
these tests run on the construction output directly.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np
from shapely.geometry import box

from modeling.mesh_builder import MeshBuilder
from modeling.validation import analyze_topology, component_topology


def only(mesh):
    report = analyze_topology(mesh)
    assert len(report["components"]) == 1, report["components"]
    return report["components"][0]


def assert_closed(test, stats, label=""):
    test.assertEqual(stats["connected"], 1, label)
    test.assertEqual(stats["boundary_edges"], 0, label)
    test.assertEqual(stats["non_manifold_edges"], 0, label)
    test.assertEqual(stats["incoherent_edges"], 0, label)
    test.assertEqual(stats["duplicate_faces"], 0, label)
    test.assertEqual(stats["degenerate_faces"], 0, label)


class PrimitiveTopologyTests(unittest.TestCase):
    def test_plain_box_shares_eight_positions(self):
        mb = MeshBuilder(box(-5, -5, 5, 5))
        mb.box(np.array([0.0, 0.0]), np.array([1.0, 0.0]), np.array([0.0, -1.0]),
               0, 2.0, 0.0, 0.4, 0.0, 0.3, "stone", "boundary_cap")
        mesh = mb.finish()
        stats = only(mesh)
        self.assertEqual((stats["vertices"], stats["faces"]), (8, 12))
        assert_closed(self, stats, "box")
        self.assertEqual(mesh.corner_uv.shape, (12, 3, 2))
        self.assertIsNotNone(mesh.uv)

    def test_box_is_not_triangle_soup(self):
        mb = MeshBuilder(box(-5, -5, 5, 5))
        mb.box(np.array([0.0, 0.0]), np.array([1.0, 0.0]), np.array([0.0, -1.0]),
               0, 2.0, 0.0, 0.4, 0.0, 0.3, "stone", "boundary_cap")
        mesh = mb.finish()
        self.assertLess(len(mesh.vertices), len(mesh.faces),
                        "a closed box reuses positions; soup would need 3 per face")

    def test_beam_is_a_closed_indexed_cylinder(self):
        mb = MeshBuilder(box(-5, -5, 5, 5))
        mb.beam((0, 0, 0), (0, 0, 1.0), 0.05, material="metal", semantic="rail")
        mesh = mb.finish()
        stats = only(mesh)
        self.assertEqual((stats["vertices"], stats["faces"]), (18, 32))
        assert_closed(self, stats, "beam")

    def test_solid_extrusion_is_closed(self):
        mb = MeshBuilder(box(-5, -5, 5, 5))
        mb.solid(box(0, 0, 2, 1), 0.0, 0.5, "plaster", "wall")
        mesh = mb.finish()
        assert_closed(self, only(mesh), "solid")

    def test_solid_with_hole_keeps_the_hole_and_closes(self):
        ring = box(0, 0, 3, 3).difference(box(1, 1, 2, 2))
        mb = MeshBuilder(box(-5, -5, 5, 5))
        mb.solid(ring, 0.0, 0.5, "plaster", "wall")
        mesh = mb.finish()
        stats = only(mesh)
        assert_closed(self, stats, "solid-with-hole")
        # 4 exterior + 4 hole corners, two levels, shared caps and walls.
        self.assertEqual(stats["vertices"], 16)

    def test_chamfered_box_is_one_closed_shell(self):
        mb = MeshBuilder(box(-5, -5, 5, 5))
        mb.box(np.array([0.0, 0.0]), np.array([1.0, 0.0]), np.array([0.0, -1.0]),
               0, 2.0, 0.0, 0.4, 0.0, 0.3, "stone", "boundary_cap", chamfer=0.02)
        mesh = mb.finish()
        stats = only(mesh)
        self.assertEqual((stats["vertices"], stats["faces"]), (12, 20))
        assert_closed(self, stats, "chamfer")

    def test_foliage_is_a_closed_indexed_ellipsoid(self):
        mb = MeshBuilder(box(-5, -5, 5, 5))
        mb.foliage((0.0, 0.0, 1.0), (0.4, 0.4, 0.4), np.random.default_rng(1))
        mesh = mb.finish()
        stats = only(mesh)
        # 2 poles + 5 rings of 10 shared positions, not 3 per triangle.
        self.assertEqual(stats["vertices"], 52)
        self.assertLess(stats["vertices"], stats["faces"])
        assert_closed(self, stats, "foliage")

    def test_component_identity_survives_finish(self):
        mb = MeshBuilder(box(-5, -5, 5, 5))
        with mb.assembly("window_front_03"):
            with mb.component("window_frame", component_id="window_front_03/frame"):
                mb.beam((0, 0, 0), (0, 0, 1.0), 0.05)
        mesh = mb.finish()
        self.assertEqual(len(mesh.parts), 1)
        part = mesh.parts[0]
        self.assertEqual(part["component_id"], "window_front_03/frame")
        self.assertEqual(part["assembly_id"], "window_front_03")
        self.assertEqual(mesh.components[0]["component_id"], "window_front_03/frame")


class AssemblyTopologyTests(unittest.TestCase):
    def test_facade_wall_with_openings_is_one_shell(self):
        from domain.models import FacadeSpecification, Opening
        from modeling.grammar import facade

        length, total = 9.0, 5.6
        ops = (
            Opening("door", 0.4, 0.04, 1.0, 2.2),
            Opening("window", 2.2, 0.9, 1.6, 1.5),
            Opening("window", 4.6, 0.9, 1.6, 1.5),
            Opening("window", 2.2, 3.7, 1.6, 1.5),
            Opening("window", 4.6, 3.7, 1.6, 1.5),
        )
        spec = FacadeSpecification(
            "edge_0", (0.0, 0.0), (length, 0.0), length, (0.0, -1.0),
            (0.0, 2.8, total), openings=ops, is_front=True)
        mb = MeshBuilder(box(-2, -2, 12, 2))
        facade(mb, spec, total)
        mesh = mb.finish()
        walls = [c for c in analyze_topology(mesh)["components"]
                 if c["semantic"] == "wall"]
        # One coplanar band, one depth: a single shell with five real holes.
        self.assertEqual(len(walls), 1)
        assert_closed(self, walls[0], "facade wall")
        self.assertGreater(walls[0]["faces"], 20)

    def test_window_prefab_rings_are_closed(self):
        from domain.models import Opening
        from modeling.grammar import opening as build_legacy_opening
        from modeling.prefabs import build_opening

        a, t, n = (np.array([0.0, 0.0]), np.array([1.0, 0.0]),
                   np.array([0.0, -1.0]))
        mb = MeshBuilder(box(-2, -2, 12, 2))
        with mb.assembly("w"):
            build_legacy_opening(
                mb, a, t, n,
                Opening("window", 1.0, 0.9, 1.6, 1.5, prefab="legacy"), "vertical")
            build_opening(
                mb, a, t, n,
                Opening("window", 4.0, 0.9, 1.6, 1.5, prefab="slim_window",
                        curtain=0.4))
        mesh = mb.finish()
        report = analyze_topology(mesh)
        rings = [c for c in report["components"]
                 if c["semantic"] in ("window_frame", "slim_frame")]
        self.assertEqual(len(rings), 2)
        for ring in rings:
            assert_closed(self, ring, ring["semantic"])
        # Frame and glazing stay separate physical objects.
        kinds = {c["semantic"] for c in report["components"]}
        self.assertIn("glazing", kinds)
        self.assertEqual(report["total_boundary_edges"], 0)
        self.assertEqual(report["total_non_manifold_edges"], 0)

    def test_fence_is_an_assembly_of_closed_pieces(self):
        from shapely.geometry import LineString
        from modeling.boundaries import BoundarySpec
        from modeling.site import draw_fence

        mb = MeshBuilder(box(-8, -8, 8, 8))
        a = np.array([-5.0, -5.0])
        t = np.array([1.0, 0.0])
        n = np.array([0.0, 1.0])
        with mb.assembly("site/fence_00"):
            draw_fence(mb, a, t, n, 10.0,
                       BoundarySpec(line=LineString([(-5, -5), (5, -5)]),
                                    kind="reja", height=2.1, gate_u=1.0,
                                    gate_width=1.1),
                       np.random.default_rng(7))
        mesh = mb.finish()
        report = analyze_topology(mesh)
        self.assertGreater(report["component_count"], 10)
        for comp in report["components"]:
            assert_closed(self, comp, comp["semantic"])
        ids = [c["component_id"] for c in report["components"]]
        self.assertEqual(len(set(ids)), len(ids), "component ids are unique")

    def test_roof_slab_and_prop_are_closed(self):
        from domain.architecture import BuildingProgram, MassSpec
        from modeling.geometry_constraints import front_lines, parcel_polygon
        from modeling.roofscape import build_roof, plan_roof
        from domain.architecture import ParcelContext

        lot = box(-6, -6, 6, 6)
        coords = tuple((float(x), float(y)) for x, y in lot.exterior.coords)
        context = ParcelContext(polygon=coords, explicit_fronts=(0,))
        mass = MassSpec(id="main_0", footprint=coords, base_z=0.0, roof_z=8.4,
                        floor_levels=(0.0, 2.8, 5.6, 8.4), role="main",
                        roof_spec=None)
        program = BuildingProgram(
            use="residential", occupancy="medium", placement="flush",
            architectural_language="informal", finish_profile="standard",
            maintenance="average", construction_state="completed", seed=7)
        parcel = parcel_polygon(context)
        mb = MeshBuilder(parcel, envelope=parcel.buffer(1.5))
        plan = plan_roof(mass, program, lot, front_lines(context), parcel, 7)
        build_roof(mb, plan, np.random.default_rng(7))
        mesh = mb.finish()
        report = analyze_topology(mesh)
        slabs = [c for c in report["components"] if c["semantic"] == "roof_slab"]
        self.assertTrue(slabs)
        for comp in report["components"]:
            assert_closed(self, comp, comp["semantic"])
        self.assertTrue(all(c["assembly_id"].startswith("roof/main_0")
                            for c in report["components"]))

    def test_v4_building_is_an_assembly_of_closed_components(self):
        from domain.architecture import (BuildingProgram, BuildingSpecificationV4,
                                         ParcelContext, SitePlan)
        from modeling.grammar import generate_v4_mesh
        from modeling.massing import generate_masses

        parcel = box(-4, -6, 4, 6)
        coords = tuple((float(x), float(y)) for x, y in parcel.exterior.coords)
        ctx = ParcelContext(polygon=coords, explicit_fronts=(0,))
        program = BuildingProgram(
            use="residential", occupancy="medium", placement="flush",
            architectural_language="quiet_house", finish_profile="standard",
            maintenance="average", construction_state="completed",
            primary_color=(0.85, 0.84, 0.80), seed=7)
        masses = generate_masses(ctx, program, 5.6, 2.8)
        spec = BuildingSpecificationV4(
            context=ctx, program=program,
            site_plan=SitePlan(masses=masses, free_space=(), access_nodes=(),
                               boundaries=(), exclusion_zones=()),
            facades=(), components=(), seed=7)
        mesh = generate_v4_mesh(spec)
        report = analyze_topology(mesh)
        self.assertLess(len(mesh.vertices), len(mesh.faces),
                        "shared topology: fewer positions than 3 per triangle")
        self.assertEqual(report["total_boundary_edges"], 0)
        self.assertEqual(report["total_non_manifold_edges"], 0)
        for comp in report["components"]:
            self.assertEqual(comp["connected"], 1, comp["component_id"])
        windows = [c["assembly_id"] for c in report["components"]
                   if "/opening_" in c["assembly_id"]]
        self.assertTrue(windows, "window assemblies are traceable")


if __name__ == "__main__":
    unittest.main()
