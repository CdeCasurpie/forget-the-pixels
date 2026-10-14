"""Run: python -m apps.theta_author.server (http://127.0.0.1:8767)."""
import argparse
from contextlib import asynccontextmanager
from io import BytesIO
import json
from pathlib import Path
import zipfile
import asyncio
from functools import lru_cache

from fastapi import FastAPI, Query, Request
from starlette.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from pyproj import Transformer
from shapely.geometry import mapping, shape
from shapely.ops import transform

from packages.barranco_data.store import Store, Conflict
from apps.cadastral_editor.photos import Photos
from .service import Author

REPOSITORY = Path(__file__).resolve().parents[2]


def create_app(data=None, workspace=None, cadastral_workspace=None, provider=None, workers=2):
    data = Path(data or REPOSITORY/'data/barranco')
    cadastral = Store(cadastral_workspace or data/'editor')
    if not (cadastral.directory/'current.json').exists():
        raise ValueError('Primero inicializa el catastro con la aplicación A.')
    photos = Photos(data, REPOSITORY, fast=True)
    author = Author(workspace or data/'theta_author', cadastral, photos, provider, workers)
    to_map = Transformer.from_crs(32718, 4326, always_xy=True).transform
    projection_slots = asyncio.Semaphore(2)

    @asynccontextmanager
    async def lifespan(app):
        yield
        author.close()

    app = FastAPI(title='Barranco · Autor de thetas · MOCK temporal', lifespan=lifespan)
    app.state.author = author

    @app.exception_handler(ValueError)
    async def invalid(request, exc):
        return JSONResponse({'detail': str(exc)}, status_code=422)

    @app.exception_handler(ValidationError)
    async def validation_error(request, exc):
        return JSONResponse({'detail': str(exc)}, status_code=422)

    @app.exception_handler(Conflict)
    async def conflict(request, exc):
        return JSONResponse({'detail': str(exc)}, status_code=409)

    @app.get('/api/lots')
    def lots():
        return map_state(author.state()['revision'])

    @lru_cache(maxsize=2)
    def map_state(revision):
        state = author.revision(revision)
        return dict(revision=state['revision'], features=[dict(type='Feature', id=l['lot_id'],
            geometry=mapping(transform(to_map, shape(l['geometry']))), properties=dict(block_id=l['block_id']))
            for l in state['lots'].values() if l['status'] == 'active'])

    @app.get('/api/progress')
    def progress():
        return author.progress()

    @app.get('/api/lots/{identifier}/editor')
    def editor(identifier: str):
        snapshot = author.snapshot(identifier)
        form = author.latest_form(identifier)
        polygon = shape(snapshot['lot']['geometry'])
        cameras = photos.candidates(polygon, limit=3)
        if form and form['geometry_revision'] == snapshot['lot']['geometry_revision']:
            cameras = [photos.describe(pid, polygon) for pid in form['photo_ids'][:3] if pid in photos.meta]
        runs = author.runs(identifier)
        return dict(snapshot=snapshot, photos=cameras, form=form, latest_run=runs[0] if runs else None)

    @app.get('/api/lots/{identifier}/candidates')
    def candidates(identifier: str, offset: int = Query(0, ge=0), limit: int = Query(3, ge=1, le=12)):
        snapshot = author.snapshot(identifier)
        return photos.candidates(shape(snapshot['lot']['geometry']), limit=limit, offset=offset)

    @app.post('/api/lots/{identifier}/autosave')
    def autosave(identifier: str, body: dict):
        return author.autosave(identifier, body)

    @app.post('/api/lots/{identifier}/prepare-quick')
    def prepare_quick(identifier: str, body: dict):
        return author.prepare_quick(identifier, body)

    @app.get('/api/lots/{identifier}')
    def lot(identifier: str):
        snapshot = author.snapshot(identifier)
        return dict(snapshot=snapshot, photos=photos.candidates(shape(snapshot['lot']['geometry'])),
                    fronts_map=[dict(f, geometry=mapping(transform(to_map, shape(f['geometry']))))
                                for f in snapshot['lot']['fronts']],
                    drafts=author.drafts(identifier), runs=author.runs(identifier), selection=author.selection(identifier))

    @app.post('/api/lots/{identifier}/drafts')
    def draft(identifier: str, body: dict):
        return author.save_draft(identifier, body)

    @app.post('/api/lots/{identifier}/prepare')
    def prepare(identifier: str, body: dict):
        return author.prepare(identifier, body)

    @app.get('/api/photos/{pid}')
    async def photo(request: Request, pid: str, lot_id: str, revision: str):
        snapshot = author.revision(revision)
        lot = cadastral.active(snapshot, [lot_id])[0]
        async with projection_slots:
            # Aborted browser requests must not accumulate panorama work behind new lots.
            if await request.is_disconnected():
                return Response(status_code=499)
            content = await run_in_threadpool(photos.base, pid, json.dumps(lot['geometry']))
        return Response(content, media_type='image/jpeg',
                        headers={'Cache-Control': 'private, max-age=3600'})

    @app.get('/api/cameras/{pid}')
    def camera(pid: str, lot_id: str, revision: str):
        lot = cadastral.active(author.revision(revision), [lot_id])[0]
        return photos.describe(pid, shape(lot['geometry']))

    @app.get('/api/runs/{run_id}')
    def run(run_id: str):
        return author.detail(run_id)

    @app.get('/api/runs/{run_id}/status')
    def run_status(run_id: str):
        r = author.record(run_id)
        return dict(r, stale=author.stale(r))

    @app.post('/api/runs/{run_id}/start')
    def start(run_id: str):
        return author.start(run_id)

    @app.post('/api/runs/{run_id}/cancel')
    def cancel(run_id: str):
        return author.cancel(run_id)

    @app.post('/api/runs/{run_id}/import')
    def import_response(run_id: str, body: dict):
        raw = body.get('raw_response')
        if not isinstance(raw, str) or len(raw) > 2_000_000:
            raise ValueError('Respuesta debe ser texto JSON de hasta 2 MB')
        return author.import_response(run_id, raw)

    @app.post('/api/runs/{run_id}/select')
    def select(run_id: str):
        return author.select(run_id)

    @app.get('/api/runs/{run_id}/export')
    def export(run_id: str):
        buffer = BytesIO()
        with author.lock, zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
            directory = author.path(run_id)
            if author.record(run_id)['status'] in ('preparing', 'queued', 'running'):
                raise Conflict('El paquete todavía está en proceso')
            for path in sorted(directory.rglob('*')):
                if path.is_file():
                    archive.write(path, str(path.relative_to(directory)))
        return Response(buffer.getvalue(), media_type='application/zip',
                        headers={'Content-Disposition': f'attachment; filename="theta-{run_id}.zip"'})

    @app.get('/')
    def index():
        return FileResponse(Path(__file__).parent/'static/index.html')

    # Shared angular canvas renderer used by A and B.
    app.mount('/shared', StaticFiles(directory=REPOSITORY/'packages/barranco_imaging/static'), name='shared')
    app.mount('/static', StaticFiles(directory=Path(__file__).parent/'static'), name='static')
    return app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8767)
    parser.add_argument('--data', type=Path)
    parser.add_argument('--workspace', type=Path)
    parser.add_argument('--cadastral-workspace', type=Path)
    parser.add_argument('--workers', type=int, choices=range(1, 9), default=2, help='Trabajos concurrentes (1–8)')
    args = parser.parse_args()
    import uvicorn
    uvicorn.run(create_app(args.data, args.workspace, args.cadastral_workspace, workers=args.workers), host='127.0.0.1', port=args.port)


if __name__ == '__main__':
    main()
