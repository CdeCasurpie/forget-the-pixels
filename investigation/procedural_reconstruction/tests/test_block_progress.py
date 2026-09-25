"""Regression checks for the block GLB that previously contained only roofs."""

from pathlib import Path
import sys

import numpy as np
import trimesh
from shapely.geometry.polygon import orient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from domain.models import MeshData
from domain.theta import ReconstructionContext
from modeling.exporters.glb_exporter import export_glb
from modeling.theta import resolve_theta
from scripts.glb_incremental import append_glb
from scripts.step1_select_block import clean_geometry, load_lots, select_block_lots
from scripts.step3_generate_full_block import choose_theta, select_fronts
from spatial.street_fronts import annotate_street_fronts


def test_central_lot_resolves_ground_walls_after_translation():
    lots = load_lots()
    centre, selected, seed_index = select_block_lots(lots)
    assert seed_index in centre and len(selected) > len(centre)
    origin = selected.geometry.union_all().centroid
    selected.geometry = selected.translate(xoff=-origin.x, yoff=-origin.y).apply(clean_geometry)
    selected = annotate_street_fronts(selected)
    row = selected.loc[seed_index]
    fronts, _ = select_fronts(row)
    context = ReconstructionContext(tuple(orient(row.geometry, sign=1).exterior.coords), fronts)
    theta, _ = choose_theta(123, seed_index)
    resolved = resolve_theta(context, theta)
    assert len(resolved.walls) >= 4
    assert resolved.walls[0].base_z == 0


def test_incremental_glb_preserves_both_building_walls(tmp_path):
    material = {"name": "plaster", "color": (0.8, 0.7, 0.6)}

    def triangle(x):
        return MeshData(
            vertices=np.array(((x, 0., 0.), (x + 1., 0., 0.), (x, 0., 2.))),
            faces=np.array(((0, 1, 2),)),
            face_materials=np.array((0,)),
            materials=(material,),
            parts=({"name": "wall", "face_start": 0, "face_count": 1,
                    "assembly_id": "facade", "component_id": "wall_0"},),
        )

    first, second = tmp_path / "first.glb", tmp_path / "second.glb"
    partial, combined = tmp_path / "partial.glb", tmp_path / "combined.glb"
    export_glb(triangle(0), first, library=False)
    export_glb(triangle(10), second, library=False)
    append_glb(None, first, partial, lot_id=1)
    append_glb(partial, second, combined, lot_id=2)
    scene = trimesh.load(combined, force="scene")
    assert sum(len(geometry.faces) for geometry in scene.geometry.values()) == 2
    assert any(name.startswith("lot_1/") for name in scene.graph.nodes_geometry)
    assert any(name.startswith("lot_2/") for name in scene.graph.nodes_geometry)
    assert scene.bounds[0, 0] == 0
    assert scene.bounds[1, 0] == 11
