import json

import pytest
from fastapi.testclient import TestClient
from shapely.geometry import box, shape

from apps.cadastral_editor.server import create_app
from packages.barranco_data.store import Store, Conflict


@pytest.fixture
def store(tmp_path):
    result = Store(tmp_path/'editor')
    result.initialize([('a', box(0, 0, 10, 10)), ('b', box(10, 0, 20, 10)),
                       ('c', box(40, 0, 50, 10))], {'type': 'test'})
    return result


def execute(store, **command):
    prepared = store.prepare(dict(revision=store.load()['revision'], **command))
    return store.commit(prepared)


def test_split_merge_lineage_and_undo(store):
    state = execute(store, type='split', ids=['a'], line=[[5, -1], [5, 11]])
    children = state['operation']['result_ids']
    assert sum(shape(state['lots'][i]['geometry']).area for i in children) == pytest.approx(100)
    assert state['lots']['a']['status'] == 'superseded'
    right = max(children, key=lambda i: shape(state['lots'][i]['geometry']).centroid.x)
    merged = execute(store, type='merge', ids=[right, 'b'])
    new = merged['operation']['result_ids'][0]
    assert merged['lots'][new]['source_lot_ids'] == ['a', 'b']
    assert set(merged['lots'][new]['parent_lot_ids']) == {right, 'b'}
    restored = execute(store, type='undo')
    assert restored['lots'][new]['status'] == 'superseded'
    assert restored['lots']['b']['status'] == 'active'
    assert Store(store.directory).load() == restored


def test_invalid_edits_do_not_publish(store):
    revision = store.load()['revision']
    for operation in [dict(type='split', ids=['a'], line=[[-1, -1], [-1, 11]]),
                      dict(type='split', ids=['a'], line=[[.1, -1], [.1, 11]]),
                      dict(type='merge', ids=['a', 'c'])]:
        with pytest.raises(ValueError):
            execute(store, **operation)
        assert store.load()['revision'] == revision


def test_block_movement_and_fronts(store):
    state = execute(store, type='assign_block', ids=['a', 'b'], block_id='block')
    for identifier in ('a', 'b'):
        lot = state['lots'][identifier]
        assert sum(shape(f['geometry']).length for f in lot['fronts'] if f['is_front']) == pytest.approx(30)
    c = state['lots']['c']
    moved = execute(store, type='translate_block', block_id='block', dx=2, dy=3)
    assert moved['lots']['c'] == c
    assert shape(moved['lots']['a']['geometry']).bounds == (2, 3, 12, 13)
    assert shape(Store(store.directory).load()['lots']['a']['geometry']).bounds == (2, 3, 12, 13)
    with pytest.raises(ValueError, match='solapamiento'):
        execute(store, type='translate_block', block_id='block', dx=30, dy=-3)


def test_conflicts_and_orphan_revision(store):
    revision = store.load()['revision']
    command = dict(type='assign_block', ids=['a'], revision=revision)
    prepared = store.prepare(command)
    execute(store, type='assign_block', ids=['b'])
    with pytest.raises(Conflict):
        store.commit(prepared)
    with pytest.raises(Conflict):
        store.prepare(command)
    # An unpublished snapshot never changes the pointer visible to readers.
    pointer = store.load()['revision']
    (store.directory/'revisions'/('f'*32+'.json')).write_text('{}')
    assert Store(store.directory).load()['revision'] == pointer


def test_consecutive_undo_and_manual_restoration(store):
    first = execute(store, type='assign_block', ids=['a'], block_id='one')
    front = first['lots']['a']['fronts'][0]['id']
    execute(store, type='edit_fronts', ids=['a'], fronts={front: False})
    execute(store, type='translate_block', block_id='one', dx=0, dy=2)
    undone_move = execute(store, type='undo')
    assert not undone_move['lots']['a']['fronts'][0]['is_front']
    assert shape(undone_move['lots']['a']['geometry']).bounds == (0, 0, 10, 10)
    undone_front = execute(store, type='undo')
    assert undone_front['lots']['a']['fronts'][0]['is_front']
    undone_block = execute(store, type='undo')
    assert undone_block['lots']['a']['block_id'] is None
    with pytest.raises(ValueError, match='anterior'):
        execute(store, type='undo')


