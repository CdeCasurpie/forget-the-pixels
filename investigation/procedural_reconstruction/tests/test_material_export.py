"""Material export expectations: grammar semantic -> slot -> GLB.

Pins the end-to-end behavior without inventing assets: explicit colors must
survive as linear baseColorFactor, PBR scalars must match the slot, glass
stays translucent and double-sided, and synthetic texture maps (test-local
fixtures, not shipped assets) must wire through when a catalog exists.
"""

import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np
from shapely.geometry import box

from domain.models import BuildingAppearance, MaterialSpecification
from modeling.exporters.glb_exporter import export_glb
from modeling.mesh_builder import MeshBuilder


def srgb_to_linear(c):
    c = np.asarray(c, float)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def glb_tree(path):
    data = Path(path).read_bytes()
    length = struct.unpack_from("<I", data, 12)[0]
    return json.loads(data[20:20 + length])


def appearance_for(colors):
    return BuildingAppearance(
        materials=tuple(
            MaterialSpecification(slot, "test_family", rgb, 0.5, metallic=0.1)
            for slot, rgb in colors.items()
        ),
        source="test",
    )


class ColorSurvivalTests(unittest.TestCase):
    def export_box(self, appearance, tmp):
        mb = MeshBuilder(box(-5, -5, 5, 5), appearance)
        mb.box(np.array([0.0, 0.0]), np.array([1.0, 0.0]), np.array([0.0, -1.0]),
               0, 1.0, 0.0, 1.0, 0.0, 0.5, "plaster", "wall")
        path = Path(tmp) / "box.glb"
        export_glb(mb.finish(), path)
        return glb_tree(path)

    def test_primary_red_green_blue_survive_as_linear_base_color(self):
        for name, rgb in (("red", (1.0, 0.0, 0.0)),
                          ("green", (0.0, 1.0, 0.0)),
                          ("blue", (0.0, 0.0, 1.0))):
            with self.subTest(color=name):
                with tempfile.TemporaryDirectory() as tmp:
                    tree = self.export_box(
                        appearance_for({"plaster": rgb}), tmp)
                    plaster = next(m for m in tree["materials"]
                                   if m["name"] == "plaster")
                    np.testing.assert_allclose(
                        plaster["pbrMetallicRoughness"]["baseColorFactor"],
                        [*srgb_to_linear(rgb), 1.0], rtol=1e-6)
                    self.assertAlmostEqual(
                        plaster["pbrMetallicRoughness"]["roughnessFactor"], 0.5)
                    self.assertAlmostEqual(
                        plaster["pbrMetallicRoughness"]["metallicFactor"], 0.1)

    def test_srgb_conversion_is_pinned(self):
        rgb = (1.0, 0.5, 0.25)
        with tempfile.TemporaryDirectory() as tmp:
            tree = self.export_box(appearance_for({"plaster": rgb}), tmp)
            plaster = next(m for m in tree["materials"]
                           if m["name"] == "plaster")
            factor = plaster["pbrMetallicRoughness"]["baseColorFactor"]
            # Pipeline converts sRGB -> linear; trimesh then quantizes the
            # factor to uint8 on write, so pin round(linear*255)/255 exactly.
            expected = [round(v * 255) / 255 for v in (*srgb_to_linear(rgb), 1.0)]
            np.testing.assert_allclose(factor, expected, rtol=1e-6)

    def test_glass_stays_translucent_and_double_sided(self):
        with tempfile.TemporaryDirectory() as tmp:
            mb = MeshBuilder(box(-5, -5, 5, 5))
            mb.box(np.array([0.0, 0.0]), np.array([1.0, 0.0]),
                   np.array([0.0, -1.0]), 0, 1.0, 0.0, 1.0, 0.0, 0.1,
                   "glass", "glazing")
            path = Path(tmp) / "glass.glb"
            export_glb(mb.finish(), path)
            glass = next(m for m in glb_tree(path)["materials"]
                         if m["name"] == "glass")
            self.assertEqual(glass["alphaMode"], "BLEND")
            # Alpha rides baseColorFactor[3] through trimesh uint8 storage.
            self.assertAlmostEqual(
                glass["pbrMetallicRoughness"]["baseColorFactor"][3],
                round(0.34 * 255) / 255)
            self.assertTrue(glass["doubleSided"])


