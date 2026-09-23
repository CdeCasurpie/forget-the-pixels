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
        bounds_u = [0.25, length - 0.25]
        for c in np.arange(4.0, length - 0.5, 4.0):
            bounds_u += [c - 0.125, c + 0.125]
        bounds_z = []
        for fl in levels[1:]:
            bounds_z += [fl - 0.20, fl]
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


if __name__ == "__main__":
    unittest.main()
