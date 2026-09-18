import numpy as np
from shapely.geometry import Polygon
from shapely.ops import triangulate
import random

from domain import BuildingSpecification, MeshData

def triangulate_polygon(polygon: Polygon, z_height: float) -> tuple[np.ndarray, np.ndarray]:
    triangles = triangulate(polygon)
    inside_triangles = []
    for tri in triangles:
        if polygon.contains(tri.centroid) or polygon.intersection(tri.centroid).area > 0 or polygon.distance(tri.centroid) < 1e-6:
            inside_triangles.append(tri)
            
    verts = []
    faces = []
    vert_idx = 0
    for tri in inside_triangles:
        coords = list(tri.exterior.coords)[:3]
        for x, y in coords:
            verts.append([x, y, z_height])
        faces.append([vert_idx, vert_idx+1, vert_idx+2])
        vert_idx += 3
    return np.array(verts, dtype=float), np.array(faces, dtype=int)

class MeshBuilder:
    def __init__(self):
        self.vertices = []
        self.faces = []
        self.materials = []
        self.mat_idx = {}

    def get_mat(self, name, color):
        if name not in self.mat_idx:
            self.mat_idx[name] = len(self.materials)
            self.materials.append({"name": name, "color": color})
        return self.mat_idx[name]

    def add_quad(self, p1, p2, p3, p4, mat_name, color):
        v = len(self.vertices)
        self.vertices.extend([p1, p2, p3, p4])
        mat = self.get_mat(mat_name, color)
        self.faces.append((v, v+1, v+2, mat))
        self.faces.append((v, v+2, v+3, mat))

    def add_facade_box(self, A, t, Z, n, u1, u2, v1, v2, w1, w2, mat_name, color):
        if u2 <= u1 or v2 <= v1: return
        def P(u, v, w): return A + u*t + v*Z + w*n
            
        p00_out = P(u1, v1, w2); p10_out = P(u2, v1, w2)
        p11_out = P(u2, v2, w2); p01_out = P(u1, v2, w2)
        
        p00_in = P(u1, v1, w1); p10_in = P(u2, v1, w1)
        p11_in = P(u2, v2, w1); p01_in = P(u1, v2, w1)
        
        self.add_quad(p00_out, p10_out, p11_out, p01_out, mat_name, color) # Front
        self.add_quad(p10_in, p00_in, p01_in, p11_in, mat_name, color)     # Back
        self.add_quad(p01_out, p11_out, p11_in, p01_in, mat_name, color)   # Top
        self.add_quad(p00_in, p10_in, p10_out, p00_out, mat_name, color)   # Bottom
        self.add_quad(p10_out, p10_in, p11_in, p11_out, mat_name, color)   # Right
        self.add_quad(p00_in, p00_out, p01_out, p01_in, mat_name, color)   # Left

