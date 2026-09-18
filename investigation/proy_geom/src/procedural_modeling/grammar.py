import numpy as np
from shapely.geometry import Polygon, LinearRing
from shapely.ops import triangulate

from domain import BuildingSpecification, MeshData

def triangulate_polygon(polygon: Polygon, z_height: float) -> tuple[np.ndarray, np.ndarray]:
    triangles = triangulate(polygon)
    inside_triangles = []
    for tri in triangles:
        # Check if centroid is inside the original polygon
        if polygon.contains(tri.centroid) or polygon.distance(tri.centroid) < 1e-6:
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
        # Counter-clockwise winding
        self.faces.append((v, v+1, v+2, mat))
        self.faces.append((v, v+2, v+3, mat))

    def add_facade_box(self, A, t, Z, n, u1, u2, v1, v2, w1, w2, mat_name, color):
        if u2 <= u1 or v2 <= v1 or w2 <= w1: return
        def P(u, v, w): return A + u*t + v*Z + w*n
            
        # Outer face (w2)
        p00_out = P(u1, v1, w2); p10_out = P(u2, v1, w2)
        p11_out = P(u2, v2, w2); p01_out = P(u1, v2, w2)
        
        # Inner face (w1)
        p00_in = P(u1, v1, w1); p10_in = P(u2, v1, w1)
        p11_in = P(u2, v2, w1); p01_in = P(u1, v2, w1)
        
        self.add_quad(p00_out, p10_out, p11_out, p01_out, mat_name, color) # Front
        self.add_quad(p10_in, p00_in, p01_in, p11_in, mat_name, color)     # Back
        self.add_quad(p01_out, p11_out, p11_in, p01_in, mat_name, color)   # Top
        self.add_quad(p00_in, p10_in, p10_out, p00_out, mat_name, color)   # Bottom
        self.add_quad(p10_out, p10_in, p11_in, p11_out, mat_name, color)   # Right
        self.add_quad(p00_in, p00_out, p01_out, p01_in, mat_name, color)   # Left

