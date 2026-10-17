"""Phase 4: constructive envelope, metric apertures, joinery and slabs.

The bank test replans all frozen phase-0 cases; geometry tests read the plan
dictionary, so they describe the exported envelope rather than private helpers.
"""
import json
from collections import Counter
from functools import lru_cache
from pathlib import Path

import numpy as np
import pytest
from shapely.geometry import shape
from shapely.strtree import STRtree

from domain.architectural_plan import PlanningError
from planning.envelope import (LINTEL, PROFILE_WIDTH, RATIOS, SLAB,
                               plan_envelope, window_dimensions)
from planning.envelope_export import export_envelope
from planning.massing import polygons


ROOT=Path(__file__).parents[1]
BANK=ROOT/'experiments'/'phase0'/'cases'
FIXTURES=ROOT/'experiments'/'phase4'/'cases'
PHASE3=ROOT/'experiments'/'phase3'/'cases'
DECISION_REASONS={'requested proportion adapted to available useful height',
                  'head limited by slab and lintel',
                  'perimeter room on unspecified exposed wall',
                  'shift along same shared wall for frame clearance',
                  'reveals merge inside a shared thin wall'}


def bank_paths():
    return sorted(BANK.glob('*/*.json'))


def bank_ids():
    return [path.stem for path in bank_paths()]


def fixture_paths():
    return sorted(FIXTURES.glob('*.json'))


def fixture_ids():
    return [path.stem for path in fixture_paths()]


def request_for(path, seed=17):
    request=json.loads(Path(path).read_text())['request'];request['seed']=seed
    return request


@lru_cache(maxsize=None)
def envelope(path, seed=17):
    return plan_envelope(request_for(path,seed)).to_dict()


def bank_plan(identifier, seed=17):
    return envelope(next(path for path in bank_paths() if path.stem==identifier),seed)


def fixture_plan(name, seed=17):
    return envelope(FIXTURES/f'{name}.json',seed)


def phase3_plan(name, seed=17):
    return envelope(PHASE3/f'{name}.json',seed)


def windows_of(plan, source=None):
    return [opening for opening in plan['openings'] if opening['kind']=='window'
            and (source is None or opening['source']==source)]


def parts_of(plan, opening_id):
    return [part for part in plan['parts'] if part['opening']==opening_id]


def min_ring_edge(polygon):
    smallest=float('inf')
    for ring in [polygon.exterior]+list(polygon.interiors):
        coordinates=np.asarray(ring.coords)
        if len(coordinates)<2:continue
        smallest=min(smallest,float(np.linalg.norm(np.diff(coordinates,axis=0),axis=1).min()))
    return smallest


def cross_material_overlap(plan):
    """Volume shared by parts of different materials, as the GLB audit sees it."""
    parts=plan['parts'];shapes=[shape(part['geometry']) for part in parts]
    tree=STRtree(shapes);total=0.
    for index,part in enumerate(parts):
        for other_index in tree.query(shapes[index]):
            if other_index<=index:continue
            other=parts[other_index]
            if other['material']==part['material']:continue
            depth=min(part['top_m'],other['top_m'])-max(part['bottom_m'],other['bottom_m'])
            if depth<=1e-6:continue
            area=shapes[index].intersection(shapes[other_index]).area
            if area<1e-6:continue
            total+=area*depth
    return total


def declared_scopes(request):
    return {(facade['body'],facade['front'],floor)
            for facade in request['building'].get('facades',[]) if facade.get('windows')
            for floor in facade.get('floors',[])}


# --- bank-wide guarantees -------------------------------------------------

