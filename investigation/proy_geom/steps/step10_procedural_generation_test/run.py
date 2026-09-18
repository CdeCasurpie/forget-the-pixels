import sys
from pathlib import Path
sys.path.append(str(Path("src").resolve()))

import geopandas as gpd
from domain.models import BuildingSpecification, FacadeSpecification, Opening, HeightEstimate, RoofSpecification
from procedural_modeling.grammar import generate_mesh
from exporters.obj_exporter import export_obj
import numpy as np

def run():
    print("Loading cadastre...")
    shp_path = "../Lotes/shp_files/BARRANCO_LM_geogpsperu_SuyoPomalia.shp"
    gdf = gpd.read_file(shp_path)
    if gdf.crs.to_epsg() != 32718:
        gdf = gdf.to_crs(epsg=32718)
        
    target_lots = [1134711, 1134712, 1135743]
    
    for objectid in target_lots:
        row = gdf[gdf['objectid'] == objectid]
        if row.empty:
            row = gdf[gdf['objectid'] == objectid]
            if row.empty:
                continue
            
        geom = row.geometry.iloc[0]
        centroid = geom.centroid
        coords = np.array(geom.exterior.coords)
        local_coords = coords - [centroid.x, centroid.y]
        
        floors = 3 if objectid == 1135743 else 2
        floor_h = 2.8
        
        height_est = HeightEstimate(
            continuous_height_m=floors * floor_h,
            reprojection_rmse_px=0.0,
            used_pano_ids=(),
            regularized_height_m=floors * floor_h,
            floor_count=floors,
            floor_height_m=floor_h
        )
        
        facades = []
        for i in range(len(local_coords) - 1):
            A = local_coords[i]
            B = local_coords[i+1]
            dx, dy = B[0] - A[0], B[1] - A[1]
            width = np.hypot(dx, dy)
            if width < 0.1:
                continue
            normal = (dy/width, -dx/width)
            
            # Put windows on any edge longer than 3.5 meters
            is_front = width > 3.5
            openings = []
            
            if is_front:
                # Ground floor: Door and Windows
                # Door at 0.5m from the left
                openings.append(Opening(kind="door", u_m=0.5, v_m=0.0, width_m=1.0, height_m=2.2, recess_m=0.1))
                
                # Windows on the rest of the ground floor
                u_curr = 2.5
                while u_curr + 1.5 < width - 0.5:
                    openings.append(Opening(kind="window", u_m=u_curr, v_m=1.0, width_m=1.5, height_m=1.4, recess_m=0.1))
                    u_curr += 2.5 # Gap between windows
                    
                # Upper floors: Balconies and Windows
                for f in range(1, floors):
                    u_curr = 0.5
                    while u_curr + 1.5 < width - 0.5:
                        if u_curr == 0.5:
                            openings.append(Opening(kind="balcony_window", u_m=u_curr, v_m=f*floor_h + 0.2, width_m=1.5, height_m=2.0, recess_m=0.1))
                        else:
                            openings.append(Opening(kind="window", u_m=u_curr, v_m=f*floor_h + 1.0, width_m=1.5, height_m=1.4, recess_m=0.1))
                        u_curr += 2.5

            facades.append(FacadeSpecification(
                edge_id=f"edge_{i}",
                vertex_a=tuple(A),
                vertex_b=tuple(B),
                width_m=width,
                normal_xy=normal,
                floor_levels_m=tuple(f*floor_h for f in range(floors+1)),
                openings=tuple(openings),
                is_front=is_front
            ))
            
        spec = BuildingSpecification(
            footprint_xy=tuple(map(tuple, local_coords)),
            crs="EPSG:32718",
            height=height_est,
            facade_edges=tuple(facades),
            roof=RoofSpecification(kind="flat"),
            metadata={}
        )
        
        mesh = generate_mesh(spec)
        out_path = Path(f"steps/step10_procedural_generation_test/outputs/lot_{objectid}.obj")
        export_obj(mesh, out_path, y_up=True)
        print(f"Exported {out_path} with {len(mesh.vertices)} vertices and {len(mesh.faces)} faces.")

if __name__ == "__main__":
    run()
