import numpy as np
from typing import Dict, Any, List
import shapely
from shapely.geometry import Polygon, MultiLineString, LineString
from shapely.ops import unary_union
from domain.architecture import MassSpec, SitePlan

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
        poly = Polygon(mass.footprint)
        clean_footprint = shapely.set_precision(poly, grid_size=tolerance)
        if not clean_footprint.is_valid:
            clean_footprint = clean_footprint.buffer(0)
        
        clean_masses.append({
            "id": mass.id,
            "footprint": clean_footprint,
            "base_z": mass.base_z,
            "roof_z": mass.roof_z
        })

    z_values = set()
    for m in clean_masses:
        z_values.add(m["base_z"])
        z_values.add(m["roof_z"])
    
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
            other_footprints = [other["footprint"] for other in present if other["id"] != m["id"]]
            
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
