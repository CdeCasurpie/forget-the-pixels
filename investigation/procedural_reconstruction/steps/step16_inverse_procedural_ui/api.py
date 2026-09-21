import sys
import os
import json
import random
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point
import uvicorn

ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT / "src"))

from spatial.street_fronts import street_facing_edges
from domain.architecture import ParcelContext, BuildingProgram, MassSpec, SitePlan, BuildingSpecificationV4
from modeling.grammar import generate_v4_mesh
from modeling.exporters.glb_exporter import export_glb

app = FastAPI(title="Procedural Barranco API")

STATIC_DIR = Path(__file__).resolve().parent / "static"
ASSETS_DIR = STATIC_DIR / "assets"
ASSETS_DIR.mkdir(exist_ok=True, parents=True)

GEOJSON_PATH = ROOT / "Lotes" / "shp_files" / "BARRANCO_LM_geogpsperu.geojson"
METADATA_PATH = ROOT / "steps" / "step2_vector_to_lots" / "data" / "barranco_metadata" / "metadata.json"
CACHE_DIR = ROOT / "Lotes" / "streetview_cache"

print("Cargando datos espaciales...")
gdf_lots = gpd.read_file(GEOJSON_PATH)
gdf_utm = gdf_lots.to_crs(epsg=32718)

print("Cargando metadatos de cámaras...")
with open(METADATA_PATH, "r") as f:
    meta = json.load(f)
df_cams = pd.DataFrame.from_dict(meta["panoramas"], orient='index')
gdf_cams = gpd.GeoDataFrame(df_cams, geometry=gpd.points_from_xy(df_cams.lon, df_cams.lat), crs="EPSG:4326")
gdf_cams_utm = gdf_cams.to_crs(epsg=32718)

app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR)), name="assets")

@app.get("/")
def read_root():
    return FileResponse(str(STATIC_DIR / "index.html"))

@app.get("/api/lots")
def get_lots():
    gdf_minimal = gdf_lots[['geometry']].copy()
    gdf_minimal['id'] = gdf_minimal.index
    if gdf_minimal.crs and gdf_minimal.crs.to_epsg() != 4326:
        gdf_minimal = gdf_minimal.to_crs(epsg=4326)
    return JSONResponse(content=json.loads(gdf_minimal.to_json()))

@app.get("/api/cameras/{lot_idx}")
def get_cameras(lot_idx: int):
    if lot_idx not in gdf_utm.index:
        raise HTTPException(status_code=404, detail="Lot not found")
        
    lot_geom = gdf_utm.loc[lot_idx].geometry
    buffer = lot_geom.buffer(15.0) # 15 meters radius
    nearby_cams = gdf_cams_utm[gdf_cams_utm.geometry.intersects(buffer)]
    
    cameras = []
    for pano_id, row in nearby_cams.iterrows():
        is_downloaded = (CACHE_DIR / f"{pano_id}.jpg").exists()
        cameras.append({
            "pano_id": pano_id,
            "lat": row.lat,
            "lon": row.lon,
            "downloaded": is_downloaded
        })
    return {"cameras": cameras}

def estimate_parameters(lot_idx: int, cameras: list):
    """
    Mock function to simulate parameter extraction from StreetView images.
    Returns the contract (dictionary) needed for BuildingProgram and MassSpec.
    """
    random.seed(lot_idx) # Stable random for the same lot
    
    # Simulate height extraction from cameras (e.g. 1 floor = 3m, up to 5 floors)
    floors = random.randint(1, 4)
    if len(cameras) > 5: floors = random.randint(3, 5) # Dense areas have taller buildings
    
    roof_z = floors * 3.0
    floor_levels = tuple(float(i * 3.0) for i in range(floors + 1))
    
    uses = ["residential", "commercial", "mixed"]
    finishes = ["plastered", "bare_brick", "painted"]
    placements = ["flush", "front_setback"]
    colors = [(0.9, 0.9, 0.9), (0.8, 0.7, 0.6), (0.6, 0.8, 0.7), (0.9, 0.6, 0.6)]
    
    return {
        "use": random.choice(uses),
        "finish_profile": random.choice(finishes),
        "placement": random.choice(placements),
        "primary_color": random.choice(colors),
        "roof_z": roof_z,
        "floor_levels": floor_levels
    }

@app.post("/api/generate/{lot_idx}")
def generate_model(lot_idx: int):
    try:
        if lot_idx not in gdf_utm.index:
            raise HTTPException(status_code=404, detail="Lot not found")
            
        target_poly = gdf_utm.loc[lot_idx].geometry
        edges = street_facing_edges(gdf_utm, lot_idx)
        
        def find_edge_idx(poly, coord):
            coords = list(poly.exterior.coords)
            for i, c in enumerate(coords):
                if (abs(c[0]-coord[0]) < 1e-4) and (abs(c[1]-coord[1]) < 1e-4):
                    return i
            return 0
            
        front_indices = tuple([find_edge_idx(target_poly, e.start_xy) for e in edges] if edges else [])
        
        # Get cameras to pass to estimation
        lot_geom = gdf_utm.loc[lot_idx].geometry
        nearby_cams = gdf_cams_utm[gdf_cams_utm.geometry.intersects(lot_geom.buffer(15.0))]
        cams_list = nearby_cams.index.tolist()
        
        # 1. Run parameter extraction (Mock)
        params = estimate_parameters(lot_idx, cams_list)
        
        # Translate to origin
        cx, cy = target_poly.centroid.x, target_poly.centroid.y
        local_coords = tuple((c[0] - cx, c[1] - cy) for c in target_poly.exterior.coords)
        
        ctx = ParcelContext(polygon=local_coords, explicit_fronts=front_indices)
        program = BuildingProgram(
            use=params["use"], occupancy="medium", placement=params["placement"],
            architectural_language="informal", finish_profile=params["finish_profile"],
            maintenance="average", construction_state="completed",
            front_setback=0.0, side_setback=0.0,
            primary_color=params["primary_color"], seed=lot_idx,
            is_corner=(len(front_indices) > 1), has_fence=False, fence_type="none"
        )
        mass = MassSpec(
            id="main", footprint=local_coords, base_z=0.0, 
            roof_z=params["roof_z"], floor_levels=params["floor_levels"], 
            role="tower", roof_spec=None
        )
        site = SitePlan(masses=(mass,), free_space=(), access_nodes=(), boundaries=(), exclusion_zones=())
        spec = BuildingSpecificationV4(context=ctx, program=program, site_plan=site, facades=(), components=(), seed=lot_idx)
        
        mesh = generate_v4_mesh(spec)
        
        glb_filename = f"lot_{lot_idx}.glb"
        glb_path = ASSETS_DIR / glb_filename
        export_glb(mesh, glb_path)
        
        # Geographic centroid for Deck.gl placement
        poly_4326 = gdf_lots.loc[lot_idx:lot_idx].to_crs(epsg=4326).geometry.iloc[0]
        geo_centroid = poly_4326.centroid
        
        return {
            "status": "success",
            "url": f"/assets/{glb_filename}",
            "lat": geo_centroid.y,
            "lon": geo_centroid.x,
            "params": params
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
