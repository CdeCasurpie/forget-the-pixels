"""GLB export with separate semantic nodes, Z-up to Y-up, and metric UVs."""

from pathlib import Path
import numpy as np
import trimesh


def export_glb(mesh, path):
    scene = trimesh.Scene()
    transform = np.array(
        [[1, 0, 0, 0], [0, 0, 1, 0], [0, -1, 0, 0], [0, 0, 0, 1]], float
    )
    labels = np.empty(len(mesh.faces), object)
    labels[:] = "building"
    for part in mesh.parts:
        labels[part["face_start"] : part["face_start"] + part["face_count"]] = part[
            "name"
        ]
    has_uv = mesh.uv is not None and len(mesh.uv) == len(mesh.vertices)

    for label in sorted(set(labels)):
        for mi, material in enumerate(mesh.materials):
            mask = (labels == label) & (mesh.face_materials == mi)
            if not mask.any():
                continue

            sub_faces = mesh.faces[mask]

            # Remap vertices for this submesh, preserving per-vertex UVs
            used = np.unique(sub_faces)
            remap = np.full(len(mesh.vertices), -1, dtype=int)
            remap[used] = np.arange(len(used))

            sub_verts = mesh.vertices[used]
            sub_faces_remapped = remap[sub_faces]

            sub = trimesh.Trimesh(
                vertices=sub_verts, faces=sub_faces_remapped, process=False
            )

            opacity = float(material.get("opacity", 1.0))
            pbr_mat = trimesh.visual.material.PBRMaterial(
                name=material["name"],
                baseColorFactor=[*material["color"], opacity],
                metallicFactor=float(material.get("metallic", 0.0)),
                roughnessFactor=float(material.get("roughness", 0.8)),
                alphaMode="BLEND" if opacity < 0.999 else "OPAQUE",
                doubleSided=material.get("family") == "glass",
            )

            if has_uv:
                sub_uv = mesh.uv[used]
                sub.visual = trimesh.visual.TextureVisuals(
                    uv=sub_uv, material=pbr_mat
                )
            else:
                sub.visual = trimesh.visual.TextureVisuals(material=pbr_mat)

            scene.add_geometry(sub, node_name=f"{label}_{mi}", transform=transform)

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_bytes(scene.export(file_type="glb"))
