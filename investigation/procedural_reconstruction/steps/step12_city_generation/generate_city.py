import sys
import numpy as np
from pathlib import Path
import geopandas as gpd
from shapely.geometry import Point, LineString, Polygon
from collections import namedtuple
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from modeling.layout import propose_building
from modeling.grammar import generate_mesh
from modeling.exporters.glb_exporter import MaterialLibrary, export_glb
from render import render
from domain.models import MeshData

class MutableMesh:
    def __init__(self):
        self.vertices = []
        self.faces = []
        self.uv = []
        self.face_materials = []
        self.parts = []
        self.materials = []
        self.material_index = {}

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
    if mesh_data.uv is not None:
        merged.uv.extend(mesh_data.uv)
    else:
        # Pad with zeros if a mesh lacks UVs
        merged.uv.extend([(0.0, 0.0)] * len(mesh_data.vertices))
    
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
    out_dir = Path(__file__).resolve().parent / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    
    print("Cargando catastro...")
    gdf = gpd.read_file(root / "Lotes/shp_files/BARRANCO_LM_geogpsperu_SuyoPomalia.shp").to_crs(32718)
    
    rng = np.random.default_rng(42)
    
    central_idx = rng.integers(0, len(gdf))
    central_lot = gdf.iloc[central_idx].geometry
    
    print("Calculando los 25 lotes más cercanos...")
    gdf['dist'] = gdf.geometry.distance(central_lot.centroid)
    neighborhood = gdf.sort_values('dist').head(25).copy()
    
    catalog = MaterialLibrary(root / "assets/pbr/catalog.json")
    merged_data = MutableMesh()
    
    from shapely.geometry.polygon import orient
    
    print("Centrando coordenadas a 0 para evitar inestabilidad de coma flotante...")
    cx = neighborhood.geometry.centroid.x.mean()
    cy = neighborhood.geometry.centroid.y.mean()
    from shapely.affinity import translate
    neighborhood.geometry = neighborhood.geometry.apply(lambda geom: translate(geom, xoff=-cx, yoff=-cy))
    
    print("Generando edificios de la cuadra con lógicas realistas...")
    for idx, row in neighborhood.iterrows():
        # Obligar la misma orientación que usa layout.py (antihorario)
        parcel = orient(row.geometry, sign=1)
        if parcel.geom_type != "Polygon":
            continue
            
        coords = list(parcel.exterior.coords)
        front_edges = []
        others = neighborhood.drop(idx).geometry.union_all()
        
        for i, (a, b) in enumerate(zip(coords[:-1], coords[1:])):
            edge = LineString([a, b])
            midpoint = edge.centroid
            if not midpoint.buffer(0.5).intersects(others):
                front_edges.append(i)
                
        if not front_edges:
            front_edges = [0]
            
        # NO omitir lotes. Generamos todos los 25 lotes.
        family = rng.choice(["quiet_house", "ribbon_windows", "balcony_apartments", "mixed_use", "workshop", "brick_courtyard"])
        
        # Logic constraints based on user feedback
        if len(front_edges) >= 2:
            # Esquina o con múltiples frentes (corner)
            style = "corner"
            setback = 0.0
            boundary = "open"
        elif family in ("mixed_use", "workshop"):
            # Shops MUST be flush with the street
            style = "narrow"
            setback = 0.0
            boundary = "open"
        else:
            style = rng.choice(["narrow", "courtyard"])
            if style == "narrow":
                # Flush with street
                setback = 0.0
                boundary = "open"
            else:
                # Setback allowed
                setback = float(rng.uniform(1.0, 2.0))
                boundary = "wall"

        floors = int(rng.integers(1, 6))
        if family == "workshop":
            floors = int(rng.integers(1, 3))

        try:
            try:
                spec = propose_building(
                    parcel=parcel, front_edges=tuple(front_edges), floors=floors,
                    style=style, seed=idx, architectural_family=family,
                    setback_m=setback, boundary=boundary
                )
            except ValueError as ve:
                if "split/collapse footprint" in str(ve):
                    # Si el setback colapsa el lote, forzamos setback 0
                    setback = 0.0
                    boundary = "open"
                    spec = propose_building(
                        parcel=parcel, front_edges=tuple(front_edges), floors=floors,
                        style=style, seed=idx, architectural_family=family,
                        setback_m=setback, boundary=boundary
                    )
                else:
                    raise ve

            mesh = generate_mesh(spec)
            
            # Reconstruction of MeshData for merge
            # We don't need to rebuild it, just use the mesh as is!
            merge_builders(merged_data, mesh)
            print(f"Lote {idx}: {family} ({style}), {floors} pisos, frentes={front_edges}, setback={setback:.1f}m")
        except Exception as e:
            print(f"Error generando lote {idx}: {e}")

    file_name = out_dir / "cuadra_realista.glb"
    
    # Repack as numpy arrays for render/export
    merged_data_np = MeshData(
        vertices=np.array(merged_data.vertices), faces=np.array(merged_data.faces), uv=np.array(merged_data.uv),
        face_materials=np.array(merged_data.face_materials), parts=tuple(merged_data.parts), materials=tuple(merged_data.materials)
    )
    
    export_glb(merged_data_np, file_name, library=catalog)
    print(f"\nGLB exportado a {file_name}")
    
    # Render for the subagent
    img_path = out_dir / "cuadra_render.png"
    render(merged_data_np, str(img_path), size=1200, clay=False, checker=False)
    print(f"Render exportado a {img_path}")

if __name__ == "__main__":
    main()
