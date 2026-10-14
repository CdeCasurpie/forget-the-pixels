"""Regression tests for metric mapping and actual embedded GLB resources."""
import json
import struct
import tempfile
import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import numpy as np
from shapely.geometry import box, Polygon
from modeling.mesh_builder import MeshBuilder
from modeling.exporters.glb_exporter import export_glb
from modeling.texturing.library import MaterialLibrary, default_catalog_path


class PBRTests(unittest.TestCase):
    def test_solid_scale_and_diagonal_clip(self):
        builder = MeshBuilder(Polygon([(0,0),(3,0),(0,3)]))
        builder.box(np.array([0.,0.]),np.array([1.,0.]),np.array([0.,1.]),
                    0,3,0,2,0,3, "stone")
        mesh = builder.finish()
        xyz = mesh.vertices[mesh.faces]
        uv = np.asarray(mesh.corner_uv)
        world = np.linalg.norm(np.cross(xyz[:,1]-xyz[:,0],xyz[:,2]-xyz[:,0]),axis=1)/2
        a,b = uv[:,1]-uv[:,0],uv[:,2]-uv[:,0]
        area = np.abs(a[:,0]*b[:,1]-a[:,1]*b[:,0])/2
        np.testing.assert_allclose(area, world/.8**2, rtol=1e-7)

    def test_glb_embeds_pbr_maps_and_ao(self):
        builder = MeshBuilder(box(-1,-1,4,4))
        builder.solid(box(0,0,2,2),0,2)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/"test.glb"
            export_glb(builder.finish(),path)
            data = path.read_bytes()
            length = struct.unpack_from("<I",data,12)[0]
            tree = json.loads(data[20:20+length])
            mat = tree["materials"][0]
            # glTF layout: metallicRoughness lives inside pbrMetallicRoughness;
            # normal/occlusion textures are top-level material members.
            self.assertIn("metallicRoughnessTexture",mat["pbrMetallicRoughness"])
            self.assertIn("normalTexture",mat)
            self.assertIn("occlusionTexture",mat)
            self.assertTrue(all("bufferView" in image for image in tree["images"]))


class RealCatalogTests(unittest.TestCase):
    def test_default_catalog_resolves_and_loads(self):
        catalog = default_catalog_path()
        self.assertIsNotNone(catalog)
        self.assertTrue(catalog.is_file(), catalog)
        lib = MaterialLibrary(catalog)
        self.assertEqual(lib.warnings, [])
        for name in ("brick_running_bond", "concrete_clean", "stucco_smooth",
                     "galvanized_corrugated", "wood_vertical"):
            tset = lib.get_texture_set(name)
            self.assertIsNotNone(tset, name)
            maps = lib.load_all_maps(name)
            self.assertIn("normal", maps)
            self.assertIn("orm", maps)
        # Documented catalog truth: brick ships base color, stucco and
        # clean concrete do not (procedural baseColorFactor drives them).
        self.assertIn("base_color",
                      lib.load_all_maps("brick_running_bond"))
        self.assertNotIn("base_color",
                         lib.load_all_maps("stucco_smooth"))
        self.assertNotIn("base_color",
                         lib.load_all_maps("concrete_clean"))

    def test_real_maps_embed_per_spec(self):
        """brick/concrete/plaster/metal/wood through the shipped catalog:
        maps attach where the set defines them, scalars defer to ORM."""
        from domain.models import BuildingAppearance, MaterialSpecification

        appearance = BuildingAppearance(materials=(
            MaterialSpecification("plaster", "stucco", (0.85, 0.2, 0.15), 0.82,
                                  texture_set="stucco_smooth", real_scale_m=1.0),
            MaterialSpecification("brick", "brick", (0.6, 0.43, 0.31), 0.88,
                                  texture_set="brick_running_bond",
                                  real_scale_m=1.0),
            MaterialSpecification("metal", "painted_steel", (0.19, 0.22, 0.23),
                                  0.3, metallic=0.75, texture_set=None),
        ), source="test")
        builder = MeshBuilder(box(-5, -5, 15, 5), appearance)
        a = np.array([0.0, 0.0])
        t = np.array([1.0, 0.0])
        n = np.array([0.0, -1.0])
        builder.box(a, t, n, 0, 3, 0, 2, 0, 0.5, "plaster", "wall")
        builder.box(a, t, n, 4, 7, 0, 2, 0, 0.5, "brick", "wall")
        builder.box(a, t, n, 8, 10, 0, 1, 0, 0.2, "metal", "trim")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "real.glb"
            export_glb(builder.finish(), path)
            data = path.read_bytes()
        length = struct.unpack_from("<I", data, 12)[0]
        tree = json.loads(data[20:20 + length])
        by_name = {m["name"]: m for m in tree["materials"]}
        brick, plaster, metal = (by_name["brick"], by_name["plaster"],
                                 by_name["metal"])
        # Brick ships a base color map: texture x procedural factor.
        self.assertIn("baseColorTexture",
                      brick["pbrMetallicRoughness"])
        self.assertIn("normalTexture", brick)
        self.assertIn("metallicRoughnessTexture",
                      brick["pbrMetallicRoughness"])
        self.assertAlmostEqual(
            brick["pbrMetallicRoughness"]["roughnessFactor"], 1.0)
        self.assertAlmostEqual(
            brick["pbrMetallicRoughness"]["metallicFactor"], 1.0)
        # Plaster has no base color map: the procedural wall color rules.
        self.assertNotIn("baseColorTexture",
                         plaster["pbrMetallicRoughness"])
        self.assertIn("normalTexture", plaster)
        factor = plaster["pbrMetallicRoughness"]["baseColorFactor"][:3]
        # Warm red tint survives linearization + uint8 quantization.
        self.assertGreater(factor[0], 0.5)
        self.assertGreater(factor[0], factor[1] * 5)
        self.assertGreater(factor[1], factor[2])
        # Metal has no texture set at all: pure scalars survive.
        self.assertNotIn("baseColorTexture",
                         metal["pbrMetallicRoughness"])
        self.assertAlmostEqual(
            metal["pbrMetallicRoughness"]["metallicFactor"], 0.75)
        self.assertTrue(tree.get("images"))
