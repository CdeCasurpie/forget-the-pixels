"""Component topology baseline: documents the triangle-soup regime.

These tests PASS on the pre-manifold MeshBuilder and exist to pin the starting
point. As primitives migrate to shared topology by construction, the
soup-specific assertions (vertices == 3 * faces, one connected component per
triangle) must be replaced by manifold invariants. See validation.py for the
canonical analyzer once it lands.
"""

import sys
import unittest
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np
from shapely.geometry import box

from modeling.mesh_builder import MeshBuilder


def soup_stats(vertices, faces):
    """Topology metrics over an indexed mesh. Test-local until validation.py
    grows the canonical analyzer."""
    verts = np.asarray(vertices, float).reshape(-1, 3)
    tris = np.asarray(faces, int).reshape(-1, 3)
    parent = list(range(len(verts)))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    edge_count = Counter()
    for a, b, c in tris:
        union(a, b)
        union(b, c)
        for u, v in ((a, b), (b, c), (c, a)):
            edge_count[(min(u, v), max(u, v))] += 1
    roots = {find(i) for i in range(len(verts))}
    areas = (
        np.linalg.norm(np.cross(verts[tris[:, 1]] - verts[tris[:, 0]],
                                verts[tris[:, 2]] - verts[tris[:, 0]]), axis=1) / 2.0
    )
    return {
        "vertices": len(verts),
        "faces": len(tris),
        "connected": len({find(i) for i in range(len(verts)) if any(
            i in tri for tri in tris)}),
        "boundary_edges": sum(1 for n in edge_count.values() if n == 1),
        "non_manifold_edges": sum(1 for n in edge_count.values() if n > 2),
        "min_area": float(areas.min()) if len(areas) else 0.0,
    }


class SoupBaselineTests(unittest.TestCase):
    """Pre-manifold behavior, pinned so the migration is measurable."""

    def test_plain_box_is_triangle_soup_today(self):
        mb = MeshBuilder(box(-5, -5, 5, 5))
        mb.box(np.array([0.0, 0.0]), np.array([1.0, 0.0]), np.array([0.0, -1.0]),
               0, 2.0, 0.0, 0.4, 0.0, 0.3, "stone", "boundary_cap")
        mesh = mb.finish()
        stats = soup_stats(mesh.vertices, mesh.faces)
        self.assertEqual(stats["faces"], 12)
        # Every triangle owns its 3 vertices: no index is ever shared.
        self.assertEqual(stats["vertices"], 3 * stats["faces"])
        self.assertEqual(stats["connected"], stats["faces"])
        self.assertGreater(stats["boundary_edges"], 0)

    def test_beam_is_triangle_soup_today(self):
        mb = MeshBuilder(box(-5, -5, 5, 5))
        mb.beam((0, 0, 0), (0, 0, 1.0), 0.05, material="metal", semantic="rail")
        mesh = mb.finish()
        stats = soup_stats(mesh.vertices, mesh.faces)
        self.assertEqual(stats["vertices"], 3 * stats["faces"])

    def test_solid_extrusion_is_triangle_soup_today(self):
        mb = MeshBuilder(box(-5, -5, 5, 5))
        mb.solid(box(0, 0, 2, 1), 0.0, 0.5, "plaster", "wall")
        mesh = mb.finish()
        self.assertEqual(len(mesh.vertices), 3 * len(mesh.faces))

    def test_v4_building_vertex_to_face_ratio_is_three_today(self):
        from domain.architecture import BuildingProgram, ParcelContext, SitePlan
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
        spec_props = dict(context=ctx, program=program,
                          site_plan=SitePlan(masses=masses, free_space=(),
                                             access_nodes=(), boundaries=(),
                                             exclusion_zones=()),
                          facades=(), components=(), seed=7)
        from domain.architecture import BuildingSpecificationV4
        mesh = generate_v4_mesh(BuildingSpecificationV4(**spec_props))
        ratio = len(mesh.vertices) / len(mesh.faces)
        self.assertAlmostEqual(ratio, 3.0, places=6)


if __name__ == "__main__":
    unittest.main()
