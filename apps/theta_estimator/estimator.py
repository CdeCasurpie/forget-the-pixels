"""Estimador standalone de parámetros arquitectónicos con opencode como backend.

Expone una sola función, `estimate()`, que envía fotos a `opencode run` y
devuelve el JSON del formulario de B (pisos, alturas, primer piso, estilo).
No importa nada de B: la conexión se hará después contra este contrato.
"""
from __future__ import annotations

import json
import re
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

STYLES = ('republicano', 'barroco', 'clasico', 'madera', 'moderno')
PROMPT_PATH = Path(__file__).resolve().parent / 'prompts' / 'estimate_v1.txt'


@dataclass
class EstimateResult:
    floors: int | None = None
    floor_height_m: float | None = None
    first_floor_different: bool = False
    first_floor_height_m: float | None = None
    style: str | None = None
    notes: str = ''
    raw_text: str = ''
    model: str = ''
    latency_s: float = 0.0
    error: str | None = None


def render_prompt(lot_id: str | None, n_images: int, style_sheet: bool = False) -> str:
    template = PROMPT_PATH.read_text()
    note = ('La PRIMERA imagen es una lámina de referencia con los 5 estilos '
            'numerados (1 republicano, 2 barroco, 3 clasico, 4 madera, 5 moderno). '
            'Compara el edificio del prisma con esa lámina antes de decidir el estilo. '
            'Las demás imágenes son las fotos del lote.\n' if style_sheet else '')
    return template.replace('{lot_id}', lot_id or 'desconocido').replace('{n_images}', str(n_images)).replace('{style_note}', note)


def extract_text(stdout: str) -> str:
    """Saca el texto del asistente del envelope `--format json`.

    Punto verificado en la etapa probe: si el formato cambia, se ajusta aquí
    sin tocar el resto. Si no hay JSON reconocible, devuelve stdout tal cual.
    """
    chunks: list[str] = []
    parsed_any = False
    for line in stdout.splitlines():
        line = line.strip()
        if not line.startswith('{'):
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        parsed_any = True
        chunks.extend(_texts_from(event))
    if parsed_any:
        return '\n'.join(c for c in chunks if c).strip() or stdout.strip()
    try:
        whole = json.loads(stdout)
        texts = _texts_from(whole)
        if texts:
            return '\n'.join(texts).strip()
    except json.JSONDecodeError:
        pass
    return stdout.strip()


def _texts_from(node) -> list[str]:
    found: list[str] = []
    if isinstance(node, dict):
        kind = node.get('type', '')
        if kind in ('text', 'message') and isinstance(node.get('text'), str):
            found.append(node['text'])
        for value in node.values():
            found.extend(_texts_from(value))
    elif isinstance(node, list):
        for value in node:
            found.extend(_texts_from(value))
    return found


def extract_json(text: str) -> dict:
    """Extrae el primer objeto JSON: bloque ```json, objeto suelto o texto."""
    fence = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
    if fence:
        return json.loads(fence.group(1))
    start = text.find('{')
    if start < 0:
        raise ValueError('la respuesta no contiene ningún objeto JSON')
    decoder = json.JSONDecoder()
    try:
        data, _ = decoder.raw_decode(text[start:])
    except json.JSONDecodeError as e:
        raise ValueError(f'JSON incompleto o inválido: {e}') from e
    if not isinstance(data, dict):
        raise ValueError('el JSON raíz no es un objeto')
    return data


def validate(data: dict) -> dict:
    """Normaliza y valida contra el vocabulario del formulario de B."""
    floors = data.get('floors')
    if not isinstance(floors, int) or isinstance(floors, bool) or not 1 <= floors <= 30:
        raise ValueError(f'floors fuera de rango 1-30: {floors!r}')
    height = data.get('floor_height_m')
    if not isinstance(height, (int, float)) or isinstance(height, bool) or not 2 <= height <= 6:
        raise ValueError(f'floor_height_m fuera de rango 2-6: {height!r}')
    different = bool(data.get('first_floor_different', False))
    first = data.get('first_floor_height_m')
    if different:
        if not isinstance(first, (int, float)) or isinstance(first, bool) or not 2 <= first <= 8:
            raise ValueError(f'first_floor_height_m fuera de rango 2-8: {first!r}')
        first = float(first)
    else:
        first = None
    style = data.get('style')
    if style not in STYLES:
        raise ValueError(f'style desconocido: {style!r} (esperado uno de {", ".join(STYLES)})')
    notes = data.get('notes', '')
    if not isinstance(notes, str):
        raise ValueError('notes debe ser texto')
    return dict(floors=floors, floor_height_m=float(height), first_floor_different=different,
                first_floor_height_m=first, style=style, notes=notes[:2000])


def estimate(images: list[str | Path], lot_id: str | None = None, model: str = 'opencode/muse-spark-1.3-contributor-free',
             agent: str | None = None, timeout_s: int = 180, runner=subprocess,
             style_sheet: str | Path | None = None) -> EstimateResult:
    """Estima el formulario de B desde fotos. Sesión siempre fresca, sin -c."""
    paths = [Path(p) for p in images]
    sheet = Path(style_sheet) if style_sheet else None
    if sheet and not sheet.is_file():
        return EstimateResult(error=f'lamina de estilos inexistente: {sheet}')
    missing = [str(p) for p in paths if not p.is_file()]
    if missing:
        return EstimateResult(error=f'imágenes inexistentes: {", ".join(missing)}')
    prompt = render_prompt(lot_id, len(paths), style_sheet=sheet is not None)
    command = ['opencode', 'run', '--model', model, '--format', 'json']
    if agent:
        command += ['--agent', agent]
    for path in ([sheet] if sheet else []) + paths:
        command += ['--file', str(path)]
    command.append(prompt)
    start = time.monotonic()
    try:
        completed = runner.run(command, capture_output=True, text=True, timeout=timeout_s)
    except Exception as e:
        return EstimateResult(model=model, latency_s=time.monotonic() - start, error=f'falló la llamada: {e}')
    latency = time.monotonic() - start
    if completed.returncode != 0:
        return EstimateResult(model=model, latency_s=latency,
                              error=f'opencode salió con {completed.returncode}: {(completed.stderr or "")[:500]}')
    raw = extract_text(completed.stdout or '')
    try:
        return EstimateResult(**validate(extract_json(raw)), raw_text=raw, model=model, latency_s=latency)
    except ValueError as e:
        return EstimateResult(raw_text=raw, model=model, latency_s=latency, error=str(e))
