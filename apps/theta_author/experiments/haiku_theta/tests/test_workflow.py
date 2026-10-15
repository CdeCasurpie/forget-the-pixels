import json
from copy import deepcopy

import numpy as np
import pytest

from apps.theta_author.experiments.haiku_theta.case import make_base
from apps.theta_author.experiments.haiku_theta.schemas import STAGES, response_schema
from apps.theta_author.experiments.haiku_theta.workflow import (
    apply_response, validate_floor_grid, materialize,
)
from apps.theta_author.experiments.haiku_theta.client import response_text
from apps.theta_author.experiments.haiku_theta.rendering import camera_rays, angular_views
from apps.theta_author.experiments.haiku_theta.prompting import sections, REFERENCES, GUIDE, message_body
from packages.barranco_imaging.angular import project_points, view_spec
from shapely.geometry import Polygon


@pytest.fixture
def package():
    return dict(snapshot=dict(crs='EPSG:32718',lot=dict(
        geometry=dict(type='Polygon',coordinates=[[[100,200],[112,200],[112,216],[100,216],[100,200]]]),
        fronts=[dict(is_front=True,geometry=dict(type='LineString',coordinates=[[100,200],[112,200]]))])),
        human_parameters=dict(floors=dict(value=2,mode='suggested'),height=dict(value=5.8,mode='suggested'),
            style=dict(value='republicano',mode='suggested'),floor_height_m=2.7,
            first_floor_different=True,first_floor_height_m=3.1))


def reply(stage, changes):
    return json.dumps(dict(stage=stage,changes=changes,evidence=[],notes=[],blockers=[]))


def reading(state):
    return apply_response(state,reply('01_lectura',dict(target_description='Casa',inventory=[],occlusions=[])),[])[0]


def language_state(package):
    state = reading(make_base(package))
    changes = dict(floor_levels_m=state['floor_levels_m'],masses=state['request']['theta']['masses'])
    state = apply_response(state,reply('02_masas',changes),[])[0]
    return apply_response(state,reply('03_lenguaje',dict(architectural_style='moderno')),[])[0]


def test_base_is_local_and_human_floors_override_legacy_flag(package):
    before = deepcopy(package)
    state = make_base(package)
    assert package == before
    assert state['constraints']['floors'] == 2
    assert state['request']['context']['metric_origin'] == [106.,208.,0]
    assert state['request']['context']['fronts'] == [0]
    assert state['floor_levels_m'] == [0,3.1,5.8]
    assert state['request']['theta']['architectural_style'] is None


def test_floor_count_cannot_be_changed(package):
    state = reading(make_base(package))
    masses = deepcopy(state['request']['theta']['masses']); masses[0]['levels_m']=[0,3,6,9]
    with pytest.raises(ValueError,match='Pisos humanos'):
        apply_response(state,reply('02_masas',dict(floor_levels_m=[0,3,6,9],masses=masses)),[])
    assert state['accepted'] == ['01_lectura']


def test_stacked_mass_cannot_hide_extra_storey(package):
    state = make_base(package)
    state['request']['theta']['masses'].append(dict(role='extra',footprint=state['request']['context']['parcel'],levels_m=[5.8,8.4]))
    with pytest.raises(ValueError,match='fuera'):
        validate_floor_grid(state['request'],state['floor_levels_m'],state['constraints'])


def test_fixed_height_and_skipped_internal_levels(package):
    state = make_base(package)
    state['constraints']['height_m']=6
    with pytest.raises(ValueError,match='altura humana'):
        validate_floor_grid(state['request'],state['floor_levels_m'],state['constraints'])
    state['constraints']['height_m']=None
    state['request']['theta']['masses'][0]['levels_m']=[0,5.8]
    with pytest.raises(ValueError,match='omite'):
        validate_floor_grid(state['request'],state['floor_levels_m'],state['constraints'])


def test_windows_preserve_doors_and_disallow_cross_stage_changes(package):
    state = language_state(package)
    door = dict(id='entrada',mass_ref='principal:0',edge=0,opening=dict(
        kind='door',u_m=1.,v_m=.12,width_m=1.2,height_m=2.4,door=dict(model='moderno')))
    state = apply_response(state,reply('04_puertas',dict(placements=[door])),[])[0]
    before = deepcopy(state)
    window = dict(id='ventana',mass_ref='principal:0',edge=0,opening=dict(
        kind='window',u_m=4.,v_m=.9,width_m=1.5,height_m=1.5,prefab='slim_window'))
    new, _ = apply_response(state,reply('05_ventanas',dict(placements=[window])),[])
    assert state == before
    assert new['request']['theta']['facades'][0]['controls']['openings'][0] == state['request']['theta']['facades'][0]['controls']['openings'][0]
    assert len(new['opening_ledger']) == 2
    with pytest.raises(ValueError):
        apply_response(state,reply('05_ventanas',dict(placements=[],masses=[])),[])
    window['opening']['invented_option'] = True
    with pytest.raises(ValueError,match='invented_option'):
        apply_response(state,reply('05_ventanas',dict(placements=[window])),[])


def test_references_and_blockers_do_not_advance(package):
    state = make_base(package)
    obj=json.loads(reply('01_lectura',dict(target_description='casa',inventory=[],occlusions=[])))
    obj['evidence']=[dict(element='casa',view_ids=['inventada'],status='observed',description='x')]
    with pytest.raises(ValueError,match='vista inexistente'):
        apply_response(state,json.dumps(obj),['real'])
    obj['evidence']=[];obj['blockers']=['No identifico el lote']
    with pytest.raises(ValueError,match='Bloqueos'):
        apply_response(state,json.dumps(obj),['real'])
    assert state['accepted']==[]


