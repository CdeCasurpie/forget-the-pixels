"""Versioned local workflow. No model SDK or UI dependencies."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
import fcntl
import json
from pathlib import Path
import re
import threading
from functools import lru_cache

from shapely.geometry import shape
from packages.barranco_data.store import Conflict, now, uid, write_json
from .contracts import Form
from .compiler import compile_response
from .prompting import build_package
from .providers import MockProvider


def safe_id(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', value):
        raise ValueError('Identificador inválido')
    return value


class Author:
    def __init__(self, directory, cadastral, photos, provider=None, workers=2):
        self.directory = Path(directory)
        for name in ('drafts', 'runs', 'selections', 'autosaves'):
            (self.directory/name).mkdir(parents=True, exist_ok=True)
        self.process_lock = (self.directory/'.server.lock').open('a')
        try:
            fcntl.flock(self.process_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self.process_lock.close()
            raise ValueError('Ya hay un autor de thetas usando este workspace')
        self.cadastral, self.photos = cadastral, photos
        self.provider = provider or MockProvider()
        self.lock = threading.RLock()
        self.executor = ThreadPoolExecutor(max_workers=workers)
        self.preparations = ThreadPoolExecutor(max_workers=2)
        self.run_index = {}
        self.draft_index = {}
        self.autosave_index = {p.stem:json.loads(p.read_text()) for p in (self.directory/'autosaves').glob('*.json')}
        for path in (self.directory/'drafts').glob('*.json'):
            d = json.loads(path.read_text())
            self.draft_index.setdefault(d['lot_id'], []).append(d)
        for path in (self.directory/'runs').glob('*/record.json'):
            record = json.loads(path.read_text())
            if record['status'] in ('preparing', 'queued', 'running'):
                record.update(status='interrupted', error='Aplicación reiniciada; no se reenvió la llamada.', updated_at=now())
                write_json(path, record)
            self.run_index[record['run_id']] = record

    def close(self):
        self.preparations.shutdown(wait=True)
        self.executor.shutdown(wait=True)
        self.process_lock.close()

    @lru_cache(maxsize=3)
    def revision(self, revision):
        return self.cadastral.load(revision)

    def state(self):
        revision = json.loads((self.cadastral.directory/'current.json').read_text())['revision']
        with self.lock:
            return self.revision(revision)

    def snapshot(self, identifier):
        safe_id(identifier)
        state = self.state()
        lot = self.cadastral.active(state, [identifier])[0]
        settings = self.cadastral.view_settings(identifier)
        return dict(dataset_id=state['dataset_id'], revision=state['revision'], crs=state['crs'],
                    lot=lot, view_settings=settings,
                    view_settings_stale=bool(settings and settings['geometry_revision'] != lot['geometry_revision']))

    def stale(self, record):
        lot = self.state()['lots'].get(record['lot_id'])
        return not lot or lot['status'] != 'active' or lot['geometry_revision'] != record['geometry_revision']

    def validate_form(self, identifier, value):
        form = Form.model_validate(value)
        snapshot = self.snapshot(identifier)
        if snapshot['lot']['geometry_revision'] != form.geometry_revision:
            raise Conflict('El lote cambió en A. Recarga y revisa los parámetros antes de guardar.')
        polygon = shape(snapshot['lot']['geometry'])
        for pid in form.photo_ids:
            self.photos.describe(pid, polygon)
        front_ids = {f['id'] for f in snapshot['lot']['fronts'] if f['is_front']}
        if any(c.front_id not in front_ids for c in form.massing.cuts):
            raise ValueError('Selecciona un frente habilitado para cada retiro/mordida')
        return form, snapshot

    @staticmethod
    def fingerprint(form):
        return hashlib.sha256(json.dumps(form, sort_keys=True).encode()).hexdigest()

    def autosave(self, identifier, value):
        form, snapshot = self.validate_form(identifier, value)
        record = dict(lot_id=identifier, form=form.model_dump(), updated_at=now())
        with self.lock:
            write_json(self.directory/'autosaves'/f'{safe_id(identifier)}.json', record)
            self.autosave_index[identifier] = record
        return record

    def latest_form(self, identifier):
        safe_id(identifier)
        if identifier in self.autosave_index:
            return self.autosave_index[identifier]['form']
        drafts = self.draft_index.get(identifier, [])
        return max(drafts, key=lambda d:d['created_at'])['form'] if drafts else None

    def save_draft(self, identifier, value):
        form, snapshot = self.validate_form(identifier, value)
        record = dict(draft_id=uid(), lot_id=identifier, geometry_revision=form.geometry_revision,
                      created_at=now(), form=form.model_dump(), snapshot=snapshot)
        with self.lock:
            write_json(self.directory/'drafts'/f"{record['draft_id']}.json", record)
            self.draft_index.setdefault(identifier, []).append(record)
        return record

    def drafts(self, identifier):
        safe_id(identifier)
        result = self.draft_index.get(identifier, [])
        return sorted([dict(d, stale=self.stale(d)) for d in result if d['lot_id'] == identifier],
                      key=lambda d: d['created_at'], reverse=True)

    def prepare_quick(self, identifier, value):
        form, snapshot = self.validate_form(identifier, value)
        signature = self.fingerprint(form.model_dump())
        with self.lock:
            for r in reversed(list(self.run_index.values())):
                if (r['lot_id'] == identifier and r.get('form_hash') == signature
                    and r['status'] in ('preparing', 'prepared', 'queued', 'running', 'succeeded')
                    and r.get('validation_status') != 'invalid'):
                    return dict(r, reused=True)
            draft = self.save_draft(identifier, value)
            record = self._new_run(draft, signature)
            self.preparations.submit(self._assemble, record['run_id'], draft)
            return record

    def _new_run(self, draft, signature=None):
        run_id = uid()
        directory = self.directory/'runs'/run_id
        directory.mkdir()
        (directory/'evidence').mkdir()
        record = dict(run_id=run_id, lot_id=draft['lot_id'], geometry_revision=draft['geometry_revision'],
                      draft_id=draft['draft_id'], status='preparing', created_at=now(), updated_at=now(),
                      provider=self.provider.name, model=self.provider.model, is_mock=self.provider.is_mock,
                      attempts=0, review_status='pending', validation_status='not_run', form_hash=signature)
        write_json(directory/'record.json', record)
        self.run_index[run_id] = record
        return record

    def prepare(self, identifier, value):
        # Retained for synchronous/manual clients. Interactive UI uses prepare_quick.
        draft = self.save_draft(identifier, value)
        record = self._new_run(draft, self.fingerprint(draft['form']))
        self._assemble(record['run_id'], draft)
        return self.record(record['run_id'])

    def _assemble(self, run_id, draft):
        try:
            self._assemble_package(run_id, draft)
        except Exception as exc:
            with self.lock:
                if self.record(run_id)['status'] != 'cancelled':
                    self.update(run_id, status='failed', error=str(exc))

    def _assemble_package(self, run_id, draft):
        directory = self.path(run_id)
        evidence = []
        geometry = draft['snapshot']['lot']['geometry']
        for number, pid in enumerate(draft['form']['photo_ids']):
            if self.record(run_id)['status'] == 'cancelled':
                return
            camera = self.photos.describe(pid, shape(geometry))
            content = self.photos.base(pid, json.dumps(geometry))
            relative = f'evidence/{number+1:03d}.jpg'
            (directory/relative).write_bytes(content)
            evidence.append(dict(**camera, attachment=relative, sha256=hashlib.sha256(content).hexdigest(),
                                 image_role='clean_projected_image'))
        package = build_package(draft['snapshot'], draft['form'], evidence)
        package['draft_id'] = draft['draft_id']
        package['run_id'] = run_id
        write_json(directory/'package.json', package)
        with self.lock:
            r = self.record(run_id)
            if r['status'] == 'cancelled':
                return
            self.update(run_id, status='prepared', package_sha256=hashlib.sha256((directory/'package.json').read_bytes()).hexdigest())
            if r.get('send_when_ready'):
                self.start(run_id)

    def path(self, run_id):
        path = self.directory/'runs'/safe_id(run_id)
        if not (path/'record.json').exists():
            raise ValueError('Ejecución desconocida')
        return path

    def record(self, run_id):
        return json.loads((self.path(run_id)/'record.json').read_text())

    def update(self, run_id, **values):
        record = self.record(run_id)
        record.update(**values, updated_at=now())
        write_json(self.path(run_id)/'record.json', record)
        self.run_index[run_id] = record
        return record

    def runs(self, identifier):
        result = list(self.run_index.values())
        return sorted([dict(r, stale=self.stale(r)) for r in result if r['lot_id'] == identifier],
                      key=lambda r: r['created_at'], reverse=True)

    def detail(self, run_id):
        with self.lock:
            record = self.record(run_id)
            result = dict(record, stale=self.stale(record))
            for name in ('package', 'proposal', 'request', 'validation'):
                path = self.path(run_id)/f'{name}.json'
                result[name] = json.loads(path.read_text()) if path.exists() else None
            raw = self.path(run_id)/'response.txt'
            result['raw_response'] = raw.read_text() if raw.exists() else None
            return result

    def start(self, run_id):
        with self.lock:
            r = self.record(run_id)
            if r['status'] == 'preparing':
                return self.update(run_id, send_when_ready=True)
            if r['status'] in ('queued', 'running', 'succeeded'):
                return r
            if r['status'] != 'prepared':
                raise Conflict('Solo una ejecución preparada puede enviarse; prepara otra versión para reintentar.')
            if self.stale(r):
                raise Conflict('Lote desactualizado; prepara una nueva versión.')
            result = self.update(run_id, status='queued')
            self.executor.submit(self._work, run_id)
            return result

    def _finish(self, run_id, raw):
        directory = self.path(run_id)
        (directory/'response.txt').write_text(raw)
        package = json.loads((directory/'package.json').read_text())
        try:
            proposal, request, validation = compile_response(raw, package)
        except (ValueError, TypeError) as exc:
            proposal, request = None, None
            validation = dict(status='invalid', errors=[str(exc)])
        for name, value in [('proposal', proposal), ('request', request), ('validation', validation)]:
            write_json(directory/f'{name}.json', value)
        return self.update(run_id, status='succeeded', validation_status=validation['status'])

    def _work(self, run_id):
        with self.lock:
            if self.record(run_id)['status'] != 'queued':
                return
            self.update(run_id, status='running', attempts=1)
        try:
            package = json.loads((self.path(run_id)/'package.json').read_text())
            raw = self.provider.generate(deepcopy(package))
            if not isinstance(raw, str):
                raise ValueError('El proveedor debe devolver texto original')
            with self.lock:
                self._finish(run_id, raw)
        except Exception as exc:
            with self.lock:
                self.update(run_id, status='failed', error=str(exc))

    def cancel(self, run_id):
        with self.lock:
            if self.record(run_id)['status'] not in ('preparing', 'prepared', 'queued'):
                raise Conflict('Solo se pueden cancelar trabajos pendientes; una llamada en ejecución continúa.')
            return self.update(run_id, status='cancelled')

    def import_response(self, run_id, raw):
        # Never overwrite a prior response: manual edits/imports get their own run.
        with self.lock:
            source = self.record(run_id)
            if source['status'] == 'preparing':
                raise Conflict('Espera a que termine la preparación antes de importar una respuesta')
            new_id = uid()
            import shutil
            destination = self.directory/'runs'/new_id
            destination.mkdir()
            shutil.copy2(self.path(run_id)/'package.json', destination/'package.json')
            shutil.copytree(self.path(run_id)/'evidence', destination/'evidence')
            record = dict(source, run_id=new_id, parent_run_id=run_id, provider='manual-import',
                          model='user-supplied', is_mock=source['is_mock'], status='prepared',
                          attempts=0, review_status='pending', validation_status='not_run',
                          created_at=now(), updated_at=now())
            record.pop('error', None)
            write_json(destination/'record.json', record)
            self.run_index[new_id] = record
            return self._finish(new_id, raw)

    def select(self, run_id):
        with self.lock:
            r = self.record(run_id)
            if r['status'] != 'succeeded' or r['validation_status'] != 'valid' or self.stale(r):
                raise Conflict('La versión vigente debe estar validada y actualizada.')
            selection = dict(lot_id=r['lot_id'], run_id=run_id, selected_at=now(),
                             review_status='human_selected', is_mock=r['is_mock'])
            write_json(self.directory/'selections'/f"{safe_id(r['lot_id'])}.json", selection)
            return selection

    def selection(self, identifier):
        path = self.directory/'selections'/f'{safe_id(identifier)}.json'
        return json.loads(path.read_text()) if path.exists() else None

    def progress(self):
        lots = self.state()['lots']
        result = {}
        with self.lock:
            for r in sorted(self.run_index.values(), key=lambda r:r['created_at']):
                lot = lots.get(r['lot_id'])
                if not lot or lot['status'] != 'active' or lot['geometry_revision'] != r['geometry_revision']:
                    continue
                if r['status'] == 'succeeded' and r['validation_status'] == 'valid':
                    stage = 'generated'
                elif r['status'] in ('prepared', 'queued', 'running'):
                    stage = 'prepared'
                elif r['status'] == 'preparing':
                    stage = 'preparing'
                else:
                    continue
                result[r['lot_id']] = dict(stage=stage, run_id=r['run_id'], form_hash=r.get('form_hash'))
            for identifier, value in result.items():
                form = self.latest_form(identifier)
                value['changed'] = bool(form and value['form_hash'] != self.fingerprint(form))
        return result
