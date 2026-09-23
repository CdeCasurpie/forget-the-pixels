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


if __name__ == "__main__":
    unittest.main()