@pytest.mark.parametrize('identifier',bank_ids())
def test_bank_case_builds_a_sound_envelope(identifier):
    plan=bank_plan(identifier);levels=plan['request']['context']['levels_m']
    checks=plan['checks']
    assert checks['aperture_intrusion_m3']<=1e-5
    assert checks['minimum_lintel_m']>=LINTEL-1e-6
    assert checks['openings']==len(plan['openings'])
    assert checks['explicit_windows']==len(windows_of(plan,'explicit'))
    assert checks['completed_windows']==len(windows_of(plan,'completion'))
    assert plan['openings']
    for opening in plan['openings']:
        floor=opening['floor']
        assert opening['bottom_m']>=levels[floor-1]-1e-9
        assert opening['top_m']<=levels[floor]-SLAB-LINTEL+1e-6
        assert opening['clear_width_m']>0 and opening['clear_height_m']>0
        if opening['kind']=='window':
            assert opening['surface'] is not None
            assert opening['clear_width_m']>=.40
    for part in plan['parts']:
        assert part['top_m']-part['bottom_m']>1e-7,part
        assert shape(part['geometry']).is_valid,part


def test_other_seeds_still_build_every_bank_case():
    for path in bank_paths():
        for seed in (7,81):
            plan=envelope(path,seed)
            assert plan['checks']['aperture_intrusion_m3']<=1e-5,path
            assert plan['checks']['minimum_lintel_m']>=LINTEL-1e-6,path


@pytest.mark.parametrize('path',bank_paths()+fixture_paths(),ids=bank_ids()+fixture_ids())
def test_parts_are_sturdy_prisms(path):
    plan=envelope(path)
    for part in plan['parts']:
        for polygon in polygons(shape(part['geometry'])):
            assert min_ring_edge(polygon)>1e-8,part['id']


@pytest.mark.parametrize('path',bank_paths()+fixture_paths(),ids=bank_ids()+fixture_ids())
def test_parts_share_no_cross_material_volume(path):
    plan=envelope(path)
    assert cross_material_overlap(plan)<=1e-9,path


@pytest.mark.parametrize('identifier,seed',[('03_corner',7),('11_open_ground',7),
                                            ('15_upper_shift',81),('19_corner_loggia',17)])
def test_regression_runs_share_no_cross_material_volume(identifier,seed):
    assert cross_material_overlap(bank_plan(identifier,seed))<=1e-9


def test_same_request_is_deterministic():
    path=next(path for path in bank_paths() if path.stem=='19_corner_loggia')
    first=plan_envelope(request_for(path)).to_dict()
    second=plan_envelope(request_for(path)).to_dict()
    assert json.dumps(first,sort_keys=True)==json.dumps(second,sort_keys=True)


def test_pending_and_engineering_flags_are_honest():
    plan=bank_plan('09_loggia')
    assert [row['path'] for row in plan['pending']]==['roof','site.fence',
                                                     'site.access_route','interior.furniture']
    assert all(row['reason'] for row in plan['pending'])
    assert plan['checks']['engineering_verified'] is False
    assert plan['checks']['floor_relative_elevations'] is True


def test_decisions_stay_inside_the_documented_vocabulary():
    seen=set()
    for identifier in bank_ids():
        for decision in bank_plan(identifier)['decisions']:
            assert set(decision)>= {'id','reason'},decision
            seen.add(decision['reason'])
    assert seen<=DECISION_REASONS,seen-DECISION_REASONS


# --- requested apertures --------------------------------------------------

@pytest.mark.parametrize('path',bank_paths()+fixture_paths(),ids=bank_ids()+fixture_ids())
def test_explicit_windows_match_the_requested_counts(path):
    plan=envelope(path);request=plan['request'];counts={}
    for facade in request['building'].get('facades',[]):
        spec=facade.get('windows')
        if not spec:continue
        assert isinstance(spec['count'],int)
        for floor in facade.get('floors',[]):
            counts[floor]=counts.get(floor,0)+spec['count']
    for floor in range(1,len(request['context']['levels_m'])):
        got=sum(opening['floor']==floor for opening in windows_of(plan,'explicit'))
        assert got==counts.get(floor,0),(path,floor,got,counts.get(floor,0))


