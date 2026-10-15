import json

import pytest

from apps.theta_estimator.estimator import (
    STYLES, EstimateResult, estimate, extract_json, extract_text, render_prompt, validate,
)


class FakeCompleted:
    def __init__(self, stdout='', returncode=0, stderr=''):
        self.stdout = stdout
        self.returncode = returncode
        self.stderr = stderr


class FakeRunner:
    def __init__(self, completed):
        self.completed = completed
        self.commands = []

    def run(self, command, **kwargs):
        self.commands.append(command)
        if isinstance(self.completed, Exception):
            raise self.completed
        return self.completed


GOOD = dict(floors=3, floor_height_m=2.8, first_floor_different=True,
            first_floor_height_m=4.0, style='republicano', notes='balcones típicos')


def test_render_prompt_incluye_lote_y_cantidad(tmp_path):
    prompt = render_prompt('1135018', 2)
    assert '1135018' in prompt and '2' in prompt and 'JSON' in prompt


def test_extract_json_limpio_con_fences_y_con_texto():
    assert extract_json(json.dumps(GOOD)) == GOOD
    assert extract_json('```json\n' + json.dumps(GOOD) + '\n```') == GOOD
    assert extract_json('Creo que es esto: ' + json.dumps(GOOD) + ' saludos') == GOOD
    with pytest.raises(ValueError):
        extract_json('no hay json aquí')


def test_validate_rangos_y_estilos():
    assert validate(dict(GOOD))['style'] == 'republicano'
    assert validate({**GOOD, 'first_floor_different': False})['first_floor_height_m'] is None
    for bad in [dict(GOOD, floors=0), dict(GOOD, floor_height_m=9),
                dict(GOOD, first_floor_different=True, first_floor_height_m=1),
                dict(GOOD, style='gótico')]:
        with pytest.raises(ValueError):
            validate(bad)


def test_extract_text_acepta_envelope_y_texto_plano():
    event = json.dumps({'type': 'message', 'text': 'hola'})
    assert extract_text(event + '\n' + json.dumps({'type': 'done'})).strip() == 'hola'
    assert extract_text('texto plano') == 'texto plano'


def test_estimate_ok_con_runner_falso(tmp_path):
    image = tmp_path / 'foto.jpg'
    image.write_bytes(b'fake')
    runner = FakeRunner(FakeCompleted(stdout=json.dumps(GOOD)))
    result = estimate([image], lot_id='1', runner=runner)
    assert result.error is None and result.floors == 3 and result.style == 'republicano'
    command = runner.commands[0]
    assert command[:4] == ['opencode', 'run', '--model', 'claude-code/claude-sonnet-5']
    assert '--file' in command and str(image) in command
    assert '-c' not in command and '--continue' not in command


def test_estimate_errores_sin_romper(tmp_path):
    image = tmp_path / 'foto.jpg'
    image.write_bytes(b'fake')
    assert estimate([tmp_path / 'falta.jpg']).error.startswith('imágenes inexistentes')
    timeout = FakeRunner(TimeoutError('lento'))
    assert 'falló la llamada' in estimate([image], runner=timeout).error
    bad = FakeRunner(FakeCompleted(stdout='no es json'))
    assert estimate([image], runner=bad).error
    fail = FakeRunner(FakeCompleted(stdout='', returncode=1, stderr='boom'))
    assert 'boom' in estimate([image], runner=fail).error


@pytest.mark.live
def test_live_probe_manual():
    pytest.skip('manual: ESTIMATOR_LIVE=1 python -m apps.theta_estimator.cli probe --image ...')
