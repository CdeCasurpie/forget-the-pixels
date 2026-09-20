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


class PBRTests(unittest.TestCase):
    def test_solid_scale_and_diagonal_clip(self):
        builder = MeshBuilder(Polygon([(0,0),(3,0),(0,3)]))
        builder.box(np.array([0.,0.]),np.array([1.,0.]),np.array([0.,1.]),
                    0,3,0,2,0,3, "stone")
        mesh = builder.finish()
        xyz = mesh.vertices[mesh.faces]
        uv = mesh.uv[mesh.faces]
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
            self.assertIn("normalTexture",mat["pbrMetallicRoughness"])
            self.assertIn("metallicRoughnessTexture",mat["pbrMetallicRoughness"])
            self.assertIn("normalTexture",mat)
            self.assertIn("occlusionTexture",mat)
            self.assertTrue(all("bufferView" in image for image in tree["images"]))
