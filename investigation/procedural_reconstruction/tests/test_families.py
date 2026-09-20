"""Families preserve geometry, serialization and deterministic composition."""
import sys
import tempfile
import unittest
from pathlib import Path
from dataclasses import asdict
import json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
import numpy as np
from shapely.geometry import Polygon
from procedural_modeling.families import FAMILIES
from procedural_modeling.layout import propose_building
from procedural_modeling.grammar import generate_mesh
from procedural_modeling.validation import validate_mesh
from procedural_modeling.io import read_specification

class FamilyTests(unittest.TestCase):
    def test_families_containment_and_roundtrip(self):
        lot=Polygon([(0,0),(10,0),(10,5),(6,5),(6,12),(0,12)])
        for family in FAMILIES:
            with self.subTest(family=family):
                spec=propose_building(lot,architectural_family=family,seed=19,
                                      floors=3,setback_m=1.2)
                mesh=generate_mesh(spec)
                validate_mesh(mesh,lot)
                self.assertFalse(any(f.cladding=="horizontal" for f in spec.facade_edges))
                with tempfile.TemporaryDirectory() as tmp:
                    path=Path(tmp)/"spec.json"
                    path.write_text(json.dumps({"schema_version":3,**asdict(spec)}))
                    np.testing.assert_array_equal(mesh.vertices,generate_mesh(read_specification(path)).vertices)
    def test_auto_seed_and_invalid_family(self):
        lot=Polygon([(0,0),(8,0),(8,9),(0,9)])
        a=propose_building(lot,architectural_family="auto",seed=9)
        b=propose_building(lot,architectural_family="auto",seed=9)
        self.assertEqual(asdict(a),asdict(b))
        with self.assertRaises(ValueError):
            propose_building(lot,architectural_family="not_a_family")
