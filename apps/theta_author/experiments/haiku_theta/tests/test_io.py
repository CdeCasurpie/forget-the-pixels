import asyncio
import hashlib
import json
from pathlib import Path

import httpx
import pytest

from apps.theta_author.experiments.haiku_theta import case, client
from apps.theta_author.experiments.haiku_theta.cli import accept, branch
from apps.theta_author.experiments.haiku_theta.workflow import next_stage
from .test_workflow import package, reply


def test_http_transport_uses_messages_contract_without_logging_key(monkeypatch):
    monkeypatch.setenv('ANTHROPIC_BASE_URL','https://example.invalid/anthropic/')
    monkeypatch.setenv('ANTHROPIC_API_KEY','test-secret')
    received=[]

    def handler(request):
        assert str(request.url)=='https://example.invalid/anthropic/v1/messages'
        assert request.headers['x-api-key']=='test-secret'
        assert request.headers['anthropic-version']=='2023-06-01'
        received.append(json.loads(request.content))
        return httpx.Response(200,json=dict(id='r',model='claude-haiku-4-5',stop_reason='end_turn',
            usage=dict(input_tokens=3,output_tokens=2),content=[dict(type='text',text='{}')]))

    real_client=httpx.AsyncClient
    monkeypatch.setattr(client.httpx,'AsyncClient',lambda **kw:real_client(transport=httpx.MockTransport(handler),**kw))
    body=dict(model='claude-haiku-4-5',max_tokens=8192,messages=[dict(role='user',content='prueba')])
    data,metrics=asyncio.run(client.request(body))
    assert received==[body]
    assert metrics['usage']['input_tokens']==3
    assert 'test-secret' not in json.dumps([data,metrics])


def test_prepare_freezes_input_and_rejects_stale_geometry(package,tmp_path,monkeypatch):
    monkeypatch.setattr(case,'prepare_images',lambda *args:None)
    package['snapshot']['lot'].update(lot_id='lot',geometry_revision='g1')
    package['human_parameters']['geometry_revision']='g1'
    source=tmp_path/'theta_author/runs/run';source.mkdir(parents=True)
    image=source/'photo.jpg';image.write_bytes(b'frozen image bytes')
    package['evidence']=[dict(id='view',attachment='photo.jpg',sha256=hashlib.sha256(image.read_bytes()).hexdigest())]
    case.write_json(source/'package.json',package)
    editor=tmp_path/'editor';(editor/'revisions').mkdir(parents=True)
    case.write_json(editor/'current.json',dict(revision='r1'))
    revision=dict(lots=dict(lot=dict(status='active',geometry_revision='g1')))
    case.write_json(editor/'revisions/r1.json',revision)
    before=(source/'package.json').read_bytes()
    state=case.prepare(source/'package.json',tmp_path/'experiment',editor)
    assert (tmp_path/'experiment/inputs/evidence/001.jpg').read_bytes()==image.read_bytes()
    assert (source/'package.json').read_bytes()==before
    assert state['constraints']['floors']==2
    revision['lots']['lot']['geometry_revision']='g2'
    case.write_json(editor/'revisions/r1.json',revision)
    with pytest.raises(ValueError,match='desactualizado'):
        case.prepare(source/'package.json',tmp_path/'stale',editor)
    assert not (tmp_path/'stale').exists()


def test_accept_checkpoint_and_branch_preserve_previous_case(package,tmp_path):
    state=case.make_base(package)
    source=tmp_path/'experiment';(source/'inputs').mkdir(parents=True)
    case.write_json(source/'inputs/evidence.json',[])
    case.write_json(source/'manifest.json',dict(test=True))
    checkpoint=source/'checkpoints/00_base';checkpoint.mkdir(parents=True)
    case.write_json(checkpoint/'state.json',state)
    case.write_json(source/'state.json',state)
    attempt=source/'attempts/01_lectura/001';attempt.mkdir(parents=True)
    accepted=accept(source,state,reply('01_lectura',dict(target_description='casa',inventory=[],occlusions=[])),attempt,False)
    assert next_stage(accepted)=='02_masas'
    published=(source/'state.json').read_bytes()
    # Una etapa incorrecta no publica state.json.
    wrong=source/'attempts/02_masas/001';wrong.mkdir(parents=True)
    with pytest.raises(ValueError):
        accept(source,accepted,reply('03_lenguaje',dict(architectural_style='moderno')),wrong,False)
    assert (source/'state.json').read_bytes()==published
    branch(source,tmp_path/'branch','01_lectura','Revisar identificación del lote.')
    assert next_stage(json.loads((tmp_path/'branch/state.json').read_text()))=='01_lectura'
    assert json.loads((tmp_path/'branch/branch.json').read_text())['review_instruction']=='Revisar identificación del lote.'
    assert (source/'state.json').read_bytes()==published
