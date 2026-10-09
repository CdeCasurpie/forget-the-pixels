"""Step21: SVG de lotes + frentes. Uso: venv310/bin/python steps/step21_lot_fronts/plot_fronts.py"""
import json, sys
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
import geopandas as gpd
STEP = Path(__file__).resolve().parent
ROOT = STEP.parent.parent

def main():
    gdf = gpd.read_file(ROOT/'data/lotes/BARRANCO_LM_geogpsperu.geojson').to_crs(32718)
    fronts = json.loads((STEP/'lot_fronts.json').read_text())
    fig, ax = plt.subplots(figsize=(14, 14))
    gdf.boundary.plot(ax=ax, color='#999999', linewidth=0.25)
    segs, empty = [], []
    for _, row in gdf.iterrows():
        rec = fronts[str(row['objectid'])]
        idx = set(rec['street_edge_indices'])
        edges = rec['edges']
        if not idx:
            empty.append(row.geometry)
        for e in edges:
            if e['edge_index'] in idx:
                segs.append([e['start_xy'], e['end_xy']])
    if empty:
        gpd.GeoSeries(empty).plot(ax=ax, color='#ffaa00', alpha=0.5)
    ax.add_collection(LineCollection(segs, colors='red', linewidths=0.8))
    ax.set_aspect('equal'); ax.axis('off')
    ax.set_title(f'Barranco: {len(gdf)} lotes, {len(segs)} segmentos de frente (rojo); sin frente (naranja)',
                 fontsize=11)
    fig.savefig(STEP/'lot_fronts.svg', format='svg', bbox_inches='tight')
    fig.savefig(STEP/'lot_fronts.png', dpi=110, bbox_inches='tight')
    print(f'segmentos frente={len(segs)} | lotes sin frente={len(empty)}', flush=True)

if __name__ == '__main__':
    main()
