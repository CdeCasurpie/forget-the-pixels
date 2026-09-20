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
    if not getattr(program, 'has_fence', True):
        return []
        
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
            
            # The front edge of the parcel is always near y=0 in our coordinate system
            is_front = (abs(sp1[1]) < 0.1 and abs(sp2[1]) < 0.1)
            
            # If it's a corner lot, x=0 is also a street edge
            is_side_street = getattr(program, 'is_corner', False) and (abs(sp1[0]) < 0.1 and abs(sp2[0]) < 0.1)
            
            is_street = is_front or is_side_street
            
            if is_street:
                boundaries.append(BoundarySpec(
                    line=seg,
                    kind=getattr(program, 'fence_type', 'reja'),
                    height=3.2,
                    gate_u=0.2 if is_front else None, 
                    gate_width=1.0,
                    garage_u=1.5 if is_front else None, 
                    garage_width=3.5
                ))
            # WE NO LONGER GENERATE BOUNDARIES FOR NON-STREET EDGES!
            # (Neighbouring houses are assumed to enclose the lot)
                    
    return boundaries
