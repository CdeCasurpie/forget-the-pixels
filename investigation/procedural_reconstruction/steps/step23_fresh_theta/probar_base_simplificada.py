"""Run a compact two-storey base recipe against the real house parcel."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from domain.theta import from_json, decode
from modeling.base_massing import BaseFloor, with_base
from modeling.exporters.glb_exporter import export_glb
from pipeline.theta import reconstruct

LOT = Path(__file__).parent / 'lotes/1134299_casa_salmon_republicana'
RECIPE = {
    'floors': [
        {'height_m': 3.5, 'setbacks': [{'edge': 1, 'depth_m': 1.4}],
         'bites': [{'edge': 1, 'end': 'end', 'width_m': 4.2086, 'depth_m': 5.0}]},
        {'height_m': 3.5, 'setbacks': [{'edge': 1, 'depth_m': 1.4}],
         'bites': [{'edge': 1, 'end': 'end', 'width_m': 4.2086, 'depth_m': 5.0}]}
    ]
}


if __name__ == '__main__':
    source = json.loads((LOT / 'fresh/request.json').read_text())
    source['theta']['facade'] = {'mode': 'explicit', 'openings': [], 'projections': []}
    source['theta']['facades'] = []
    source['theta']['roofs'] = []
    source['theta']['site'] = {'fence': 'none', 'runs': [], 'zones': [], 'garden': False}
    source['evidence'] = {}
    request = with_base(from_json(json.dumps(source)),
                        tuple(decode(BaseFloor, f) for f in RECIPE['floors']))
    result = reconstruct(request)
    assert not result.resolved.boundaries
    assert all(not w.facade.openings for w in result.resolved.walls)
    out = LOT / 'base_simplificada'
    out.mkdir(exist_ok=True)
    (out / 'base.json').write_text(json.dumps(RECIPE, indent=2) + '\n')
    export_glb(result.mesh, out / 'building.glb')
    print(out, len(result.mesh.faces), 'triangles; zero openings and fences')