def build_facade(mb: MeshBuilder, facade, is_ccw: bool, floors=2, floor_height=2.8):
    A = np.array([facade.vertex_a[0], facade.vertex_a[1], 0.0])
    B = np.array([facade.vertex_b[0], facade.vertex_b[1], 0.0])
    t = B - A
    width = np.linalg.norm(t)
    if width < 0.1: return
    t = t / width
    Z = np.array([0, 0, 1.0])
    
    # Calculate outward normal based on polygon winding
    if is_ccw:
        n = np.array([t[1], -t[0], 0.0]) # Outward for CCW
    else:
        n = np.array([-t[1], t[0], 0.0]) # Outward for CW
        
    # Greyscale colors for structural clarity (no blues/browns)
    c_wall = [0.95, 0.95, 0.95]
    c_blind = [0.90, 0.90, 0.90]
    c_trim = [0.85, 0.85, 0.85]
    c_frame = [0.75, 0.75, 0.75]
    c_glass = [0.60, 0.60, 0.60]
    c_metal = [0.50, 0.50, 0.50]
    
    is_front = getattr(facade, 'is_front', False)
    
    # Blind wall
    if not is_front:
        mb.add_facade_box(A, t, Z, n, 0, width, 0, floors*floor_height, -0.2, 0.0, "wall", c_blind)
        # Parapet for blind wall
        mb.add_facade_box(A, t, Z, n, 0, width, floors*floor_height, floors*floor_height+0.8, -0.2, 0.0, "wall", c_blind)
        return

    # Base wall grid
    for floor in range(floors):
        v_base = floor * floor_height
        v_top = (floor + 1) * floor_height
        
        u_coords = [0.0, width]
        v_coords = [v_base, v_top]
        
        # Filter openings for this floor
        floor_openings = []
        for op in facade.openings:
            if v_base - 0.5 <= op.v_m < v_top:
                floor_openings.append(op)
                u_coords.extend([op.u_m, op.u_m + op.width_m])
                v_coords.extend([op.v_m, op.v_m + op.height_m])
                
        u_coords = np.unique(np.clip(u_coords, 0, width))
        v_coords = np.unique(np.clip(v_coords, v_base, v_top))
        
        # Wall blocks
        for i in range(len(u_coords)-1):
            for j in range(len(v_coords)-1):
                u1, u2 = u_coords[i], u_coords[i+1]
                v1, v2 = v_coords[j], v_coords[j+1]
                cu, cv = (u1+u2)/2, (v1+v2)/2
                
                in_opening = False
                for op in floor_openings:
                    if op.u_m <= cu <= op.u_m + op.width_m and op.v_m <= cv <= op.v_m + op.height_m:
                        in_opening = True
                        break
                if not in_opening:
                    # Wall starts at w=-0.2 (inward) and ends at w=0.0 (facade line)
                    mb.add_facade_box(A, t, Z, n, u1, u2, v1, v2, -0.2, 0.0, "wall", c_wall)

        # Openings logic
        for op in floor_openings:
            u1, u2 = op.u_m, op.u_m + op.width_m
            v1, v2 = op.v_m, op.v_m + op.height_m
            
            # PROTRUDING Trim Frame (w from 0.0 to 0.08) - goes OUTSIDE the house
            mb.add_facade_box(A, t, Z, n, u1-0.1, u1+0.05, v1-0.1, v2+0.1, 0.0, 0.08, "trim", c_trim)
            mb.add_facade_box(A, t, Z, n, u2-0.05, u2+0.1, v1-0.1, v2+0.1, 0.0, 0.08, "trim", c_trim)
            mb.add_facade_box(A, t, Z, n, u1, u2, v2-0.05, v2+0.1, 0.0, 0.08, "trim", c_trim)
            
            if op.kind == "window":
                # Sill (alféizar) - protruding more
                mb.add_facade_box(A, t, Z, n, u1-0.15, u2+0.15, v1, v1+0.1, 0.0, 0.15, "trim", c_trim)
                
                # Inner window frame (slightly recessed: -0.1 to 0.0)
                mb.add_facade_box(A, t, Z, n, u1, u1+0.05, v1, v2, -0.1, 0.0, "frame", c_frame)
                mb.add_facade_box(A, t, Z, n, u2-0.05, u2, v1, v2, -0.1, 0.0, "frame", c_frame)
                mb.add_facade_box(A, t, Z, n, u1, u2, v1, v1+0.05, -0.1, 0.0, "frame", c_frame)
                mb.add_facade_box(A, t, Z, n, u1, u2, v2-0.05, v2, -0.1, 0.0, "frame", c_frame)
                
                # Central Mullion
                um = (u1+u2)/2
                mb.add_facade_box(A, t, Z, n, um-0.03, um+0.03, v1, v2, -0.1, 0.0, "frame", c_frame)
                
                # Glass (deeply recessed: -0.15 to -0.1)
                mb.add_facade_box(A, t, Z, n, u1+0.05, u2-0.05, v1+0.05, v2-0.05, -0.15, -0.1, "glass", c_glass)
                
            elif op.kind == "balcony_window":
                # French Doors
                mb.add_facade_box(A, t, Z, n, u1, u1+0.05, v1, v2, -0.1, 0.0, "frame", c_frame)
                mb.add_facade_box(A, t, Z, n, u2-0.05, u2, v1, v2, -0.1, 0.0, "frame", c_frame)
                mb.add_facade_box(A, t, Z, n, u1+0.05, u2-0.05, v1, v2, -0.15, -0.1, "glass", c_glass)
                
                # Balcony Slab (protruding OUTWARD from 0.0 to 0.8)
                mb.add_facade_box(A, t, Z, n, u1-0.4, u2+0.4, v1, v1+0.15, 0.0, 0.8, "trim", c_trim)
                
                # Balcony Railing (Baranda geométrica)
                mb.add_facade_box(A, t, Z, n, u1-0.4, u2+0.4, v1+0.9, v1+1.0, 0.75, 0.8, "metal", c_metal)
                bars = int((u2 - u1 + 0.8) / 0.15)
                for b in range(bars):
                    bx = u1 - 0.4 + (b + 0.5) * 0.15
                    mb.add_facade_box(A, t, Z, n, bx-0.02, bx+0.02, v1+0.15, v1+0.9, 0.76, 0.8, "metal", c_metal)
                    
            elif op.kind == "door":
                mb.add_facade_box(A, t, Z, n, u1, u2, v1, v2, -0.1, 0.0, "frame", c_frame)
                mb.add_facade_box(A, t, Z, n, u1+0.05, u2-0.05, v1, v2-0.05, -0.15, -0.1, "glass", c_glass)

        # Floor separators / Cornices
        if floor < floors - 1:
            mb.add_facade_box(A, t, Z, n, 0, width, v_top-0.2, v_top, 0.0, 0.1, "trim", c_trim)

    # Parapet & Roof Alero
    roof_height = floors * floor_height
    mb.add_facade_box(A, t, Z, n, 0, width, roof_height, roof_height+0.8, -0.2, 0.0, "wall", c_wall)
    # Alero (Overhang) protruding outward by 0.4
    mb.add_facade_box(A, t, Z, n, -0.1, width+0.1, roof_height+0.8, roof_height+1.0, -0.3, 0.4, "trim", c_trim)

def generate_mesh(spec: BuildingSpecification) -> MeshData:
    mb = MeshBuilder()
    floors = spec.height.floor_count or 2
    floor_height = spec.height.floor_height_m or 2.8
    
    poly = Polygon(spec.footprint_xy)
    ring = LinearRing(spec.footprint_xy)
    is_ccw = ring.is_ccw
    
    for facade in spec.facade_edges:
        build_facade(mb, facade, is_ccw, floors=floors, floor_height=floor_height)
        
    total_height = floors * floor_height
    
    r_verts, r_faces = triangulate_polygon(poly, total_height)
    if len(r_verts) > 0:
        v_offset = len(mb.vertices)
        mb.vertices.extend(r_verts)
        mat = mb.get_mat("roof", [0.8, 0.8, 0.8])
        for f in r_faces:
            if is_ccw:
                mb.faces.append((v_offset + f[0], v_offset + f[1], v_offset + f[2], mat))
            else:
                mb.faces.append((v_offset + f[2], v_offset + f[1], v_offset + f[0], mat))
            
    f_verts, f_faces = triangulate_polygon(poly, 0.0)
    if len(f_verts) > 0:
        v_offset = len(mb.vertices)
        mb.vertices.extend(f_verts)
        mat = mb.get_mat("floor", [0.8, 0.8, 0.8])
        for f in f_faces:
            if is_ccw:
                mb.faces.append((v_offset + f[2], v_offset + f[1], v_offset + f[0], mat))
            else:
                mb.faces.append((v_offset + f[0], v_offset + f[1], v_offset + f[2], mat))
            
    return MeshData(
        vertices=np.array(mb.vertices, dtype=float),
        faces=np.array([[f[0], f[1], f[2]] for f in mb.faces], dtype=int),
        face_materials=np.array([f[3] for f in mb.faces], dtype=int),
        materials=tuple(mb.materials)
    )
