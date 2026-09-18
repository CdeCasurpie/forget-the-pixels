import numpy as np
from shapely.geometry import Polygon
from shapely.ops import triangulate

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
            
        p00_out = P(u1, v1, w2)
        p10_out = P(u2, v1, w2)
        p11_out = P(u2, v2, w2)
        p01_out = P(u1, v2, w2)
        
        p00_in = P(u1, v1, w1)
        p10_in = P(u2, v1, w1)
        p11_in = P(u2, v2, w1)
        p01_in = P(u1, v2, w1)
        
        self.add_quad(p00_out, p10_out, p11_out, p01_out, mat_name, color) # Front
        self.add_quad(p10_in, p00_in, p01_in, p11_in, mat_name, color)     # Back
        self.add_quad(p01_out, p11_out, p11_in, p01_in, mat_name, color)   # Top
        self.add_quad(p00_in, p10_in, p10_out, p00_out, mat_name, color)   # Bottom
        self.add_quad(p10_out, p10_in, p11_in, p11_out, mat_name, color)   # Right
        self.add_quad(p00_in, p00_out, p01_out, p01_in, mat_name, color)   # Left

def build_barranco_facade(mb: MeshBuilder, facade, spec_style, floors=2, floor_height=2.8):
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
    fence_color = [0.6, 0.3, 0.2] # Brick/Grille mix
    
    is_front = getattr(facade, 'is_front', False)
    
    # If not front, it's a blind wall (Lima style)
    if not is_front:
        mb.add_facade_box(A, t, Z, n, 0, width, 0, floors*floor_height, -0.2, 0.0, "wall_blind", blind_wall_color)
        mb.add_facade_box(A, t, Z, n, 0, width, floors*floor_height, floors*floor_height+0.5, -0.2, 0.0, "wall_blind", blind_wall_color)
        return

    # If it is front, and style is setback_fence, we draw a fence on A->B, and push the facade back!
    if spec_style == "setback_fence":
        # Draw Fence at street edge
        mb.add_facade_box(A, t, Z, n, 0, width, 0, 0.5, -0.2, 0.0, "fence_base", fence_color)
        mb.add_facade_box(A, t, Z, n, 0, 0.4, 0, 2.5, -0.2, 0.05, "fence_pillar", trim_color)
        mb.add_facade_box(A, t, Z, n, width-0.4, width, 0, 2.5, -0.2, 0.05, "fence_pillar", trim_color)
        mb.add_facade_box(A, t, Z, n, 0.4, width-0.4, 0.5, 2.5, -0.1, 0.0, "grille", [0.2, 0.2, 0.2])
        # Garage door in fence
        if width > 3.0:
            mb.add_facade_box(A, t, Z, n, width-2.8, width-0.4, 0, 2.5, -0.15, 0.0, "garage", garage_color)
            
        # Push A and B back by 3 meters for the actual facade
        A = A - 3.0 * n
        B = B - 3.0 * n
        # Note: the footprint triangulation doesn't know about this setback, so the roof will cover the yard.
        # But this is just for facade rendering visualization.

    # 1. Base plinth
    mb.add_facade_box(A, t, Z, n, 0, width, 0, 0.4, 0.0, 0.05, "trim", trim_color)
    
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
        
        # Draw Wall Grid
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
                    mb.add_facade_box(A, t, Z, n, u1, u2, v1, v2, -0.2, 0.0, "wall", wall_color)

        # Draw Openings Details
        for op in floor_openings:
            u1, u2 = op.u_m, op.u_m + op.width_m
            v1, v2 = op.v_m, op.v_m + op.height_m
            
            # Flush or slightly protruding outer frame
            mb.add_facade_box(A, t, Z, n, u1-0.1, u1+0.05, v1-0.1, v2+0.1, 0.0, 0.05, "trim", trim_color)
            mb.add_facade_box(A, t, Z, n, u2-0.05, u2+0.1, v1-0.1, v2+0.1, 0.0, 0.05, "trim", trim_color)
            mb.add_facade_box(A, t, Z, n, u1, u2, v2-0.05, v2+0.1, 0.0, 0.05, "trim", trim_color)
            
            if op.kind == "window" or op.kind == "wide_window":
                # Sill (alféizar)
                mb.add_facade_box(A, t, Z, n, u1-0.15, u2+0.15, v1, v1+0.1, 0.0, 0.1, "trim", trim_color)
                # Recessed Inner frame
                mb.add_facade_box(A, t, Z, n, u1, u1+0.05, v1, v2, -0.1, 0.0, "frame", door_color)
                mb.add_facade_box(A, t, Z, n, u2-0.05, u2, v1, v2, -0.1, 0.0, "frame", door_color)
                
                if op.kind == "wide_window":
                    # Multiple mullions
                    for m in range(1, 4):
                        um = u1 + m * (u2-u1)/4
                        mb.add_facade_box(A, t, Z, n, um-0.03, um+0.03, v1, v2, -0.1, 0.0, "frame", door_color)
                else:
                    um = (u1+u2)/2
                    mb.add_facade_box(A, t, Z, n, um-0.03, um+0.03, v1, v2, -0.1, 0.0, "frame", door_color)
                    
                # Glass
                mb.add_facade_box(A, t, Z, n, u1+0.05, u2-0.05, v1+0.1, v2-0.05, -0.12, -0.08, "glass", glass_color)
                
            elif op.kind == "balcony_window":
                # French doors + balcony
                mb.add_facade_box(A, t, Z, n, u1+0.05, u2-0.05, v1, v2-0.05, -0.12, -0.08, "glass", glass_color)
                # Slab
                mb.add_facade_box(A, t, Z, n, u1-0.4, u2+0.4, v1, v1+0.2, 0.0, 0.8, "trim", trim_color)
                # Railing (Baranda)
                mb.add_facade_box(A, t, Z, n, u1-0.4, u2+0.4, v1+0.2, v1+1.0, 0.75, 0.8, "railing", [0.1, 0.1, 0.1])
                mb.add_facade_box(A, t, Z, n, u1-0.4, u1-0.35, v1+0.2, v1+1.0, 0.0, 0.8, "railing", [0.1, 0.1, 0.1])
                mb.add_facade_box(A, t, Z, n, u2+0.35, u2+0.4, v1+0.2, v1+1.0, 0.0, 0.8, "railing", [0.1, 0.1, 0.1])
                
            elif op.kind == "storefront":
                mb.add_facade_box(A, t, Z, n, u1, u2, v1, v2, -0.1, 0.0, "glass", glass_color)
                mb.add_facade_box(A, t, Z, n, u1, u2, v1, v1+0.5, 0.0, 0.05, "trim", trim_color)
                
            elif op.kind == "garage":
                mb.add_facade_box(A, t, Z, n, u1, u2, v1, v2, -0.1, 0.0, "garage", garage_color)
                
            elif op.kind == "door":
                mb.add_facade_box(A, t, Z, n, u1+0.05, u2-0.05, v1, v2-0.05, -0.12, -0.05, "door", door_color)

        # Cornice (Cornisa)
        if floor < floors - 1:
            mb.add_facade_box(A, t, Z, n, -0.1, width+0.1, v_top-0.2, v_top, 0.0, 0.15, "trim", trim_color)

    # 4. Parapet
    roof_height = floors * floor_height
    mb.add_facade_box(A, t, Z, n, 0, width, roof_height, roof_height+0.8, -0.2, 0.0, "wall", wall_color)
    mb.add_facade_box(A, t, Z, n, -0.15, width+0.15, roof_height+0.8, roof_height+1.0, -0.25, 0.15, "trim", trim_color)
    
    # 5. Pilasters (only front facade)
    mb.add_facade_box(A, t, Z, n, 0, 0.3, 0, roof_height, 0.0, 0.1, "trim", trim_color)
    mb.add_facade_box(A, t, Z, n, width-0.3, width, 0, roof_height, 0.0, 0.1, "trim", trim_color)

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
