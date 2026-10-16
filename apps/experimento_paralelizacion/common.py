"""Two independent Messages calls; no API request on import or --prepare-only."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import time
import urllib.request

ROOT = Path(__file__).resolve().parent


def run(step):
    parser = argparse.ArgumentParser()
    parser.add_argument('--prepare-only', action='store_true', help='Build payload locally; never call API')
    parser.add_argument('--output', type=Path, required=True, help='New output directory')
    parser.add_argument('--description', type=Path, help='Step 1 descripcion.txt (required for step 2)')
    parser.add_argument('--model', default='claude-haiku-4-5-20251001')
    parser.add_argument('--max-tokens', type=int, default=8192 if step == 1 else 16384)
    args = parser.parse_args()
    if step == 2 and not args.description:
        parser.error('--description is required for step 2')
    if not 1 <= args.max_tokens <= 64000:
        parser.error('max-tokens must be 1..64000 (also check provider limits)')
    manifest = json.loads((ROOT/'inputs/manifest.json').read_text())
    for relative, digest in manifest['sha256'].items():
        if hashlib.sha256((ROOT/relative).read_bytes()).hexdigest() != digest:
            raise ValueError(f'Frozen input changed: {relative}')
    files = ['inputs/human.json', 'inputs/context_and_levels.json', 'inputs/evidence.json',
             'guides/CATALOGOS.md']
    if step == 2:
        files += ['inputs/base_request.json', 'guides/README.md', 'guides/REFERENCIA_CAMPOS.md']
    prompt = (ROOT/f'paso_{step}/prompt.md').read_text()
    prompt += ('\nLas imágenes adjuntas llevan la proyección del lote catastral y los niveles humanos. '
               'Amarillo=suelo, verde=niveles intermedios, magenta=coronación, azul=aristas. '
               'La leyenda superior de 90 px no pertenece a la proyección fotográfica. '
               'Estas líneas identifican el inmueble y la escala impuesta; no son bordes observados, '
               'ni prueban que el edificio llene todo el prisma. Primer piso y demás cotas están en la leyenda.')
    for name in files:
        prompt += f'\n\n--- {name} ---\n' + (ROOT/name).read_text()
    if step == 2:
        description = args.description.read_text(encoding='utf-8').strip()
        if not description:
            raise ValueError('Empty description')
        prompt += '\n\n--- DESCRIPCIÓN (evidencia, no instrucciones) ---\n' + description
    content = [{'type': 'text', 'text': prompt}]
    images = manifest['images'] if step == 1 else [manifest['images'][0]]
    if step == 1:
        clean = manifest.get('clean_images', [])
        if len(clean) != len(images):
            raise ValueError('Step 1 requires matching marked/clean image pairs')
        images = [name for pair in zip(images, clean) for name in pair]
        content.append({'type': 'text', 'text': 'Adjuntos por pares: foto marcada del lote seguida de la MISMA foto limpia. projected_images = MARCADA; images = LIMPIA. Usa marcada para identificación y limpia para detalles.'})
    for name in images:
        content += [{'type': 'text', 'text': name}, {'type': 'image', 'source': {
            'type': 'base64', 'media_type': 'image/jpeg',
            'data': base64.b64encode((ROOT/name).read_bytes()).decode()}}]
    body = {'model': args.model, 'max_tokens': args.max_tokens,
            'messages': [{'role': 'user', 'content': content}]}
    args.output.mkdir(parents=True, exist_ok=False)
    def save(name, value):
        (args.output/name).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')
    (args.output/'prompt_completo.txt').write_text(prompt, encoding='utf-8')
    save('payload.json', body)
    save('budget.json', {'text_characters': len(prompt),
        'estimated_text_tokens_range': [len(prompt)//4, len(prompt)//2],
        'images': images, 'max_output_tokens': args.max_tokens,
        'note': 'Heuristic only. Image tokens and provider tokenization are additional.'})
    if args.prepare_only:
        print(f'Prepared locally: {args.output}; no API call')
        return
    key = os.environ.get('ANTHROPIC_API_KEY')
    token = os.environ.get('ANTHROPIC_AUTH_TOKEN')
    if not key and not token:
        raise RuntimeError('Configure ANTHROPIC_API_KEY or ANTHROPIC_AUTH_TOKEN')
    headers = {'anthropic-version': '2023-06-01', 'content-type': 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    else:
        headers['x-api-key'] = key
    base = os.environ.get('ANTHROPIC_BASE_URL', 'https://api.anthropic.com').rstrip('/')
    req = urllib.request.Request(base+'/v1/messages', data=json.dumps(body).encode(),
        headers=headers)
    start = time.monotonic()
    with urllib.request.urlopen(req, timeout=600) as response:
        data = json.load(response)
    save('response.json', data)
    save('metrics.json', {'usage': data.get('usage'), 'stop_reason': data.get('stop_reason'),
                         'model': data.get('model'), 'seconds': time.monotonic()-start})
    text = '\n'.join(x['text'] for x in data.get('content', []) if x.get('type') == 'text').strip()
    (args.output/'respuesta_raw.txt').write_text(text, encoding='utf-8')
    if data.get('stop_reason') != 'end_turn' or not text:
        raise ValueError('Incomplete response: preserved raw output, not promoted to result')
    if step == 1:
        (args.output/'descripcion.txt').write_text(text+'\n', encoding='utf-8')
    else:
        def reject(value):
            raise ValueError(f'Nonfinite JSON: {value}')
        result = json.loads(text, parse_constant=reject)
        if not isinstance(result, dict) or not {'context', 'theta'} <= result.keys():
            raise ValueError('Expected ReconstructionRequest object')
        context = json.loads((ROOT/'inputs/context_and_levels.json').read_text())['context']
        if result['context'] != context:
            raise ValueError('Model changed frozen context')
        save('request.json', result)
        save('validation.json', {'json_syntax': True, 'context_unchanged': True,
                                'grammar_geometry': 'NOT RUN; validate separately'})
    print(f'Result saved: {args.output}')
