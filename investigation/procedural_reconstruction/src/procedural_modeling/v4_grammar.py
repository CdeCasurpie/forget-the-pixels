import numpy as np
from domain.architecture import BuildingSpecificationV4
from domain.models import MeshData, Opening
from procedural_modeling.mesh_builder import MeshBuilder
from procedural_modeling.exposure import calculate_mass_exposures
from shapely.geometry import Polygon, LineString, Point

from procedural_modeling.materials import appearance_for_style

def generate_v4_mesh(spec: BuildingSpecificationV4) -> MeshData:
    # Convert program color (0.0 - 1.0) to RGB (0-255) for the legacy appearance function
    r, g, b = spec.program.primary_color
    rgb_255 = (int(r * 255), int(g * 255), int(b * 255))
    appearance = appearance_for_style(spec.program.architectural_language, rgb_255, spec.seed)
    
    builder = MeshBuilder(Polygon(spec.context.polygon), appearance)
    
    # Calculate exposures to know what is exterior
    exposures = calculate_mass_exposures(spec.site_plan)
    
    for mass in spec.site_plan.masses:
        mass_exposure = exposures[mass.id]
        
        # 1. Draw exterior walls by Z-bands
        for wall_band in mass_exposure["walls"]:
            z_bottom = wall_band["z_bottom"]
            z_top = wall_band["z_top"]
            segments = wall_band["exposed_segments"]
            
            # Extract line coordinates
            lines = [segments] if segments.geom_type == 'LineString' else segments.geoms
            for line in lines:
                coords = list(line.coords)
                for i in range(len(coords) - 1):
                    p1 = coords[i]
                    p2 = coords[i+1]
                    # Basic wall extrusion using builder.box for proper thickness
                    a = np.array(p1)
                    b = np.array(p2)
                    t_vec = b - a
                    length = np.linalg.norm(t_vec)
                    if length < 1e-4: continue
                    t_vec /= length
                    n_vec = np.array([t_vec[1], -t_vec[0]])
                    
                    # Ensure n_vec points OUTWARDS
                    from shapely.geometry import Point
                    mid = a + t_vec * (length / 2.0)
                    mass_poly = Polygon(mass.footprint)
                    if mass_poly.contains(Point(mid + n_vec * 0.01)):
                        n_vec = -n_vec
                    
                    from procedural_modeling.programs import generate_facade_openings
                    
                    prog = "commercial" if mass.role == "podium" else "residential"
                    openings = generate_facade_openings(length, tuple(mass.floor_levels), prog, z_bottom, z_top)
                    
                    # Determine wall material
                    if n_vec[1] < -0.5:
                        wall_mat = "plaster" # Front facade is always plastered/painted
                    else:
                        # Side/Back walls depend on the program finish
                        wall_mat = "plaster" if spec.program.side_wall_finish == "plastered" else "brick"
                    
                    if not openings:
                        builder.box(a, t_vec, n_vec, 0.0, length, z_bottom, z_top, -0.20, 0.0, wall_mat, "wall")
                    else:
                        builder.box(a, t_vec, n_vec, 0.0, length, z_bottom, z_top, -0.20, -0.10, wall_mat, "wall")
                        
                        for op in openings:
                            op_z = z_bottom + op.v
                            if op.kind == "shopfront":
                                builder.box(a, t_vec, n_vec, op.u, op.u + op.width, op_z, op_z + op.height, -0.10, 0.0, "metal", "shopfront")
                                builder.box(a, t_vec, n_vec, op.u - 0.1, op.u + op.width + 0.1, op_z + op.height, op_z + op.height + 0.2, -0.1, 0.8, "metal", "canopy")
                            else:
                                builder.box(a, t_vec, n_vec, op.u, op.u + op.width, op_z, op_z + op.height, -0.15, -0.12, "glass", "window")
                                builder.box(a, t_vec, n_vec, op.u - 0.05, op.u + op.width + 0.05, op_z - 0.05, op_z + op.height + 0.05, -0.16, 0.05, "frame", "frame")
                    
        # 2. Draw exposed roofs and parapets (and Phase 7: Calaminas)
        roof_data = mass_exposure.get("roof")
        if roof_data and roof_data["exposed_area"]:
            roof_z = roof_data["z"]
            exposed_area = roof_data["exposed_area"]
            
            polys = [exposed_area] if exposed_area.geom_type == 'Polygon' else exposed_area.geoms
            for poly in polys:
                builder.solid(poly, roof_z - 0.2, roof_z, material="concrete")
                builder.solid(poly.boundary.buffer(0.1, cap_style=2, join_style=2), roof_z, roof_z + 1.0, material="plaster")
                
                # Draw Exposed Rebars ("Fierros de espera")
                coords = list(poly.exterior.coords)
                for pt in coords[:-1]:
                    pt_poly = Point(pt).buffer(0.05, resolution=2)
                    builder.solid(pt_poly, roof_z, roof_z + 1.2, material="metal")
                    
                # Phase 7: Zinc Roofs (Calaminas) on top of the tower
                if mass.role == "tower":
                    # Draw thin wooden poles at the corners
                    for pt in coords[:-1]:
                        pole_poly = Point(pt).buffer(0.08, resolution=2)
                        builder.solid(pole_poly, roof_z, roof_z + 2.5, material="wood")
                    
                    # Draw a slanted zinc roof (calamina) slightly larger than the footprint
                    # We can approximate a slanted roof by extruding it and slicing it, or using builder.solid with a custom top height field.
                    # builder.solid accepts a callable for height: `def height(x, y)`
                    def slanted_roof(x, y):
                        # Slant upwards along the Y axis
                        return roof_z + 2.5 + (y - 10) * 0.1
                        
                    calamina_poly = poly.buffer(0.5, join_style=2)
                    builder.solid(calamina_poly, lambda x, y: slanted_roof(x, y) - 0.05, slanted_roof, material="metal")
                    
        # 3. Draw Boundaries (Fences, Walls, Gates - Phase 5)
        from procedural_modeling.boundaries import generate_boundaries
        boundaries = generate_boundaries(spec.context, spec.program, spec.site_plan)
        
        for bnd in boundaries:
            coords = list(bnd.line.coords)
            a = np.array(coords[0])
            b_pt = np.array(coords[1])
            t_vec = b_pt - a
            length = np.linalg.norm(t_vec)
            if length < 1e-4: continue
            t_vec /= length
            n_vec = np.array([t_vec[1], -t_vec[0]])
            
            # Ensure n_vec points OUTWARDS from the parcel
            mid = a + t_vec * (length / 2.0)
            parcel_poly = Polygon(spec.context.polygon)
            if parcel_poly.contains(Point(mid + n_vec * 0.01)):
                n_vec = -n_vec
                
            if bnd.kind == "fence":
                def is_gate(u):
                    if bnd.gate_u is not None and bnd.gate_u <= u <= bnd.gate_u + bnd.gate_width: return True
                    if bnd.garage_u is not None and bnd.garage_u <= u <= bnd.garage_u + bnd.garage_width: return True
                    return False
                
                # Low brick wall
                builder.box(a, t_vec, n_vec, 0.0, length, 0.0, 0.8, -0.15, 0.0, "brick", "wall")
                
                # Metal bars above (every 0.15m)
                for u_bar in np.arange(0.0, length, 0.15):
                    if not is_gate(u_bar):
                        builder.box(a, t_vec, n_vec, u_bar, u_bar + 0.03, 0.8, bnd.height, -0.08, -0.05, "metal", "fence")
                
                # Top horizontal rail (thicker for visibility)
                builder.box(a, t_vec, n_vec, 0.0, length, bnd.height - 0.10, bnd.height, -0.12, -0.01, "metal", "fence")
                
                # Solid Garage Door (Portón) with paneling
                if bnd.garage_u is not None:
                    # Frame/Columns
                    builder.box(a, t_vec, n_vec, bnd.garage_u - 0.1, bnd.garage_u, 0.0, bnd.height, -0.20, 0.05, "concrete", "column")
                    builder.box(a, t_vec, n_vec, bnd.garage_u + bnd.garage_width, bnd.garage_u + bnd.garage_width + 0.1, 0.0, bnd.height, -0.20, 0.05, "concrete", "column")
                    # Header
                    builder.box(a, t_vec, n_vec, bnd.garage_u - 0.1, bnd.garage_u + bnd.garage_width + 0.1, bnd.height - 0.2, bnd.height, -0.25, 0.10, "concrete", "header")
                    
                    # Horizontal panels for the door
                    for panel_z in np.arange(0.0, bnd.height - 0.2, 0.4):
                        builder.box(a, t_vec, n_vec, bnd.garage_u, bnd.garage_u + bnd.garage_width, panel_z, panel_z + 0.38, -0.15, 0.0, "metal", "gate")
                
                # Pedestrian Gate (Reja)
                if bnd.gate_u is not None:
                    builder.box(a, t_vec, n_vec, bnd.gate_u, bnd.gate_u + bnd.gate_width, 0.0, bnd.height, -0.10, 0.0, "metal", "gate")
                    # Frame
                    builder.box(a, t_vec, n_vec, bnd.gate_u - 0.05, bnd.gate_u, 0.0, bnd.height, -0.15, 0.05, "metal", "frame")
                    builder.box(a, t_vec, n_vec, bnd.gate_u + bnd.gate_width, bnd.gate_u + bnd.gate_width + 0.05, 0.0, bnd.height, -0.15, 0.05, "metal", "frame")
                    
            else:
                # Solid perimeter wall (Muro ciego)
                builder.box(a, t_vec, n_vec, 0.0, length, 0.0, bnd.height, -0.15, 0.0, "brick", "wall")
                
    return builder.finish()
