import importlib.util
import json
from pathlib import Path

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient
from shapely.geometry import box, mapping

from apps.cadastral_editor.photos import Photos
from apps.cadastral_editor.server import create_app, REPOSITORY
from packages.barranco_imaging.angular import camera_to_enu, view_spec, project_points


def fixture_photos(tmp_path):
    (tmp_path/'poses_barranco').mkdir()
    (tmp_path/'fotos_barranco').mkdir()
    m=dict(lon=-77.020,lat=-12.144,heading_deg=12,pitch_deg=-3,roll_deg=1,date='2026-01')
    (tmp_path/'poses_barranco/metadata.json').write_text(json.dumps({'panoramas':{'camera':m}}))
    im=np.zeros((256,512,3),dtype=np.uint8)
    im[:,:,0]=np.arange(512)[None,:]%256
    im[:,:,1]=np.arange(256)[:,None]
    assert cv2.imwrite(str(tmp_path/'fotos_barranco/camera.jpg'),im)
    return Photos(tmp_path,REPOSITORY)


def test_camera_convention_and_known_projected_points():
    path=REPOSITORY/'house_grammar/steps/step20_sfm_esferico/geometry_stage4.py'
    spec=importlib.util.spec_from_file_location('camera_reference',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    for angles in [(0,0,0),(90,10,-5),(233,-17,4)]:
        np.testing.assert_allclose(camera_to_enu(*angles),module.camera_to_enu(*angles),atol=1e-12)
    view=view_spec(box(-5,10,5,20),[0,0])
    # North-facing camera, a point on the optical horizon maps to the horizontal centre.
    p=project_points([[0,15,2.5]],view)[0]
    assert p[0]==pytest.approx(480)
    assert p[1]==pytest.approx(640*85/120)
    higher=project_points([[0,15,10]],view)[0]
    assert higher[1]<p[1]


def test_height_changes_reuse_base_image_and_geometry_invalidates(tmp_path,monkeypatch):
    photos=fixture_photos(tmp_path)
    camera=photos.positions['camera']
    polygon=box(camera[0]-4,camera[1]+10,camera[0]+4,camera[1]+20)
    geometry=json.dumps(mapping(polygon))
    calls=[]
    original=cv2.imread
    def read(*args,**kwargs):
        calls.append(args[0]);return original(*args,**kwargs)
    monkeypatch.setattr(cv2,'imread',read)
    clean=photos.base('camera',geometry)
    assert photos.base('camera',geometry)==clean
    low=photos.render('camera',geometry,5)
    high=photos.render('camera',geometry,12)
    assert low!=high
    assert len(calls)==1
    changed=json.dumps(mapping(box(camera[0]-3,camera[1]+10,camera[0]+5,camera[1]+20)))
    photos.base('camera',changed)
    assert len(calls)==2
    record=photos.describe('camera',polygon)
    assert record['camera_lonlat']==[-77.020,-12.144]
    assert record['projection']['camera_xy']==camera.tolist()


def test_shared_view_settings_export_and_revision_guard(tmp_path):
    data=tmp_path/'data';data.mkdir();fixture_photos(data)
    client=TestClient(create_app(data=data,workspace=tmp_path/'work',demo=True))
    lot=client.get('/api/lots/demo-a').json()
    body=dict(geometry_revision=lot['geometry_revision'],photo_ids=['camera'],reference_height_m=7.5)
    response=client.post('/api/lots/demo-a/view-settings',json=body)
    assert response.status_code==200,response.text
    exported=client.get('/api/lots/demo-a/snapshot').json()
    assert exported['view_settings']['height_role']=='cadastral_preview_only'
    assert exported['cameras'][0]['id']=='camera'
    assert exported['cameras'][0]['projection']['version']=='angular-enu-v1'
    assert not exported['view_settings_stale']
    camera=client.get('/api/cameras/camera',params={'lot_id':'demo-a','revision':lot['revision']})
    assert camera.status_code==200
    for height in (5,10):
        image=client.get('/api/photos/camera',params=dict(lot_id='demo-a',revision=lot['revision'],clean=True,height=height))
        assert image.status_code==200
        if height==5: first=image.content
        else: assert image.content==first
    preview=client.post('/api/preview',json=dict(type='assign_block',ids=['demo-a'],revision=lot['revision'])).json()
    client.post('/api/commit',json={'token':preview['token']}).raise_for_status()
    assert client.get('/api/lots/demo-a/snapshot').json()['view_settings_stale']
    assert client.post('/api/lots/demo-a/view-settings',json=body).status_code==409