@pytest.mark.parametrize('path',bank_paths()+fixture_paths(),ids=bank_ids()+fixture_ids())
def test_completion_only_fills_open_scopes(path):
    plan=envelope(path);declared=declared_scopes(plan['request'])
    explicit={(opening['floor'],opening['room']) for opening in windows_of(plan,'explicit')}
    completions=Counter()
    for opening in windows_of(plan,'completion'):
        assert opening['id'].endswith('/auto_window')
        assert (opening['body'],opening['front'],opening['floor']) not in declared
        assert (opening['floor'],opening['room']) not in explicit
        completions[(opening['floor'],opening['room'])]+=1
    assert all(count==1 for count in completions.values())


def test_completion_is_active_across_the_bank():
    completed=sum(bool(windows_of(bank_plan(identifier),'completion')) for identifier in bank_ids())
    assert completed>=15,completed


def test_empty_facade_list_disables_completion():
    request=request_for(next(path for path in bank_paths() if path.stem=='02_wide_bar'))
    request['building']['facades']=[]
    plan=plan_envelope(request).to_dict()
    assert not windows_of(plan)


def test_fixture_closes_its_declared_front_and_completes_the_rest():
    plan=fixture_plan('p4_completion_upper_floor')
    for floor in (2,3):
        assert [opening for opening in windows_of(plan,'completion') if opening['floor']==floor]
    assert not [opening for opening in windows_of(plan,'completion') if opening['floor']==1]


@pytest.mark.parametrize('name',['p4_fixed_count_narrow','p4_fixed_count_wide'])
def test_fixture_keeps_the_requested_proportion_set(name):
    plan=fixture_plan(name)
    for floor in (1,2):
        values=sorted(opening['proportion'] for opening in windows_of(plan)
                      if opening['floor']==floor)
        assert values==['horizontal','small_high','vertical']


def test_narrow_and_wide_parcels_share_the_count_and_adapt_the_width():
    narrow=fixture_plan('p4_fixed_count_narrow');wide=fixture_plan('p4_fixed_count_wide')
    def widths(plan):
        return sorted(round(opening['clear_width_m'],3) for opening in windows_of(plan)
                      if opening['floor']==1)
    assert len(widths(narrow))==len(widths(wide))==3
    assert max(widths(wide))>max(widths(narrow))+.2


@pytest.mark.parametrize('name',['p4_fixed_count_wide','p4_low_ceiling','p4_tall_floor',
                                 'p4_guillotine_tracks','p4_staggered_distribution'])
def test_window_proportions_stay_inside_their_band_or_are_recorded(name):
    plan=fixture_plan(name)
    adapted={decision['id'] for decision in plan['decisions']
             if decision['reason']=='requested proportion adapted to available useful height'}
    for opening in windows_of(plan):
        if opening['id'] in adapted:continue
        lo,hi,_=RATIOS[opening['proportion']]
        ratio=opening['width_m']/(opening['head_m']-opening['sill_m'])
        assert lo-1e-6<=ratio<=hi+1e-6,(opening['id'],ratio)


# --- window dimensions ----------------------------------------------------

def test_window_dimensions_adapts_instead_of_squashing():
    sill,head,adapted=window_dimensions(1.20,'vertical','bathroom',2.62)
    assert adapted is True
    assert sill==pytest.approx(1.20)
    assert head-sill==pytest.approx(2.62-LINTEL-1.20)


def test_window_dimensions_keeps_the_proportion_when_it_fits():
    sill,head,adapted=window_dimensions(.90,'vertical','bedroom',2.62)
    assert adapted is False
    assert .90/(head-sill)==pytest.approx(.65)


def test_window_dimensions_rejects_an_impossible_wall():
    with pytest.raises(PlanningError) as error:
        window_dimensions(1.0,'vertical','bathroom',1.70)
    assert error.value.code=='useful_height'


