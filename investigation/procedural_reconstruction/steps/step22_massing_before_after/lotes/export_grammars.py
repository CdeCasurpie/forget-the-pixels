"""Create a portable, text-only dump of all per-lot Step22 before grammars."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / 'gramaticas_lotes.json'
SELECTED = ROOT.parents[1] / 'step21_lot_fronts/seleccion/lotes.json'


def main():
    cases = []
    for folder in sorted(ROOT.iterdir()):
        if not folder.is_dir() or not (folder/'before/request.json').exists():
            continue
        request = json.loads((folder/'before/request.json').read_text())
        resolved = json.loads((folder/'before/resolved_theta.json').read_text())
        manifest = json.loads((folder/'before/manifest.json').read_text())
        lot_id, slug = folder.name.split('_', 1)
        if int(lot_id) != manifest['lot']:
            raise ValueError(f'Lot ID mismatch in {folder}')
        if request['theta'].get('masses') or request['theta'].get('massing', {}).get('pattern') == 'explicit':
            raise ValueError(f'Explicit masses in {folder}')
        cases.append({
            'objectid': int(lot_id),
            'nombre': slug.replace('_', ' '),
            'carpeta': folder.name,
            'request': request,
            'resolved_theta': resolved['theta'],
            'street_edge_indices': manifest['street_edge_indices'],
            'fronts_ring_order': manifest['fronts_ring_order'],
            'mesh_triangles': manifest['triangles'],
            'envelope_test': manifest['validation']['envelope_test'],
            'source': 'before/request.json + before/resolved_theta.json',
        })
    selected = {int(item['objectid']) for item in json.loads(SELECTED.read_text())['lots']}
    present = {case['objectid'] for case in cases}
    missing = sorted(selected - present)
    unexpected = sorted(present - selected)
    if unexpected:
        raise ValueError(f'Unexpected IDs outside selected lots: {unexpected}')
    dump = {
        'description': 'Step22 before grammars; no explicit masses; original cadastral parcels translated to local metres',
        'schema': 'ReconstructionRequest / theta candidate 0.2',
        'spatial_context': 'EPSG:32718; local parcel coordinates in metres; renderer applies data/cadastral_offset.json for Street View alignment only',
        'selected_lot_count': len(selected),
        'exported_lot_count': len(cases),
        'missing_ids': missing,
        'note': 'Missing IDs have no current before/request.json; no grammar is fabricated for them.',
        'lots': cases,
    }
    OUTPUT.write_text(json.dumps(dump, ensure_ascii=False, indent=2)+'\n')
    print(f'{len(cases)} grammars -> {OUTPUT}')


if __name__ == '__main__':
    main()
