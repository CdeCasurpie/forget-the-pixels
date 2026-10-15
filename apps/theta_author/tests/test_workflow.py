import io
import json
import hashlib
from pathlib import Path
import subprocess
import sys
import threading
import time
import zipfile

from fastapi.testclient import TestClient
import pytest
from shapely.geometry import box

from packages.barranco_data.store import Store
from apps.theta_author.providers import MockProvider
from apps.theta_author.server import create_app
from apps.theta_author.service import Author


@pytest.fixture
def setup(tmp_path):
    store = Store(tmp_path/'editor')
    state = store.initialize([('one', box(280000, 8656000, 280020, 8656020)),
                              ('two', box(280030, 8656000, 280050, 8656020))], {})
    state = store.commit(store.prepare(dict(type='edit_fronts', revision=state['revision'], ids=['one'],
                                           fronts={f['id']:True for f in state['lots']['one']['fronts']})))
    form = dict(geometry_revision=state['revision'], height=dict(value=12, mode='fixed'),
                floors=dict(value=3, mode='fixed'), style=dict(value='republicano', mode='fixed'),
                photo_ids=[], notes='Sin imágenes en fixture sintético')
    app = create_app(tmp_path, tmp_path/'author', tmp_path/'editor')
    with TestClient(app) as client:
        yield client, app.state.author, store, form


def complete(client, run_id):
    assert client.post(f'/api/runs/{run_id}/start').status_code == 200
    for _ in range(100):
        result = client.get(f'/api/runs/{run_id}').json()
        if result['status'] not in ('queued', 'running'):
            return result
        time.sleep(.01)
    pytest.fail('job did not finish')


def test_round_trip_versions_export_and_real_contract(setup):
    client, author, store, form = setup
    prepared = client.post('/api/lots/one/prepare', json=form)
    assert prepared.status_code == 200, prepared.text
    run_id = prepared.json()['run_id']
    result = complete(client, run_id)
    assert result['status'] == 'succeeded'
    assert result['validation_status'] == 'valid'
    assert result['proposal']['height_m'] == 12
    assert result['request']['theta']['masses'][0]['levels_m'] == [0, 4, 8, 12]
    assert result['is_mock'] and result['package']['prompt_status'] == 'provisional'
    assert client.post(f'/api/runs/{run_id}/start').json()['attempts'] == 1
    assert client.post(f'/api/runs/{run_id}/select').status_code == 200
    assert client.get('/api/lots/one').json()['selection']['run_id'] == run_id
    imported = client.post(f'/api/runs/{run_id}/import', json={'raw_response':result['raw_response']}).json()
    assert imported['run_id'] != run_id
    assert len(client.get('/api/lots/one').json()['runs']) == 2
    assert not client.get('/api/lots/two').json()['runs']
    export = client.get(f'/api/runs/{run_id}/export')
    with zipfile.ZipFile(io.BytesIO(export.content)) as archive:
        assert {'package.json','record.json','request.json','response.txt','validation.json'} <= set(archive.namelist())
    # Actual strict grammar decoder, in an isolated process (no sys.path pollution).
    root = Path(__file__).resolve().parents[3]/'house_grammar/src'
    code = 'import sys,json;sys.path.insert(0,sys.argv[1]);from domain.theta import decode,ReconstructionRequest;decode(ReconstructionRequest,json.load(sys.stdin))'
    decoded = subprocess.run([sys.executable, '-c', code, str(root)], input=json.dumps(result['request']), text=True, capture_output=True)
    assert decoded.returncode == 0, decoded.stderr