def test_low_ceiling_caps_heads_and_tall_floor_allows_tall_windows():
    low=fixture_plan('p4_low_ceiling');tall=fixture_plan('p4_tall_floor')
    levels=low['request']['context']['levels_m']
    assert all(opening['top_m']<=levels[opening['floor']]-SLAB-LINTEL+1e-6
               for opening in windows_of(low))
    assert all(opening['head_m']-opening['sill_m']>=.35-1e-9 for opening in windows_of(low))
    heights=[opening['head_m']-opening['sill_m'] for opening in windows_of(tall)]
    assert heights and min(heights)>=1.0-1e-9


def test_raised_ground_keeps_elevations_floor_relative():
    plan=fixture_plan('p4_raised_ground');levels=plan['request']['context']['levels_m']
    for opening in plan['openings']:
        assert opening['bottom_m']>=levels[opening['floor']-1]-1e-9
    entrance=next(opening for opening in plan['openings'] if opening['kind']=='entrance')
    assert entrance['bottom_m']==pytest.approx(.5)
    for opening in plan['openings']:
        if opening['kind']=='door':
            assert opening['bottom_m']==pytest.approx(levels[opening['floor']-1])


def test_staggered_alignment_moves_upper_floors_within_their_cells():
    plan=fixture_plan('p4_staggered_distribution')
    by_floor={}
    for opening in windows_of(plan):
        by_floor.setdefault(opening['floor'],[]).append(opening)
    first=[shape(opening['geometry']).centroid for opening in by_floor[1]]
    second=[shape(opening['geometry']).centroid for opening in by_floor[2]]
    assert max(min(a.distance(b) for b in second) for a in first)>.05


# --- styles, materials and mechanisms -------------------------------------

@pytest.mark.parametrize('style',sorted(PROFILE_WIDTH))
def test_frame_profile_follows_the_requested_style(style):
    request={'version':'intent-v1','seed':17,
             'context':{'parcel':[[0,0],[10,0],[10,18],[0,18]],'fronts':{'F1':0},
                        'levels_m':[0,3.2,6]},
             'building':{'profile':'barranco_residential','organization':'compact','style':style,
                         'facades':[{'body':'main','front':'F1','floors':[1],
                                     'windows':{'count':1,'proportion':'vertical'}}]}}
    plan=plan_envelope(request).to_dict()
    explicit=windows_of(plan,'explicit')
    assert explicit
    assert all(opening['style']==style for opening in explicit)
    assert all(opening['frame_width_m']==pytest.approx(PROFILE_WIDTH[style]) for opening in explicit)


def test_mechanisms_are_derived_from_use_and_validated():
    request={'version':'intent-v1','seed':17,
             'context':{'parcel':[[0,0],[10,0],[10,18],[0,18]],'fronts':{'F1':0},
                        'levels_m':[0,3.2,6]},
             'building':{'profile':'barranco_residential','organization':'compact',
                         'facades':[{'body':'main','front':'F1','floors':[1],
                                     'windows':{'count':2,'proportion':'vertical'}}]}}
    plan=plan_envelope(request).to_dict()
    explicit=windows_of(plan,'explicit')
    assert {opening['mechanism'] for opening in explicit}=={'casement'}
    assert {opening['material'] for opening in explicit}=={'metal'}
    request['building']['facades'][0]['windows']['mechanism']='fixed'
    plan=plan_envelope(request).to_dict()
    assert {opening['mechanism'] for opening in windows_of(plan,'explicit')}=={'fixed'}
    request['building']['facades'][0]['windows']['mechanism']='venetian'
    with pytest.raises(ValueError):
        plan_envelope(request)


