import json
from pathlib import Path
import pytest
from domain.building_intent import validate_intent, from_json, operation_order
from domain.generation_profile import PROFILES, profile_for

ROOT=Path(__file__).parents[1]/'experiments/phase0'


def base():
    return {'version':'intent-v1','context':{'parcel':[[0,0],[8,0],[8,12],[0,12]],
            'fronts':{'street':0},'levels_m':[0,3,6]},'building':{}}


def test_completion_is_not_absence():
    d=base();assert validate_intent(d).data['building']=={}
    d['building']['site']={'fence':False,'garage':False}
    d['building']['roof']={'objects':[]}
    assert from_json(validate_intent(d).to_json()).data==d


def test_mixed_styles_and_optional_evidence():
    d=base();d['building']={'style':'republicano','facades':[{'body':'main','front':'street','floors':[2],
        'style':'moderno','windows':{'count':2,'style':'madera'}}]}
    validate_intent(d)
    d['evidence']={'note':'optional'};validate_intent(d)


def test_order_independent_of_json_list_order():
    d=base();d['building']['operations']=[
        {'id':'a','kind':'crown','body':'main','front':'street'},
        {'id':'b','kind':'setback','body':'main','front':'street'},
        {'id':'c','kind':'loggia','body':'main','front':'street','after':['b']}]
    expected=operation_order(validate_intent(d))
    d['building']['operations'].reverse()
    assert operation_order(validate_intent(d))==expected==('b','c','a')


@pytest.mark.parametrize('change',[
    lambda d:d.update(version='old'),
    lambda d:d['context'].update(levels_m=[0,3,2]),
    lambda d:d['context'].update(fronts={'F':99}),
    lambda d:d['context'].update(parcel=[[0,0],[2,2],[0,2],[2,0]]),
    lambda d:d['building'].update(unknown=True),
    lambda d:d['building'].update(organization='cube_magic'),
    lambda d:d['building'].update(bodies=[]),
    lambda d:d['building'].update(operations=[{'id':'o','kind':'loggia','body':'missing','front':'street'}]),
    lambda d:d['building'].update(operations=[{'id':'o','kind':'setback','body':'main','front':'street','floors':[0]}]),
    lambda d:d['building'].update(operations=[{'id':'o','kind':'setback','body':'main','front':'street','depth_m':3}]),
    lambda d:d['building'].update(operations=[{'id':'o','kind':'depth_rhythm','body':'main','front':'street','weights':[1,2],'planes':['base']}]),
    lambda d:d['building'].update(site={'garage':None}),
])
def test_invalid_inputs_have_diagnostics(change):
    d=base();change(d)
    with pytest.raises(ValueError):validate_intent(d)


def test_cycle_and_unknown_dependency():
    d=base();d['building']['operations']=[
        {'id':'a','kind':'setback','body':'main','front':'street','after':['b']},
        {'id':'b','kind':'loggia','body':'main','front':'street','after':['a']}]
    with pytest.raises(ValueError,match='cycle'):validate_intent(d)
    d['building']['operations'][0]['after']=['missing']
    with pytest.raises(ValueError,match='dependency'):validate_intent(d)


def test_all_cases_and_separate_evaluation_set():
    paths=list((ROOT/'cases').glob('*/*.json'));assert len(paths)==20
    ids=set();splits={}
    for path in paths:
        case=json.loads(path.read_text());assert case['id'] not in ids;ids.add(case['id'])
        assert case['split']==path.parent.name
        splits[case['split']]=splits.get(case['split'],0)+1
        assert case['source']=='synthetic_design_fixture'
        validate_intent(case['request'])
    assert splits=={'tuning':14,'evaluation':6}


def test_profiles_are_design_priors_and_copied():
    for name in PROFILES:
        profile=profile_for(name)
        assert profile['interiors'] and profile['roof_objects'] and not profile['evidence_required']
        profile['use']='changed'
        assert profile_for(name)['use']!='changed'


def test_scope_must_exist_on_body():
    d=base();d['building']['bodies']=[{'id':'low','floors':[1]}]
    d['building']['operations']=[{'id':'o','kind':'loggia','body':'low','front':'street','floors':[2]}]
    with pytest.raises(ValueError,match='absent from body'):validate_intent(d)


def test_duplicate_facade_scope_is_ambiguous():
    d=base();f={'body':'main','front':'street','floors':[1]}
    d['building']['facades']=[f,f]
    with pytest.raises(ValueError,match='ambiguous'):validate_intent(d)


def test_dependency_cannot_reverse_architectural_phases():
    d=base();d['building']['operations']=[
        {'id':'a','kind':'setback','body':'main','front':'street','after':['b']},
        {'id':'b','kind':'crown','body':'main','front':'street'}]
    with pytest.raises(ValueError,match='phase order'):validate_intent(d)


def test_elevated_floor_and_clockwise_parcel_preserved():
    d=base();d['context']['levels_m']=[.6,3.6,6.6];d['context']['ground_z_m']=0
    d['context']['parcel'].reverse()
    assert validate_intent(d).data==d


@pytest.mark.parametrize('value',[None,[],False,{'x':1}])
def test_bad_reference_types_report_value_error(value):
    d=base();d['building']['operations']=[{'id':'o','kind':'loggia','body':value,'front':'street'}]
    with pytest.raises(ValueError):validate_intent(d)