def build_barranco_facade(mb: MeshBuilder, facade, spec_style, floors=2, floor_height=2.8):
    # Deterministic randomness for realistic variations
    edge_id_hash = hash(facade.edge_id) % 10000
    rng = random.Random(edge_id_hash)
    
    A = np.array([facade.vertex_a[0], facade.vertex_a[1], 0.0])
    B = np.array([facade.vertex_b[0], facade.vertex_b[1], 0.0])
    t = B - A
    width = np.linalg.norm(t)
    if width < 0.1: return
    t = t / width
    Z = np.array([0, 0, 1.0])
    n = np.array([t[1], -t[0], 0.0]) # Outward normal
    
    wall_color = [0.85, 0.82, 0.78]
    blind_wall_color = [0.75, 0.75, 0.72]
    trim_color = [0.95, 0.95, 0.95]
    glass_color = [0.15, 0.25, 0.35]
    door_color = [0.35, 0.20, 0.10]
    garage_color = [0.3, 0.3, 0.3]
    metal_color = [0.2, 0.2, 0.2]
    
    is_front = getattr(facade, 'is_front', False)
    
    # 1. Blind walls (medianeras)
    if not is_front:
        mb.add_facade_box(A, t, Z, n, 0, width, 0, floors*floor_height, -0.2, 0.0, "wall_blind", blind_wall_color)
        mb.add_facade_box(A, t, Z, n, 0, width, floors*floor_height, floors*floor_height+0.5, -0.2, 0.0, "wall_blind", blind_wall_color)
        return

    # 2. Retiro y Cerco
    if spec_style == "setback_fence":
        mb.add_facade_box(A, t, Z, n, 0, width, 0, 0.5, -0.2, 0.0, "fence_base", wall_color)
        # Brick columns
        x = 0
        while x < width:
            mb.add_facade_box(A, t, Z, n, x, min(x+0.4, width), 0, 2.5, -0.2, 0.05, "brick", [0.7, 0.4, 0.3])
            # Metal grilles between columns
            if x + 0.4 < width - 0.4:
                gw_start = x + 0.4
                gw_end = min(x + 2.0, width - 0.4)
                mb.add_facade_box(A, t, Z, n, gw_start, gw_end, 0.5, 2.4, -0.1, 0.0, "metal", metal_color)
                # Vertical bars
                bars = int((gw_end - gw_start) / 0.15)
                for b in range(bars):
                    bx = gw_start + (b + 0.5) * 0.15
                    mb.add_facade_box(A, t, Z, n, bx-0.02, bx+0.02, 0.5, 2.5, 0.0, 0.02, "metal", metal_color)
            x += 2.0
            
        if width > 3.0:
            # Garage in fence
            mb.add_facade_box(A, t, Z, n, width-2.8, width-0.4, 0, 2.5, -0.15, 0.0, "garage", garage_color)
        # Push back actual house
        A = A - 3.0 * n
        B = B - 3.0 * n

    # 3. Base Rustication (Sillares/Zócalo de piedra)
    block_w = 0.8
    x = 0
    while x < width:
        bw = min(block_w, width - x)
        if bw > 0.1:
            # Blocks with gaps
            mb.add_facade_box(A, t, Z, n, x, x+bw-0.05, 0, 0.8, 0.0, 0.08, "stone", [0.6, 0.6, 0.6])
        x += bw
    mb.add_facade_box(A, t, Z, n, 0, width, 0.8, 0.9, 0.0, 0.1, "trim", trim_color)
    
    # 4. Floors
    for floor in range(floors):
        v_base = floor * floor_height
        v_top = (floor + 1) * floor_height
        
        u_coords = [0.0, width]
        v_coords = [v_base, v_top]
        
        floor_openings = []
        for op in facade.openings:
            if v_base - 0.5 <= op.v_m < v_top:
                # Add some organic randomness to window positions
                u_shift = rng.uniform(-0.1, 0.1)
                floor_openings.append((max(0, op.u_m + u_shift), min(width, op.u_m + op.width_m + u_shift), op.v_m, op.v_m + op.height_m, op.kind))
                
        for op in floor_openings:
            u_coords.extend([op[0], op[1]])
            v_coords.extend([op[2], op[3]])
            
        u_coords = np.unique(np.clip(u_coords, 0, width))
        v_coords = np.unique(np.clip(v_coords, v_base, v_top))
        
        for i in range(len(u_coords)-1):
            for j in range(len(v_coords)-1):
                u1, u2 = u_coords[i], u_coords[i+1]
                v1, v2 = v_coords[j], v_coords[j+1]
                cu, cv = (u1+u2)/2, (v1+v2)/2
                
                in_opening = False
                for op in floor_openings:
                    if op[0] <= cu <= op[1] and op[2] <= cv <= op[3]:
                        in_opening = True
                        break
                if not in_opening:
                    mb.add_facade_box(A, t, Z, n, u1, u2, v1, v2, -0.2, 0.0, "wall", wall_color)

        for op in floor_openings:
            u1, u2, v1, v2, kind = op
            
            # Outer protruding frame
            mb.add_facade_box(A, t, Z, n, u1-0.1, u1+0.05, v1-0.1, v2+0.1, 0.0, 0.06, "trim", trim_color)
            mb.add_facade_box(A, t, Z, n, u2-0.05, u2+0.1, v1-0.1, v2+0.1, 0.0, 0.06, "trim", trim_color)
            mb.add_facade_box(A, t, Z, n, u1, u2, v2-0.05, v2+0.1, 0.0, 0.06, "trim", trim_color)
            
            if kind == "window" or kind == "wide_window":
                # Sill (alféizar)
                mb.add_facade_box(A, t, Z, n, u1-0.15, u2+0.15, v1, v1+0.1, 0.0, 0.12, "trim", trim_color)
                
                # Grilles (Rejas) for ground floor windows
                if floor == 0:
                    bars = int((u2 - u1) / 0.15)
                    for b in range(bars):
                        bx = u1 + (b + 0.5) * 0.15
                        mb.add_facade_box(A, t, Z, n, bx-0.02, bx+0.02, v1+0.1, v2-0.05, 0.02, 0.04, "metal", metal_color)
                        
                # AC Unit (Aire Acondicionado) randomness (20% chance per upper window)
                if floor > 0 and rng.random() < 0.2:
                    mb.add_facade_box(A, t, Z, n, u1+0.1, u1+0.7, v1-0.4, v1-0.05, 0.0, 0.35, "ac_unit", [0.9, 0.9, 0.9])
                    mb.add_facade_box(A, t, Z, n, u1+0.15, u1+0.65, v1-0.35, v1-0.1, 0.35, 0.34, "ac_fan", [0.2, 0.2, 0.2])

                # Inner frames and mullions
                mb.add_facade_box(A, t, Z, n, u1, u1+0.05, v1, v2, -0.1, 0.0, "frame", door_color)
                mb.add_facade_box(A, t, Z, n, u2-0.05, u2, v1, v2, -0.1, 0.0, "frame", door_color)
                
                mullion_count = 3 if kind == "wide_window" else 1
                for m in range(1, mullion_count+1):
                    um = u1 + m * (u2-u1)/(mullion_count+1)
                    mb.add_facade_box(A, t, Z, n, um-0.03, um+0.03, v1, v2, -0.1, 0.0, "frame", door_color)
                    
                mb.add_facade_box(A, t, Z, n, u1+0.05, u2-0.05, v1+0.1, v2-0.05, -0.12, -0.08, "glass", glass_color)
                
            elif kind == "balcony_window":
                mb.add_facade_box(A, t, Z, n, u1+0.05, u2-0.05, v1, v2-0.05, -0.12, -0.08, "glass", glass_color)
                mb.add_facade_box(A, t, Z, n, u1-0.4, u2+0.4, v1, v1+0.2, 0.0, 0.8, "trim", trim_color)
                # Railing geometric bars
                mb.add_facade_box(A, t, Z, n, u1-0.4, u2+0.4, v1+0.9, v1+1.0, 0.75, 0.8, "metal", metal_color)
                bars = int((u2 - u1 + 0.8) / 0.15)
                for b in range(bars):
                    bx = u1 - 0.4 + (b + 0.5) * 0.15
                    mb.add_facade_box(A, t, Z, n, bx-0.02, bx+0.02, v1+0.2, v1+0.9, 0.76, 0.79, "metal", metal_color)
                mb.add_facade_box(A, t, Z, n, u1-0.4, u1-0.35, v1+0.2, v1+1.0, 0.0, 0.8, "metal", metal_color)
                mb.add_facade_box(A, t, Z, n, u2+0.35, u2+0.4, v1+0.2, v1+1.0, 0.0, 0.8, "metal", metal_color)
                
            elif kind == "storefront":
                mb.add_facade_box(A, t, Z, n, u1, u2, v1, v2, -0.1, 0.0, "glass", glass_color)
                # Roll-up door box at top
                mb.add_facade_box(A, t, Z, n, u1-0.1, u2+0.1, v2-0.4, v2+0.1, 0.0, 0.3, "metal", metal_color)
                
            elif kind == "garage":
                # Garage door with horizontal panels
                panels = 5
                for p in range(panels):
                    pv1 = v1 + p * (v2-v1)/panels
                    pv2 = v1 + (p+1) * (v2-v1)/panels
                    mb.add_facade_box(A, t, Z, n, u1, u2, pv1+0.02, pv2-0.02, -0.1, 0.0, "garage", garage_color)
                
            elif kind == "door":
                # Wooden door with panels
                mb.add_facade_box(A, t, Z, n, u1+0.05, u2-0.05, v1, v2-0.05, -0.12, -0.05, "door", door_color)
                mb.add_facade_box(A, t, Z, n, u1+0.15, u2-0.15, v1+0.2, v1+0.8, -0.13, -0.06, "door_panel", [0.4, 0.25, 0.15])
                mb.add_facade_box(A, t, Z, n, u1+0.15, u2-0.15, v1+1.0, v2-0.2, -0.13, -0.06, "door_panel", [0.4, 0.25, 0.15])

        # Cornice with details (Dentils)
        if floor < floors - 1:
            mb.add_facade_box(A, t, Z, n, -0.1, width+0.1, v_top-0.2, v_top, 0.0, 0.15, "trim", trim_color)
            # Add dentils (pequeños bloques decorativos)
            dx = 0
            while dx < width:
                mb.add_facade_box(A, t, Z, n, dx, dx+0.1, v_top-0.3, v_top-0.2, 0.0, 0.1, "trim", trim_color)
                dx += 0.3

    # 5. Roof Parapet and Details
    roof_height = floors * floor_height
    mb.add_facade_box(A, t, Z, n, 0, width, roof_height, roof_height+0.8, -0.2, 0.0, "wall", wall_color)
    # Alero (Overhang)
    mb.add_facade_box(A, t, Z, n, -0.2, width+0.2, roof_height+0.8, roof_height+1.0, -0.3, 0.4, "trim", trim_color)
    
    # 6. Pilasters
    mb.add_facade_box(A, t, Z, n, 0, 0.4, 0, roof_height, 0.0, 0.1, "trim", trim_color)
    mb.add_facade_box(A, t, Z, n, width-0.4, width, 0, roof_height, 0.0, 0.1, "trim", trim_color)

    # 7. Water Tank (Rotoplas)
    if width > 2.5:
        rotoplas_u = width / 2.0
        # Draw it behind the parapet
        mb.add_facade_box(A, t, Z, n, rotoplas_u-0.6, rotoplas_u+0.6, roof_height, roof_height+1.2, -3.0, -1.8, "rotoplas", [0.1, 0.1, 0.1])
        mb.add_facade_box(A, t, Z, n, rotoplas_u-0.4, rotoplas_u+0.4, roof_height+1.2, roof_height+1.4, -2.8, -2.0, "rotoplas", [0.1, 0.1, 0.1])

