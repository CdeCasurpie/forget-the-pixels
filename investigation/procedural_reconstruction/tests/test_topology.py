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
            self.assertEqual(comp["unused_vertices"], 0, comp["component_id"])
        windows = [c["assembly_id"] for c in report["components"]
                   if "/opening_" in c["assembly_id"]]
        self.assertTrue(windows, "window assemblies are traceable")

    def test_open_surface_classification(self):
        """A deliberately thin sheet is an open_surface only when declared;
        undeclared, it is a violation. Grammar glass panes are thin boxes,
        hence closed solids, not surfaces."""
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
        self.assertEqual(report["violations"], [])
        glazing = [c for c in report["components"] if c["semantic"] == "glazing"]
        self.assertTrue(glazing)
        self.assertTrue(all(c["expectation"] == "closed_solid" for c in glazing))

    def test_declared_open_sheet_classifies_as_surface(self):
        mb = MeshBuilder(box(-5, -5, 5, 5))
        mb.begin_component("test_sheet", component_id="sheet/00")
        a = mb.vert((0.0, 0.0, 1.0))
        b = mb.vert((1.0, 0.0, 1.0))
        c = mb.vert((1.0, 0.0, 2.0))
        d = mb.vert((0.0, 0.0, 2.0))
        mi = mb.mat_index("glass")
        mb.tri(a, b, c, ((0, 0), (1, 0), (1, 1)), mi)
        mb.tri(a, c, d, ((0, 0), (1, 1), (0, 1)), mi)
        mb.end_component()
        mesh = mb.finish()
        strict = analyze_topology(mesh)
        self.assertEqual(len(strict["violations"]), 1)
        declared = analyze_topology(mesh, open_semantics=("test_sheet",))
        self.assertEqual(declared["violations"], [])
        self.assertEqual(len(declared["open_components"]), 1)
        self.assertEqual(declared["open_components"][0]["expectation"],
                         "open_surface")


