"""Acceptance tests for geometric robustness and architectural metadata."""

import json
import tempfile
import unittest
from dataclasses import replace, asdict
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import numpy as np
from shapely.geometry import Polygon, box
import trimesh
import geopandas as gpd
from domain.models import (
    BuildingAppearance,
    BuildingSpecification,
    ExteriorStairSpecification,
    FacadeMaterialRegion,
    FacadeProjection,
    HeightEstimate,
    MaterialSpecification,
    RoofSpecification,
)
from procedural_modeling.grammar import generate_mesh, triangulate_polygon
from procedural_modeling.layout import propose_building
from procedural_modeling.validation import validate_mesh
from procedural_modeling.mesh_builder import MeshBuilder
from procedural_modeling.io import read_specification
from exporters.obj_exporter import export_obj
from exporters.glb_exporter import export_glb
from cadastral_geometry.street_fronts import street_facing_edges
from procedural_modeling.block import build_block_specifications, load_height_fits


class GrammarTests(unittest.TestCase):
    def test_facade_regions_projections_and_exterior_stairs(self):
        parcel = box(0, 0, 12, 14)
        footprint = box(2, 2.2, 10, 12)
        spec = propose_building(
            parcel,
            footprint=footprint,
            front_edges=(0,),
            floors=3,
            height_m=8.4,
            setback_m=0,
            boundary="open",
        )
        front = next(facade for facade in spec.facade_edges if facade.is_front)
        decorated = replace(
            front,
            material_regions=(
                FacadeMaterialRegion(1.1, 2.5, 4.8, 4.8, "accent"),
            ),
            projections=(
                FacadeProjection("frame", 0.8, 2.3, 5.4, 5.2, 0.22, "accent", 0.25),
                FacadeProjection("canopy", 6.4, 2.1, 1.2, 0.18, 0.8, "stone"),
                FacadeProjection("curved_canopy", 1.4, 2.0, 3.2, 0.16, 0.7, "accent"),
            ),
            exterior_stairs=(
                ExteriorStairSpecification(
                    5.9, 0.0, 2.8, flight_width_m=0.8, run_m=1.7,
                    step_count=12, switchback=True, material_slot="accent",
                ),
            ),
        )
        facades = tuple(decorated if f.edge_id == front.edge_id else f for f in spec.facade_edges)
        mesh = generate_mesh(replace(spec, facade_edges=facades))
        validate_mesh(mesh, parcel)
        names = {part["name"] for part in mesh.parts}
        self.assertIn("facade_projection_frame", names)
        self.assertIn("facade_projection_canopy", names)
        self.assertIn("facade_projection_curved_canopy", names)
        self.assertIn("exterior_stair_step", names)
        self.assertIn("exterior_stair_landing", names)
        self.assertIn("stair_handrail", names)

    def test_explicit_footprint_controls_building_and_free_site(self):
        parcel = box(0, 0, 10, 12)
        footprint = box(2, 3, 8, 11)
        appearance = BuildingAppearance(
            materials=(
                MaterialSpecification(
                    "plaster", "painted_stucco", (.72, .31, .20), .66,
                    texture_set="stucco_rough", weathering=.2,
                ),
            ),
            source="manual_prior",
        )
        spec = propose_building(
            parcel, footprint=footprint, front_edges=(3,), floors=2,
            height_m=5.6, setback_m=0, boundary="open",
        )
        spec = replace(spec, appearance=appearance)
        self.assertEqual(spec.metadata["footprint_source"], "explicit")
        self.assertAlmostEqual(Polygon(spec.footprint_xy).area, footprint.area)
        mesh = generate_mesh(spec)
        validate_mesh(mesh, parcel)
        names = {part["name"] for part in mesh.parts}
        self.assertIn("building_slab", names)
        self.assertIn("site_surface", names)
        plaster = next(material for material in mesh.materials if material["name"] == "plaster")
        self.assertEqual(plaster["family"], "painted_stucco")
        self.assertEqual(plaster["color"], (.72, .31, .20))
        self.assertEqual(plaster["roughness"], .66)
        with self.assertRaises(ValueError):
            propose_building(parcel, footprint=box(-1, 0, 8, 8))

    def test_invalid_pbr_material_is_rejected(self):
        spec = propose_building(box(0, 0, 6, 8))
        invalid = BuildingAppearance(
            (MaterialSpecification("glass", "glass", (0, 0, 0), 1.2),)
        )
        with self.assertRaises(ValueError):
            generate_mesh(replace(spec, appearance=invalid))

    def test_street_fronts_reject_shared_wall_and_batch_skips_missing_height(self):
        lots = gpd.GeoDataFrame(
            {"objectid": [10, 11, 12]},
            geometry=[box(0, 0, 4, 4), box(4, 0, 8, 4), box(0, 7, 4, 11)],
            crs=32718,
        )
        edges = street_facing_edges(lots, 0)
        shared = next(edge for edge in edges if edge.outward_normal_xy[0] > 0.9)
        self.assertFalse(shared.is_street_facing)
        self.assertGreaterEqual(sum(edge.is_street_facing for edge in edges), 2)
        heights = {10: HeightEstimate(6.1, 1.0, ("pano",), 5.6, 2, 2.8)}
        specs, report = build_block_specifications(lots, heights, setback_m=0.2)
        self.assertEqual([item[0] for item in specs], [10])
        self.assertEqual(
            {item["reason"] for item in report if item["status"] == "skipped"},
            {"missing_height"},
        )

    def test_foliage_is_closed_and_outward(self):
        builder = MeshBuilder(box(0, 0, 2, 2))
        builder.foliage((1, 1, 0.7), (0.4, 0.4, 0.4), np.random.default_rng(42))
        mesh = builder.finish()
        tree = trimesh.Trimesh(mesh.vertices, mesh.faces, process=False)
        self.assertTrue(tree.is_watertight)
        self.assertTrue(tree.is_winding_consistent)
        self.assertGreater(tree.volume, 0)
        validate_mesh(mesh, box(0, 0, 2, 2))

    def test_rotated_lots_and_low_single_storey(self):
        from shapely.affinity import rotate

        shape = Polygon([(0, 0), (8, 0), (8, 3), (3, 3), (3, 10), (0, 10)])
        for angle in (17, 63, 127):
            parcel = rotate(shape, angle, origin=(0, 0))
            spec = propose_building(
                parcel, setback_m=0.8, style="corner", boundary="fence"
            )
            validate_mesh(generate_mesh(spec), parcel)
        parcel = box(0, 0, 6, 8)
        spec = propose_building(parcel, floors=1, height_m=2, style="narrow")
        validate_mesh(generate_mesh(spec), parcel)

    def test_invalid_numeric_parameters(self):
        for args in (
            {"floors": 2.5},
            {"height_m": float("nan")},
            {"setback_m": float("inf")},
            {"boundary": "typo"},
        ):
            with self.assertRaises(ValueError):
                propose_building(box(0, 0, 6, 8), **args)

    def test_constrained_caps_cover_concavity_and_hole_exactly(self):
        shapes = [
            Polygon([(0, 0), (8, 0), (8, 2), (3, 2), (3, 8), (0, 8)]),
            Polygon(
                box(0, 0, 10, 10).exterior.coords, [box(3, 3, 7, 7).exterior.coords]
            ),
        ]
        for shape in shapes:
            v, f = triangulate_polygon(shape, 5)
            triangles = [Polygon(v[tri, :2]) for tri in f]
            self.assertTrue(all(shape.covers(t) for t in triangles))
            self.assertAlmostEqual(sum(t.area for t in triangles), shape.area, places=8)

    def test_each_clipped_component_is_closed_and_outward(self):
        parcel = Polygon([(0, 0), (5, 0), (5, 2), (2, 2), (2, 5), (0, 5)])
        builder = MeshBuilder(parcel)
        builder.solid(box(-1, -1, 6, 6), 0, 2)
        mesh = builder.finish()
        m = trimesh.Trimesh(mesh.vertices, mesh.faces, process=False)
        self.assertTrue(m.is_watertight)
        self.assertTrue(m.is_winding_consistent)
        self.assertAlmostEqual(m.volume, parcel.area * 2, places=7)

    def test_seed_is_reproducible_and_changes_variant(self):
        parcel = box(0, 0, 8, 10)
        a = generate_mesh(propose_building(parcel, seed=42))
        b = generate_mesh(propose_building(parcel, seed=42))
        np.testing.assert_array_equal(a.vertices, b.vertices)
        np.testing.assert_array_equal(a.faces, b.faces)
        c = generate_mesh(propose_building(parcel, seed=8))
        self.assertFalse(np.array_equal(a.vertices, c.vertices))

    def test_courtyard_and_reversed_winding_are_supported(self):
        parcel = Polygon(
            box(0, 0, 10, 10).exterior.coords, [box(4, 4, 6, 6).exterior.coords]
        )
        spec = BuildingSpecification(
            tuple(parcel.exterior.coords),
            "EPSG:32718",
            HeightEstimate(6, 0, ()),
            footprint_holes=(tuple(parcel.interiors[0].coords),),
            parcel_holes=(tuple(parcel.interiors[0].coords),),
            roof=RoofSpecification(terrace_room=False, canopy=False, water_tank=False),
        )
        for footprint in [spec.footprint_xy, tuple(reversed(spec.footprint_xy))]:
            m = generate_mesh(replace(spec, footprint_xy=footprint))
            self.assertEqual(validate_mesh(m, parcel)["envelope_test"], "passed")

    def test_concave_layout_and_narrow_neck_do_not_leak(self):
        shapes = [
            Polygon([(0, 0), (8, 0), (8, 3), (3, 3), (3, 9), (0, 9)]),
            Polygon(
                [
                    (0, 0),
                    (4, 0),
                    (4, 4),
                    (2.1, 4),
                    (2.1, 8),
                    (4, 8),
                    (4, 12),
                    (0, 12),
                    (0, 8),
                    (1.9, 8),
                    (1.9, 4),
                    (0, 4),
                ]
            ),
        ]
        for poly in shapes:
            spec = BuildingSpecification(
                tuple(poly.exterior.coords), "EPSG:32718", HeightEstimate(6, 0, ())
            )
            validate_mesh(generate_mesh(spec), poly)

    def test_fence_only_on_selected_edges_and_expected_detail(self):
        parcel = Polygon([(0, 0), (10, 0), (10, 12), (0, 12)])
        spec = propose_building(
            parcel, style="corner", front_edges=(0,), boundary="fence", setback_m=1.5
        )
        mesh = generate_mesh(spec)
        names = {p["name"] for p in mesh.parts}
        self.assertTrue(
            {
                "balcony_slab",
                "balcony_return",
                "corrugation",
                "water_tank",
                "security_bar",
                "shrub",
            }
            <= names
        )
        for part in mesh.parts:
            if part["name"] == "fence_bar":
                faces = mesh.faces[
                    part["face_start"] : part["face_start"] + part["face_count"]
                ]
                self.assertLess(np.max(mesh.vertices[faces, 1]), 0.3)
        validate_mesh(mesh, parcel)

    def test_invalid_setback_and_openings_report_errors(self):
        with self.assertRaises(ValueError):
            propose_building(box(0, 0, 3, 3), setback_m=10)
        spec = propose_building(Polygon([(0, 0), (8, 0), (8, 8), (0, 8)]))
        front = next(f for f in spec.facade_edges if f.is_front)
        broken = replace(front, openings=(replace(front.openings[0], width_m=100),))
        with self.assertRaises(ValueError):
            generate_mesh(replace(spec, facade_edges=(broken,)))

    def test_height_and_sloped_roof(self):
        p = box(0, 0, 7, 9)
        for kind in ["flat", "shed", "gable"]:
            s = propose_building(p, height_m=7.1, floors=2, roof_kind=kind)
            m = generate_mesh(s)
            validate_mesh(m, p)
            roof = next(part for part in m.parts if part["name"] == "roof_slab")
            self.assertAlmostEqual(
                m.vertices[
                    m.faces[
                        roof["face_start"] : roof["face_start"] + roof["face_count"]
                    ],
                    2,
                ].max(),
                7.1,
            )

    def test_spec_roundtrip_and_export_axes(self):
        spec = propose_building(box(0, 0, 6, 8), seed=12)
        mesh = generate_mesh(spec)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            (path / "input.json").write_text(
                json.dumps({"schema_version": 3, **asdict(spec)})
            )
            loaded = read_specification(path / "input.json")
            np.testing.assert_array_equal(generate_mesh(loaded).vertices, mesh.vertices)
            export_obj(mesh, path / "house.obj")
            export_glb(mesh, path / "house.glb")
            obj = trimesh.load(path / "house.obj", force="mesh", process=False)
            np.testing.assert_allclose(
                obj.bounds, [mesh.vertices.min(0), mesh.vertices.max(0)], atol=1e-5
            )
            scene = trimesh.load(path / "house.glb", force="scene")
            rotated = mesh.vertices[:, [0, 2, 1]].copy()
            rotated[:, 2] *= -1
            np.testing.assert_allclose(
                scene.bounds, [rotated.min(0), rotated.max(0)], atol=1e-5
            )
