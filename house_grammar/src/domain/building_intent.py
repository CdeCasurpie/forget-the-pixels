"""Architectural intent v1: qualitative authoring, not a mesh request.

Omission authorizes completion; false/empty means explicit absence. Source
coordinates and levels belong to context, never to an individual feature.
"""
from dataclasses import dataclass
import json
import math
import re

from shapely.geometry import Polygon


ORGANIZATIONS = ('compact', 'bar', 'L', 'U', 'courtyard', 'stepped',
                 'podium', 'attached', 'corner', 'incremental')
OPERATIONS = ('setback', 'bite', 'courtyard', 'attach', 'advance', 'overhang',
              'open_ground', 'recess', 'depth_rhythm', 'floor_shift',
              'chamfer', 'round_corner', 'crown', 'loggia', 'portico', 'vestibule', 'balcony')
STYLES = ('republicano', 'moderno', 'clasico', 'barroco', 'madera', 'mixed')
POSITIONS = ('left', 'center', 'right', 'corner', 'rear', 'all')
SIZES = ('shallow', 'medium', 'deep')
PHASE_ORDER = ('site', 'bodies', 'voids', 'storeys', 'planes', 'spaces', 'crowns')
OP_PHASE = dict(setback='storeys', bite='voids', courtyard='voids', attach='bodies',
                advance='bodies', overhang='storeys', open_ground='spaces',
                recess='planes', depth_rhythm='planes', floor_shift='planes',
                 chamfer='voids', round_corner='voids', crown='crowns', loggia='spaces',
                 portico='spaces', vestibule='spaces', balcony='spaces')


@dataclass(frozen=True)
class IntentRequest:
    """Validated intent; original omitted keys remain omitted on serialization."""
    data: dict

    def to_json(self):
        return json.dumps(self.data, ensure_ascii=False, indent=2) + '\n'


def _check(condition, path, message):
    if not condition:
        raise ValueError(f'{path}: {message}')


def _object(value, allowed, required, path):
    _check(isinstance(value, dict), path, 'expected object')
    _check(not set(value)-set(allowed), path, f'unsupported keys {sorted(set(value)-set(allowed))}')
    _check(set(required)<=set(value), path, f'required keys: {required}')


def _enum(value, choices, path):
    _check(value in choices, path, f'expected one of {choices}')


def _id(value, path):
    _check(isinstance(value, str) and re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]*', value), path, 'invalid semantic ID')


def _list(value, path):
    _check(isinstance(value, list), path, 'expected array')
    return value


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def _floors(value, count, path):
    _check(isinstance(value, list) and bool(value) and all(type(x) is int and 1<=x<=count for x in value), path, 'floors are 1-based existing storeys')
    _check(value == sorted(set(value)), path, 'floors must be unique and ascending')


