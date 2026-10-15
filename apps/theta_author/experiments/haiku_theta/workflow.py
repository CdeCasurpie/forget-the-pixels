"""Fusión acotada, invariantes humanos y tablas de anclaje del resolver real."""
from copy import deepcopy
from dataclasses import asdict
import json
import math

from .schemas import STAGES, response_model
from domain.theta import from_json, canonical
from modeling.theta import resolve_theta
from pipeline.theta import reconstruct
from domain.architecture import ParcelContext
from modeling.grammar import street_envelope
from modeling.validation import validate_mesh, analyze_topology
from shapely.geometry import Polygon


def next_stage(state):
    return next((stage for stage in STAGES if stage not in state['accepted']), None)


def validate_floor_grid(request, levels, constraints):
    """El número derivado por masa no detecta pisos extra en masas apiladas."""
    n = constraints['floors']
    if (len(levels) != n + 1 or levels[0] != 0 or
            any(not math.isfinite(z) for z in levels) or
            any(not 2.2 <= b-a <= 6 for a, b in zip(levels, levels[1:]))):
        raise ValueError(f'Pisos humanos fijos: se requieren {n+1} cotas desde 0; incrementos 2.2–6 m.')
    fixed_height = constraints.get('height_m')
    if fixed_height is not None and abs(levels[-1] - fixed_height) > 1e-6:
        raise ValueError('La altura humana fija fue alterada.')
    masses = request['theta'].get('masses') or request['theta']['massing'].get('components',[])
    if not masses or not any(abs(m['levels_m'][-1]-levels[-1]) < 1e-6 for m in masses):
        raise ValueError('Alguna masa debe llegar al último nivel humano.')
    for m in masses:
        zs = m['levels_m']
        if len(zs) < 2 or zs[0] < 0 or zs[-1] > levels[-1] + 1e-6:
            raise ValueError('Masa fuera de la altura de la retícula de pisos.')
        if not any(abs(zs[0]-z) < 1e-6 for z in levels):
            raise ValueError('La base de una masa debe corresponder a una cota de piso.')
        expected = [z for z in levels if zs[0]+1e-6 < z < zs[-1]-1e-6]
        if len(zs[1:-1]) != len(expected) or any(abs(a-b)>1e-6 for a,b in zip(zs[1:-1], expected)):
            raise ValueError('La masa añade/omite niveles interiores de la retícula humana.')
    for low, high in zip(levels, levels[1:]):
        if not any(m['levels_m'][0] <= low+1e-6 and m['levels_m'][-1] >= high-1e-6 for m in masses):
            raise ValueError('Un piso de la retícula no tiene masa construida.')


def resolve(request):
    obj = from_json(json.dumps(request, allow_nan=False))
    return resolve_theta(obj.context, obj.theta)


def wall_chart(resolved):
    chart = []
    for wall in resolved.walls:
        f = wall.facade
        chart.append(dict(id=f.edge_id, mass_ref=wall.mass_role, edge=wall.edge,
            vertex_a=list(f.vertex_a), vertex_b=list(f.vertex_b), base_z=wall.base_z,
            width_m=f.width_m, height_m=wall.height_m,
            visible_domains=wall.visible_domains,
            openings=[dict(index=i, **asdict(o)) for i,o in enumerate(f.openings)]))
    return chart


def _facade(theta, mass, edge):
    for f in theta['facades']:
        if f['mass_role'] == mass and f['edge'] == edge:
            return f['controls']
    controls = dict(mode='explicit', openings=[], projections=[], material_regions=[])
    theta['facades'].append(dict(mass_role=mass, edge=edge, controls=controls))
    return controls


