"""Run from the repository: python -m apps.cadastral_editor.server."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import threading
from functools import lru_cache

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
import geopandas as gpd
from pyproj import Transformer
from shapely import affinity
from shapely.geometry import mapping, shape, box
from shapely.ops import transform

from packages.barranco_data.store import Store, Conflict
from .photos import Photos

REPOSITORY = Path(__file__).resolve().parents[2]


def create_app(data=None, workspace=None, demo=False, minimum_area=6., auto_blocks=True):
    data = Path(data or REPOSITORY/'data/barranco')
    store = Store(workspace or data/'editor')
    if not (store.directory/'current.json').exists():
        if demo:
            records = [('demo-a', box(279950, 8656480, 279962, 8656500)),
                       ('demo-b', box(279962, 8656480, 279974, 8656500)),
                       ('demo-c', box(279995, 8656480, 280007, 8656500))]
            source = {'type': 'synthetic'}
        else:
            source_path = data/'lotes/BARRANCO_LM_geogpsperu_SuyoPomalia.shp'
            if not source_path.exists():
                source_path = data/'lotes/BARRANCO_LM_geogpsperu.geojson'
            frame = gpd.read_file(source_path).to_crs(32718)
            offset_path = data/'cadastral_offset.json'
            offset = json.loads(offset_path.read_text()) if offset_path.exists() else {}
            if offset and offset.get('crs') != 'EPSG:32718':
                raise ValueError('CRS del offset no admitido')
            dx, dy = offset.get('east_m', 0), offset.get('north_m', 0)
            records = [(str(int(row.objectid)), affinity.translate(row.geometry, dx, dy)) for _, row in frame.iterrows()]
            source = dict(path=str(source_path.relative_to(data)), applied_offset_m=[dx, dy],
                sha256=hashlib.sha256(source_path.read_bytes()).hexdigest())
            if source_path.suffix == '.shp':
                source['companion_hashes'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in sorted(source_path.parent.glob(source_path.stem+'.*')) if p.is_file()}
        store.initialize(records, source, minimum_area)
    # Fill missing assignments once, without reimporting edited XY or reapplying offsets.
    current = store.load()
    if auto_blocks and not demo and not current.get('block_detection') and any(l['status'] == 'active' and not l['block_id'] for l in current['lots'].values()):
        store.commit(store.prepare(dict(type='auto_blocks', revision=current['revision'])))
    photos = Photos(data, REPOSITORY)
    to_map = Transformer.from_crs(32718, 4326, always_xy=True).transform
    to_metric = Transformer.from_crs(4326, 32718, always_xy=True).transform
    app = FastAPI(title='Barranco · Editor catastral')
    app.state.store = store
    pending = {}
    pending_lock = threading.Lock()
    snapshot_lock = threading.Lock()

    @lru_cache(maxsize=2)
    def cached_snapshot(revision):
        return store.load(revision)

    def read_snapshot(revision):
        # Read-only immutable revision, shared by concurrent image requests.
        with snapshot_lock:
            return cached_snapshot(revision)

    def feature(lot):
        return dict(type='Feature', id=lot['lot_id'], properties={k: lot[k] for k in
            ('lot_id', 'block_id', 'geometry_revision', 'status', 'source_lot_ids', 'fronts_review')},
            geometry=mapping(transform(to_map, shape(lot['geometry']))))

    @app.exception_handler(Conflict)
    async def conflict(request, exc):
        from fastapi.responses import JSONResponse
        return JSONResponse({'detail': str(exc)}, status_code=409)

    @app.exception_handler(ValueError)
    async def invalid(request, exc):
        from fastapi.responses import JSONResponse
        return JSONResponse({'detail': str(exc)}, status_code=422)

    @app.get('/api/config')
    def config():
        return dict(google_maps_key=os.environ.get('GOOGLE_MAPS_API_KEY', ''), demo=demo)

    @app.get('/api/state')
    def state():
        current = store.load()
        return dict(revision=current['revision'], type='FeatureCollection', source=current['source'],
            features=[feature(l) for l in current['lots'].values() if l['status'] == 'active'],
            blocks={k: dict(block_id=k, lot_ids=b['lot_ids'], geometry=mapping(transform(to_map, shape(b['geometry']))))
                    for k, b in current['blocks'].items()})

    @app.get('/api/original')
    def original():
        current = store.load()
        while current['parent_revision']:
            current = store.load(current['parent_revision'])
        return dict(type='FeatureCollection', features=[feature(l) for l in current['lots'].values()])

    @app.get('/api/lots/{identifier}')
    def lot_detail(identifier: str):
        current = store.load()
        if identifier not in current['lots']:
            raise HTTPException(404, 'Lote desconocido')
        lot = current['lots'][identifier]
        return dict(**lot, revision=current['revision'], crs=current['crs'],
            fronts_map=[{**f, 'geometry': mapping(transform(to_map, shape(f['geometry'])))} for f in lot['fronts']],
            photos=photos.candidates(shape(lot['geometry'])), area_m2=shape(lot['geometry']).area,
            view_settings=store.view_settings(identifier))

    @app.get('/api/lots/{identifier}/snapshot')
    def snapshot(identifier: str):
        current = store.load()
        if identifier not in current['lots']:
            raise HTTPException(404, 'Lote desconocido')
        lot = current['lots'][identifier]
        settings = store.view_settings(identifier)
        ids = settings['photo_ids'] if settings else []
        return dict(schema_version=1, dataset_id=current['dataset_id'], revision=current['revision'], crs=current['crs'],
            lot=lot, imagery='poses_barranco/metadata.json', view_settings=settings,
            view_settings_stale=bool(settings and settings['geometry_revision'] != lot['geometry_revision']),
            cameras=[photos.describe(p, shape(lot['geometry'])) for p in ids if p in photos.meta],
            missing_photo_ids=[p for p in ids if p not in photos.meta])

    @app.post('/api/lots/{identifier}/view-settings')
    def save_views(identifier: str, body: dict):
        ids = body.get('photo_ids')
        if not isinstance(ids, list) or any(not isinstance(p, str) or p not in photos.meta for p in ids):
            raise ValueError('Fotografías desconocidas')
        return store.save_view_settings(identifier, body.get('geometry_revision'), ids, body.get('reference_height_m'))

    @app.get('/api/cameras/{pid}')
    def camera(pid: str, lot_id: str, revision: str):
        state = read_snapshot(revision)
        if lot_id not in state['lots']:
            raise HTTPException(404, 'Lote desconocido')
        return photos.describe(pid, shape(state['lots'][lot_id]['geometry']))

    @app.get('/api/freshness/{identifier}/{revision}')
    def freshness(identifier: str, revision: str):
        current = store.load()
        lot = current['lots'].get(identifier)
        return dict(stale=not lot or lot['status'] != 'active' or lot['geometry_revision'] != revision)

    @app.get('/api/photos/{pid}')
    def photo(pid: str, lot_id: str, revision: str, height: float = 12, clean: bool = False):
        if not 1 <= height <= 150:
            raise ValueError('Altura fuera de rango')
        state = read_snapshot(revision)
        if lot_id not in state['lots']:
            raise HTTPException(404, 'Lote desconocido')
        geometry = json.dumps(state['lots'][lot_id]['geometry'])
        image = photos.base(pid, geometry) if clean else photos.render(pid, geometry, height)
        return Response(image, media_type='image/jpeg', headers={'Cache-Control':'private, max-age=3600'})

    @app.post('/api/preview')
    def preview(command: dict):
        if 'line_lonlat' in command:
            command['line'] = [list(to_metric(*p)) for p in command.pop('line_lonlat')]
        if command.get('type') == 'translate_block' and 'drag_lonlat' in command:
            start, end = command.pop('drag_lonlat')
            a, b = to_metric(*start), to_metric(*end)
            command['dx'], command['dy'] = b[0]-a[0], b[1]-a[1]
        prepared = store.prepare(command)
        with pending_lock:
            if len(pending) >= 32:
                pending.pop(next(iter(pending)))
            pending[prepared['revision']] = prepared
        ids = prepared['operation']['result_ids']
        return dict(token=prepared['revision'], affected=prepared['operation']['affected'], result_ids=ids,
            parameters=prepared['operation']['parameters'],
            features=[feature(prepared['lots'][i]) for i in ids if prepared['lots'][i]['status'] == 'active'])

    @app.post('/api/commit')
    def commit(body: dict):
        with pending_lock:
            prepared = pending.get(body.get('token'))
            if prepared is None:
                raise ValueError('Previsualización ausente o expirada')
            result = store.commit(prepared)
            pending.pop(body['token'])
        return dict(revision=result['revision'], result_ids=result['operation']['result_ids'])

    @app.get('/api/history')
    def history():
        current = store.load()
        result = []
        while True:
            result.append(dict(revision=current['revision'], **current['operation']))
            if not current['parent_revision'] or len(result) >= 100:
                break
            current = store.load(current['parent_revision'])
        return result

    @app.get('/')
    def index():
        return FileResponse(Path(__file__).parent/'static/index.html')

    app.mount('/shared', StaticFiles(directory=REPOSITORY/'packages/barranco_imaging/static'), name='shared')
    app.mount('/static', StaticFiles(directory=Path(__file__).parent/'static'), name='static')
    return app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--data', type=Path)
    parser.add_argument('--workspace', type=Path)
    parser.add_argument('--demo', action='store_true')
    parser.add_argument('--min-area', type=float, default=6., help='Área mínima de nuevos lotes, fijada al crear el workspace')
    parser.add_argument('--no-auto-blocks', action='store_true', help='No precalcular manzanas sin asignar al iniciar')
    args = parser.parse_args()
    if args.demo and not args.workspace:
        parser.error('--demo requiere --workspace para separar las pruebas de datos reales')
    import uvicorn
    uvicorn.run(create_app(args.data, args.workspace, args.demo, args.min_area, not args.no_auto_blocks), host='127.0.0.1', port=args.port)


if __name__ == '__main__':
    main()
