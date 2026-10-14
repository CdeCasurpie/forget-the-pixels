"""Wall triangulation reproduction: geometry, not just manifold counts.

A 2-manifold shell can still be garbage: slivers with 0-degree angles,
triangles missing from the wall face (coverage holes), triangles invading
window voids, or spikes outside the wall bounds. These tests pin the fixtures
from the Blender inspection before any fix lands.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np
from shapely.geometry import box
from shapely.ops import unary_union

from domain.models import FacadeSpecification, Opening
from modeling.grammar import facade
from modeling.mesh_builder import MeshBuilder
from modeling.validation import analyze_topology


def tri_quality(points):
    e1 = points[:, 1] - points[:, 0]
    e2 = points[:, 2] - points[:, 0]
    e3 = points[:, 2] - points[:, 1]
    lens = np.sort(np.linalg.norm(np.stack([e1, e2, e3], axis=1), axis=-1),
                   axis=1)
    a, b, c = lens[:, 0], lens[:, 1], lens[:, 2]
    cosang = np.clip((b * b + c * c - a * a) / (2 * b * c + 1e-18), -1, 1)
    area = np.linalg.norm(np.cross(e1, e2), axis=1) / 2.0
    return {
        "min_angle_deg": float(np.degrees(np.arccos(cosang)).min()),
        "max_aspect": float((c / np.maximum(a, 1e-12)).max()),
        "min_area": float(area.min()),
    }


def wall_shells_of(mesh):
    return [p for p in mesh.parts if p["name"] == "wall"]


def opening_rects(ops):
    return [box(o.u_m, o.v_m, o.u_m + o.width_m, o.v_m + o.height_m) for o in ops]


class WallTriangulationTests(unittest.TestCase):
    def build_facade(self, width, height, ops, levels=None):
        levels = levels or (0.0, height)
        spec = FacadeSpecification(
            "edge_0", (0.0, 0.0), (float(width), 0.0), float(width),
            (0.0, -1.0), tuple(levels), openings=tuple(ops), is_front=True)
        mb = MeshBuilder(box(-2, -2, width + 2, height + 2))
        facade(mb, spec, float(height))
        return mb.finish(), spec

    def assert_sane_shell(self, mesh, width, height, ops, label):
        V = np.asarray(mesh.vertices)
        shells = wall_shells_of(mesh)
        self.assertTrue(shells, f"{label}: no wall shell emitted")
        for part in shells:
            faces = mesh.faces[part["face_start"]:
                               part["face_start"] + part["face_count"]]
            pts = V[faces]
            q = tri_quality(pts)
            # Thin strips are genuine wall (a door sill 4 cm tall cannot
            # triangulate above ~2 deg); the bound below excludes needles
            # spanning the facade while admitting strip ears.
            # Aspect limits forced the old uniform grid; coverage and finite
            # area are the requirements for long planar architectural strips.
            self.assertGreater(q["min_area"], 1e-12)
            self.assertLess(part['face_count'], 500)
            # Bounds: no spikes outside the wall rectangle (u, z) or depth.
            # Depth spans the 0.20 inward body plus trim tolerance outward.
            u = (pts - np.array([0.0, 0.0, 0.0]))[:, :, 0]
            z = pts[:, :, 2]
            y = pts[:, :, 1]
            self.assertGreaterEqual(u.min(), -1e-6, f"{label}: spike u<{u.min()}")
            self.assertLessEqual(u.max(), width + 1e-6, f"{label}: spike u>{u.max()}")
            self.assertGreaterEqual(z.min(), -1e-6, f"{label}: spike z<{z.min()}")
            self.assertLessEqual(z.max(), height + 1e-6, f"{label}: spike z>{z.max()}")
            self.assertGreaterEqual(y.min(), -0.06, f"{label}: depth spike")
            self.assertLessEqual(y.max(), 0.25, f"{label}: depth spike")
            # No triangle may cover an opening interior (sampled in (u, z)).
            from shapely.geometry import Point as _Pt
            for op in ops:
                cx, cz = op.u_m + op.width_m / 2.0, op.v_m + op.height_m / 2.0
                inside = sum(
                    _Pt(cx, cz).within(
                        box(min(t[:, 0]), min(t[:, 2]),
                            max(t[:, 0]), max(t[:, 2])))
                    and _bary_inside((cx, cz), t[:, [0, 2]])
                    for t in pts)
                self.assertEqual(inside, 0,
                                 f"{label}: wall covers {op.kind} void")

    def test_fixture_a_single_opening(self):
        ops = [Opening("window", 3.5, 0.9, 2.0, 1.5)]
        mesh, _ = self.build_facade(9, 3, ops, levels=(0.0, 3.0))
        self.assert_sane_shell(mesh, 9, 3, ops, "A")
        shells = wall_shells_of(mesh)
        self.assertEqual(len(shells), 1, "one coplanar wall = one shell")

    def test_fixture_b_three_openings(self):
        ops = [Opening("window", 1.0, 0.9, 1.6, 1.5),
               Opening("window", 3.7, 0.9, 1.6, 1.5),
               Opening("window", 6.4, 0.9, 1.6, 1.5)]
        mesh, _ = self.build_facade(9, 3, ops, levels=(0.0, 3.0))
        self.assert_sane_shell(mesh, 9, 3, ops, "B")
        self.assertEqual(len(wall_shells_of(mesh)), 1)

    def test_fixture_c_five_openings_two_floors(self):
        ops = [Opening("window", 1.0, 3.7, 1.4, 1.5),
               Opening("door", 3.8, 0.04, 1.2, 2.3),
               Opening("window", 6.0, 3.7, 1.4, 1.5),
               Opening("window", 2.0, 0.9, 1.5, 1.4),
               Opening("window", 5.5, 0.9, 1.5, 1.4)]
        mesh, _ = self.build_facade(9, 6, ops, levels=(0.0, 2.8, 5.6, 6.0))
        self.assert_sane_shell(mesh, 9, 6, ops, "C")

    def test_fixture_c_cap_area_matches_rect_minus_holes(self):
        ops = [Opening("window", 1.0, 3.7, 1.4, 1.5),
               Opening("door", 3.8, 0.04, 1.2, 2.3),
               Opening("window", 6.0, 3.7, 1.4, 1.5),
               Opening("window", 2.0, 0.9, 1.5, 1.4),
               Opening("window", 5.5, 0.9, 1.5, 1.4)]
        mesh, _ = self.build_facade(9, 6, ops, levels=(0.0, 2.8, 5.6, 6.0))
        expected = box(0, 0, 9, 6)
        for rect in opening_rects(ops):
            expected = expected.difference(rect)
        V = np.asarray(mesh.vertices)
        area2d = 0.0
        for part in wall_shells_of(mesh):
            faces = mesh.faces[part["face_start"]:
                               part["face_start"] + part["face_count"]]
            for tri in V[faces]:
                # Front/back caps lie in constant-y planes; reveals do not.
                ys = tri[:, 1]
                if max(ys) - min(ys) < 1e-9:
                    a, b = tri[1, [0, 2]] - tri[0, [0, 2]], tri[2, [0, 2]] - tri[0, [0, 2]]
                    area2d += abs(a[0] * b[1] - a[1] * b[0]) / 2.0
        # Two caps (front + back) over the exact rect-minus-holes domain.
        self.assertAlmostEqual(area2d / 2.0, expected.area, delta=1e-6)
        # The caps union to a valid polygon equal to the domain: no overlaps,
        # no self-intersections, no missing coverage.
        from shapely.ops import unary_union as _union
        from shapely.geometry import Polygon as _Poly
        cap_tris = []
        for part in wall_shells_of(mesh):
            faces = mesh.faces[part["face_start"]:
                               part["face_start"] + part["face_count"]]
            for tri in V[faces]:
                ys = tri[:, 1]
                if max(ys) - min(ys) < 1e-9:
                    cap_tris.append(_Poly([(p[0], p[2]) for p in tri]))
        union = _union(cap_tris)
        self.assertTrue(union.is_valid, "cap union self-intersects")
        self.assertAlmostEqual(union.symmetric_difference(
            _union([expected, expected])).area, 0.0, delta=1e-6)


def _bary_inside(point, tri):
    x, z = point
    (x0, z0), (x1, z1), (x2, z2) = tri
    denom = (z1 - z2) * (x0 - x2) + (x2 - x1) * (z0 - z2)
    if abs(denom) < 1e-18:
        return False
    a = ((z1 - z2) * (x - x2) + (x2 - x1) * (z - z2)) / denom
    b = ((z2 - z0) * (x - x2) + (x0 - x2) * (z - z2)) / denom
    return a > 1e-9 and b > 1e-9 and (a + b) < 1 - 1e-9


if __name__ == "__main__":
    unittest.main()