class GrammarSlotTests(unittest.TestCase):
    def test_rich_building_keeps_every_slot(self):
        from domain.architecture import (BuildingProgram, BuildingSpecificationV4,
                                         ParcelContext, SitePlan)
        from modeling.grammar import generate_v4_mesh
        from modeling.massing import generate_masses

        parcel = box(-4, -6, 4, 6)
        coords = tuple((float(x), float(y)) for x, y in parcel.exterior.coords)
        ctx = ParcelContext(polygon=coords, explicit_fronts=(0,))
        program = BuildingProgram(
            use="mixed", occupancy="medium", placement="flush",
            architectural_language="mixed_use", finish_profile="standard",
            maintenance="average", construction_state="completed",
            primary_color=(0.8, 0.2, 0.2), seed=11)
        masses = generate_masses(ctx, program, 8.4, 2.8)
        spec = BuildingSpecificationV4(
            context=ctx, program=program,
            site_plan=SitePlan(masses=masses, free_space=(), access_nodes=(),
                               boundaries=(), exclusion_zones=()),
            facades=(), components=(), seed=11)
        mesh = generate_v4_mesh(spec)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rich.glb"
            export_glb(mesh, path)
            tree = glb_tree(path)
        names = {m["name"] for m in tree["materials"]}
        for slot in ("plaster", "concrete", "frame", "glass", "metal", "wood",
                     "brick", "stone"):
            self.assertIn(slot, names, f"slot {slot} lost in export")
        # The grammar's red wall color reaches the plaster factor (linear).
        plaster = next(m for m in tree["materials"] if m["name"] == "plaster")
        factor = plaster["pbrMetallicRoughness"]["baseColorFactor"][:3]
        self.assertGreater(factor[0], factor[1],
                           "red primary color must tint plaster warm")

    def test_multi_material_component_keeps_both_primitives(self):
        mb = MeshBuilder(box(-5, -5, 5, 5))
        a = np.array([0.0, 0.0])
        t = np.array([1.0, 0.0])
        n = np.array([0.0, -1.0])
        from shapely.geometry import Polygon as _Poly
        with mb.assembly("wall"):
            mb.panel(a, t, n, [_Poly([(0, 0), (4, 0), (4, 2), (0, 2)])],
                     -0.2, 0.0,
                     lambda kind, u, v, w: "brick" if v < 1.0 else "plaster",
                     "wall", component_id="wall/00")
        mesh = mb.finish()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "multi.glb"
            export_glb(mesh, path)
            tree = glb_tree(path)
        nodes = [x["name"] for x in tree["nodes"]]
        wall_nodes = [x for x in nodes if x.startswith("wall/wall/00")]
        # One logical object per component, even with several materials.
        self.assertEqual(len(wall_nodes), 1, nodes)
        mesh_idx = next(x["mesh"] for x in tree["nodes"]
                        if x["name"] == wall_nodes[0])
        prims = tree["meshes"][mesh_idx]["primitives"]
        self.assertEqual(len(prims), 2, "one primitive per material")
        used = {tree["materials"][p["material"]]["name"] for p in prims}
        self.assertEqual(used, {"brick", "plaster"})


class SyntheticMapTests(unittest.TestCase):
    def make_catalog(self, root):
        from PIL import Image
        d = Path(root) / "maps"
        d.mkdir()
        Image.new("RGB", (4, 4), (200, 100, 50)).save(d / "bc.png")
        Image.new("RGB", (4, 4), (128, 128, 255)).save(d / "n.png")
        Image.new("RGB", (4, 4), (255, 128, 64)).save(d / "orm.png")
        catalog = {
            "test_brick": {
                "maps": {"base_color": "maps/bc.png", "normal": "maps/n.png",
                         "orm": "maps/orm.png"},
                "scale_u": 2.0,
                "scale_v": 2.0,
            }
        }
        path = Path(root) / "catalog.json"
        path.write_text(json.dumps(catalog))
        return path

    def test_texture_maps_wire_through(self):
        from modeling.texturing.library import MaterialLibrary

        with tempfile.TemporaryDirectory() as tmp:
            lib = MaterialLibrary(self.make_catalog(tmp))
            appearance = BuildingAppearance(
                materials=(MaterialSpecification(
                    "brick", "brick", (1.0, 1.0, 1.0), 0.9, texture_set="test_brick",
                    real_scale_m=1.0),),
                source="test")
            mb = MeshBuilder(box(-5, -5, 5, 5), appearance)
            mb.box(np.array([0.0, 0.0]), np.array([1.0, 0.0]),
                   np.array([0.0, -1.0]), 0, 1.0, 0.0, 1.0, 0.0, 0.5,
                   "brick", "wall")
            path = Path(tmp) / "tex.glb"
            export_glb(mb.finish(), path, library=lib)
            tree = glb_tree(path)
        brick = next(m for m in tree["materials"] if m["name"] == "brick")
        pbr = brick["pbrMetallicRoughness"]
        self.assertIn("baseColorTexture", pbr)
        self.assertIn("metallicRoughnessTexture", pbr)
        self.assertIn("normalTexture", brick)
        # With ORM the scalar factors defer to the map.
        self.assertAlmostEqual(pbr["roughnessFactor"], 1.0)
        self.assertAlmostEqual(pbr["metallicFactor"], 1.0)
        self.assertTrue(tree.get("images"), "maps must be embedded")
        self.assertTrue(tree.get("textures"), "maps must be referenced")


class DecalTests(unittest.TestCase):
    def test_decals_export_as_independent_blend_cosmetics(self):
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
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "decals.glb"
            export_glb(mesh, path)
            tree = glb_tree(path)
        names = {m["name"] for m in tree["materials"]}
        self.assertTrue({"decal_moisture", "decal_drip"} & names,
                        "decal cosmetics must survive export")
        for decal in (m for m in tree["materials"]
                      if m["name"].startswith("decal_")):
            self.assertEqual(decal["alphaMode"], "BLEND")
            self.assertAlmostEqual(
                decal["pbrMetallicRoughness"]["baseColorFactor"][3],
                round(0.99 * 255) / 255)
            # The shipped catalog defines decal base-color maps, so they
            # attach; alpha still rides the factor.
            self.assertIn("baseColorTexture",
                          decal["pbrMetallicRoughness"])


if __name__ == "__main__":
    unittest.main()
