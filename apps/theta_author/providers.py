"""Replace generate(package) with a remote API or local model adapter.

Input is a frozen package with prompt, response schema and evidence paths.
Output is RAW response text. Parsing/validation/persistence belong to the caller.
A real multimodal adapter must attach evidence images, not merely send their paths.
"""
import json
from typing import Protocol


class Provider(Protocol):
    name: str
    model: str
    is_mock: bool

    def generate(self, package: dict) -> str:
        """Return original response text; raise on transport/provider failure."""
        ...


class MockProvider:
    name = 'temporary-mock'
    model = 'deterministic-placeholder-v1'
    is_mock = True

    def generate(self, package):
        f = package['human_parameters']
        defaults = {'height': 'altura 9 m', 'floors': '3 pisos', 'style': 'estilo moderno'}
        invented = [description for field, description in defaults.items() if f[field]['value'] is None]
        levels = None
        if f.get('floor_height_m') is not None:
            first = f['first_floor_height_m'] if f.get('first_floor_different') else f['floor_height_m']
            levels = [0] + [round(first+i*f['floor_height_m'], 4) for i in range(int(f['floors']['value']))]
        return json.dumps(dict(schema_version='authoring-v1',
            height_m=f['height']['value'] or 9,
            floors=int(f['floors']['value'] or 3),
            style=f['style']['value'] or 'moderno', massing=f['massing'],
            levels_m=levels, construction=None, material=None, color=None,
            assumptions=['MOCK TEMPORAL: no se analizaron fotografías.',
                'Valores desconocidos simulados: '+(', '.join(invented) if invented else 'ninguno')+'.',
                'Huella de referencia derivada del lote; no es una huella observada.',
                'Sin detalles de fachada; alturas sugeridas solo para probar el flujo.']), ensure_ascii=False)
