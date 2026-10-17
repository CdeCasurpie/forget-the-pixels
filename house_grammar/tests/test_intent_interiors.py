"""Phase 3: interior plans, circulation graph, vertical core and openings.

The bank test replans all frozen phase-0 cases; geometry tests read the plan
dictionary, so they describe the exported plan rather than private helpers.
"""
import json
import math
from functools import lru_cache
from pathlib import Path

import pytest
from shapely.geometry import shape, Point
from shapely.ops import unary_union

from domain.architectural_plan import PlanningError
from planning.interiors import plan_interiors


ROOT=Path(__file__).parents[1]
BANK=ROOT/'experiments'/'phase0'/'cases'
FIXTURES=ROOT/'experiments'/'phase3'/'cases'


def bank_paths():
    return sorted(BANK.glob('*/*.json'))


def bank_ids():
    return [path.stem for path in bank_paths()]


def request_for(path, seed=17):
    request=json.loads(path.read_text())['request'];request['seed']=seed;return request


@lru_cache(maxsize=None)
def bank_plan(identifier, seed=17):
    path=next(p for p in bank_paths() if p.stem==identifier)
    return plan_interiors(request_for(path,seed)).to_dict()


@lru_cache(maxsize=None)
def fixture_plan(name):
    request=json.loads((FIXTURES/f'{name}.json').read_text())['request']
    return plan_interiors(request).to_dict()


def floors_of(data):
    return {row['floor']:row for row in data['floors']}


def rooms_of(row):
    return {room['id']:room for room in row['rooms']}


# --- bank-wide guarantees -------------------------------------------------

@pytest.mark.parametrize('identifier',bank_ids())
def test_bank_case_plans_habitable_interiors(identifier):
    data=bank_plan(identifier);rows=floors_of(data)
    assert rows and all(row['checks']['connected'] for row in rows.values())
    for row in rows.values():
        # Area is preserved exactly: no lost slivers, no double coverage.
        assert row['checks']['coverage_error_m2']<1e-5
        assert row['corridor_width_m']>=0.99
        owners=[window['room'] for window in row['windows']]
        assert all(owner in rooms_of(row) for owner in owners)
        for room in row['rooms']:
            if room['kind'] in ('bedroom','living','kitchen_dining','service','open_ground','shop'):
                assert room['area_m2']>=3.5,room


def test_other_seeds_still_plan_every_bank_case():
    for path in bank_paths():
        for seed in (7,81):
            result=plan_interiors(request_for(path,seed))
            assert all(row['checks']['coverage_error_m2']<1e-5 for row in result.floors)


def test_same_request_is_deterministic():
    path=next(p for p in bank_paths() if p.stem=='19_corner_loggia')
    first=plan_interiors(request_for(path)).to_dict()
    second=plan_interiors(request_for(path)).to_dict()
    assert json.dumps(first,sort_keys=True)==json.dumps(second,sort_keys=True)


# --- doors, partitions and openings ---------------------------------------

@pytest.mark.parametrize('identifier',['03_corner','13_L_rear_wing','14_U_courtyard','19_corner_loggia','20_complex_combination'])
def test_doors_open_on_real_shared_walls(identifier):
    data=bank_plan(identifier)
    for row in data['floors']:
        rooms=rooms_of(row)
        for door in row['doors']:
            source,target=shape(rooms[door['source']]['geometry']),shape(rooms[door['target']]['geometry'])
            # Overlay re-noding leaves ~1e-9 offsets; a 1e-6 tolerance is still
            # four orders of magnitude below the 6 cm wall half thickness.
            shared=source.boundary.intersection(target.buffer(1e-6))
            assert shared.length>=.84,door
            line=shape(door['geometry'])
            assert line.length in (pytest.approx(.85),pytest.approx(.9))
            # The leaf sits on the shared wall and inside the enclosed body.
            assert shared.buffer(1e-6).covers(line),door
            assert shape(row['envelope']).buffer(.01).covers(line)


@pytest.mark.parametrize('identifier',['02_wide_bar','12_mixed_styles','19_corner_loggia','20_complex_combination'])
def test_partitions_respect_window_clearances(identifier):
    data=bank_plan(identifier);checked=0
    for row in data['floors']:
        envelope=shape(row['envelope'])
        boundaries=unary_union([shape(room['geometry']).boundary for room in row['rooms']])
        internal=boundaries.difference(envelope.boundary.buffer(1e-6))
        for window in row['windows']:
            landing=shape(window['clearance']).buffer(-.05)
            assert internal.intersection(landing).length<1e-6,window
            checked+=1
    if identifier in ('12_mixed_styles','19_corner_loggia'):assert checked>0


# --- vertical core and stairs ---------------------------------------------

@pytest.mark.parametrize('identifier',['09_loggia','14_U_courtyard'])
def test_vertical_core_is_continuous(identifier):
    data=bank_plan(identifier);rows=floors_of(data)
    stairs=[shape(rooms_of(row)['floor%d/stairs'%row['floor']]['geometry']) for row in rows.values()]
    assert all(s.bounds==pytest.approx(stairs[0].bounds) for s in stairs)
    assert all(rows[floor]['rooms'] for floor in rows)
    for floor,row in rows.items():
        rooms=rooms_of(row)
        assert any(room['kind']=='stairs' for room in rooms.values())
        assert any(room['kind']=='circulation' for room in rooms.values())
        assert any(room['kind']=='bathroom' or room['kind']=='service' for room in rooms.values())
    for flight in data['core']['flights']:
        rise=flight['top_m']-flight['bottom_m']
        assert flight['risers']==math.ceil(rise/.18)
        assert .15<=flight['riser_m']<=.19
        assert flight['tread_m']==pytest.approx(.27)
        assert flight['flight_width_m']==pytest.approx(.95)


