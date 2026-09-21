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


ALIGNMENT_PATH = ROOT / "steps" / "step16_inverse_procedural_ui" / "alignment.json"

print("Cargando datos espaciales y aplicando desfase...")
try:
    with open(ALIGNMENT_PATH, "r") as f:
        align_data = json.load(f)
        offset_x = align_data.get("east_m", 0.0)
        offset_y = align_data.get("north_m", 0.0)
except Exception:
    offset_x, offset_y = 0.0, 0.0

gdf_lots = gpd.read_file(GEOJSON_PATH)
gdf_utm_raw = gdf_lots.to_crs(epsg=32718)

# Aplicar desfase a todo
gdf_utm = gdf_utm_raw.copy()
gdf_utm.geometry = gdf_utm.geometry.translate(xoff=offset_x, yoff=offset_y)
gdf_lots = gdf_utm.to_crs(epsg=4326)


print("Cargando metadatos de cámaras...")
with open(METADATA_PATH, "r") as f:
    meta = json.load(f)
df_cams = pd.DataFrame.from_dict(meta["panoramas"], orient='index')
gdf_cams = gpd.GeoDataFrame(df_cams, geometry=gpd.points_from_xy(df_cams.lon, df_cams.lat), crs="EPSG:4326")
gdf_cams_utm = gdf_cams.to_crs(epsg=32718)

app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR)), name="assets")
app.mount("/cache", StaticFiles(directory=str(CACHE_DIR)), name="cache")

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


from pydantic import BaseModel
class OffsetModel(BaseModel):
    x: float
    y: float

@app.post("/api/offset")
def update_offset(offset: OffsetModel):
    global gdf_utm, gdf_lots, offset_x, offset_y
    offset_x = offset.x
    offset_y = offset.y
    gdf_utm = gdf_utm_raw.copy()
    gdf_utm.geometry = gdf_utm.geometry.translate(xoff=offset_x, yoff=offset_y)
    gdf_lots = gdf_utm.to_crs(epsg=4326)
    
    # Save to file
    try:
        with open(ALIGNMENT_PATH, "r") as f:
            align_data = json.load(f)
    except:
        align_data = {}
    align_data["east_m"] = offset_x
    align_data["north_m"] = offset_y
    with open(ALIGNMENT_PATH, "w") as f:
        json.dump(align_data, f, indent=2)
        
    return {"status": "success", "x": offset_x, "y": offset_y}

@app.get("/api/offset")
def get_offset():
    return {"x": offset_x, "y": offset_y}

@app.get("/api/cameras")
def get_all_cameras():
    cameras = []
    for pano_id, row in gdf_cams_utm.iterrows():
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


def get_explicit_fronts(lot_idx: int, target_poly, gdf_utm):
    import numpy as np
    from shapely.geometry import Point, LineString
    
    coords = list(target_poly.exterior.coords)
    front_indices = []
    
    minx, miny, maxx, maxy = target_poly.bounds
    possible_matches_index = list(gdf_utm.sindex.intersection((minx-5, miny-5, maxx+5, maxy+5)))
    other_lots = gdf_utm.iloc[possible_matches_index]
    other_lots = other_lots[other_lots.index != lot_idx]
    
    for i in range(len(coords) - 1):
        p1 = np.array(coords[i])
        p2 = np.array(coords[i+1])
        
        mid = (p1 + p2) / 2.0
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        length = np.hypot(dx, dy)
        if length == 0: continue
        
        # Normals
        nx = dx / length
        ny = dy / length
        
        # Mover 0.5 metros exactos afuera
        is_ccw = target_poly.exterior.is_ccw
        if is_ccw:
            outward_vec = np.array([ny, -nx])
        else:
            outward_vec = np.array([-ny, nx])
            
        outward_pt = Point(mid[0] + outward_vec[0] * 0.5, mid[1] + outward_vec[1] * 0.5)
        
        # Preguntamos si ese punto cae DENTRO de un lote vecino
        is_party_wall = False
        for _, other_row in other_lots.iterrows():
            if other_row.geometry.intersects(outward_pt):
                is_party_wall = True
                break
                
        if not is_party_wall:
            front_indices.append(i)
            
    return tuple(front_indices)

@app.get("/api/preview_fronts/{lot_idx}")
def preview_fronts(lot_idx: int):
    import geopandas as gpd
    import numpy as np
    from shapely.geometry import LineString, Point
    import json
    
    if lot_idx not in gdf_utm.index:
        raise HTTPException(status_code=404, detail="Lot not found")
        
    target_poly = gdf_utm.loc[lot_idx].geometry
    
    # We will recalculate here just to get the points for the UI
    coords = list(target_poly.exterior.coords)
    features = []
    
    minx, miny, maxx, maxy = target_poly.bounds
    possible_matches = list(gdf_utm.sindex.intersection((minx-5, miny-5, maxx+5, maxy+5)))
    other_lots = gdf_utm.iloc[possible_matches]
    other_lots = other_lots[other_lots.index != lot_idx]
    
    for i in range(len(coords) - 1):
        p1 = np.array(coords[i])
        p2 = np.array(coords[i+1])
        
        mid = (p1 + p2) / 2.0
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        length = np.hypot(dx, dy)
        if length == 0: continue
        
        nx = dx / length
        ny = dy / length
        
        is_ccw = target_poly.exterior.is_ccw
        if is_ccw:
            outward_vec = np.array([ny, -nx])
        else:
            outward_vec = np.array([-ny, nx])
            
        outward_pt = Point(mid[0] + outward_vec[0] * 0.5, mid[1] + outward_vec[1] * 0.5)
        
        is_party_wall = False
        for _, other_row in other_lots.iterrows():
            if other_row.geometry.intersects(outward_pt):
                is_party_wall = True
                break
                
        is_front = not is_party_wall
        
        line = LineString([coords[i], coords[i+1]])
        features.append({
            "type": "Feature",
            "geometry": line.__geo_interface__,
            "properties": {
                "type": "edge",
                "is_front": is_front
            }
        })
        
        features.append({
            "type": "Feature",
            "geometry": outward_pt.__geo_interface__,
            "properties": {
                "type": "point",
                "is_front": is_front
            }
        })
        
    gdf_feats = gpd.GeoDataFrame.from_features(features, crs="EPSG:32718")
    gdf_feats_4326 = gdf_feats.to_crs(epsg=4326)
    
    return {"type": "FeatureCollection", "features": json.loads(gdf_feats_4326.to_json())["features"]}

@app.post("/api/generate/{lot_idx}")

def generate_model(lot_idx: int):
    try:
        if lot_idx not in gdf_utm.index:
            raise HTTPException(status_code=404, detail="Lot not found")
            
        target_poly = gdf_utm.loc[lot_idx].geometry
        front_indices = get_explicit_fronts(lot_idx, target_poly, gdf_utm)
        
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

@app.post("/api/download_camera/{pano_id}")
def download_camera(pano_id: str):
    from streetlevel import streetview
    
    cache_path = CACHE_DIR / f"{pano_id}.jpg"
    if cache_path.exists():
        return {"status": "success", "url": f"/cache/{pano_id}.jpg"}
        
    try:
        pano = streetview.find_panorama_by_id(pano_id, download_depth=False)
        if not pano:
            raise HTTPException(status_code=404, detail="Pano no encontrado en Google APIs")
        streetview.download_panorama(pano, str(cache_path))
        return {"status": "success", "url": f"/cache/{pano_id}.jpg"}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
