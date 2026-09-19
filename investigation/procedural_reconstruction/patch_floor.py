import re

with open("src/procedural_modeling/grammar.py", "r") as f:
    code = f.read()

# Find the Roof generation part
roof_code = """    # 2. Generate Roof
    poly = Polygon(spec.footprint_xy)
    H = spec.height.regularized_height_m or spec.height.continuous_height_m
    r_verts, r_faces = triangulate_polygon(poly, H)
    if len(r_verts) > 0:
        vertices.extend(r_verts)
        for f in r_faces:
            faces.append([v_offset + f[0], v_offset + f[1], v_offset + f[2]])
            face_materials.append(mat_idx["roof"])
        v_offset += len(r_verts)"""

floor_code = """    # 2. Generate Roof and Floor
    poly = Polygon(spec.footprint_xy)
    H = spec.height.regularized_height_m or spec.height.continuous_height_m
    
    # Roof
    r_verts, r_faces = triangulate_polygon(poly, H)
    if len(r_verts) > 0:
        vertices.extend(r_verts)
        for f in r_faces:
            faces.append([v_offset + f[0], v_offset + f[1], v_offset + f[2]])
            face_materials.append(mat_idx["roof"])
        v_offset += len(r_verts)
        
    # Floor (inverted faces)
    f_verts, f_faces = triangulate_polygon(poly, 0.0)
    if len(f_verts) > 0:
        vertices.extend(f_verts)
        for f in f_faces:
            faces.append([v_offset + f[2], v_offset + f[1], v_offset + f[0]]) # Inverted winding
            face_materials.append(mat_idx["roof"]) # Or floor material, but wall/roof is fine
        v_offset += len(f_verts)"""

new_code = code.replace(roof_code, floor_code)
with open("src/procedural_modeling/grammar.py", "w") as f:
    f.write(new_code)