class ExportIdentityTests(unittest.TestCase):
    def test_multi_material_component_exports_one_node(self):
        import json
        import struct
        import tempfile
        from pathlib import Path
        from shapely.geometry import Polygon as _Poly
        from modeling.exporters.glb_exporter import export_glb

        mb = MeshBuilder(box(-5, -5, 5, 5))
        a = np.array([0.0, 0.0])
        t = np.array([1.0, 0.0])
        n = np.array([0.0, -1.0])
        with mb.assembly("wall"):
            mb.panel(a, t, n, [_Poly([(0, 0), (4, 0), (4, 2), (0, 2)])],
                     -0.2, 0.0,
                     lambda kind, u, v, w: "brick" if v < 1.0 else "plaster",
                     "wall", component_id="wall/00")
        mesh = mb.finish()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "multi.glb"
            export_glb(mesh, path)
            data = Path(path).read_bytes()
        length = struct.unpack_from("<I", data, 12)[0]
        tree = json.loads(data[20:20 + length])
        nodes = [x["name"] for x in tree["nodes"]]
        self.assertEqual(nodes, ["wall/wall/00"], nodes)
        prims = tree["meshes"][tree["nodes"][0]["mesh"]]["primitives"]
        self.assertEqual(len(prims), 2, "one primitive per material")
        used = {tree["materials"][p["material"]]["name"] for p in prims}
        self.assertEqual(used, {"brick", "plaster"})

    def test_beam_split_statistics(self):
        """Source shares 18 ring positions; GLB splits only at genuine UV
        seams: 16 side-vs-cap splits, 2 cylinder wrap splits (u=0 and
        u=circumference share a position), 2 shared cap centers."""
        import json
        import struct
        import tempfile
        from pathlib import Path
        from modeling.exporters.glb_exporter import export_glb

        mb = MeshBuilder(box(-5, -5, 5, 5))
        mb.beam((0, 0, 0), (0, 0, 1.0), 0.05, material="metal", semantic="rail")
        mesh = mb.finish()
        self.assertEqual((len(mesh.vertices), len(mesh.faces)), (18, 32))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "beam.glb"
            export_glb(mesh, path)
            data = Path(path).read_bytes()
        length = struct.unpack_from("<I", data, 12)[0]
        tree = json.loads(data[20:20 + length])
        render_verts = sum(
            tree["accessors"][p["attributes"]["POSITION"]]["count"]
            for m in tree["meshes"] for p in m["primitives"])
        self.assertEqual(render_verts, 36)
        self.assertAlmostEqual(render_verts / len(mesh.vertices), 36 / 18)

    def test_obj_preserves_geometric_connectivity(self):
        """OBJ carries separate v/vt indices: the file's v records and face
        indices match the source component exactly (positions shared, UVs
        per corner). Parsed directly: trimesh's own loader would expand
        (v, vt) pairs, which is loader behavior, not file content."""
        import tempfile
        from pathlib import Path
        from modeling.exporters.obj_exporter import export_obj

        mb = MeshBuilder(box(-5, -5, 5, 5))
        mb.beam((0, 0, 0), (0, 0, 1.0), 0.05, material="metal", semantic="rail")
        mesh = mb.finish()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "beam.obj"
            export_obj(mesh, path)
            lines = Path(path).read_text().splitlines()
        verts = [tuple(map(float, ln.split()[1:4])) for ln in lines
                 if ln.startswith("v ")]
        uvs = [tuple(map(float, ln.split()[1:3])) for ln in lines
               if ln.startswith("vt ")]
        faces = [[tuple(map(int, c.split("/"))) for c in ln.split()[1:]]
                 for ln in lines if ln.startswith("f ")]
        self.assertEqual(len(verts), len(mesh.vertices),
                         "one v record per shared position")
        self.assertEqual(len(uvs), 3 * len(mesh.faces),
                         "one vt record per corner")
        self.assertEqual(len(faces), len(mesh.faces))
        for (vi, _), src in zip(faces[0], mesh.faces[0]):
            self.assertEqual(vi - 1, src)
        src_edges = set()
        for a, b, c in np.asarray(mesh.faces):
            for u, v in ((a, b), (b, c), (c, a)):
                pa, pb = tuple(np.asarray(mesh.vertices[u])), tuple(
                    np.asarray(mesh.vertices[v]))
                src_edges.add((min(pa, pb), max(pa, pb)))
        got_edges = set()
        for (a, _), (b, _), (c, _) in faces:
            for u, v in ((a - 1, b - 1), (b - 1, c - 1), (c - 1, a - 1)):
                pa, pb = verts[u], verts[v]
                got_edges.add((min(pa, pb), max(pa, pb)))
        rnd = lambda e: tuple(tuple(round(x, 4) for x in p) for p in e)
        self.assertEqual({rnd(e) for e in src_edges},
                         {rnd(e) for e in got_edges})


    def test_component_ids_are_globally_unique(self):
        """Two walls from different lines of one exposure must never share
        ids: a repeated component id collapses two GLB nodes into one and
        orphans geometry. Rotated lots with setbacks produce multi-line
        exposures, so cover them explicitly."""
        from collections import Counter
        from shapely.affinity import rotate
        from domain.architecture import (BuildingProgram, BuildingSpecificationV4,
                                         ParcelContext, SitePlan)
        from modeling.grammar import generate_v4_mesh
        from modeling.massing import generate_masses

        cases = [
            (box(-4, -6, 4, 6), (0,), 0.0, 7, "quiet_house"),
            (rotate(box(-4.5, -10, 4.5, 10), 37, origin=(0, 0)), (0,), 1.8, 11,
             "galeria_madera"),
            (box(-5.5, -10, 5.5, 10), (0,), 2.6, 23, "mixed_use"),
        ]
        for parcel, fronts, setback, seed, family in cases:
            with self.subTest(seed=seed):
                coords = tuple((float(x), float(y))
                               for x, y in parcel.exterior.coords)
                ctx = ParcelContext(polygon=coords, explicit_fronts=fronts)
                program = BuildingProgram(
                    use="residential", occupancy="medium",
                    placement="front_setback" if setback else "flush",
                    architectural_language=family, finish_profile="standard",
                    maintenance="average", construction_state="completed",
                    front_setback=setback, primary_color=(0.85, 0.84, 0.80),
                    seed=seed, has_fence=bool(setback), fence_type="reja")
                masses = generate_masses(ctx, program, 8.4, 2.8)
                spec = BuildingSpecificationV4(
                    context=ctx, program=program,
                    site_plan=SitePlan(masses=masses, free_space=(),
                                       access_nodes=(), boundaries=(),
                                       exclusion_zones=()),
                    facades=(), components=(), seed=seed)
                mesh = generate_v4_mesh(spec)
                ids = [(p.get("assembly_id", ""), p.get("component_id", ""))
                       for p in mesh.parts]
                dupes = [k for k, v in Counter(ids).items() if v > 1]
                self.assertEqual(dupes, [], f"repeated component ids: {dupes[:3]}")
                # Node identity the exporter relies on: group faces exactly
                # like export_glb does — one node per (part, material) — and
                # require unique node names, else two GLB nodes merge and
                # geometry goes orphan.
                fm = np.asarray(mesh.face_materials)
                seen = Counter()
                for i, part in enumerate(mesh.parts):
                    s = part["face_start"]
                    mats = set(int(m) for m in fm[s:s + part["face_count"]])
                    a = part.get("assembly_id", "")
                    cid = part.get("component_id", f"part_{i}")
                    label = f"{a}/{cid}" if a else cid
                    for mi in mats:
                        seen[f"{label}#{mesh.materials[mi]['name']}"] += 1
                dupes = [k for k, v in seen.items() if v > 1]
                self.assertEqual(dupes, [], f"repeated GLB nodes: {dupes[:3]}")


if __name__ == "__main__":
    unittest.main()
