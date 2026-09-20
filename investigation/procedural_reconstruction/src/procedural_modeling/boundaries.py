from dataclasses import dataclass
from shapely.geometry import LineString, Polygon
from typing import List, Optional
from domain.architecture import ParcelContext, BuildingProgram, SitePlan
import numpy as np

@dataclass
class BoundarySpec:
    line: LineString
    kind: str # 'fence', 'solid_wall'
    height: float
    gate_u: Optional[float] = None
    gate_width: float = 0.0
    garage_u: Optional[float] = None
    garage_width: float = 0.0

def generate_boundaries(context: ParcelContext, program: BuildingProgram, site_plan: SitePlan) -> List[BoundarySpec]:
    boundaries = []
    
    # Calculate union of all mass footprints
    import shapely
    from shapely.ops import unary_union
    mass_polys = [shapely.geometry.Polygon(m.footprint) for m in site_plan.masses]
    built_area = unary_union(mass_polys)
    
    poly = shapely.geometry.Polygon(context.polygon)
    coords = list(poly.exterior.coords)
    
    for i in range(len(coords) - 1):
        p1 = np.array(coords[i])
        p2 = np.array(coords[i+1])
        line = LineString([p1, p2])
        
        # Determine if this segment is uncovered by buildings
        exposed_line = line.difference(built_area.buffer(1e-4))
        
        if exposed_line.is_empty:
            continue
            
        segments = [exposed_line] if exposed_line.geom_type == 'LineString' else exposed_line.geoms
        
        for seg in segments:
            c = list(seg.coords)
            sp1 = np.array(c[0])
            sp2 = np.array(c[-1])
            seg_length = np.linalg.norm(sp2 - sp1)
            
            # If it's the front edge (Y approx 0)
            if abs(sp1[1]) < 0.1 and abs(sp2[1]) < 0.1:
                boundaries.append(BoundarySpec(
                    line=seg,
                    kind="fence",
                    height=2.8,
                    gate_u=0.2, gate_width=1.0,     # Pedestrian
                    garage_u=1.5, garage_width=3.5  # Garage
                ))
            else:
                # Side medianera wall enclosing the yard
                boundaries.append(BoundarySpec(
                    line=seg,
                    kind="solid_wall",
                    height=2.8
                ))
                    
    return boundaries
