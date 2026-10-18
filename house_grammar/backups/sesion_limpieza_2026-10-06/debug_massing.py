import sys
from pathlib import Path
sys.path.insert(0, str(Path("src").resolve()))
from shapely.geometry import Polygon, LineString, Point
from domain.theta import ThetaCandidate, MassingControls, SiteControls
from domain.theta import ReconstructionContext
from modeling.theta import resolve_theta

def run_test():
    parcel_coords = [(0, 0), (10, 0), (10, 20), (0, 20)]
    fronts = (0,)
    massing = MassingControls(
        pattern="front_tall_rear_low", front_setback_m=3.0,
        upper_setback_m=None, front_depth_m=6.0,
        low_floors=1, podium_floors=None
    )
    theta = ThetaCandidate(
        height_m=6.0, floors=2, family="mixed_use", primary_color=(1,1,1),
        massing=massing, schema_version="0.2"
    )
    p = ReconstructionContext(parcel=tuple(parcel_coords), fronts=fronts)
    resolved = resolve_theta(p, theta)
    print(f"Generated {len(resolved.walls)} walls.")
    for w in resolved.walls:
        print(f"  Wall {w.facade.edge_id} base_z={w.base_z} height={w.height_m} is_front={w.facade.is_front} material={w.facade.wall_material}")

run_test()