def test_modern_joinery_on_a_republican_body_keeps_both():
    plan=fixture_plan('p4_modern_frame_republican')
    explicit=windows_of(plan,'explicit')
    completion=[opening for opening in windows_of(plan,'completion') if opening['floor']==3]
    assert explicit and all(opening['style']=='moderno' and
                            opening['frame_width_m']==PROFILE_WIDTH['moderno'] for opening in explicit)
    assert completion and all(opening['style']=='republicano' and
                              opening['frame_width_m']==PROFILE_WIDTH['republicano'] for opening in completion)


def test_street_door_object_accepts_material_independent_from_style():
    request=request_for(FIXTURES/'p4_door_materials.json')
    request['building']['site']={'door':{'position':'center','style':'moderno','material':'glass'}}
    plan=plan_envelope(request).to_dict()
    entrance=[opening for opening in plan['openings'] if opening['kind']=='entrance'][0]
    assert entrance['material']=='glass' and entrance['style']=='moderno'
    assert entrance['mechanism']=='hinged'
    materials={part['material'] for part in parts_of(plan,entrance['id'])}
    assert 'glass' in materials and 'metal' in materials
    assert entrance['clear_width_m']>=.70


def test_fixture_street_door_uses_the_requested_design():
    plan=fixture_plan('p4_door_materials')
    entrance=next(opening for opening in plan['openings'] if opening['kind']=='entrance')
    assert entrance['material']=='metal' and entrance['style']=='clasico'
    assert entrance['frame_width_m']==pytest.approx(PROFILE_WIDTH['clasico'])


# --- joinery --------------------------------------------------------------

def test_guillotine_mechanism_builds_two_horizontal_sashes():
    plan=fixture_plan('p4_guillotine_tracks')
    guillotine=[opening for opening in windows_of(plan) if opening['mechanism']=='guillotine']
    assert guillotine and all(opening['leaves']==2 for opening in guillotine)
    assert all(opening['material']=='wood' for opening in guillotine)
    opening=next(x for x in guillotine if x['floor']==1)
    low=next(part for part in parts_of(plan,opening['id']) if part['kind']=='leaf0_left')
    high=next(part for part in parts_of(plan,opening['id']) if part['kind']=='leaf1_left')
    lowbounds=shape(low['geometry']).bounds;highbounds=shape(high['geometry']).bounds
    # Horizontal tracks: both sashes span the full opening width.
    assert lowbounds[0]==pytest.approx(highbounds[0],abs=.02)
    assert lowbounds[2]==pytest.approx(highbounds[2],abs=.02)
    # The two sashes split the clear height without sharing volume.
    assert low['top_m']<=high['bottom_m']+1e-9 or high['top_m']<=low['bottom_m']+1e-9
    assert min(low['bottom_m'],high['bottom_m'])==pytest.approx(
        opening['bottom_m']+opening['frame_width_m']+.004,abs=.03)


def test_vertical_sliding_sashes_split_the_width():
    plan=fixture_plan('p4_door_materials')
    opening=next(x for x in windows_of(plan) if x['mechanism']=='sliding')
    left=next(part for part in parts_of(plan,opening['id']) if part['kind']=='leaf0_left')
    right=next(part for part in parts_of(plan,opening['id']) if part['kind']=='leaf1_left')
    leftbounds=shape(left['geometry']).bounds;rightbounds=shape(right['geometry']).bounds
    assert leftbounds[2]<=rightbounds[0]+1e-9
    # Vertical sashes share the full clear height on separate tracks.
    assert left['bottom_m']==pytest.approx(right['bottom_m'],abs=.02)
    assert left['top_m']==pytest.approx(right['top_m'],abs=.02)