def test_partial_front_and_manual_override(tmp_path):
    store = Store(tmp_path)
    store.initialize([('a', box(0, 0, 10, 10)), ('b', box(10, 0, 20, 5))], {})
    state = execute(store, type='assign_block', ids=['a', 'b'], block_id='x')
    fs = state['lots']['a']['fronts']
    assert sum(shape(f['geometry']).length for f in fs if f['is_front']) == pytest.approx(35)
    front = next(f for f in fs if f['is_front'])
    edited = execute(store, type='edit_fronts', ids=['a'], fronts={front['id']: False})
    assert next(f for f in edited['lots']['a']['fronts'] if f['id'] == front['id'])['origin'] == 'manual'


def test_reassignment_invalidates_previous_block_members(store):
    initial = execute(store, type='assign_block', ids=['a', 'b'], block_id='first')
    revision = initial['lots']['b']['geometry_revision']
    changed = execute(store, type='assign_block', ids=['a'], block_id='second')
    assert changed['lots']['b']['geometry_revision'] != revision
    assert all(f['is_front'] for f in changed['lots']['b']['fronts'])


def test_interrupted_publication_keeps_previous_pointer(store, monkeypatch):
    from packages.barranco_data import store as module
    before = store.load()['revision']
    prepared = store.prepare(dict(type='assign_block', ids=['a'], revision=before))
    original = module.write_json
    def interrupted(path, value):
        if path.name == 'current.json':
            raise OSError('simulated interruption')
        return original(path, value)
    monkeypatch.setattr(module, 'write_json', interrupted)
    with pytest.raises(OSError):
        store.commit(prepared)
    assert store.load()['revision'] == before


def test_api_preview_commit_export_and_stale(tmp_path):
    app = create_app(data=tmp_path/'data', workspace=tmp_path/'work', demo=True)
    client = TestClient(app)
    assert client.get('/').status_code == 200
    state = client.get('/api/state').json()
    before = client.get('/api/lots/demo-a/snapshot').json()
    response = client.post('/api/preview', json=dict(type='assign_block', ids=['demo-a', 'demo-b'],
        block_id='test', revision=state['revision']))
    assert response.status_code == 200, response.text
    assert client.get('/api/state').json()['revision'] == state['revision']
    result = client.post('/api/commit', json={'token': response.json()['token']})
    assert result.status_code == 200
    assert client.get('/api/freshness/demo-a/'+before['lot']['geometry_revision']).json()['stale']
    assert client.post('/api/commit', json={'token': response.json()['token']}).status_code == 422
    assert client.post('/api/preview', json=dict(type='assign_block', ids=['demo-c'], revision=state['revision'])).status_code == 409
    assert client.get('/api/lots/demo-a').json()['photos'] == []
    assert len(client.get('/api/history').json()) == 2


def test_drag_uses_metric_transform(tmp_path):
    from pyproj import Transformer
    client = TestClient(create_app(data=tmp_path/'data', workspace=tmp_path/'work', demo=True))
    revision = client.get('/api/state').json()['revision']
    preview = client.post('/api/preview', json=dict(type='assign_block', ids=['demo-a', 'demo-b'],
        block_id='block', revision=revision)).json()
    revision = client.post('/api/commit', json={'token': preview['token']}).json()['revision']
    transform = Transformer.from_crs(32718, 4326, always_xy=True)
    start = transform.transform(279950, 8656480)
    end = transform.transform(279950.37, 8656480.81)
    response = client.post('/api/preview', json=dict(type='translate_block', block_id='block',
        revision=revision, drag_lonlat=[start, end]))
    assert response.status_code == 200, response.text
    assert response.json()['parameters']['dx'] == pytest.approx(.37, abs=1e-6)
    assert response.json()['parameters']['dy'] == pytest.approx(.81, abs=1e-6)


