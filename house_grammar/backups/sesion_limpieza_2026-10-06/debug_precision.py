import sys
import shapely
from pathlib import Path
sys.path.insert(0, str(Path("src").resolve()))
from shapely.geometry import Polygon, LineString, Point
from domain.theta import ThetaCandidate, MassingControls, SiteControls, ReconstructionContext
from modeling.theta import resolve_theta

def run_test():
    # Add a tiny epsilon to x
    parcel_coords = [(0.0, 0.0), (10.0000000000001, 0.0), (10.0000000000001, 20.0), (0.0, 20.0)]
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

run_test()