def test_single_storey_has_no_stairs_but_keeps_services():
    data=bank_plan('01_compact_narrow');row=data['floors'][0]
    rooms=rooms_of(row)
    assert all(room['kind']!='stairs' for room in rooms.values())
    assert any(room['kind']=='bathroom' for room in rooms.values())
    assert not data['core']['flights']


# --- windows own rooms -----------------------------------------------------

@pytest.mark.parametrize('name',['p3_two_large_windows','p3_three_unequal_windows','p3_small_high_window',
                                 'p3_upper_floor_different','p3_connected_loggia','p3_garage_independent'])
def test_windows_own_usable_rooms(name):
    data=fixture_plan(name)
    for row in data['floors']:
        rooms=rooms_of(row);envelope=shape(row['envelope'])
        for window in row['windows']:
            owner=rooms[window['room']]
            assert owner['kind'] not in ('circulation','stairs','garage')
            assert window['width_m']>=.5
            assert shape(window['geometry']).length==pytest.approx(window['width_m'],abs=.01)
            landing=shape(window['clearance'])
            # The room behind the window owns the usable part of its clearance,
            # inside the wall band; the corridor may clip at most a corner
            # (the planner allows up to 0.20 m2 of overlap).
            part=landing.intersection(envelope)
            owned=part.intersection(shape(owner['geometry'])).area
            assert owned>=part.area*.75,window
            assert part.area-owned<=.21,window


def test_floor_specific_windows_stay_on_their_floor():
    data=fixture_plan('p3_upper_floor_different');rows=floors_of(data)
    assert [len(rows[1]['windows']),len(rows[2]['windows']),len(rows[3]['windows'])]==[0,0,2]
    data=fixture_plan('p3_connected_loggia');rows=floors_of(data)
    assert [len(rows[1]['windows']),len(rows[2]['windows']),len(rows[3]['windows'])]==[2,0,2]


def test_small_high_window_lands_on_service_room():
    data=fixture_plan('p3_small_high_window');row=data['floors'][0]
    rooms=rooms_of(row)
    owners=[rooms[window['room']]['kind'] for window in row['windows']]
    assert owners==['service']
    assert len(data['floors'])==1


# --- garage and loggia connections -----------------------------------------

def test_garage_keeps_independent_street_access():
    data=fixture_plan('p3_garage_independent');rows=floors_of(data)
    garage=[room for row in rows.values() for room in row['rooms'] if room['kind']=='garage']
    assert len(garage)==1 and garage[0]['id']=='floor1/garage'
    assert any(connection['kind']=='vehicle_entry' for connection in data['connections'])
    doors=[connection for connection in data['connections'] if connection['kind']=='door']
    # Nobody walks to another room through the garage.
    assert not any(door['source'].endswith('/garage') for door in doors)
    owner_kinds={rooms_of(row)[window['room']]['kind'] for row in rows.values() for window in row['windows']}
    assert 'garage' not in owner_kinds


def test_loggia_connects_to_exactly_one_room_per_space():
    data=fixture_plan('p3_connected_loggia');rows=floors_of(data)
    spaces=[connection for connection in data['connections'] if connection['kind']=='exterior_space']
    assert len(spaces)==1
    connection=spaces[0];row=rows[2]
    room=rooms_of(row)[connection['source']]
    assert room['kind'] not in ('circulation','stairs','garage')
    access=shape(connection['geometry'])
    opening=shape(room['usable_geometry']).boundary.intersection(access)
    assert opening.length>=.6


# --- diagnostics never invent passable interiors ---------------------------

def test_impossible_parcel_reports_conflict_instead_of_guessing():
    request=dict(version='intent-v1',seed=17,
                 context=dict(parcel=[[0,0],[2,0],[2,2.5],[0,2.5]],fronts={'F1':0},levels_m=[0,3.2]),
                 building={})
    with pytest.raises(PlanningError) as info:
        plan_interiors(request)
    assert info.value.code in ('service_core_fit','vertical_core_fit','circulation_clearance','no_feasible_layout')


def test_more_windows_than_facade_capacity_is_explicit():
    request=dict(version='intent-v1',seed=17,
                 context=dict(parcel=[[0,0],[5,0],[5,20],[0,20]],fronts={'F1':0},levels_m=[0,3.2]),
                 building=dict(profile='barranco_residential',
                               facades=[{'body':'main','front':'F1','floors':[1],
                                         'windows':{'count':8,'proportion':'vertical'}}]))
    with pytest.raises(PlanningError,match='window_capacity'):
        plan_interiors(request)


def test_conflicts_list_alternatives_instead_of_silent_fallback():
    request=dict(version='intent-v1',seed=17,
                 context=dict(parcel=[[0,0],[3,0],[3,3],[0,3]],fronts={'F1':0},levels_m=[0,3.2,6]),
                 building=dict(profile='barranco_residential'))
    with pytest.raises(PlanningError) as info:
        plan_interiors(request)
    assert info.value.code in ('vertical_core_fit','no_feasible_layout','circulation_clearance')
    if info.value.code=='no_feasible_layout':
        assert ':' in str(info.value)
