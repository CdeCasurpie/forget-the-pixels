"""API Messages directa con httpx, igual al transporte probado por el usuario."""
import os
import time

import httpx


async def request(body, timeout_s=240):
    url = os.environ['ANTHROPIC_BASE_URL'].rstrip('/') + '/v1/messages'
    key = os.environ['ANTHROPIC_API_KEY']
    started = time.monotonic()
    async with httpx.AsyncClient(timeout=timeout_s) as client:
        response = await client.post(url, headers={'x-api-key':key,
            'anthropic-version':'2023-06-01','content-type':'application/json'},json=body)
        # No persistir cabeceras ni variables de entorno.
        if response.is_error:
            raise RuntimeError(f'API HTTP {response.status_code}; no se avanzó la etapa.')
        data = response.json()
    metrics = dict(latency_s=round(time.monotonic()-started,3),usage=data.get('usage'),
                   stop_reason=data.get('stop_reason'),model=data.get('model'),id=data.get('id'))
    return data, metrics


def response_text(data):
    if data.get('stop_reason') != 'end_turn':
        raise ValueError(f"Respuesta no terminada normalmente: {data.get('stop_reason')}; revisar límite de salida.")
    text = '\n'.join(x['text'] for x in data.get('content',[]) if x['type']=='text').strip()
    if not text:
        raise ValueError('La API no devolvió texto.')
    return text