@pytest.mark.parametrize('name',['p4_guillotine_tracks','p4_door_materials'])
def test_joinery_stays_inside_its_reveal_without_cross_material_volume(name):
    plan=fixture_plan(name)
    for opening in plan['openings']:
        parts=parts_of(plan,opening['id'])
        if not parts:continue
        cut=shape(opening['cut_geometry'])
        for part in parts:
            assert part['bottom_m']>=opening['bottom_m']-1e-9
            assert part['top_m']<=opening['top_m']+1e-9
            if part['kind']=='sill_cap':continue
            assert shape(part['geometry']).difference(cut).area<=5e-9,part['id']
        for index in range(len(parts)):
            for other in parts[index+1:]:
                if parts[index]['material']==other['material']:continue
                if min(parts[index]['top_m'],other['top_m'])<=max(parts[index]['bottom_m'],
                                                                 other['bottom_m'])+1e-9:continue
                assert shape(parts[index]['geometry']).intersection(
                    shape(other['geometry'])).area<=1e-6,(parts[index]['id'],other['id'])


def test_window_sill_cap_is_stone_and_separated_from_the_frame():
    plan=fixture_plan('p4_fixed_count_wide')
    for opening in windows_of(plan):
        parts=parts_of(plan,opening['id'])
        caps=[part for part in parts if part['kind']=='sill_cap']
        assert len(caps)==1,opening['id']
        cap=caps[0]
        assert cap['material']=='stone'
        assert cap['top_m']-cap['bottom_m']==pytest.approx(.0235)
        assert all(part['bottom_m']>=cap['top_m']-1e-9
                   for part in parts if part is not cap),opening['id']


@pytest.mark.parametrize('identifier',['12_mixed_styles','19_corner_loggia','20_complex_combination'])
def test_handles_on_doors_and_glazing_on_windows(identifier):
    plan=bank_plan(identifier);checked=0
    for opening in plan['openings']:
        parts=parts_of(plan,opening['id'])
        if opening['kind']=='window':
            assert any(part['kind']=='leaf0_infill' and part['material']=='glass'
                       for part in parts),opening['id']
            assert not any(part['kind'].startswith('handle') for part in parts)
        else:
            assert any(part['kind']=='handle0' for part in parts),opening['id']
        checked+=1
    assert checked


# --- doors, passages and shared walls -------------------------------------

@pytest.mark.parametrize('identifier',['02_wide_bar','12_mixed_styles','19_corner_loggia',
                                       '20_complex_combination'])
def test_interior_doors_keep_phase3_topology(identifier):
    plan=bank_plan(identifier)
    for row in plan['interior']['floors']:
        doors=[opening for opening in plan['openings']
               if opening['kind']=='door' and opening['floor']==row['floor']]
        assert {opening['id'] for opening in doors}=={door['id'] for door in row['doors']}
        rooms={room['id']:shape(room['geometry']) for room in row['rooms']}
        for opening in doors:
            door=next(door for door in row['doors'] if door['id']==opening['id'])
            axis=shape(opening['axis'])
            assert rooms[door['source']].buffer(1e-3).covers(axis),opening['id']
            assert rooms[door['target']].buffer(1e-3).covers(axis),opening['id']
            assert opening['width_m']==pytest.approx(shape(door['geometry']).length)


@pytest.mark.parametrize('identifier',['02_wide_bar','12_mixed_styles',
                                       '19_corner_loggia','20_complex_combination'])
def test_doors_reach_their_rooms_and_streets(identifier):
    plan=bank_plan(identifier);levels=plan['request']['context']['levels_m']
    entrances=[opening for opening in plan['openings'] if opening['kind']=='entrance']
    assert entrances,identifier
    for opening in plan['openings']:
        if opening['kind']=='window':continue
        assert opening['clear_width_m']>=.70-1e-9,opening['id']
    for opening in entrances:
        assert opening['surface'] is not None
        assert opening['bottom_m']==pytest.approx(levels[opening['floor']-1])


def test_open_ground_defers_the_street_entrance():
    plan=bank_plan('11_open_ground')
    assert not [opening for opening in plan['openings'] if opening['kind']=='entrance']
    assert [row['path'] for row in plan['pending']][:3]==['roof','site.fence','site.access_route']


