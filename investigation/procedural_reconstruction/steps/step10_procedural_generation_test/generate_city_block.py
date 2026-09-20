import sys
import json
import numpy as np
from pathlib import Path
import geopandas as gpd
from shapely.geometry import Point, LineString, Polygon

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from procedural_modeling.layout import propose_building
from procedural_modeling.grammar import generate_mesh
from procedural_modeling.families import apply_family
from procedural_modeling.mesh_builder import MeshBuilder
from exporters.glb_exporter import MaterialLibrary, export_glb

def merge_builders(merged, mesh_data):
    mat_map = {}
    for i, mat in enumerate(mesh_data.materials):
        if mat["name"] not in merged.material_index:
            merged.material_index[mat["name"]] = len(merged.materials)
            merged.materials.append(mat)
        mat_map[i] = merged.material_index[mat["name"]]
    
    v_offset = len(merged.vertices)
    f_offset = len(merged.faces)
    
    merged.vertices.extend(mesh_data.vertices)
    merged.uv.extend(mesh_data.uv)
    
    for face in mesh_data.faces:
        merged.faces.append(tuple(v + v_offset for v in face))
        
    for mat_idx in mesh_data.face_materials:
        merged.face_materials.append(mat_map[mat_idx])
        
    for part in mesh_data.parts:
        merged.parts.append({
            "name": part["name"],
            "face_start": part["face_start"] + f_offset,
            "face_count": part["face_count"]
        })

def main():
    root = Path(__file__).resolve().parents[2]
    out_dir = Path(__file__).resolve().parent / "outputs/city_block"
    out_dir.mkdir(parents=True, exist_ok=True)
    
    print("Cargando catastro...")
    gdf = gpd.read_file(root / "Lotes/shp_files/BARRANCO_LM_geogpsperu_SuyoPomalia.shp").to_crs(32718)
    
    rng = np.random.default_rng(777)
    
    # Escoger un lote central al azar
    central_idx = rng.integers(0, len(gdf))
    central_lot = gdf.iloc[central_idx].geometry
    
    print("Calculando los 15 lotes más cercanos...")
    gdf['dist'] = gdf.geometry.distance(central_lot.centroid)
    neighborhood = gdf.sort_values('dist').head(15).copy()
    
    catalog = MaterialLibrary(root / "assets/pbr/catalog.json")
    
    # Crear un contenedor base con la misma estructura que requiere export_glb
    from collections import namedtuple
    MeshData = namedtuple("MeshData", ["vertices", "faces", "uv", "face_materials", "parts", "materials", "material_index"])
    merged_data = MeshData([], [], [], [], [], [], {})
    
    print("Generando edificios y determinando fachadas...")
    for idx, row in neighborhood.iterrows():
        parcel = row.geometry
        if not parcel.is_valid or parcel.geom_type != "Polygon":
            continue
            
        coords = list(parcel.exterior.coords)
        front_edges = []
        
        # Buscar qué bordes no tocan a los vecinos (son calles)
        others = neighborhood.drop(idx).geometry.buffer(0.5).union_all()
        
        for i, (a, b) in enumerate(zip(coords[:-1], coords[1:])):
            edge = LineString([a, b])
            if not edge.intersects(others):
                front_edges.append(i)
                
        if not front_edges:
            front_edges = [0]
            
        if rng.random() < 0.15:
            # Corralón / muro
            spec = propose_building(
                parcel=parcel, front_edges=tuple(front_edges), floors=1,
                style="narrow", seed=idx, architectural_family="brick_courtyard",
                height_m=2.5
            )
        else:
            style = str(rng.choice(["narrow", "courtyard", "corner"]))
            floors = int(rng.integers(1, 5))
            spec = propose_building(
                parcel=parcel, front_edges=tuple(front_edges), floors=floors,
                style=style, seed=idx, architectural_family="auto"
            )
            
        try:
            mesh = generate_mesh(spec)
            merge_builders(merged_data, mesh)
        except Exception as e:
            print(f"Error generando lote {idx}: {e}")

    file_name = out_dir / "cuadra_aleatoria.glb"
    export_glb(merged_data, file_name, library=catalog)
    print(f"\n¡Cuadra completa de 15 lotes exportada en:\n{file_name}")

if __name__ == "__main__":
    main()
