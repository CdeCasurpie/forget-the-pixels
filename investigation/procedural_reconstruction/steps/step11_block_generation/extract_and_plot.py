import os
import geopandas as gpd
import matplotlib.pyplot as plt
from shapely.geometry import Point, LineString, Polygon
import numpy as np
from pathlib import Path

def main():
    out_dir = Path("outputs")
    out_dir.mkdir(exist_ok=True, parents=True)

    root = Path("../../") 
    shp_path = root / "Lotes/shp_files/BARRANCO_LM_geogpsperu_SuyoPomalia.shp"

    print("Cargando catastro...")
    gdf = gpd.read_file(shp_path).to_crs(32718)
    
    rng = np.random.default_rng(42) # Semilla fija para revisar la misma cuadra
    central_idx = rng.integers(0, len(gdf))
    central_lot = gdf.iloc[central_idx].geometry

    print("Calculando 25 lotes más cercanos...")
    gdf['dist'] = gdf.geometry.distance(central_lot.centroid)
    neighborhood = gdf.sort_values('dist').head(25).copy()

    fig, ax = plt.subplots(figsize=(12, 12))
    # Dibujar polígonos base
    neighborhood.plot(ax=ax, facecolor='#dddddd', edgecolor='none')

    print("Calculando aristas exteriores e interiores...")
    exterior_count = 0
    interior_count = 0
    
    from shapely.geometry.polygon import orient
    
    for idx, row in neighborhood.iterrows():
        parcel = orient(row.geometry, sign=1)
        if parcel.geom_type != "Polygon":
            continue
            
        others = neighborhood.drop(idx).geometry.union_all()
        coords = list(parcel.exterior.coords)
        
        for i, (a, b) in enumerate(zip(coords[:-1], coords[1:])):
            edge = LineString([a, b])
            midpoint = edge.centroid
            # Buffer de 0.5m hacia afuera desde el centroide
            search_area = midpoint.buffer(0.5)
            
            x, y = edge.xy
            if search_area.intersects(others):
                # Interior
                ax.plot(x, y, color='red', linewidth=2, linestyle=':')
                interior_count += 1
            else:
                # Exterior (Calle)
                ax.plot(x, y, color='green', linewidth=4)
                exterior_count += 1

    plt.axis('equal')
    plt.title(f"Revisión de Fachadas\nVerde = Exterior ({exterior_count}), Rojo = Interior ({interior_count})")
    
    out_file = out_dir / "block_edges.png"
    plt.savefig(out_file, dpi=150, bbox_inches='tight')
    print(f"Gráfico guardado en {out_file.absolute()}")

if __name__ == "__main__":
    main()
