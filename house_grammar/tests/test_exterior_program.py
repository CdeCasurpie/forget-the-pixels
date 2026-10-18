"""R2.1: use belongs to the exterior program, not to interior BSP rooms."""
from copy import deepcopy

import pytest

from domain.building_intent import validate_intent
from planning.articulation import plan_articulation
from planning.exterior_program import plan_exterior_program


def request():
    return dict(version='intent-v1', seed=17,
                context=dict(parcel=[[0, 0], [12, 0], [12, 18], [0, 18]],
                             fronts={'street': 0}, levels_m=[0, 3.2, 6., 8.8]),
                building=dict(profile='barranco_residential', organization='compact'))


def test_omitted_program_is_completed_without_changing_masses():
    authored = request()
    before = deepcopy(authored)
    planned = plan_exterior_program(authored)
    assert authored == before
    assert planned.massing == plan_articulation(authored).to_dict()
    assert planned.program['use'] == 'residential'
    assert planned.program['residential'] == 'multi_family'
    assert [s['use'] for s in planned.storeys] == ['residential'] * 3
    assert 'interior' not in planned.to_dict()
    assert all(d['source'] == 'completion' for d in planned.decisions)


@pytest.mark.parametrize('use', ['residential', 'commercial', 'office'])
def test_use_does_not_require_rooms_or_change_masses(use):
    authored = request()
    authored['building']['program'] = dict(use=use)
    result = plan_exterior_program(authored)
    assert {s['use'] for s in result.storeys} == {use}
    assert result.massing == plan_articulation(authored).to_dict()


def test_mixed_use_has_commercial_ground_and_repeatable_residential_storeys():
    authored = request()
    authored['building']['program'] = dict(use='mixed', residential='multi_family')
    result = plan_exterior_program(authored)
    assert [s['use'] for s in result.storeys] == ['commercial', 'residential', 'residential']
    assert [s['id'] for s in result.storeys] == [s['id'] for s in result.massing['storeys']]


def test_explicit_floor_and_front_override_only_their_scope():
    authored = request()
    authored['building']['program'] = dict(
        use='residential', evolution='progressive', condition='weathered', occupancy='vacant',
        floors=[dict(body='main', floor=1, use='commercial',
                     sectors=[dict(front='street', use='office')])])
    result = plan_exterior_program(authored)
    assert result.program['evolution'] == 'progressive'
    assert result.program['condition'] == 'weathered'
    assert result.program['occupancy'] == 'vacant'
    assert result.storeys[0]['use'] == 'commercial'
    assert result.storeys[0]['sectors'] == {'street': 'office'}
    assert result.storeys[1]['use'] == 'residential'
    assert result.storeys[1]['sectors'] == {}
    assert not any(d['path'] == 'program/main/floor1/use' for d in result.decisions)


def test_fence_is_independent_and_explicit_absence_remains_absence():
    authored = request()
    authored['building']['site'] = {'fence': False}
    authored['building']['program'] = {'use': 'commercial', 'condition': 'abandoned'}
    result = plan_exterior_program(authored)
    assert result.program['fence'] is False
    assert result.program['use'] == 'commercial'
    assert result.program['condition'] == 'abandoned'
    # Condition and occupancy are independent: abandonment does not imply a
    # fabricated claim about a particular building's actual occupants.
    authored['building']['program']['occupancy'] = 'vacant'
    assert plan_exterior_program(authored).program['occupancy'] == 'vacant'


@pytest.mark.parametrize('program,diagnostic', [
    ({'use': 'magic'}, 'building.program.use'),
    ({'floors': [{'body': 'main', 'floor': 0}]}, 'building.program.floor.floor'),
    ({'floors': [{'body': 'ghost', 'floor': 1}]}, 'building.program.floor.body'),
    ({'floors': [{'body': 'main', 'floor': 1}, {'body': 'main', 'floor': 1}]},
     'duplicate body/floor'),
    ({'floors': [{'body': 'main', 'floor': 1,
                 'sectors': [{'front': 'back', 'use': 'commercial'}]}]}, 'unknown front'),
    ({'floors': [{'body': 'main', 'floor': 1, 'sectors': [
        {'front': 'street', 'use': 'office'}, {'front': 'street', 'use': 'commercial'}]}]},
     'duplicate front'),
    ({'floors': [{'body': 'main', 'floor': 1, 'use': 'mixed'}]},
     'building.program.floor.use'),
])
def test_bad_program_has_local_diagnostic(program, diagnostic):
    authored = request()
    authored['building']['program'] = program
    with pytest.raises(ValueError, match=diagnostic):
        validate_intent(authored)
