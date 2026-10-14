"""Step21: frentes de los 4926 lotes. Uso: venv310/bin/python steps/step21_lot_fronts/compute_fronts.py"""
import json, time, sys
from pathlib import Path
import geopandas as gpd
STEP = Path(__file__).resolve().parent
ROOT = STEP.parent.parent
sys.path.insert(0, str(ROOT))
from src.spatial.street_fronts import annotate_street_fronts

def main():
    t0 = time.time()
    gdf = gpd.read_file(ROOT/'data/lotes/BARRANCO_LM_geogpsperu.geojson').to_crs(32718)
    print(f'cargados {len(gdf)} lotes ({time.time()-t0:.1f}s)', flush=True)
    t1 = time.time()
    ann = annotate_street_fronts(gdf)
    print(f'frentes calculados ({time.time()-t1:.1f}s)', flush=True)
    out = {}
    for _, row in ann.iterrows():
        # street_edges ya son dicts JSON-compatibles
        out[str(row.get('objectid'))] = {
            'street_edge_indices': row['street_edge_indices'],
            'edges': row['street_edges'],
        }
    (STEP/'lot_fronts.json').write_text(json.dumps(out))
    counts = [len(v['street_edge_indices']) for v in out.values()]
    import statistics
    print(f'lotes={len(out)} frentes_total={sum(counts)} media={statistics.mean(counts):.2f} '
          f'min={min(counts)} max={max(counts)} sin_frente={sum(1 for c in counts if c==0)}', flush=True)
    from collections import Counter
    print('distribucion:', dict(sorted(Counter(counts).items())), flush=True)
    print(f'TOTAL {time.time()-t0:.1f}s', flush=True)

if __name__ == '__main__':
    main()
