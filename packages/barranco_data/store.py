"""Immutable revisions published through one atomic pointer (single local host)."""
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
import fcntl
import json
import math
import os
import re
from pathlib import Path
import uuid

from shapely import affinity
from shapely.geometry import LineString, Point, mapping, shape
from shapely.geometry.polygon import orient
from shapely.ops import split, unary_union
from .blocks import suggest_blocks


def uid():
    return uuid.uuid4().hex


def now():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, value):
    temp = path.with_name(path.name + '.' + uid() + '.tmp')
    with temp.open('w') as stream:
        json.dump(value, stream, ensure_ascii=False, allow_nan=False)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)
    fd = os.open(path.parent, os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


class Conflict(ValueError):
    pass


class Store:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        (self.directory / 'revisions').mkdir(exist_ok=True)

    def view_settings(self, identifier):
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', identifier):
            raise ValueError('ID de lote inválido')
        path = self.directory/'views'/f'{identifier}.json'
        return json.loads(path.read_text()) if path.exists() else None

    def save_view_settings(self, identifier, geometry_revision, photo_ids, reference_height_m):
        if not isinstance(photo_ids, list) or len(photo_ids) > 200 or any(not isinstance(p, str) for p in photo_ids):
            raise ValueError('Lista de fotografías inválida')
        if not isinstance(reference_height_m, (int, float)) or not 1 <= reference_height_m <= 150:
            raise ValueError('Altura de referencia fuera de rango')
        with self.lock():
            current = self.load()
            self.active(current, [identifier])
            if current['lots'][identifier]['geometry_revision'] != geometry_revision:
                raise Conflict('El lote cambió; actualiza antes de guardar las vistas')
            self.view_settings(identifier)  # Validate the filename before writing.
            path = self.directory/'views'
            path.mkdir(exist_ok=True)
            value = dict(schema_version=1, lot_id=identifier, geometry_revision=geometry_revision,
                photo_ids=list(dict.fromkeys(photo_ids)), reference_height_m=reference_height_m,
                height_role='cadastral_preview_only', updated_at=now())
            write_json(path/f'{identifier}.json', value)
        return value

    @contextmanager
    def lock(self):
        with (self.directory / '.lock').open('a') as stream:
            fcntl.flock(stream, fcntl.LOCK_EX)
            yield

    def load(self, revision=None):
        if revision is None:
            revision = json.loads((self.directory / 'current.json').read_text())['revision']
        if not isinstance(revision, str) or len(revision) != 32 or any(c not in '0123456789abcdef' for c in revision):
            raise ValueError('Revisión inválida')
        return json.loads((self.directory / 'revisions' / (revision + '.json')).read_text())

    def publish(self, state):
        write_json(self.directory / 'revisions' / (state['revision'] + '.json'), state)
        write_json(self.directory / 'current.json', {'revision': state['revision']})

    def initialize(self, records, source, minimum_area_m2=6.):
        if not math.isfinite(minimum_area_m2) or minimum_area_m2 <= 0:
            raise ValueError('Área mínima inválida')
        with self.lock():
            if (self.directory / 'current.json').exists():
                return self.load()
            revision = uid()
            lots = {}
            for identifier, polygon in records:
                identifier = str(identifier)
                if identifier in lots:
                    raise ValueError('ID duplicado: ' + identifier)
                if polygon.geom_type != 'Polygon' or not polygon.is_valid or polygon.is_empty:
                    raise ValueError('Parcela fuente inválida: ' + identifier)
                lots[identifier] = dict(lot_id=identifier, source_lot_ids=[identifier], parent_lot_ids=[],
                    status='active', replaced_by=[], block_id=None, geometry=mapping(orient(polygon)),
                    geometry_revision=revision, fronts=fronts(polygon, None), fronts_review=False, created_at=now())
            state = dict(schema_version=1, dataset_id='barranco', crs='EPSG:32718', units='m',
                revision=revision, parent_revision=None, source=source, lots=lots, blocks={},
                operation=dict(type='import', date=now(), affected=list(lots)), invalidated_lot_ids=[],
                minimum_lot_area_m2=minimum_area_m2)
            self.publish(state)
            return state

    @staticmethod
    def active(state, ids):
        if not ids or len(set(ids)) != len(ids):
            raise ValueError('Selecciona lotes distintos')
        if any(i not in state['lots'] or state['lots'][i]['status'] != 'active' for i in ids):
            raise ValueError('Lote inexistente o reemplazado')
        return [state['lots'][i] for i in ids]

    @staticmethod
    def polygon_ok(polygon, minimum_area):
        if polygon.geom_type != 'Polygon' or not polygon.is_valid or polygon.interiors or polygon.area < minimum_area:
            raise ValueError(f'Se requiere un polígono válido sin huecos y con área ≥ {minimum_area:g} m²')

    def prepare(self, command):
        base = self.load()
        if command.get('revision') != base['revision']:
            raise Conflict('Los datos cambiaron. Actualiza la selección.')
        state = deepcopy(base)
        state['revision'] = uid()
        state['parent_revision'] = base['revision']
        kind = command.get('type')
        ids = command.get('ids', [])
        affected = set()
        result_ids = list(ids)
        if kind == 'undo':
            target = base
            undone = set()
            while target['parent_revision']:
                if target['operation']['type'] == 'undo':
                    undone.add(target['operation']['parameters']['undo_revision'])
                elif target['revision'] not in undone:
                    break
                target = self.load(target['parent_revision'])
            if not target['parent_revision']:
                raise ValueError('No hay una operación anterior')
            command = {**command, 'undo_revision': target['revision']}
            prior = self.load(target['parent_revision'])
            state['lots'], state['blocks'] = deepcopy(prior['lots']), deepcopy(prior['blocks'])
            affected = set(target['operation']['affected'])
            # Retain retired IDs even when undo removes newly created lots.
            for i, lot in base['lots'].items():
                if i not in state['lots']:
                    state['lots'][i] = deepcopy(lot)
                    state['lots'][i]['status'] = 'superseded'
            result_ids = [i for i in affected if state['lots'][i]['status'] == 'active']
        elif kind in ('split', 'merge'):
            lots = self.active(state, ids)
            blocks = {lot['block_id'] for lot in lots}
            if len(blocks) > 1:
                raise ValueError('Asigna los lotes a la misma manzana antes de fusionar')
            polys = [shape(lot['geometry']) for lot in lots]
            if kind == 'split':
                if len(lots) != 1:
                    raise ValueError('El corte requiere un solo lote')
                coords = command.get('line', [])
                if len(coords) < 2 or not all(len(p) == 2 and all(math.isfinite(x) for x in p) for p in coords):
                    raise ValueError('Dibuja una línea de corte válida')
                line = LineString(coords)
                if not line.is_simple or line.length < .01:
                    raise ValueError('La línea no debe cruzarse a sí misma')
                parts = list(split(polys[0], line).geoms)
                if len(parts) != 2:
                    raise ValueError('El corte debe producir exactamente dos partes')
            else:
                if len(lots) < 2:
                    raise ValueError('Selecciona al menos dos lotes')
                union = unary_union(polys)
                if sum(p.area for p in polys) - union.area > .01:
                    raise ValueError('Los lotes se solapan; revisa la geometría')
                parts = [union]
            for p in parts:
                self.polygon_ok(p, state.get('minimum_lot_area_m2', 6.))
            if unary_union(parts).symmetric_difference(unary_union(polys)).area > .001:
                raise ValueError('La operación no conserva el área')
            result_ids = []
            for p in parts:
                identifier = uid()
                state['lots'][identifier] = dict(lot_id=identifier,
                    source_lot_ids=sorted({s for lot in lots for s in lot['source_lot_ids']}),
                    parent_lot_ids=ids, status='active', replaced_by=[], block_id=lots[0]['block_id'],
                    geometry=mapping(orient(p)), geometry_revision=state['revision'], fronts=[],
                    fronts_review=any(lot['fronts'] for lot in lots), created_at=now())
                result_ids.append(identifier)
            for lot in lots:
                lot['status'], lot['replaced_by'] = 'superseded', result_ids
            affected.update(ids + result_ids)
        elif kind == 'auto_blocks':
            assignments, ambiguous = suggest_blocks(state['lots'])
            if not assignments:
                raise ValueError('Todos los lotes activos ya tienen manzana')
            for identifier, block in assignments.items():
                state['lots'][identifier]['block_id'] = block
                state['lots'][identifier]['block_assignment'] = 'connected_component'
            affected.update(assignments)
            result_ids = sorted(assignments)
            state['block_detection'] = dict(method='intersects_connected_components',
                date=now(), ambiguous_blocks=ambiguous, newly_assigned=len(assignments))
        elif kind == 'assign_block':
            lots = self.active(state, ids)
            block = command.get('block_id') or uid()
            if not isinstance(block, str) or not block.strip() or len(block) > 100:
                raise ValueError('ID de manzana inválido')
            for lot in lots:
                lot['block_id'] = block
                lot['block_assignment'] = 'manual'
            affected.update(ids)
        elif kind == 'translate_block':
            block = command.get('block_id')
            if not block or block not in state['blocks']:
                raise ValueError('Selecciona una manzana')
            dx, dy = float(command.get('dx', 0)), float(command.get('dy', 0))
            if not all(math.isfinite(v) for v in (dx, dy)) or math.hypot(dx, dy) > 1000:
                raise ValueError('Desplazamiento inválido (máximo 1000 m)')
            members = [l for l in state['lots'].values() if l['status'] == 'active' and l['block_id'] == block]
            others = [shape(l['geometry']) for l in state['lots'].values() if l['status'] == 'active' and l['block_id'] != block]
            from shapely.strtree import STRtree
            tree = STRtree(others)
            for lot in members:
                before = shape(lot['geometry'])
                after = affinity.translate(before, dx, dy)
                for idx in tree.query(after):
                    other = others[int(idx)]
                    if after.intersection(other).area > max(.05, before.intersection(other).area + .01):
                        raise ValueError('El movimiento aumenta un solapamiento con otra manzana/lote')
                lot['geometry'] = mapping(after)
                for front in lot['fronts']:
                    front['geometry'] = mapping(affinity.translate(shape(front['geometry']), dx, dy))
                affected.add(lot['lot_id'])
            result_ids = sorted(affected)
        elif kind == 'edit_fronts':
            lots = self.active(state, ids)
            if len(lots) != 1:
                raise ValueError('Selecciona un lote para editar frentes')
            lot = lots[0]
            edits = command.get('fronts', {})
            available = {f['id'] for f in lot['fronts']}
            if not edits or not set(edits).issubset(available) or any(type(v) is not bool for v in edits.values()):
                raise ValueError('Segmentos o estados inválidos')
            for f in lot['fronts']:
                if f['id'] in edits:
                    f.update(is_front=edits[f['id']], origin='manual')
            lot['fronts_review'] = False
            affected.update(ids)
        else:
            raise ValueError('Operación desconocida')
        self.rebuild(state, affected, preserve_fronts=kind in ('edit_fronts', 'translate_block', 'undo'))
        for i in affected:
            state['lots'][i]['geometry_revision'] = state['revision']
        state['invalidated_lot_ids'] = sorted(affected)
        state['operation'] = dict(type=kind, date=now(), parameters=command,
            affected=sorted(affected), result_ids=result_ids, operation_id=uid())
        return state

    @staticmethod
    def rebuild(state, affected, preserve_fronts=False):
        groups = {}
        for lot in state['lots'].values():
            if lot['status'] == 'active' and lot['block_id']:
                groups.setdefault(lot['block_id'], []).append(lot)
        old_blocks = state['blocks']
        state['blocks'] = {}
        for block, lots in groups.items():
            union = unary_union([shape(l['geometry']) for l in lots])
            members = sorted(l['lot_id'] for l in lots)
            changed = bool(set(members) & affected) or old_blocks.get(block, {}).get('lot_ids') != members
            state['blocks'][block] = dict(block_id=block, lot_ids=members, geometry=mapping(union),
                revision=state['revision'] if changed else old_blocks[block]['revision'])
            if not changed:
                continue
            polygons = list(union.geoms) if union.geom_type == 'MultiPolygon' else [union]
            exterior = unary_union([p.exterior for p in polygons])
            for lot in lots:
                affected.add(lot['lot_id'])
                if preserve_fronts and lot['fronts']:
                    continue
                if any(f['origin'] == 'manual' for f in lot['fronts']):
                    lot['fronts_review'] = True
                lot['fronts'] = fronts(shape(lot['geometry']), exterior)
        for i in list(affected):
            lot = state['lots'][i]
            if lot['status'] == 'active' and not lot['block_id'] and not preserve_fronts:
                lot['fronts'] = fronts(shape(lot['geometry']), None)

    def commit(self, prepared):
        with self.lock():
            if self.load()['revision'] != prepared['parent_revision']:
                raise Conflict('La previsualización quedó desactualizada. Vuelve a prepararla.')
            self.publish(prepared)
        return self.load(prepared['revision'])


def fronts(polygon, exterior):
    """Split edges at exact block-boundary intersections; tolerate 1 cm alignment."""
    result = []
    ring = list(orient(polygon).exterior.coords)
    for a, b in zip(ring, ring[1:]):
        edge = LineString([a, b])
        exposed = edge.intersection(exterior) if exterior is not None else LineString()
        pieces = list(exposed.geoms) if hasattr(exposed, 'geoms') else [exposed]
        distances = [0., edge.length]
        for piece in pieces:
            if piece.geom_type == 'LineString' and not piece.is_empty:
                distances.extend(edge.project(Point(p)) for p in (piece.coords[0], piece.coords[-1]))
        values = sorted(set(round(v, 8) for v in distances))
        for lo, hi in zip(values, values[1:]):
            if hi-lo < 1e-6:
                continue
            segment = LineString([edge.interpolate(lo), edge.interpolate(hi)])
            flag = exterior is not None and exterior.distance(segment.interpolate(.5, normalized=True)) < .01
            result.append(dict(id=f'F{len(result)+1}', geometry=mapping(segment), is_front=bool(flag),
                               origin='block_boundary' if exterior is not None else 'unassigned'))
    return result
