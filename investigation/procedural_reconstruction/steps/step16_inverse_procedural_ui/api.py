import sys
import os
import json
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
import geopandas as gpd
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

print("Cargando datos espaciales...")
gdf_lots = gpd.read_file(GEOJSON_PATH)
gdf_utm = gdf_lots.to_crs(epsg=32718)

# Mount static files for assets
app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR)), name="assets")

@app.get("/")
def read_root():
    return FileResponse(str(STATIC_DIR / "index.html"))

@app.get("/api/lots")
def get_lots():
    # Return a simplified geojson for the frontend map to render quickly
    # We only need a subset or we can send the whole thing (it's around 14k polygons)
    # Let's send the whole thing but only the geometry and id
    gdf_minimal = gdf_lots[['geometry']].copy()
    gdf_minimal['id'] = gdf_minimal.index
    if gdf_minimal.crs and gdf_minimal.crs.to_epsg() != 4326:
        gdf_minimal = gdf_minimal.to_crs(epsg=4326)
    return JSONResponse(content=json.loads(gdf_minimal.to_json()))

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
        
        # Translate to origin
        cx, cy = target_poly.centroid.x, target_poly.centroid.y
        local_coords = tuple((c[0] - cx, c[1] - cy) for c in target_poly.exterior.coords)
        
        ctx = ParcelContext(polygon=local_coords, explicit_fronts=front_indices)
        program = BuildingProgram(
            use="residential", occupancy="medium", placement="flush",
            architectural_language="informal", finish_profile="plastered",
            maintenance="average", construction_state="completed",
            front_setback=0.0, side_setback=0.0,
            primary_color=(0.8, 0.8, 0.8), seed=42,
            is_corner=(len(front_indices) > 1), has_fence=False, fence_type="none"
        )
        mass = MassSpec(id="main", footprint=local_coords, base_z=0.0, roof_z=6.0, floor_levels=(0.0, 3.0, 6.0), role="tower", roof_spec=None)
        site = SitePlan(masses=(mass,), free_space=(), access_nodes=(), boundaries=(), exclusion_zones=())
        spec = BuildingSpecificationV4(context=ctx, program=program, site_plan=site, facades=(), components=(), seed=42)
        
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
            "lon": geo_centroid.x
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
