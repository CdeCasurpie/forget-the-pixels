"""GLB export with logical component nodes, Z-up to Y-up, and metric UVs.

Grouping key is (component, material): two windows never merge just because
they share a semantic. Render vertices split (position, uv) pairs only where
an attribute seam requires it; the topology source stays shared.
"""

from pathlib import Path
import numpy as np
import trimesh
from PIL import Image
from modeling.texturing.library import MaterialLibrary


def _merge_component_nodes(tree):
    """One glTF node per logical component, N primitives per material.

    The scene is built with one geometry per (component, material) so each
    piece keeps its own UV layout; here geometries that share a component
    are folded into a single node/mesh whose primitives carry the materials.
    Pure JSON restructuring: accessors, buffers and materials are untouched,
    so no vertex is duplicated, welded or moved.
    """
    nodes = tree.get("nodes", [])
    meshes = tree.get("meshes", [])
    if not nodes or not meshes:
        return
    groups = {}
    for ni, node in enumerate(nodes):
        name = node.get("name", "")
        base = name.rsplit("#", 1)[0] if "#" in name else name
        groups.setdefault(base, []).append(ni)
    if all(len(members) == 1 for members in groups.values()):
        for node in nodes:
            name = node.get("name", "")
            if "#" in name:
                node["name"] = name.rsplit("#", 1)[0]
        return
    new_meshes = []
    new_nodes = []
    old_to_new = {}
    for base, members in groups.items():
        primitives = []
        transform = None
        for ni in members:
            node = nodes[ni]
            mesh_idx = node.get("mesh")
            if isinstance(mesh_idx, int) and 0 <= mesh_idx < len(meshes):
                primitives.extend(meshes[mesh_idx].get("primitives", []))
            if transform is None and "matrix" in node:
                transform = node["matrix"]
        if not primitives:
            continue
        new_index = len(new_nodes)
        for ni in members:
            old_to_new[ni] = new_index
        new_meshes.append({"name": base, "primitives": primitives})
        merged = {"name": base, "mesh": len(new_meshes) - 1}
        if transform is not None:
            merged["matrix"] = transform
        new_nodes.append(merged)
    for scene in tree.get("scenes", []):
        scene["nodes"] = [old_to_new[ni] for ni in scene.get("nodes", [])
                          if ni in old_to_new]
    tree["nodes"] = new_nodes
    tree["meshes"] = new_meshes


def _corner_uvs(mesh):
    """(M, 3, 2) corner attributes, preferring the canonical store."""
    if mesh.corner_uv is not None and len(mesh.corner_uv) == len(mesh.faces):
        return np.asarray(mesh.corner_uv, float).reshape(-1, 3, 2)
    if mesh.uv is not None and len(mesh.uv) == len(mesh.vertices):
        per_vertex = np.asarray(mesh.uv, float)
        return per_vertex[np.asarray(mesh.faces)]
    return None


def export_glb(mesh, path, *, library=None):
    catalog = Path(__file__).resolve().parents[2] / "assets/pbr/catalog.json"
    lib = library or (MaterialLibrary(catalog) if catalog.exists() else None)
    material_cache = {}
    scene = trimesh.Scene()
    transform = np.array(
        [[1, 0, 0, 0], [0, 0, 1, 0], [0, -1, 0, 0], [0, 0, 0, 1]], float
    )
    faces = np.asarray(mesh.faces)
    face_mats = np.asarray(mesh.face_materials)
    corners = _corner_uvs(mesh)
    has_uv = corners is not None

    comp_of_face = np.zeros(len(faces), int)
    comp_meta = [{"assembly_id": "", "component_id": f"part_{i}",
                  "name": p.get("name", "building")} for i, p in enumerate(mesh.parts)]
    for i, part in enumerate(mesh.parts):
        s = part["face_start"]
        comp_of_face[s:s + part["face_count"]] = i
        comp_meta[i] = {
            "assembly_id": part.get("assembly_id", ""),
            "component_id": part.get("component_id", f"part_{i}"),
            "name": part.get("name", "building"),
        }

    # Single pass over faces: one submesh per (component, material).
    groups = {}
    for f in range(len(faces)):
        key = (int(comp_of_face[f]), int(face_mats[f]))
        groups.setdefault(key, []).append(f)

    for (ci, mi), members in sorted(groups.items()):
        material = mesh.materials[mi]
        meta = comp_meta[ci]
        sub_faces = faces[members]

        if has_uv:
            sub_corners = corners[members].reshape(-1, 2)
            sub_pos = sub_faces.ravel()
            keys = np.column_stack((sub_pos, sub_corners))
            _, uniq, remap = np.unique(keys, axis=0, return_index=True,
                                       return_inverse=True)
            used = sub_faces.ravel()[uniq]
            sub_verts = np.asarray(mesh.vertices)[used]
            sub_uv = sub_corners[uniq]
            sub_faces_remapped = remap.reshape(-1, 3)
        else:
            used = np.unique(sub_faces)
            remap = np.full(len(mesh.vertices), -1, dtype=int)
            remap[used] = np.arange(len(used))
            sub_verts = np.asarray(mesh.vertices)[used]
            sub_faces_remapped = remap[sub_faces]
            sub_uv = None

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
            tset = lib.get_texture_set(texture_set_name) if lib else None
            if tset:
                # Undo legacy metres/tile, then apply physical catalog scale once.
                sub_uv = sub_uv * (material.get("real_scale_m", 1.0)
                                   / np.array([tset.scale_u, tset.scale_v]))
            sub.visual = trimesh.visual.TextureVisuals(
                uv=sub_uv, material=pbr_mat
            )
        else:
            sub.visual = trimesh.visual.TextureVisuals(material=pbr_mat)

        assembly = meta["assembly_id"]
        node = (f"{assembly}/{meta['component_id']}" if assembly
                else meta["component_id"])
        scene.add_geometry(sub, node_name=f"{node}#{material['name']}",
                           transform=transform)

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    def postprocess(tree):
        _merge_component_nodes(tree)
        by_name = {m["name"]: m for m in mesh.materials}
        for m in tree.get("materials", []):
            if "normalTexture" in m:
                m["normalTexture"]["scale"] = by_name[m["name"]].get("normal_strength", 1.0)
    Path(path).write_bytes(trimesh.exchange.gltf.export_glb(scene, tree_postprocessor=postprocess))
