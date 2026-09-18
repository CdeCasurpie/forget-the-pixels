import sys
from pathlib import Path
sys.path.append(str(Path("src").resolve()))

import geopandas as gpd
from domain.models import BuildingSpecification, FacadeSpecification, Opening, HeightEstimate, RoofSpecification
from procedural_modeling.grammar import generate_mesh
from exporters.obj_exporter import export_obj

import numpy as np
import random

def run():
    print("Loading cadastre...")
    shp_path = "../Lotes/shp_files/BARRANCO_LM_geogpsperu_SuyoPomalia.shp"
    gdf = gpd.read_file(shp_path)
    if gdf.crs.to_epsg() != 32718:
        gdf = gdf.to_crs(epsg=32718)
        
    target_lots = [1134711, 1134712, 1135743]
    
    # We will simulate different Barranco typologies for each lot
    styles = {
        1134711: {"floors": 2, "style": "setback_fence"},
        1134712: {"floors": 3, "style": "storefront"},
        1135743: {"floors": 4, "style": "residential_direct"}
    }
    
    for objectid in target_lots:
        row = gdf[gdf['objectid'] == objectid]
        if row.empty:
            row = gdf[gdf['objectid'] == objectid]
            if row.empty:
                print(f"Lot {objectid} not found!")
                continue
            
        geom = row.geometry.iloc[0]
        centroid = geom.centroid
        coords = np.array(geom.exterior.coords)
        local_coords = coords - [centroid.x, centroid.y]
        
        style_info = styles.get(objectid, {"floors": 2, "style": "residential_direct"})
        floors = style_info["floors"]
        style = style_info["style"]
        
        height_est = HeightEstimate(
            continuous_height_m=floors * 2.8,
            reprojection_rmse_px=0.0,
            used_pano_ids=(),
            regularized_height_m=floors * 2.8,
            floor_count=floors,
            floor_height_m=2.8
        )
        
        # Identify the "front" edge. Usually the shortest edge facing a street, 
        # or we just pick edge 0 for this test.
        # Actually, let's find the edge closest to the bottom of the bounding box as a simple heuristic,
        # or just edge 0.
        front_idx = 0
        
        facades = []
        for i in range(len(local_coords) - 1):
            A = local_coords[i]
            B = local_coords[i+1]
            dx, dy = B[0] - A[0], B[1] - A[1]
            width = np.hypot(dx, dy)
            if width < 0.1:
                continue
            normal = (dy/width, -dx/width)
            
            is_front = (i == front_idx)
            openings = []
            
            # Barranco rules: Only put windows on the front (or back), side walls are usually blind in Lima
            if is_front:
                if style == "storefront":
                    # Ground floor is a big business (bodega)
                    openings.append(Opening(kind="storefront", u_m=0.2, v_m=0.0, width_m=width-0.4, height_m=2.5, recess_m=0.2))
                    # Upper floors have wide windows
                    for f in range(1, floors):
                        openings.append(Opening(kind="wide_window", u_m=0.5, v_m=f*2.8 + 1.0, width_m=width-1.0, height_m=1.4, recess_m=0.1))
                
                elif style == "setback_fence":
                    # The actual facade will be pushed back in grammar.py, but for openings:
                    # Ground floor: Door and window
                    openings.append(Opening(kind="door", u_m=1.0, v_m=0.0, width_m=1.0, height_m=2.2, recess_m=0.1))
                    openings.append(Opening(kind="window", u_m=2.5, v_m=1.0, width_m=1.5, height_m=1.2, recess_m=0.1))
                    # Upper floor: Balcony window
                    for f in range(1, floors):
                        openings.append(Opening(kind="balcony_window", u_m=2.0, v_m=f*2.8 + 0.2, width_m=2.0, height_m=2.0, recess_m=0.1))
                        
                elif style == "residential_direct":
                    # Direct to street
                    openings.append(Opening(kind="garage", u_m=0.5, v_m=0.0, width_m=2.5, height_m=2.4, recess_m=0.1))
                    if width > 4.0:
                        openings.append(Opening(kind="door", u_m=3.5, v_m=0.0, width_m=1.0, height_m=2.2, recess_m=0.1))
                    
                    for f in range(1, floors):
                        bay_width = width / max(1, round(width / 3.0))
                        for b in range(max(1, round(width / 3.0))):
                            u_c = (b + 0.5) * bay_width
                            if b % 2 == 0:
                                openings.append(Opening(kind="window", u_m=u_c-0.6, v_m=f*2.8 + 1.0, width_m=1.2, height_m=1.4, recess_m=0.1))
                            else:
                                openings.append(Opening(kind="balcony_window", u_m=u_c-0.8, v_m=f*2.8 + 0.2, width_m=1.6, height_m=2.0, recess_m=0.1))
            else:
                # Side walls are blind in Lima row-houses!
                pass
                
            facades.append(FacadeSpecification(
                edge_id=f"edge_{i}",
                vertex_a=tuple(A),
                vertex_b=tuple(B),
                width_m=width,
                normal_xy=normal,
                floor_levels_m=tuple(f*2.8 for f in range(floors+1)),
                openings=tuple(openings),
                is_front=is_front
            ))
            
        spec = BuildingSpecification(
            footprint_xy=tuple(map(tuple, local_coords)),
            crs="EPSG:32718",
            height=height_est,
            facade_edges=tuple(facades),
            roof=RoofSpecification(kind="flat"),
            metadata={"style": style}
        )
        
        mesh = generate_mesh(spec)
        out_path = Path(f"steps/step10_procedural_generation_test/outputs/lot_{objectid}.obj")
        export_obj(mesh, out_path, y_up=True)
        print(f"Exported {out_path} with {len(mesh.vertices)} vertices and {len(mesh.faces)} faces.")

if __name__ == "__main__":
    run()