def test_all_stage_contracts_and_real_mesh(package):
    state = make_base(package)
    payloads = [dict(target_description='Casa de prueba, no observada',inventory=[],occlusions=[]),
        dict(floor_levels_m=state['floor_levels_m'],masses=state['request']['theta']['masses']),
        dict(architectural_style='moderno'),dict(placements=[]),dict(placements=[]),dict(balconies=[]),
        dict(vertical_members=[]),dict(crowns=[],entablatures=[],trim=dict(cornice=dict(enabled=False),plinth=dict(enabled=False)),wall_details=[]),
        dict(roof=dict(kind='flat',parapet_m=.3,props=[]),roofs=[],roof_assemblies=[],canopies=[]),
        dict(site=dict(fence='none',garden=False,runs=[],zones=[]),entrances=[]),
        dict(primary_color=[.7,.6,.5],side_material='plaster',materials=[],wall_materials=[]),
        dict(verdict='accept',findings=[],limitations=['Fixture sintética, no evaluación visual'])]
    for stage,payload in zip(STAGES,payloads):
        assert response_schema(stage)['additionalProperties'] is False
        state,_ = apply_response(state,reply(stage,payload),[])
    result,validation,topology=materialize(state['request'])
    assert validation['envelope_test']=='passed'
    assert len(result.mesh.faces)>0
    assert not topology['violations']
    assert state['review']['verdict']=='accept'


def test_angular_rays_reproduce_image_pixel_centres():
    polygon=Polygon([(100,200),(112,200),(112,216),(100,216)])
    spec=view_spec(polygon,[106,190],size=(31,23))
    rays=camera_rays(spec,np.array([106,208]))
    points=rays[...,3:].reshape(-1,3)*20
    points[:,2]+=spec['camera_height_m']
    projected=project_points(points,spec)
    xx,yy=np.meshgrid(np.arange(31)+.5,np.arange(23)+.5)
    assert np.allclose(projected,np.column_stack([xx.ravel(),yy.ravel()]),atol=1e-5)


def test_actual_angular_render(package,tmp_path):
    pytest.importorskip('open3d')
    import cv2
    state=make_base(package)
    result,_,_=materialize(state['request'])
    spec=view_spec(Polygon(package['snapshot']['lot']['geometry']['coordinates'][0]),[106,190],size=(64,48))
    cv2.imwrite(str(tmp_path/'photo.jpg'),np.full((48,64,3),220,dtype='uint8'))
    paths=angular_views(result.mesh,[dict(id='view',projection=spec,attachment='photo.jpg')],
                        [106,208],tmp_path,tmp_path/'render')
    assert paths==['01_comparison.jpg']
    render=cv2.imread(str(tmp_path/'render/01_render.png'))
    assert np.any(render != np.array([236,239,242]))
    assert cv2.imread(str(tmp_path/'render/01_comparison.jpg')).shape==(80,192,3)


def test_truncated_api_response_is_not_accepted():
    with pytest.raises(ValueError,match='max_tokens'):
        response_text(dict(stop_reason='max_tokens',content=[dict(type='text',text='{}')]))
    assert response_text(dict(stop_reason='end_turn',content=[dict(type='text',text='{}')]))=='{}'


def test_stage_references_are_complete_but_focused():
    text=(GUIDE/'CATALOGOS.md').read_text()
    masses=sections(text,REFERENCES['02_masas'][1])
    assert '## 3. Volúmenes' in masses
    assert 'SupportControls.kind' in masses
    assert '## 6. Balcones' not in masses
    for stage,(guide,catalog) in REFERENCES.items():
        assert sections((GUIDE/'README.md').read_text(),guide),stage
        assert sections(text,catalog),stage


def test_relative_components_use_cadastre_without_losing_later_openings(package):
    state=reading(make_base(package))
    changes=dict(floor_levels_m=state['floor_levels_m'],components=[dict(
        id='principal',region=dict(front_edge=0,u=[0,1],depth_m=[2,14]),levels_m=state['floor_levels_m'])])
    state,resolved=apply_response(state,reply('02_masas',changes),[])
    assert 'masses' not in state['request']['theta']
    assert len(resolved.masses)==1
    assert min(y for x,y in resolved.masses[0].footprint)==-6
    state,_=apply_response(state,reply('03_lenguaje',dict(architectural_style='moderno')),[])
    door=dict(id='entrada',mass_ref=resolved.masses[0].id,edge=0,opening=dict(
        kind='door',u_m=1,v_m=.12,width_m=1.2,height_m=2.4,door=dict(model='moderno')))
    state,_=apply_response(state,reply('04_puertas',dict(placements=[door])),[])
    result,validation,_=materialize(state['request'])
    assert validation['envelope_test']=='passed'
    assert sum(len(w.facade.openings) for w in result.resolved.walls)==1


def test_explicit_thinking_budget_leaves_room_for_output(tmp_path):
    packet=dict(prompt='test',system='test',attachments=[])
    body=message_body(tmp_path,packet,max_tokens=16384,thinking_budget=4096)
    assert body['thinking']==dict(type='enabled',budget_tokens=4096)
    assert message_body(tmp_path,packet,thinking_budget=0)['thinking']==dict(type='disabled')
    with pytest.raises(ValueError):
        message_body(tmp_path,packet,max_tokens=4096,thinking_budget=4096)