def test_invalid_fixed_fields_fronts_raw_and_staleness(setup):
    client, author, store, form = setup
    run_id = client.post('/api/lots/one/prepare', json=form).json()['run_id']
    result = complete(client, run_id)
    proposal = result['proposal']
    proposal['height_m'] = 20
    imported = client.post(f'/api/runs/{run_id}/import', json={'raw_response':json.dumps(proposal)}).json()
    bad = client.get('/api/runs/'+imported['run_id']).json()
    assert bad['validation_status'] == 'invalid'
    assert 'height_m' in bad['validation']['errors'][0]
    assert client.post('/api/runs/'+bad['run_id']+'/select').status_code == 409
    proposal['height_m'] = 12
    proposal['massing']['cuts'] = [dict(kind='setback', front_id='inventado', depth_m=2)]
    bad_id = client.post(f'/api/runs/{run_id}/import', json={'raw_response':json.dumps(proposal)}).json()['run_id']
    assert any('front_id' in e for e in client.get('/api/runs/'+bad_id).json()['validation']['errors'])
    malformed = client.post(f'/api/runs/{run_id}/import', json={'raw_response':'not json'}).json()
    assert malformed['validation_status'] == 'invalid'
    assert client.get('/api/runs/'+malformed['run_id']).json()['raw_response'] == 'not json'
    state = store.load()
    store.commit(store.prepare(dict(type='edit_fronts', revision=state['revision'], ids=['one'],
                                   fronts={state['lots']['one']['fronts'][0]['id']:False})))
    assert client.get(f'/api/runs/{run_id}').json()['stale']
    assert client.post(f'/api/runs/{run_id}/select').status_code == 409
    assert client.post('/api/lots/one/drafts', json=form).status_code == 409


def test_drafts_reload_cuts_and_bad_inputs(setup):
    client, author, store, form = setup
    front = store.load()['lots']['one']['fronts'][0]['id']
    form['massing'] = dict(corner=True, delegate_complex=False, cuts=[dict(kind='bite',front_id=front,depth_m=2,width_m=3,end='start')])
    response = client.post('/api/lots/one/drafts', json=form)
    assert response.status_code == 200, response.text
    saved = response.json()
    assert client.get('/api/lots/one').json()['drafts'][0]['form'] == saved['form']
    run = client.post('/api/lots/one/prepare', json=form).json()
    result = complete(client, run['run_id'])
    assert result['validation_status'] == 'valid'
    from shapely.geometry import Polygon
    assert Polygon(result['request']['theta']['masses'][0]['footprint']).area == pytest.approx(394)
    assert client.post('/api/lots/one/drafts', json={**form, 'floors':{'value':2.5,'mode':'fixed'}}).status_code == 422
    assert client.post('/api/lots/one/drafts', json={**form, 'photo_ids':['missing']}).status_code == 422
    assert client.post('/api/lots/one/drafts', json={**form, 'unexpected':1}).status_code == 422
    author.close()
    restored = Author(author.directory, store, author.photos)
    try:
        assert restored.drafts('one')[0]['form'] == saved['form']
        assert restored.detail(run['run_id'])['request'] == result['request']
    finally:
        restored.close()


def test_cancel_failure_and_restart(setup):
    client, author, store, form = setup
    run_id = client.post('/api/lots/one/prepare', json=form).json()['run_id']
    assert client.post(f'/api/runs/{run_id}/cancel').json()['status'] == 'cancelled'
    assert client.post(f'/api/runs/{run_id}/start').status_code == 409

    class Broken(MockProvider):
        def generate(self, package):
            raise RuntimeError('simulated provider failure')

    author.provider = Broken()
    failed_id = client.post('/api/lots/one/prepare', json=form).json()['run_id']
    result = complete(client, failed_id)
    assert result['status'] == 'failed' and result['attempts'] == 1
    assert 'simulated' in result['error']
    author.close()
    author.update(failed_id, status='running')
    restored = Author(author.directory, store, author.photos)
    try:
        assert restored.record(failed_id)['status'] == 'interrupted'
        assert restored.record(run_id)['status'] == 'cancelled'
    finally:
        restored.close()