def apply_response(state, raw, view_ids):
    """Sin efectos de disco. Solo el contrato de la etapa puede modificar theta."""
    stage = next_stage(state)
    if stage is None:
        raise ValueError('El caso ya completó sus etapas; crear una rama para revisarlo.')
    # Decodificar también el JSON original evita que dataclasses Pydantic descarten extras.
    data = json.loads(raw)
    model = response_model(stage)
    parsed = model.model_validate(data)
    _reject_unknown(data, model.model_json_schema())
    if parsed.blockers:
        raise ValueError('Bloqueos declarados: ' + '; '.join(parsed.blockers))
    for entry in parsed.evidence:
        if not set(entry.view_ids) <= set(view_ids):
            raise ValueError('Evidencia referencia una vista inexistente.')
        if entry.status == 'observed' and not entry.view_ids:
            raise ValueError('Una observación debe citar al menos una foto.')
    changes = parsed.changes.model_dump(mode='json')
    new = deepcopy(state)
    theta = new['request']['theta']
    if stage == '01_lectura':
        for item in changes['inventory']:
            if not set(item['view_ids']) <= set(view_ids):
                raise ValueError('Inventario referencia una vista inexistente.')
        new['inventory'] = changes
    elif stage == '02_masas':
        new['floor_levels_m'] = changes['floor_levels_m']
        if changes['components'] is not None:
            theta.pop('masses',None)
            theta['massing'] = dict(components=changes['components'])
        else:
            theta['massing'] = dict(pattern='explicit')
            theta['masses'] = changes['masses']
    elif stage == '03_lenguaje':
        theta['architectural_style'] = changes['architectural_style']
    elif stage in ('04_puertas', '05_ventanas'):
        allowed = {'door', 'gate'} if stage == '04_puertas' else {'window'}
        ids = {p['id'] for p in new['opening_ledger']}
        for p in changes['placements']:
            if p['id'] in ids or p['opening']['kind'] not in allowed:
                raise ValueError('ID duplicado o tipo de abertura ajeno a esta etapa.')
            ids.add(p['id'])
            _facade(theta, p['mass_ref'], p['edge'])['openings'].append(p['opening'])
            new['opening_ledger'].append(dict(stage=stage, **p))
    elif stage == '08_remates':
        for detail in changes.pop('wall_details'):
            controls = _facade(theta, detail['mass_ref'], detail['edge'])
            controls.update(top_profile=detail['top_profile'], projections=detail['projections'])
        theta.update(changes)
    elif stage == '11_materiales':
        for detail in changes.pop('wall_materials'):
            _facade(theta, detail['mass_ref'], detail['edge'])['material_regions'] = detail['material_regions']
        theta.update(changes)
    elif stage == '12_revision':
        for finding in changes['findings']:
            if finding['target_stage'] not in STAGES or finding['target_stage'] == stage:
                raise ValueError('Revisión debe señalar una etapa de autoría existente.')
            if not set(finding['view_ids']) <= set(view_ids):
                raise ValueError('Revisión referencia una vista inexistente.')
        if changes['verdict'] == 'accept' and changes['findings']:
            raise ValueError('No aceptar una revisión con correcciones pendientes.')
        new['review'] = changes
    else:
        theta.update(changes)
    validate_floor_grid(new['request'], new['floor_levels_m'], new['constraints'])
    resolved = resolve(new['request'])
    new['accepted'].append(stage)
    new['decisions'].append(data)
    new['walls'] = wall_chart(resolved)
    new['resolved_architecture'] = json.loads(canonical(resolved))
    return new, resolved


def _reject_unknown(value, schema, root=None):
    """Rechaza extras incluso en dataclasses anidadas del dominio."""
    root = schema if root is None else root
    if '$ref' in schema:
        return _reject_unknown(value, root['$defs'][schema['$ref'].split('/')[-1]], root)
    if isinstance(value, dict):
        variants = schema.get('anyOf', [])
        for variant in variants:
            if variant.get('type') != 'null':
                _reject_unknown(value, variant, root)
        props = schema.get('properties')
        if props is not None:
            if set(value)-set(props):
                raise ValueError(f'Claves desconocidas: {sorted(set(value)-set(props))}')
            for key, item in value.items():
                _reject_unknown(item, props[key], root)
    elif isinstance(value, list):
        if 'items' in schema:
            for item in value:
                _reject_unknown(item, schema['items'], root)
        elif 'anyOf' in schema:
            for variant in schema['anyOf']:
                if variant.get('type') != 'null':
                    _reject_unknown(value, variant, root)


def materialize(request):
    result = reconstruct(from_json(json.dumps(request, allow_nan=False)))
    c = result.resolved.context
    env = street_envelope(ParcelContext(c.parcel, explicit_fronts=c.fronts))
    validation = validate_mesh(result.mesh, Polygon(c.parcel), envelope=env)
    topology = analyze_topology(result.mesh)
    return result, validation, {k:v for k,v in topology.items() if k != 'components'}