def test_vehicle_entry_is_a_sliding_metal_garage_door():
    plan=phase3_plan('p3_garage_independent')
    entrance=[opening for opening in plan['openings'] if opening['kind']=='vehicle_entry']
    assert len(entrance)==1
    opening=entrance[0]
    assert opening['mechanism']=='sliding' and opening['material']=='metal'
    assert opening['clear_width_m']>=2.30
    assert opening['head_m']==pytest.approx(2.35)
    assert opening['surface'] is not None


def test_loggia_access_matches_the_interiors_reservation():
    plan=phase3_plan('p3_connected_loggia');spaces=0;parapets=0
    for storey in plan['interior']['massing']['storeys']:
        for space in storey.get('spaces',[]):
            if not space.get('protection'):continue
            spaces+=1
            openings=[opening for opening in plan['openings']
                      if opening['kind']=='exterior_space' and opening['floor']==storey['floor']]
            assert len(openings)==1,(space['id'],storey['floor'])
            assert openings[0]['width_m']==pytest.approx(space['access']['width_m'],abs=.02)
            part=next(part for part in plan['parts'] if part['id']==space['id']+'/parapet')
            assert part['material']=='plaster'
            assert part['top_m']-part['bottom_m']==pytest.approx(space['protection_height_m'])
            parapets+=1
    assert spaces==parapets>0


def test_small_high_windows_stay_high():
    plan=phase3_plan('p3_small_high_window')
    explicit=windows_of(plan,'explicit')
    assert explicit and all(opening['proportion']=='small_high' for opening in explicit)
    assert all(opening['sill_m']==pytest.approx(1.50) for opening in explicit)


# --- slabs and supports ---------------------------------------------------

@pytest.mark.parametrize('identifier',['09_loggia','14_U_courtyard','20_complex_combination'])
def test_slabs_at_every_datum_dodge_stairs_and_shaft(identifier):
    plan=bank_plan(identifier);levels=plan['request']['context']['levels_m']
    core=plan['interior']['core'];stairs=shape(core['stairs']);shaft=shape(core['shaft'])
    slabs={part['id']:part for part in plan['parts'] if part['kind']=='slab'}
    assert len(slabs)==len(levels)
    for index,level in enumerate(levels):
        part=slabs[f'level{index}/slab']
        assert part['bottom_m']==pytest.approx(level-SLAB)
        assert part['top_m']==pytest.approx(level)
        poly=shape(part['geometry'])
        if index in (0,len(levels)-1):
            assert poly.intersection(stairs).area>0
        else:
            assert poly.intersection(stairs).area<=1e-6
            assert poly.intersection(shaft).area<=1e-6


@pytest.mark.parametrize('identifier,count',[('20_complex_combination',4),('11_open_ground',24)])
def test_columns_and_plinths_are_materialized(identifier,count):
    plan=bank_plan(identifier)
    supports=[support for support in plan['interior']['massing']['supports']
              if support['kind']!='cantilever']
    parts={part['id']:part for part in plan['parts']}
    assert len(supports)==count
    for support in supports:
        part=parts[support['id']]
        assert part['kind']==support['kind'] and part['material']=='concrete'
        assert part['bottom_m']==pytest.approx(support['bottom_m'])
        assert part['top_m']<=support['top_m']+1e-9


# --- export evidence ------------------------------------------------------

def test_export_writes_watertight_pieces_and_drawings(tmp_path):
    path=next(path for path in bank_paths() if path.stem=='09_loggia')
    plan=plan_envelope(request_for(path))
    output=tmp_path/'loggia'
    report=export_envelope(plan,output)
    for name in ('plan.json','summary.json','envelope.glb','preview.png','front.png'):
        assert (output/name).exists(),name
    assert (output/'floors'/'floor1.png').exists()
    assert any((output/'elevations').glob('*.png'))
    assert report['audit']['watertight'] is True
    assert report['audit']['group_overlap_m3']==pytest.approx(0,abs=1e-9)
    assert report['openings']==len(plan.openings)
