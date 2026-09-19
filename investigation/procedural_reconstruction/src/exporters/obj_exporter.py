from pathlib import Path
from domain import MeshData


def export_obj(mesh: MeshData, output_path: Path, y_up: bool = False):
    output_path.parent.mkdir(parents=True, exist_ok=True)

    mtl_path = output_path.with_suffix(".mtl")
    obj_lines = [f"# metres; {'Y' if y_up else 'Z'} up", f"mtllib {mtl_path.name}"]
    mtl_lines = []

    # Write materials
    if mesh.materials:
        for mat in mesh.materials:
            mtl_lines.append(f"newmtl {mat['name']}")
            r, g, b = mat["color"]
            mtl_lines.append(f"Kd {r:.4f} {g:.4f} {b:.4f}")
            mtl_lines.append(f"Ka {r*0.2:.4f} {g*0.2:.4f} {b*0.2:.4f}")
            roughness = float(mat.get("roughness", 0.8))
            metallic = float(mat.get("metallic", 0.0))
            opacity = float(mat.get("opacity", 1.0))
            mtl_lines.append(f"Ns {max(1.0, (1.0-roughness)*1000):.3f}")
            mtl_lines.append(f"Pm {metallic:.4f}")
            mtl_lines.append(f"Pr {roughness:.4f}")
            mtl_lines.append(f"d {opacity:.4f}")
            mtl_lines.append(f"illum {4 if opacity < 0.999 else 2}")
            mtl_lines.append("")

    has_uv = mesh.uv is not None and len(mesh.uv) == len(mesh.vertices)

    # Write vertices
    for v in mesh.vertices:
        if y_up:
            obj_lines.append(f"v {v[0]:.6f} {v[2]:.6f} {-v[1]:.6f}")
        else:
            obj_lines.append(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}")

    # Write texture coordinates
    if has_uv:
        for uv in mesh.uv:
            obj_lines.append(f"vt {uv[0]:.6f} {uv[1]:.6f}")

    # Write faces
    current_mat = None
    part_starts = {part["face_start"]: part["name"] for part in mesh.parts}
    for i, f in enumerate(mesh.faces):
        if i in part_starts:
            obj_lines.append(f"g {part_starts[i]}_{i}")
        if mesh.face_materials is not None and len(mesh.materials) > 0:
            mat_idx = mesh.face_materials[i]
            mat_name = mesh.materials[mat_idx]["name"]
            if mat_name != current_mat:
                obj_lines.append(f"usemtl {mat_name}")
                current_mat = mat_name

        # OBJ is 1-indexed; use v/vt format when UVs are present
        if has_uv:
            obj_lines.append(
                f"f {f[0]+1}/{f[0]+1} {f[1]+1}/{f[1]+1} {f[2]+1}/{f[2]+1}"
            )
        else:
            obj_lines.append(f"f {f[0]+1} {f[1]+1} {f[2]+1}")

    output_path.write_text("\n".join(obj_lines))
    mtl_path.write_text("\n".join(mtl_lines))
