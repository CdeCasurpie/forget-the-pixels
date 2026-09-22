import sys
import os
import json
import random
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
import geopandas as gpd
import cv2
import numpy as np
import matplotlib.pyplot as plt
from shapely.geometry import Point
from shapely.ops import nearest_points
from pyproj import Transformer, Geod
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'src'))
from vision.projection.cylindrical import extract_full_vertical_strip
from vision.segmentation.roof_boundary import detect_roof_boundary
from vision.estimation.height import fit_height, predicted_row

import pandas as pd
from shapely.geometry import Point
import uvicorn

ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT / "src"))

from domain.architecture import ParcelContext, BuildingProgram, MassSpec, SitePlan, BuildingSpecificationV4
from modeling.grammar import generate_v4_mesh
from modeling.exporters.glb_exporter import export_glb

app = FastAPI(title="Procedural Barranco API")

from pydantic import BaseModel
class HeightRequest(BaseModel):
    pano_ids: list[str]

calculated_heights = {}

@app.post("/api/estimate_height/{lot_idx}")
def estimate_height(lot_idx: int, req: HeightRequest):
    if not req.pano_ids:
        return {"height_m": 6.0, "floors": 2}
        
    global calculated_heights, gdf_utm
    
    polygon = gdf_utm.loc[lot_idx].geometry
    to_geo = Transformer.from_crs('EPSG:32718', 'EPSG:4326', always_xy=True)
    geod = Geod(ellps='WGS84')
    
    observations = []
    fig, axes = plt.subplots(len(req.pano_ids), 2, figsize=(10, 4*len(req.pano_ids)), squeeze=False)
    
    for i, pano_id in enumerate(req.pano_ids):
        # 1. Load image
        img_path = str(CACHE_DIR / f"{pano_id}.jpg")
        bgr = cv2.imread(img_path)
        if bgr is None:
            continue
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        h, w = rgb.shape[:2]
        
        # 2. Get camera data
        cam_rows = gdf_cams_utm[gdf_cams_utm['pano_id'] == pano_id]
        if cam_rows.empty:
            continue
        cam_row = cam_rows.iloc[0]
        cam_x, cam_y = cam_row.geometry.x, cam_row.geometry.y
        cam_lon, cam_lat = cam_row['lon'], cam_row['lat']
        heading_deg = cam_row.get('heading_deg', 0.0) # Or however heading is stored
        if 'heading_deg' not in cam_row:
            # Fallback if heading is not found
            heading_deg = 0.0
            
        camera_point = Point(cam_x, cam_y)
        if polygon.covers(camera_point):
            continue
            
        # 3. Geometric math
        target = nearest_points(camera_point, polygon.boundary)[1]
        lon, lat = to_geo.transform(target.x, target.y)
        bearing, _, distance = geod.inv(cam_lon, cam_lat, lon, lat)
        yaw = (bearing - heading_deg + 180) % 360 - 180
        x_col = (.5 + yaw / 360) * w % w
        
        # 4. Extract strip and detect roof
        strip_width = 9
        cols = (int(round(x_col)) + np.arange(-(strip_width//2), strip_width//2+1)) % w
        base_y = h - 1 # rough bottom
        strip = rgb[:base_y+1, cols]
        
        roof = detect_roof_boundary(strip)
        cut, separation = roof['cut_y'], roof['separation']
        
        camera_height_m = 2.5
        height = camera_height_m + distance * np.tan((.5 - cut / h) * np.pi)
        usable = bool(separation >= 0.1 and 0 < cut < h/2 and 1 <= height <= 150)
        
        if usable:
            observations.append({
                'distance_m': distance,
                'image_height': h,
                'cut_y': cut,
                'separation': separation,
                'individual_height_m': float(height)
            })
        
        # 5. Plotting
        crop = extract_full_vertical_strip(rgb, yaw, 90, 600, h)
        axes[i, 0].imshow(crop)
        axes[i, 0].axvline(300, color='yellow', lw=1)
        axes[i, 0].plot(300, cut, 'rx', ms=12)
        axes[i, 0].axhline(cut, color='red', lw=.8)
        axes[i, 0].set_title(f'Pano {pano_id[:6]}... cut={cut}px; H={height:.1f}m; usable={usable}')
        
        axes[i, 1].imshow(strip, aspect='auto')
        axes[i, 1].axhline(cut, color='red')
        axes[i, 1].set_title(f'Strip {len(cols)}px | sep={separation:.3f}')
        
    fig.tight_layout()
    plot_path = f"steps/step16_inverse_procedural_ui/static/assets/height_plot_{lot_idx}.png"
    fig.savefig(plot_path, dpi=100)
    plt.close(fig)
    
    # 6. Fit height
    if len(observations) >= 2:
        try:
            fit = fit_height(observations, 2.5)
            final_h = fit['height_m']
        except Exception as e:
            final_h = sum(o['individual_height_m'] for o in observations) / len(observations)
    elif len(observations) == 1:
        final_h = observations[0]['individual_height_m']
    else:
        final_h = 6.0
        
    floors = max(1, int(final_h / 3.0))
    calculated_heights[lot_idx] = {"height_m": final_h, "floors": floors}
    
    return {
        "height_m": round(final_h, 2), 
        "floors": floors, 
        "plot_url": f"/assets/height_plot_{lot_idx}.png"
    }


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
    if lot_idx in calculated_heights:
        floors = calculated_heights[lot_idx]["floors"]
        roof_z = calculated_heights[lot_idx]["height_m"]
        # Distribute floors evenly
        floor_h = roof_z / floors
        floor_levels = tuple(float(i * floor_h) for i in range(floors + 1))
    else:
        floors = random.randint(1, 4)
        roof_z = floors * 3.0
        floor_levels = tuple(float(i * 3.0) for i in range(floors + 1))
    
    uses = ["residential", "commercial", "mixed"]
    # The grammar branches on exactly these two profiles; anything else silently
    # disabled balconies, plinths and premium window proportions.
    finish_profiles = ["standard", "premium"]
    side_wall_finishes = ["raw", "plastered"]
    placements = ["flush", "front_setback"]
    colors = [(0.9, 0.9, 0.9), (0.8, 0.7, 0.6), (0.6, 0.8, 0.7), (0.9, 0.6, 0.6)]

    return {
        "use": random.choice(uses),
        "finish_profile": random.choice(finish_profiles),
        "side_wall_finish": random.choice(side_wall_finishes),
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
    
    # Calculate Top K=4 cameras closest to the front edges
    front_lines = [feat["geometry"] for feat in features if feat["properties"].get("type") == "edge" and feat["properties"].get("is_front")]
    top_k_pano_ids = []
    
    if front_lines and not gdf_cams_utm.empty:
        from shapely.geometry import shape
        from shapely.ops import unary_union
        
        # Create a single geometry of all front edges
        front_geom = unary_union([shape(geom) for geom in front_lines])
        
        # Calculate distance from each camera to the front geometry
        distances = gdf_cams_utm.geometry.distance(front_geom)
        
        # Get the top 4 closest cameras
        closest_cams = gdf_cams_utm.loc[distances.nsmallest(4).index]
        top_k_pano_ids = closest_cams['pano_id'].tolist()
    
    return {
        "type": "FeatureCollection", 
        "features": json.loads(gdf_feats_4326.to_json())["features"],
        "top_cameras": top_k_pano_ids
    }

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
            side_wall_finish=params["side_wall_finish"],
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
