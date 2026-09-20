"""GLB export with separate semantic nodes, Z-up to Y-up, and metric UVs."""

from pathlib import Path
import numpy as np
import trimesh
from PIL import Image
from modeling.texturing.library import MaterialLibrary


def export_glb(mesh, path, *, library=None):
    catalog = Path(__file__).resolve().parents[2] / "assets/pbr/catalog.json"
    lib = library or (MaterialLibrary(catalog) if catalog.exists() else None)
    material_cache = {}
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
            # Construct PBR material
            color = np.asarray(material["color"], float)
            color = np.where(color <= .04045, color / 12.92, ((color + .055) / 1.055)**2.4)
            pbr_mat = material_cache.get(mi) or trimesh.visual.material.PBRMaterial(
                name=material["name"],
                baseColorFactor=[*color, opacity],
                metallicFactor=float(material.get("metallic", 0.0)),
                roughnessFactor=float(material.get("roughness", 0.8)),
                alphaMode="BLEND" if opacity < 0.999 else "OPAQUE",
                doubleSided=material.get("family") == "glass",
            )
            
            # Connect texture images if available
            texture_set_name = material.get("texture_set")
            if texture_set_name and has_uv and lib and mi not in material_cache:
                if lib.get_texture_set(texture_set_name):
                    maps = lib.load_all_maps(texture_set_name)
                    if "base_color" in maps:
                        try:
                            # Apply tint if color isn't purely white
                            # Keep shared sRGB image; linear factor handles tint.
                            pbr_mat.baseColorTexture = maps["base_color"]
                        except Exception as e:
                            print(f"Error processing base_color for {texture_set_name}: {e}")
                            
                    if "normal" in maps:
                        pbr_mat.normalTexture = maps["normal"]
                            
                    if "orm" in maps:
                        # Trimesh PBRMaterial uses metallicRoughnessTexture for ORM
                        pbr_mat.metallicRoughnessTexture = maps["orm"]
                        pbr_mat.occlusionTexture = maps["orm"]
                        pbr_mat.roughnessFactor = 1.0
                        pbr_mat.metallicFactor = 1.0
                    elif "ao" in maps:
                        pbr_mat.occlusionTexture = maps["ao"]


            material_cache[mi] = pbr_mat
            if has_uv:
                sub_uv = mesh.uv[used].copy()
                tset = lib.get_texture_set(texture_set_name) if lib else None
                if tset:
                    # Undo legacy metres/tile, then apply physical catalog scale once.
                    sub_uv *= material.get("real_scale_m", 1.0) / np.array([tset.scale_u, tset.scale_v])
                sub.visual = trimesh.visual.TextureVisuals(
                    uv=sub_uv, material=pbr_mat
                )
            else:
                sub.visual = trimesh.visual.TextureVisuals(material=pbr_mat)

            scene.add_geometry(sub, node_name=f"{label}_{mi}", transform=transform)

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    def postprocess(tree):
        by_name = {m["name"]: m for m in mesh.materials}
        for m in tree.get("materials", []):
            if "normalTexture" in m:
                m["normalTexture"]["scale"] = by_name[m["name"]].get("normal_strength", 1.0)
    Path(path).write_bytes(trimesh.exchange.gltf.export_glb(scene, tree_postprocessor=postprocess))
