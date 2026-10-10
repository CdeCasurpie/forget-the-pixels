import numpy as np
from typing import Dict, Any, List
import shapely
from shapely.geometry import Polygon, MultiLineString, LineString, Point
from shapely.ops import unary_union
from domain.architecture import MassSpec, SitePlan
from modeling.assembly import mass_polygon

def filter_lines(geom: shapely.Geometry) -> MultiLineString:
    """Extracts only linear components from a geometry to ignore precision-artifact points."""
    if geom.is_empty:
        return MultiLineString()
    if geom.geom_type == 'LineString':
        return MultiLineString([geom])
    elif geom.geom_type == 'MultiLineString':
        return geom
    elif geom.geom_type == 'GeometryCollection':
        lines = [g for g in geom.geoms if 'LineString' in g.geom_type]
        if not lines:
            return MultiLineString()
        return unary_union(lines)
    return MultiLineString()

def calculate_mass_exposures(site_plan: SitePlan, tolerance: float = 1e-4) -> Dict[str, Any]:
    """
    Calculates the exterior exposure of walls and roofs for a collection of masses.
    Evaluates exposure by horizontal Z-bands.
    
    Args:
        site_plan: A SitePlan object containing a tuple of MassSpec objects.
        tolerance: Grid size used for precision snapping to avoid floating-point issues.
        
    Returns:
        A dictionary mapping each MassSpec ID to its wall and roof exposures.
    """
    results = {
        mass.id: {"walls": [], "roof": None}
        for mass in site_plan.masses
    }

    clean_masses = []
    for mass in site_plan.masses:
        # Footprint is a tuple of tuples in MassSpec, convert to Polygon
        poly = mass_polygon(mass)
        clean_footprint = shapely.set_precision(poly, grid_size=tolerance)
        if not clean_footprint.is_valid:
            clean_footprint = clean_footprint.buffer(0)
        
        clean_masses.append({
            "id": mass.id,
            "footprint": clean_footprint,
            "base_z": mass.base_z,
            "roof_z": mass.roof_z,
            "kind": mass.kind,
            "levels": mass.floor_levels,
            "slab": mass.slab_m,
        })

    z_values = set()
    for m in clean_masses:
        z_values.add(m["base_z"])
        z_values.add(m["roof_z"])
        if m['kind']=='open':
            for z in m['levels'][1:]:
                z_values.update((z-m['slab'],z))
    
    sorted_z = sorted(list(z_values))
    merged_z = []
    for z in sorted_z:
        if not merged_z or (z - merged_z[-1]) > tolerance:
            merged_z.append(z)

    for i in range(len(merged_z) - 1):
        z_bottom = merged_z[i]
        z_top = merged_z[i+1]
        mid_z = (z_bottom + z_top) / 2.0
        
        present = [m for m in clean_masses if m["base_z"] <= mid_z and m["roof_z"] >= mid_z]
        
        for m in present:
            if m['kind']=='open':
                continue
            other_footprints = [other["footprint"] for other in present if other["id"] != m["id"]
                and (other['kind']=='enclosed' or any(z-other['slab']<=mid_z<=z for z in other['levels'][1:]))]
            
            if not other_footprints:
                exposed_boundary = m["footprint"].boundary
            else:
                other_union = unary_union(other_footprints)
                exposed_boundary = m["footprint"].boundary.difference(other_union)
            
            exposed_lines = filter_lines(exposed_boundary)
            
            if not exposed_lines.is_empty:
                results[m["id"]]["walls"].append({
                    "z_bottom": z_bottom,
                    "z_top": z_top,
                    "exposed_segments": exposed_lines
                })

    for m in clean_masses:
        roof_z = m["roof_z"]
        
        test_z = roof_z + (tolerance * 2)
        covering_masses = [
            other["footprint"] for other in clean_masses 
            if other["id"] != m["id"] and other["base_z"] <= test_z and other["roof_z"] > roof_z
            and other['kind']=='enclosed'
        ]
        
        if not covering_masses:
            exposed_roof = m["footprint"]
        else:
            covering_union = unary_union(covering_masses)
            exposed_roof = m["footprint"].difference(covering_union)
            
        results[m["id"]]["roof"] = {
            "z": roof_z,
            "exposed_area": exposed_roof
        }

    return results


def wall_domains(mass, masses, a, b):
    """Visible rectangles (u0,z0,u1,z1), z relative to mass base.

    Work on original edge coordinates. Only boolean adjacency gets a tiny
    tolerance; resnapping an oblique polyline must not erase its wall.
    Merge equal intervals vertically so unrelated bodies don't split a wall.
    """
    line=LineString([a,b]); length=line.length
    others=[m for m in masses if m.id!=mass.id]
    cuts={mass.base_z,mass.roof_z}
    for other in others:
        cuts.update(z for z in (other.base_z,other.roof_z) if mass.base_z<z<mass.roof_z)
        if other.kind=='open':
            cuts.update(z for level in other.floor_levels[1:] for z in (level-other.slab_m,level) if mass.base_z<z<mass.roof_z)
    domains=[]
    zs=sorted(cuts)
    for lo,hi in zip(zs,zs[1:]):
        mid=(lo+hi)/2
        blocking=[mass_polygon(m).buffer(1e-7) for m in others if m.base_z<mid<m.roof_z and
            (m.kind=='enclosed' or any(z-m.slab_m<mid<z for z in m.floor_levels[1:]))]
        visible=line.difference(unary_union(blocking)) if blocking else line
        for seg in ([visible] if visible.geom_type=='LineString' else getattr(visible,'geoms',())):
            if seg.geom_type!='LineString' or seg.length<1e-5:
                continue
            us=sorted(line.project(Point(p)) for p in seg.coords)
            u0,u1=us[0],us[-1]
            if u0<1e-6:u0=0.
            if length-u1<1e-6:u1=length
            previous=next((i for i,d in enumerate(domains) if abs(d[0]-u0)<1e-6 and abs(d[2]-u1)<1e-6 and abs(d[3]-(lo-mass.base_z))<1e-6),None)
            if previous is None:domains.append((u0,lo-mass.base_z,u1,hi-mass.base_z))
            else:domains[previous]=(u0,domains[previous][1],u1,hi-mass.base_z)
    return tuple(domains)
