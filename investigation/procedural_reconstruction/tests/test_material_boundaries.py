"""Serrated material boundaries: reproduction.

A straight architectural boundary (concrete column edge, slab edge, material
region edge) must be a topological edge. Classifying whole triangles by
centroid lets quads straddle the boundary, painting half a quad wrong and
drawing sawteeth along every frame. These tests fail until region cuts
become grid constraints.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np
from shapely.geometry import Polygon as _Poly
from shapely.geometry import box

from domain.models import FacadeMaterialRegion, FacadeSpecification
from modeling.grammar import facade
from modeling.mesh_builder import MeshBuilder


def front_cap_tris(mesh, semantic="wall"):
    V = np.asarray(mesh.vertices)
    out = []
    for part in mesh.parts:
        if part["name"] != semantic:
            continue
        faces = mesh.faces[part["face_start"]:
                           part["face_start"] + part["face_count"]]
        for tri in V[faces]:
            if max(tri[:, 1]) - min(tri[:, 1]) < 1e-9:
                out.append(tri)
    return out


def crossing(tris, bounds_u=(), bounds_z=()):
    cu = sum(1 for t in tris
             if any(min(t[:, 0]) < b < max(t[:, 0]) for b in bounds_u))
    cz = sum(1 for t in tris
             if any(min(t[:, 2]) < b < max(t[:, 2]) for b in bounds_z))
    return cu, cz


class SerratedBoundaryTests(unittest.TestCase):
    def test_brick_side_wall_has_no_crossing_tris(self):
        length, height = 12.0, 8.0
        levels = (0.0, 2.8, 5.6, 8.0)
        spec = FacadeSpecification(
            "edge_9", (0.0, 0.0), (length, 0.0), length, (0.0, 1.0), levels,
            openings=(), is_front=False, wall_material="brick")
        mb = MeshBuilder(box(-2, -2, length + 2, height + 2))
        facade(mb, spec, height)
        mesh = mb.finish()
        tris = front_cap_tris(mesh)
        self.assertTrue(tris)
        # Bounds snapped to the grid contract (nanometres): raw fl-0.2
        # arithmetic sits ~4e-16 off the snapped line.
        bounds_u = [round(0.25, 9), round(length - 0.25, 9)]
        for c in np.arange(4.0, length - 0.5, 4.0):
            bounds_u += [round(c - 0.125, 9), round(c + 0.125, 9)]
        bounds_z = []
        for fl in levels[1:]:
            bounds_z += [round(fl - 0.20, 9), round(fl, 9)]
        cu, cz = crossing(tris, bounds_u, bounds_z)
        self.assertEqual((cu, cz), (0, 0),
                         f"{cu} tris cross columns, {cz} cross slabs")

    def test_front_material_region_has_no_crossing_tris(self):
        length, height = 10.0, 5.6
        levels = (0.0, 2.8, 5.6)
        region = FacadeMaterialRegion(2.0, 2.8, 4.0, 2.8, "accent")
        spec = FacadeSpecification(
            "edge_0", (0.0, 0.0), (length, 0.0), length, (0.0, -1.0), levels,
            openings=(), is_front=True, material_regions=(region,))
        mb = MeshBuilder(box(-2, -2, length + 2, height + 2))
        facade(mb, spec, height)
        mesh = mb.finish()
        tris = front_cap_tris(mesh)
        self.assertTrue(tris)
        cu, cz = crossing(tris, (2.0, 6.0), (2.8, 5.6))
        self.assertEqual((cu, cz), (0, 0),
                         f"{cu} tris cross region sides, {cz} cross top/bottom")


class BoundaryInvariantTests(unittest.TestCase):
    def test_vertical_split_is_topological(self):
        mb = MeshBuilder(box(-2, -2, 14, 8))
        a = np.array([0.0, 0.0])
        t = np.array([1.0, 0.0])
        n = np.array([0.0, -1.0])
        mb.panel(a, t, n, [_Poly([(0, 0), (10, 0), (10, 5), (0, 5)])],
                 -0.2, 0.0,
                 lambda kind, u, v, w: "concrete" if u < 2.0 else "brick",
                 "wall", component_id="wall/00",
                 cuts_u=(2.0,), cuts_z=())
        mesh = mb.finish()
        V = np.asarray(mesh.vertices)
        for part in mesh.parts:
            faces = mesh.faces[part["face_start"]:
                               part["face_start"] + part["face_count"]]
            for tri in V[faces]:
                if max(tri[:, 1]) - min(tri[:, 1]) > 1e-9:
                    continue
                self.assertFalse(min(tri[:, 0]) < 2.0 < max(tri[:, 0]),
                                 "triangle crosses x=2")
                material = mesh.materials[int(
                    mesh.face_materials[part["face_start"]])]["name"]
                _ = material
        # Material follows the split exactly.
        for part in mesh.parts:
            faces = mesh.faces[part["face_start"]:
                               part["face_start"] + part["face_count"]]
            mats = np.asarray(mesh.face_materials)[part["face_start"]:
                                                   part["face_start"] + part["face_count"]]
            for tri, mi in zip(V[faces], mats):
                if max(tri[:, 1]) - min(tri[:, 1]) > 1e-9:
                    continue
                want = "concrete" if np.mean(tri[:, 0]) < 2.0 else "brick"
                self.assertEqual(mesh.materials[int(mi)]["name"], want)

    def test_horizontal_split_is_topological(self):
        mb = MeshBuilder(box(-2, -2, 14, 8))
        a = np.array([0.0, 0.0])
        t = np.array([1.0, 0.0])
        n = np.array([0.0, -1.0])
        mb.panel(a, t, n, [_Poly([(0, 0), (10, 0), (10, 5), (0, 5)])],
                 -0.2, 0.0,
                 lambda kind, u, v, w: "stone" if v < 1.8 else "plaster",
                 "wall", component_id="wall/01",
                 cuts_u=(), cuts_z=(1.8,))
        mesh = mb.finish()
        V = np.asarray(mesh.vertices)
        for part in mesh.parts:
            faces = mesh.faces[part["face_start"]:
                               part["face_start"] + part["face_count"]]
            for tri in V[faces]:
                if max(tri[:, 1]) - min(tri[:, 1]) > 1e-9:
                    continue
                self.assertFalse(min(tri[:, 2]) < 1.8 < max(tri[:, 2]),
                                 "triangle crosses z=1.8")

    def test_side_wall_faces_are_homogeneous(self):
        """Every cap face lies strictly inside its material region: frame
        strips are concrete, the rest brick. Boundary-touching faces may
        read either side; strict interiors must match exactly."""
        from modeling.grammar import _brick_frame_polys

        length, height = 12.0, 8.0
        levels = (0.0, 2.8, 5.6, 8.0)
        spec = FacadeSpecification(
            "edge_9", (0.0, 0.0), (length, 0.0), length, (0.0, 1.0), levels,
            openings=(), is_front=False, wall_material="brick")
        mb = MeshBuilder(box(-2, -2, length + 2, height + 2))
        facade(mb, spec, height)
        mesh = mb.finish()
        frame = _brick_frame_polys(length, height, levels)
        V = np.asarray(mesh.vertices)
        checked = 0
        for part in mesh.parts:
            if part["name"] != "wall":
                continue
            faces = mesh.faces[part["face_start"]:
                               part["face_start"] + part["face_count"]]
            mats = np.asarray(mesh.face_materials)[part["face_start"]:
                                                   part["face_start"] + part["face_count"]]
            for tri, mi in zip(V[faces], mats):
                if max(tri[:, 1]) - min(tri[:, 1]) > 1e-9:
                    continue
                poly = _Poly([(p[0], p[2]) for p in tri])
                slot = mesh.materials[int(mi)]["name"]
                if frame.contains(poly):
                    self.assertEqual(slot, "concrete", f"{poly.wkt[:80]}")
                    checked += 1
                elif _Poly(box(0, 0, length, height)).difference(
                        frame).contains(poly):
                    self.assertEqual(slot, "brick", f"{poly.wkt[:80]}")
                    checked += 1
        self.assertGreater(checked, 100)

    def test_side_wall_coverage_and_depth(self):
        """Concrete+brick projections cover the domain exactly once, at the
        right front planes, with steps only at transitions."""
        from modeling.grammar import _brick_frame_polys
        from shapely.ops import unary_union as _union

        length, height = 12.0, 8.0
        levels = (0.0, 2.8, 5.6, 8.0)
        spec = FacadeSpecification(
            "edge_9", (0.0, 0.0), (length, 0.0), length, (0.0, 1.0), levels,
            openings=(), is_front=False, wall_material="brick")
        mb = MeshBuilder(box(-2, -2, length + 2, height + 2))
        facade(mb, spec, height)
        mesh = mb.finish()
        V = np.asarray(mesh.vertices)
        # NOTE: facade frame here maps w to -y, so front planes read at
        # world y == 0.0 (concrete) and y == 0.015 (brick recess).
        conc, brick = [], []
        for part in mesh.parts:
            if part["name"] != "wall":
                continue
            faces = mesh.faces[part["face_start"]:
                               part["face_start"] + part["face_count"]]
            mats = np.asarray(mesh.face_materials)[part["face_start"]:
                                                   part["face_start"] + part["face_count"]]
            for tri, mi in zip(V[faces], mats):
                if max(tri[:, 1]) - min(tri[:, 1]) > 1e-9:
                    continue
                slot = mesh.materials[int(mi)]["name"]
                poly = _Poly([(p[0], p[2]) for p in tri])
                if abs(tri[0][1]) < 1e-9:
                    if slot == "concrete":
                        conc.append(poly)
                    elif slot == "brick":
                        self.fail("brick must sit 15 mm behind, not at y=0")
                elif abs(tri[0][1] - 0.015) < 1e-9:
                    if slot == "brick":
                        brick.append(poly)
                    elif slot == "concrete":
                        self.fail("concrete must sit flush at y=0")
        frame = _brick_frame_polys(length, height, levels)
        union_c = _union(conc)
        union_b = _union(brick)
        self.assertAlmostEqual(union_c.area, frame.area, delta=1e-6)
        self.assertAlmostEqual(
            union_b.area, box(0, 0, length, height).difference(frame).area,
            delta=1e-6)
        self.assertAlmostEqual(union_c.intersection(union_b).area, 0.0,
                               delta=1e-6)


if __name__ == "__main__":
    unittest.main()