def test_frozen_evidence_and_exclusive_workspace(setup, monkeypatch):
    client, author, store, form = setup
    camera = dict(id='test-photo', pose={'heading_deg':0}, projection={'version':'test'}, image_path='source.jpg')
    monkeypatch.setattr(author.photos, 'describe', lambda pid, polygon: camera)
    monkeypatch.setattr(author.photos, 'base', lambda pid, geometry: b'frozen-image-bytes')
    form['photo_ids'] = ['test-photo']
    r = client.post('/api/lots/one/prepare', json=form).json()
    package = client.get('/api/runs/'+r['run_id']).json()['package']
    evidence = package['evidence'][0]
    assert evidence['sha256'] == hashlib.sha256(b'frozen-image-bytes').hexdigest()
    monkeypatch.setattr(author.photos, 'base', lambda pid, geometry: b'changed-source')
    with zipfile.ZipFile(io.BytesIO(client.get('/api/runs/'+r['run_id']+'/export').content)) as archive:
        assert archive.read(evidence['attachment']) == b'frozen-image-bytes'
    with pytest.raises(ValueError, match='Ya hay'):
        Author(author.directory, store, author.photos)


def test_running_cannot_cancel_queued_can(setup):
    client, author, store, form = setup
    from concurrent.futures import ThreadPoolExecutor
    author.executor.shutdown()
    author.executor = ThreadPoolExecutor(max_workers=1)
    entered, release = threading.Event(), threading.Event()

    class Delayed(MockProvider):
        def generate(self, package):
            entered.set()
            assert release.wait(5)
            return super().generate(package)

    author.provider = Delayed()
    first = client.post('/api/lots/one/prepare', json=form).json()['run_id']
    second = client.post('/api/lots/one/prepare', json=form).json()['run_id']
    try:
        client.post(f'/api/runs/{first}/start')
        assert entered.wait(3)
        assert client.post(f'/api/runs/{first}/cancel').status_code == 409
        client.post(f'/api/runs/{second}/start')
        assert client.post(f'/api/runs/{second}/cancel').json()['status'] == 'cancelled'
    finally:
        release.set()
        author.executor.shutdown()
    assert author.record(first)['status'] == 'succeeded'
    assert author.record(second)['attempts'] == 0


def test_quick_prepare_is_nonblocking_deduplicated_and_send_once(setup, monkeypatch):
    client, author, store, form = setup
    entered, release = threading.Event(), threading.Event()
    calls = []

    def base(pid, geometry):
        entered.set()
        assert release.wait(5)
        return b'frozen'

    class Counted(MockProvider):
        def generate(self, package):
            calls.append(package['run_id'])
            return super().generate(package)

    author.provider = Counted()
    monkeypatch.setattr(author.photos, 'describe', lambda pid, polygon: {'id':pid})
    monkeypatch.setattr(author.photos, 'base', base)
    form['photo_ids'] = ['photo']
    try:
        response = client.post('/api/lots/one/prepare-quick', json=form)
        assert response.status_code == 200, response.text
        run_id = response.json()['run_id']
        assert entered.wait(2)
        # Request has returned although the projection is deliberately still blocked.
        assert client.get('/api/runs/'+run_id+'/status').json()['status'] == 'preparing'
        duplicate = client.post('/api/lots/one/prepare-quick', json=form).json()
        assert duplicate['run_id'] == run_id and duplicate['reused']
        assert len(author.drafts('one')) == 1
        assert client.post('/api/runs/'+run_id+'/start').json()['send_when_ready']
        assert client.post('/api/runs/'+run_id+'/start').json()['send_when_ready']
    finally:
        release.set()
        author.preparations.shutdown()
        author.executor.shutdown()
    assert author.record(run_id)['status'] == 'succeeded'
    assert calls == [run_id]
    assert client.post('/api/runs/'+run_id+'/start').json()['attempts'] == 1
    assert client.get('/api/progress').json()['one']['stage'] == 'generated'


