"""GLB export with separate semantic nodes and an explicit Z-up to Y-up rotation."""

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
    for label in sorted(set(labels)):
        for mi, material in enumerate(mesh.materials):
            mask = (labels == label) & (mesh.face_materials == mi)
            if not mask.any():
                continue
            sub = trimesh.Trimesh(
                vertices=mesh.vertices, faces=mesh.faces[mask], process=False
            )
            sub.remove_unreferenced_vertices()
            sub.visual = trimesh.visual.TextureVisuals(
                material=trimesh.visual.material.PBRMaterial(
                    name=material["name"],
                    baseColorFactor=[*material["color"], 1.0],
                    metallicFactor=0.35 if material["name"] == "metal" else 0.0,
                    roughnessFactor=0.35 if material["name"] == "glass" else 0.8,
                )
            )
            scene.add_geometry(sub, node_name=f"{label}_{mi}", transform=transform)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_bytes(scene.export(file_type="glb"))