def test_import_offset_only_once(tmp_path):
    import geopandas as gpd
    data, workspace = tmp_path/'data', tmp_path/'workspace'
    (data/'lotes').mkdir(parents=True)
    frame = gpd.GeoDataFrame({'objectid': [123]}, geometry=[box(279950, 8656480, 279960, 8656490)], crs=32718)
    frame.to_crs(4326).to_file(data/'lotes/BARRANCO_LM_geogpsperu.geojson', driver='GeoJSON')
    (data/'cadastral_offset.json').write_text(json.dumps({'crs': 'EPSG:32718', 'east_m': 3, 'north_m': -2}))
    first = create_app(data=data, workspace=workspace).state.store.load()
    assert shape(first['lots']['123']['geometry']).bounds == pytest.approx((279953, 8656478, 279963, 8656488))
    second = create_app(data=data, workspace=workspace).state.store.load()
    assert first == second
    assert first['source']['applied_offset_m'] == [3, -2]
    assert len(first['source']['sha256']) == 64


def test_auto_blocks_connected_chain_singleton_and_fronts(tmp_path):
    store = Store(tmp_path/'store')
    store.initialize([('a',box(0,0,10,10)), ('b',box(10,0,20,10)),
        ('c',box(20,0,30,10)), ('isolated',box(50,0,60,10))], {})
    original = {i:l['geometry'] for i,l in store.load()['lots'].items()}
    state = execute(store, type='auto_blocks')
    assert len(state['blocks']) == 2
    assert {state['lots'][i]['block_id'] for i in ('a','b','c')} == {'M-a'}
    assert state['lots']['isolated']['block_id'] != 'M-a'
    assert state['lots']['b']['fronts_review'] is False
    assert sum(shape(f['geometry']).length for f in state['lots']['b']['fronts'] if f['is_front']) == pytest.approx(20)
    assert original == {i:l['geometry'] for i,l in state['lots'].items()}
    assert shape(state['blocks']['M-a']['geometry']).area == 300


def test_auto_blocks_preserves_manual_groups(store):
    execute(store, type='assign_block', ids=['a'], block_id='human')
    state = execute(store, type='auto_blocks')
    assert state['lots']['a']['block_id'] == state['lots']['b']['block_id'] == 'human'
    assert state['lots']['a']['block_assignment'] == 'manual'
    assert state['lots']['c']['block_id'] != 'human'


def test_shapefile_preferred_and_auto_assignment_survives_restart(tmp_path):
    import geopandas as gpd
    data, workspace = tmp_path/'data', tmp_path/'workspace'
    (data/'lotes').mkdir(parents=True)
    frame = gpd.GeoDataFrame({'objectid': [10,20]}, geometry=[box(279950,8656480,279960,8656490),
        box(279960,8656480,279970,8656490)],crs=32718)
    frame.to_file(data/'lotes/BARRANCO_LM_geogpsperu_SuyoPomalia.shp')
    # A conflicting secondary file must not replace the shapefile.
    frame.iloc[:1].to_crs(4326).to_file(data/'lotes/BARRANCO_LM_geogpsperu.geojson',driver='GeoJSON')
    (data/'cadastral_offset.json').write_text(json.dumps({'crs':'EPSG:32718','east_m':4.9543,'north_m':-.1309}))
    first = create_app(data=data,workspace=workspace).state.store.load()
    assert len(first['lots']) == 2 and len(first['blocks']) == 1
    assert first['source']['path'].endswith('.shp')
    assert any(p.endswith('.dbf') for p in first['source']['companion_hashes'])
    assert shape(first['lots']['10']['geometry']).bounds[0] == pytest.approx(279954.9543)
    assert create_app(data=data,workspace=workspace).state.store.load() == first


def test_point_contact_and_gap_are_not_confused(tmp_path):
    store=Store(tmp_path/'store')
    store.initialize([('a',box(0,0,10,10)),('b',box(10,10,20,20)),('c',box(20.1,10,30,20))],{})
    state=execute(store,type='auto_blocks')
    assert state['lots']['a']['block_id']==state['lots']['b']['block_id']
    assert state['lots']['c']['block_id']!=state['lots']['b']['block_id']
