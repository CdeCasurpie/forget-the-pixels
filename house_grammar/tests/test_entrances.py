import json
import numpy as np
import pytest
import trimesh
from dataclasses import replace
from shapely.geometry import box
from domain.theta import from_json,canonical
from modeling.theta import resolve_theta,generate_resolved
from modeling.entrances import build_entrance
from modeling.mesh_builder import MeshBuilder
from test_volumetric_crowns import request


def solve(kind='steps',rise=.48,**changes):
    r=request();t=r['theta'];t['crowns']=[]
    t['facade']['openings']=[dict(kind='door',u_m=4.,v_m=rise,width_m=1.5,height_m=2.5)]
    t['entrances']=[dict(id='access',mass_ref='house:0',edge=0,opening_index=0,kind=kind)|changes]
    req=from_json(json.dumps(r))
    assert canonical(from_json(canonical(req)))==canonical(req)
    return resolve_theta(req.context,req.theta)


@pytest.mark.parametrize('kind,rise,extra',[
    ('steps',0.,{}),('steps',.48,dict(cheek_height_m=.3)),
    ('ramp',.3,dict(run_m=2.5,cheek_height_m=.12)),
    ('passage',0.,dict(run_m=2.,cheek_height_m=2.5))])
def test_access_solids_and_endpoint_levels(kind,rise,extra):
    resolved=solve(kind,rise,**extra);r=resolved.entrances[0]
    mb=MeshBuilder(box(-20,-20,30,30));build_entrance(mb,r);mesh=mb.finish()
    for part in mesh.parts:
        faces=mesh.faces[part['face_start']:part['face_start']+part['face_count']]
        used,indices=np.unique(faces,return_inverse=True)
        solid=trimesh.Trimesh(mesh.vertices[used],indices.reshape(-1,3),process=False)
        assert solid.is_watertight and solid.is_winding_consistent and solid.volume>0
    assert r.top_z_m==rise
    assert r.riser_m<=.18
    assert r.slope_deg<=15
    assert 'entrance_step' not in {p['name'] for p in generate_resolved(resolved).parts}
    assert canonical(resolved)


@pytest.mark.parametrize('changes,match',[
    ({'run_m':20.,'kind':'ramp'},'envelope'),
    ({'run_m':.5,'transition_m':.1,'kind':'ramp'},'slope'),
    ({'opening_index':9},'missing'),({'width_m':.5},'width'),
    ({'kind':'passage'},'equal levels'),({'max_riser_m':0.},'dimensions')])
def test_reject_invalid_access(changes,match):
    with pytest.raises(ValueError,match=match):solve(**changes)


def test_steps_redistribute_risers_and_keep_treads():
    r=solve(rise=.5).entrances[0]
    assert r.step_count==3
    assert r.riser_m==pytest.approx(1/6)
    assert r.length_m==pytest.approx(.9+2*.3)
