from pathlib import Path
from domain import MeshData

def export_obj(mesh: MeshData, output_path: Path, y_up: bool = True):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    mtl_path = output_path.with_suffix('.mtl')
    obj_lines = [f"mtllib {mtl_path.name}"]
    mtl_lines = []
    
    # Write materials
    if mesh.materials:
        for mat in mesh.materials:
            mtl_lines.append(f"newmtl {mat['name']}")
            r, g, b = mat['color']
            mtl_lines.append(f"Kd {r:.4f} {g:.4f} {b:.4f}")
            mtl_lines.append(f"Ka {r*0.2:.4f} {g*0.2:.4f} {b*0.2:.4f}")
            mtl_lines.append("")
    
    # Write vertices
    for v in mesh.vertices:
        if y_up:
            # Convert Z-up to Y-up
            # X_new = X, Y_new = Z, Z_new = -Y
            obj_lines.append(f"v {v[0]:.6f} {v[2]:.6f} {-v[1]:.6f}")
        else:
            obj_lines.append(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}")
        
    # Write faces
    current_mat = None
    for i, f in enumerate(mesh.faces):
        if mesh.face_materials is not None and len(mesh.materials) > 0:
            mat_idx = mesh.face_materials[i]
            mat_name = mesh.materials[mat_idx]['name']
            if mat_name != current_mat:
                obj_lines.append(f"usemtl {mat_name}")
                current_mat = mat_name
        
        # OBJ is 1-indexed
        obj_lines.append(f"f {f[0]+1} {f[1]+1} {f[2]+1}")
        
    output_path.write_text("\n".join(obj_lines))
    mtl_path.write_text("\n".join(mtl_lines))