def _validate_intent(data):
    """Strict shape and semantic validation. Does not claim geometric feasibility."""
    _object(data, ('version','context','building','seed','evidence'), ('version','context','building'), '$')
    _check(data['version']=='intent-v1', 'version', 'unsupported version')
    _check(type(data.get('seed',0)) is int, 'seed', 'expected integer')
    if 'evidence' in data:
        _check(isinstance(data['evidence'],dict), 'evidence', 'optional metadata must be an object')
    c=data['context']
    _object(c, ('parcel','fronts','levels_m','ground_z_m'), ('parcel','fronts','levels_m'), 'context')
    points=_list(c['parcel'],'context.parcel')
    _check(len(points)>=3 and all(isinstance(p,list) and len(p)==2 and all(_number(v) for v in p) for p in points), 'context.parcel','expected finite XY ring')
    polygon=Polygon(points)
    _check(polygon.is_valid and polygon.area>0 and len({tuple(p) for p in points})==len(points), 'context.parcel','invalid ring; omit closing duplicate')
    levels=_list(c['levels_m'],'context.levels_m')
    _check(len(levels)>=2 and all(_number(v) for v in levels) and all(a<b for a,b in zip(levels,levels[1:])), 'context.levels_m','finite ascending floor-finish levels required')
    if 'ground_z_m' in c:
        _check(_number(c['ground_z_m']), 'context.ground_z_m','expected finite elevation')
    fronts=c['fronts']
    _check(isinstance(fronts,dict) and bool(fronts), 'context.fronts','expected named fronts')
    for key,edge in fronts.items():
        _id(key,'context.fronts')
        _check(type(edge) is int and 0<=edge<len(points),'context.fronts.'+key,'invalid input-ring edge')
    _check(len(set(fronts.values()))==len(fronts),'context.fronts','duplicate edge')
    b=data['building']
    _object(b, ('organization','profile','style','bodies','operations','site','facades','roof','finishes'), (), 'building')
    if 'organization' in b: _enum(b['organization'],ORGANIZATIONS,'building.organization')
    if 'style' in b: _enum(b['style'],STYLES,'building.style')
    if 'profile' in b:
        from domain.generation_profile import PROFILES
        _enum(b['profile'],tuple(PROFILES),'building.profile')
    bodies=b.get('bodies',[{'id':'main'}])
    _list(bodies,'building.bodies')
    _check(bool(bodies),'building.bodies','at least one body required')
    ids=set()
    for body in bodies:
        _object(body,('id','position','floors','width','style'),('id',),'body')
        _id(body['id'],'body.id')
        _check(body['id'] not in ids,'body.id','duplicate ID')
        ids.add(body['id'])
        if 'position' in body: _enum(body['position'],POSITIONS,'body.position')
        if 'floors' in body: _floors(body['floors'],len(levels)-1,'body.floors')
        if 'width' in body: _enum(body['width'],('narrow','medium','wide'),'body.width')
        if 'style' in body: _enum(body['style'],STYLES,'body.style')
    body_floors={body['id']:set(body.get('floors',range(1,len(levels)))) for body in bodies}
    operations=_list(b.get('operations',[]),'operations')
    opids=set()
    for op in operations:
        _object(op,('id','kind','body','front','floors','position','depth','width','weights','planes','after'),('id','kind','body'),'operation')
        _id(op['id'],'operation.id')
        _check(op['id'] not in opids,'operation.id','duplicate ID')
        opids.add(op['id'])
        _enum(op['kind'],OPERATIONS,'operation.kind')
        _check(op['body'] in ids,'operation.body','unknown body')
        if 'front' in op: _check(op['front'] in fronts,'operation.front','unknown front')
        if op['kind'] not in ('attach','courtyard'):
            _check('front' in op,'operation.front','required for oriented operation')
        if 'floors' in op: _floors(op['floors'],len(levels)-1,'operation.floors')
        if 'floors' in op:
            _check(set(op['floors'])<=body_floors[op['body']],'operation.floors','floor absent from body')
        if 'position' in op: _enum(op['position'],POSITIONS,'operation.position')
        if 'depth' in op: _enum(op['depth'],SIZES,'operation.depth')
        if 'width' in op: _enum(op['width'],('narrow','medium','wide','all'),'operation.width')
        if op['kind']=='depth_rhythm':
            weights=op.get('weights'); planes=op.get('planes')
            _check(isinstance(weights,list) and len(weights)>=2 and all(_number(v) and v>0 for v in weights),'operation.weights','positive sector weights required')
            _check(isinstance(planes,list) and len(planes)==len(weights),'operation.planes','one plane per sector required')
            for plane in planes: _enum(plane,('base','recessed','projecting'),'operation.planes')
        else:
            _check(not {'weights','planes'} & set(op),'operation','weights/planes only apply to depth_rhythm')
    dependencies={op['id']:op.get('after',[]) for op in operations}
    phases={op['id']:PHASE_ORDER.index(OP_PHASE[op['kind']]) for op in operations}
    for key,refs in dependencies.items():
        _list(refs,'operation.after')
        _check(all(ref in opids and ref!=key for ref in refs),'operation.after','unknown/self dependency')
    visited=set(); active=set()
    def visit(key):
        _check(key not in active,'operation.after','dependency cycle')
        if key in visited:return
        active.add(key)
        for ref in dependencies[key]:visit(ref)
        active.remove(key);visited.add(key)
    for key in dependencies:visit(key)
    for key,refs in dependencies.items():
        _check(all(phases[ref]<=phases[key] for ref in refs),'operation.after','dependency contradicts architectural phase order')
    site=b.get('site',{})
    _object(site,('front_space','fence','door','garage'),(),'site')
    if 'front_space' in site:
        space=site['front_space']
        if space is not False:
            _object(space,('front','depth','use'),('front',),'site.front_space')
            _check(space['front'] in fronts,'site.front_space.front','unknown front')
            if 'depth' in space:_enum(space['depth'],SIZES,'site.front_space.depth')
            if 'use' in space:_enum(space['use'],('garden','patio','driveway','mixed'),'site.front_space.use')
    if 'fence' in site and site['fence'] is not False:
        fence=site['fence']
        _object(fence,('front','form','height','style','cap'),('front','form'),'site.fence')
        _check(fence['front'] in fronts,'site.fence.front','unknown front')
        _enum(fence['form'],('solid','open','base_and_rail','partial'),'site.fence.form')
        if 'height' in fence:_enum(fence['height'],('low','high'),'site.fence.height')
        if 'style' in fence:_enum(fence['style'],STYLES,'site.fence.style')
        if 'cap' in fence:_enum(fence['cap'],('plain','tile','corrugated'),'site.fence.cap')
    for key in ('door','garage'):
        if key in site:
            _check(type(site[key]) is bool or site[key] in ('left','center','right'), 'site.'+key,'boolean or horizontal position required')
    facade_scopes=set()
    for facade in _list(b.get('facades',[]),'facades'):
        _object(facade,('body','front','floors','windows','alignment','style'),('body','front','floors'),'facade')
        _check(facade['body'] in ids,'facade.body','unknown body')
        _check(facade['front'] in fronts,'facade.front','unknown front')
        _floors(facade['floors'],len(levels)-1,'facade.floors')
        _check(set(facade['floors'])<=body_floors[facade['body']],'facade.floors','floor absent from body')
        for floor in facade['floors']:
            scope=(facade['body'],facade['front'],floor)
            _check(scope not in facade_scopes,'facade','ambiguous duplicate body/front/floor')
            facade_scopes.add(scope)
        if 'style' in facade:_enum(facade['style'],STYLES,'facade.style')
        if 'alignment' in facade:_enum(facade['alignment'],('aligned','staggered','independent'),'facade.alignment')
        if 'windows' in facade:
            w=facade['windows']
            _object(w,('count','proportion','distribution','style','frame'),('count',),'windows')
            _check(type(w['count']) is int and w['count']>=0,'windows.count','nonnegative integer required')
            if 'proportion' in w:_enum(w['proportion'],('horizontal','vertical','square','small_high'),'windows.proportion')
            if 'distribution' in w:_enum(w['distribution'],('balanced','left','right','grouped'),'windows.distribution')
            if 'style' in w:_enum(w['style'],STYLES,'windows.style')
            if 'frame' in w:_enum(w['frame'],('wood','metal','pvc'),'windows.frame')
    roof=b.get('roof',{})
    _object(roof,('cover','objects','shade'),(),'roof')
    if 'cover' in roof:_enum(roof['cover'],('slab','corrugated','tile','mixed'),'roof.cover')
    if 'objects' in roof:
        for obj in _list(roof['objects'],'roof.objects'):
            _enum(obj,('water_tank','tank_elevated','laundry','antenna','planter','caseta','stair_bulkhead','hvac'),'roof.objects')
    if 'shade' in roof:_check(type(roof['shade']) is bool,'roof.shade','expected boolean')
    finishes=b.get('finishes',{})
    _object(finishes,('front','sides'),(),'finishes')
    for value in finishes.values():_enum(value,('plaster','rough_plaster','brick','concrete','mixed'),'finishes')
    # JSON roundtrip isolates caller mutations and rejects unsupported objects.
    return IntentRequest(json.loads(json.dumps(data,allow_nan=False)))


def validate_intent(data):
    try:
        return _validate_intent(data)
    except (TypeError, KeyError) as exc:
        raise ValueError(f'intent: malformed field type ({exc})') from exc


def from_json(text):
    return validate_intent(json.loads(text))


def operation_order(request):
    """Stable precedence plus explicit dependencies; does not execute geometry."""
    ops=request.data['building'].get('operations',[])
    pending={op['id']:op for op in ops}; result=[]
    while pending:
        ready=[op for op in pending.values() if all(ref in result for ref in op.get('after',[]))]
        _check(bool(ready),'operations','cyclic dependencies')
        selected=min(ready,key=lambda op:(PHASE_ORDER.index(OP_PHASE[op['kind']]),op['id']))
        result.append(selected['id']);del pending[selected['id']]
    return tuple(result)