def test_floor_sliders_autosave_and_progress_revision(setup):
    client, author, store, form = setup
    form.update(height={'mode':'suggested','value':10.9}, floors={'mode':'suggested','value':3},
                style={'mode':'suggested','value':'madera'}, floor_height_m=3.2,
                first_floor_different=True, first_floor_height_m=4.5, massing_mode='suggested')
    saved = client.post('/api/lots/one/autosave', json=form)
    assert saved.status_code == 200, saved.text
    assert author.drafts('one') == []  # slider input does not create immutable versions
    assert client.get('/api/lots/one/editor').json()['form']['first_floor_height_m'] == 4.5
    prepared = client.post('/api/lots/one/prepare', json=form).json()
    assert client.get('/api/progress').json()['one']['stage'] == 'prepared'
    result = complete(client, prepared['run_id'])
    assert result['request']['theta']['masses'][0]['levels_m'] == [0, 4.5, 7.7, 10.9]
    assert not client.get('/api/progress').json()['one']['changed']
    form['notes'] = 'cambio posterior'
    client.post('/api/lots/one/autosave', json=form)
    assert client.get('/api/progress').json()['one']['changed']
    assert client.post('/api/lots/one/autosave', json={**form,'height':{'mode':'suggested','value':99}}).status_code == 422
    state = store.load()
    store.commit(store.prepare(dict(type='edit_fronts', revision=state['revision'], ids=['one'],
                                   fronts={state['lots']['one']['fronts'][0]['id']:False})))
    assert 'one' not in client.get('/api/progress').json()
    assert client.post('/api/lots/one/autosave', json=form).status_code == 409


def test_translate_block_preserves_work_but_freezes_new_position(setup):
    client, author, store, form = setup
    state = store.load()
    store.commit(store.prepare(dict(type='assign_block', revision=state['revision'],
                                    ids=['one', 'two'], block_id='B1')))
    current = store.load()
    form['geometry_revision'] = current['lots']['one']['geometry_revision']
    run_id = client.post('/api/lots/one/prepare', json=form).json()['run_id']
    assert not client.get(f'/api/runs/{run_id}').json()['stale']
    # Mover la manzana entera no debe invalidar el trabajo de B.
    assert client.post('/api/lots/one/autosave', json=form).status_code == 200
    before = store.load()['lots']['one']['geometry']
    store.commit(store.prepare(dict(type='translate_block', revision=store.load()['revision'],
                                    block_id='B1', dx=5, dy=0)))
    assert store.load()['lots']['one']['geometry'] != before
    assert not client.get(f'/api/runs/{run_id}').json()['stale']
    assert 'one' in client.get('/api/progress').json()
    assert client.post('/api/lots/one/autosave', json=form).status_code == 200
    # Misma forma con nueva posición: nuevo paquete, sin reutilizar el antiguo origen.
    second = client.post('/api/lots/one/prepare', json=form).json()
    assert second['run_id'] != run_id


def test_keyboard_shortcuts_are_consistent():
    static = Path(__file__).resolve().parents[1]/'static'
    dump = subprocess.run(['node', '-e',
        "const m=require(process.argv[1]);console.log(JSON.stringify({keys:m.STYLE_KEYS,groups:m.SHORTCUT_GROUPS}))",
        str(static/'shortcuts.js')], capture_output=True, text=True)
    assert dump.returncode == 0, dump.stderr
    data = json.loads(dump.stdout)
    assert sorted(data['keys'].values()) == ['barroco', 'clasico', 'madera', 'moderno', 'republicano']
    documented = [item['key'].lower() for group in data['groups'] for item in group['items']]
    singles = [k for k in documented if len(k) == 1 and k not in '/?']
    assert len(set(singles)) == len(singles), 'teclas duplicadas en el mapa'
    app = (static/'app.js').read_text()
    assert 'STYLE_KEYS[k]' in app, 'app.js debe resolver estilos vía STYLE_KEYS'
    for k in singles:
        if k in data['keys']:
            continue  # estilo: se resuelve vía STYLE_KEYS, ya validado arriba
        assert f"'{k}'" in app or f'{k}:' in app, f'la tecla {k} está documentada pero no manejada'
    html = (static/'index.html').read_text()
    assert '/static/shortcuts.js' in html
    for element in ['floorsNumber', 'floorHeightNumber', 'firstHeightNumber', 'keysDialog', 'nextUnevaluated']:
        assert element in html, f'falta {element} en la UI'
