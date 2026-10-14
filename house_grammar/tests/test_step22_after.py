"""Step22 visual-suite artifacts: real parcels, fixed cameras and semantic gains."""
import hashlib
import json
import math
from pathlib import Path

import cv2
import pytest
from shapely.geometry import Polygon

from domain.theta import from_json
from modeling.assembly import mass_polygon
from modeling.theta import resolve_theta


STEP = Path(__file__).resolve().parents[1] / 'steps/step22_massing_before_after'
RECIPES = json.loads((STEP / 'after_recipes.json').read_text())


@pytest.mark.parametrize('folder_name', sorted(RECIPES))
def test_benchmark_after_preserves_input_and_all_present_views(folder_name):
    lot = STEP / 'lotes' / folder_name
    before = json.loads((lot/'before/request.json').read_text())
    after = json.loads((lot/'after/request.json').read_text())
    manifest = json.loads((lot/'after/manifest.json').read_text())
    views = json.loads((STEP/'edificios_a_probar'/folder_name.split('_')[0]/'views.json').read_text())
    labels = json.loads((STEP/'edificios_a_probar'/folder_name.split('_')[0]/'segmentation.json').read_text())['images']
    cameras = json.loads((lot/'after/cameras.json').read_text())
    present = {v['camera_id']:v for v in views['views'] if labels.get(v['camera_id'],{}).get('status') == 'present'}
    requested_before=from_json(json.dumps(before))
    requested_after=from_json(json.dumps(after))
    assert requested_before.context==requested_after.context
    assert requested_before.nuisance==requested_after.nuisance
    assert after['theta']['schema_version']=='0.3'
    assert manifest['before_request_sha256']==hashlib.sha256((lot/'before/request.json').read_bytes()).hexdigest()
    assert manifest['validation']['envelope_test']=='passed'
    assert manifest['comparisons']==len(present)==len(cameras)
    assert {c['camera_id'] for c in cameras}==set(present)
    for cam in cameras:
        ident=cam['camera_id']
        focal=(cam['width']/2)/math.tan(math.radians(present[ident]['horizontal_fov_deg'])/2)
        assert cam['focal_px']==pytest.approx(focal)
        photo=cv2.imread(str(STEP/'edificios_a_probar'/folder_name.split('_')[0]/present[ident]['file']))
        render=cv2.imread(str(lot/'after'/f'render_{ident}.jpg'))
        comparison=cv2.imread(str(lot/'after'/f'compare_{ident}.jpg'))
        assert render is not None and comparison is not None and photo is not None
        assert render.shape==photo.shape
        assert comparison.shape[:2]==(photo.shape[0]+40,2*photo.shape[1])


def test_benchmark_structural_signature_not_just_glb_validity():
    def plan(lot):
        folder=next((STEP/'lotes').glob(f'{lot}_*'))
        request=from_json((folder/'after/request.json').read_text())
        return resolve_theta(request.context,request.theta)

    grifo=plan(1137173)
    assert any(m.kind=='open' for m in grifo.masses)
    assert not [w for w in grifo.walls if w.mass_role.startswith('canopy')]
    assert len([s for s in grifo.structures if s.semantic=='support_column'])>=4
    assert any(z.kind=='parking' for z in grifo.site_zones)

    green=plan(1138283)
    parcel=Polygon(green.context.parcel)
    built=mass_polygon(next(m for m in green.masses if m.base_z==0))
    assert built.area<parcel.area*.8
    assert len([b for b in green.boundaries if b.is_street])>=1
    assert any(z.kind=='patio' for z in green.site_zones)

    block=plan(1138183)
    assert len(block.masses)>=3
    assert len({m.roof_z for m in block.masses})>=2
    assert sum(mass_polygon(m).area for m in block.masses if m.base_z==0)<Polygon(block.context.parcel).area*.6


@pytest.mark.parametrize('lot_id,zone_count', [(1137619,2),(1138323,3)])
def test_facade_zone_demo_preserves_structure_and_cameras(lot_id,zone_count):
    folder=next((STEP/'lotes').glob(f'{lot_id}_*'))
    before=from_json((folder/'after/request.json').read_text())
    after=from_json((folder/'after_facade_zones/request.json').read_text())
    assert before.context==after.context and before.nuisance==after.nuisance
    old=resolve_theta(before.context,before.theta)
    new=resolve_theta(after.context,after.theta)
    assert old.masses==new.masses and old.roofs==new.roofs
    assert old.structures==new.structures and old.site_zones==new.site_zones
    assert old.boundaries==new.boundaries
    assert len(new.theta.massing.components[0].zones)==zone_count
    walls=[w for w in new.walls if '/zone' in w.facade.edge_id]
    edge=max(walls,key=lambda w:w.facade.width_m).edge
    patches=[w for w in walls if w.edge==edge]
    assert len(patches)==zone_count
    assert len({tuple((o.width_m,o.height_m) for o in w.facade.openings) for w in patches})>=2
    original=json.loads((folder/'after/cameras.json').read_text())
    cameras=json.loads((folder/'after_facade_zones/cameras.json').read_text())
    assert original==cameras and len(cameras)==5
    manifest=json.loads((folder/'after_facade_zones/manifest.json').read_text())
    assert manifest['validation']['envelope_test']=='passed'
    assert manifest['comparisons']==5
    assert len(list((folder/'after_facade_zones').glob('compare_*.jpg')))==5