def generate_mesh(spec: BuildingSpecification) -> MeshData:
    mb = MeshBuilder()
    floors = spec.height.floor_count or 2
    floor_height = spec.height.floor_height_m or 2.8
    style = spec.metadata.get("style", "residential_direct")
    
    for facade in spec.facade_edges:
        build_barranco_facade(mb, facade, style, floors=floors, floor_height=floor_height)
        
    poly = Polygon(spec.footprint_xy)
    total_height = floors * floor_height
    
    r_verts, r_faces = triangulate_polygon(poly, total_height)
    if len(r_verts) > 0:
        v_offset = len(mb.vertices)
        mb.vertices.extend(r_verts)
        mat = mb.get_mat("roof", [0.3, 0.3, 0.3])
        for f in r_faces:
            mb.faces.append((v_offset + f[0], v_offset + f[1], v_offset + f[2], mat))
            
    f_verts, f_faces = triangulate_polygon(poly, 0.0)
    if len(f_verts) > 0:
        v_offset = len(mb.vertices)
        mb.vertices.extend(f_verts)
        mat = mb.get_mat("floor", [0.2, 0.2, 0.2])
        for f in f_faces:
            mb.faces.append((v_offset + f[2], v_offset + f[1], v_offset + f[0], mat))
            
    return MeshData(
        vertices=np.array(mb.vertices, dtype=float),
        faces=np.array([[f[0], f[1], f[2]] for f in mb.faces], dtype=int),
        face_materials=np.array([f[3] for f in mb.faces], dtype=int),
        materials=tuple(mb.materials)
    )
