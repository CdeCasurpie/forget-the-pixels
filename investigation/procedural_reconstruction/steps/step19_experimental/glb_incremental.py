"""Append a building GLB to a cumulative GLB without decoding earlier meshes.

Both files are emitted by modeling.exporters.glb_exporter. This is a narrow
glTF 2.0 merger for single-scene, single-buffer building assets; unsupported
features raise instead of silently producing a broken scene.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
import struct


JSON_CHUNK = 0x4E4F534A
BIN_CHUNK = 0x004E4942
ARRAYS = ("accessors", "bufferViews", "meshes", "nodes", "materials", "images", "textures", "samplers")


def read_glb(path: Path) -> tuple[dict, bytes]:
    data = Path(path).read_bytes()
    if len(data) < 20 or data[:4] != b"glTF" or struct.unpack_from("<I", data, 4)[0] != 2:
        raise ValueError(f"Not a glTF 2.0 GLB: {path}")
    if struct.unpack_from("<I", data, 8)[0] != len(data):
        raise ValueError(f"Incorrect GLB length: {path}")
    chunks = []
    offset = 12
    while offset < len(data):
        length, kind = struct.unpack_from("<II", data, offset)
        offset += 8
        chunks.append((kind, data[offset:offset + length]))
        offset += length
    if offset != len(data) or len(chunks) != 2 or chunks[0][0] != JSON_CHUNK or chunks[1][0] != BIN_CHUNK:
        raise ValueError("Expected one JSON and one BIN chunk")
    tree = json.loads(chunks[0][1])
    if (len(tree.get("buffers", [])) != 1 or len(tree.get("scenes", [])) != 1
            or tree.get("scene", 0) != 0 or any(tree.get(k) for k in ("animations", "skins", "cameras"))):
        raise ValueError("GLB merger supports one scene/buffer and no animation, skin or camera")
    if tree.get("extensionsRequired"):
        raise ValueError("GLB merger does not support required glTF extensions")
    return tree, chunks[1][1]


def _texture_references(material: dict, offset: int) -> None:
    pbr = material.get("pbrMetallicRoughness", {})
    for container, key in (
        (pbr, "baseColorTexture"), (pbr, "metallicRoughnessTexture"),
        (material, "normalTexture"), (material, "occlusionTexture"),
        (material, "emissiveTexture"),
    ):
        if key in container:
            container[key]["index"] += offset


def append_glb(previous: Path | None, building: Path, output: Path, *, lot_id: object) -> None:
    """Write a new complete GLB; callers should atomically replace the visible file."""
    if previous is None:
        tree = {"asset": {"version": "2.0"}, "scene": 0, "scenes": [{"nodes": []}], "buffers": [{"byteLength": 0}]}
        old_binary = b""
    else:
        tree, old_binary = read_glb(previous)
    addition, new_binary = read_glb(building)
    tree = copy.deepcopy(tree)
    addition = copy.deepcopy(addition)
    counts = {name: len(tree.get(name, [])) for name in ARRAYS}
    bin_offset = len(old_binary)
    for accessor in addition.get("accessors", []):
        if "sparse" in accessor:
            raise ValueError("Sparse glTF accessors are unsupported")
        if "bufferView" in accessor:
            accessor["bufferView"] += counts["bufferViews"]
    for view in addition.get("bufferViews", []):
        if view.get("buffer", 0) != 0:
            raise ValueError("Only buffer zero is supported")
        view["byteOffset"] = view.get("byteOffset", 0) + bin_offset
    for mesh in addition.get("meshes", []):
        for primitive in mesh["primitives"]:
            if "extensions" in primitive or "targets" in primitive:
                raise ValueError("Mesh extensions/morph targets are unsupported")
            if "indices" in primitive:
                primitive["indices"] += counts["accessors"]
            primitive["attributes"] = {
                key: value + counts["accessors"] for key, value in primitive["attributes"].items()
            }
            if "material" in primitive:
                primitive["material"] += counts["materials"]
    for node in addition.get("nodes", []):
        node["name"] = f"lot_{lot_id}/{node.get('name', 'building')}"
        if "mesh" in node:
            node["mesh"] += counts["meshes"]
        if "children" in node:
            node["children"] = [child + counts["nodes"] for child in node["children"]]
    for material in addition.get("materials", []):
        if "extensions" in material:
            raise ValueError("Material extensions are unsupported")
        _texture_references(material, counts["textures"])
    for image in addition.get("images", []):
        if "bufferView" in image:
            image["bufferView"] += counts["bufferViews"]
    for texture in addition.get("textures", []):
        if "source" in texture:
            texture["source"] += counts["images"]
        if "sampler" in texture:
            texture["sampler"] += counts["samplers"]
    for name in ARRAYS:
        if addition.get(name):
            tree.setdefault(name, []).extend(addition[name])
    tree["scenes"][0]["nodes"].extend(
        node + counts["nodes"] for node in addition["scenes"][0].get("nodes", [])
    )
    binary = old_binary + new_binary
    tree["buffers"][0]["byteLength"] = len(binary)
    json_data = json.dumps(tree, separators=(",", ":"), allow_nan=False).encode("utf-8")
    json_data += b" " * (-len(json_data) % 4)
    binary += b"\0" * (-len(binary) % 4)
    total = 12 + 8 + len(json_data) + 8 + len(binary)
    output = Path(output)
    with output.open("wb") as handle:
        handle.write(struct.pack("<4sII", b"glTF", 2, total))
        handle.write(struct.pack("<II", len(json_data), JSON_CHUNK))
        handle.write(json_data)
        handle.write(struct.pack("<II", len(binary), BIN_CHUNK))
        handle.write(binary)
