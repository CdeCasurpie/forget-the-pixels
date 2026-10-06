"""Une los 24 building.glb en un unico modelo de cuadra.

Los GLB ya comparten marco local (origen unico = centroide de la cuadra,
guardado en cada lot.json), asi que cada lote cae exactamente en su parcela
catastral sin reorientar nada: solo se concatenan buffers.
  - union a nivel GLB con scripts.glb_incremental.append_glb (nodos por lote).
  - vista iso de verificacion: remalla cada lote desde su request.json,
    combina (misma logica que step3.combine_meshes) y renderiza.

Uso:
    python steps/step19_experimental/cuadra_fotos/unir_cuadra_glb.py --cuadra steps/step19_experimental/cuadra_fotos/cuadra_seed_123
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

CUADRA_SCRIPTS = Path(__file__).resolve().parent
ROOT = CUADRA_SCRIPTS.parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "steps" / "step10_procedural_generation_test"))
sys.path.insert(0, str(ROOT / "steps" / "step19_experimental"))

import numpy as np  # noqa: E402
from glb_incremental import append_glb  # noqa: E402
from domain.models import MeshData  # noqa: E402
from domain.theta import from_json  # noqa: E402
from pipeline.theta import reconstruct  # noqa: E402
from render import render  # noqa: E402


def combine_meshes(meshes: list[tuple[object, MeshData]]) -> MeshData:
    """Misma combinacion que step3: offsets de vertices/caras y materiales
    deduplicados por clave JSON; ensamblajes prefijados por lote."""
    vertices, faces, corner_uvs, face_materials = [], [], [], []
    parts, components, materials = [], [], []
    material_ids = {}
    vertex_offset = face_offset = 0
    for lot_index, mesh in meshes:
        vertices.append(mesh.vertices)
        faces.append(mesh.faces + vertex_offset)
        corner_uvs.append(mesh.corner_uv if mesh.corner_uv is not None else np.zeros((len(mesh.faces), 3, 2)))
        mapped = np.empty(len(mesh.face_materials), dtype=int)
        for local_id, material in enumerate(mesh.materials):
            key = json.dumps(material, sort_keys=True)
            if key not in material_ids:
                material_ids[key] = len(materials)
                materials.append(material)
            mapped[mesh.face_materials == local_id] = material_ids[key]
        face_materials.append(mapped)
        for source, target in ((mesh.parts, parts), (mesh.components, components)):
            for part in source:
                record = dict(part)
                record["face_start"] += face_offset
                record["assembly_id"] = f"lot_{lot_index}/{record.get('assembly_id', '')}"
                target.append(record)
        vertex_offset += len(mesh.vertices)
        face_offset += len(mesh.faces)
    return MeshData(
        vertices=np.vstack(vertices),
        faces=np.vstack(faces),
        corner_uv=np.vstack(corner_uvs),
        face_materials=np.concatenate(face_materials),
        materials=tuple(materials),
        parts=tuple(parts),
        components=tuple(components),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cuadra", type=Path, required=True)
    parser.add_argument("--iso-size", type=int, default=1400)
    args = parser.parse_args()
    cuadra = args.cuadra.resolve()
    manifest = json.loads((cuadra / "manifest.json").read_text())
    order = [r["lot_index"] for r in manifest["results"]]

    origins = set()
    glb_path = cuadra / "cuadra_completa.glb"
    generated = 0
    per_lot = []
    for index in order:
        lot_dir = cuadra / f"lote_{index}"
        lot = json.loads((lot_dir / "lot.json").read_text())
        origins.add(tuple(lot["local_origin_utm"]))
        house = lot_dir / "salida" / "building.glb"
        if not house.exists():
            raise FileNotFoundError(f"falta {house}")
        temporary = cuadra / ".cuadra_completa.tmp.glb"
        append_glb(glb_path if generated else None, house, temporary, lot_id=index)
        os.replace(temporary, glb_path)
        generated += 1
        lm = json.loads((lot_dir / "salida" / "manifest.json").read_text())
        per_lot.append({"lot_index": index, "triangles": lm["triangles"],
                        "vertices": lm["vertices"]})
        print(f"  {generated}/{len(order)} lote_{index}: {lm['triangles']} tris", flush=True)
    if len(origins) != 1:
        raise ValueError(f"origenes locales distintos: {origins}")

    meshes = []
    for index in order:
        request = from_json((cuadra / f"lote_{index}" / "request.json").read_text())
        meshes.append((index, reconstruct(request).mesh))
    combined = combine_meshes(meshes)
    render(combined, cuadra / "cuadra_completa_iso.png",
           direction=(1, -1, 1), size=args.iso_size, clay=True)
    (cuadra / "cuadra_completa.json").write_text(json.dumps({
        "lots": len(order),
        "local_origin_utm": list(origins)[0],
        "crs": "EPSG:32718",
        "triangles": int(sum(p["triangles"] for p in per_lot)),
        "glb": str(glb_path),
        "iso": str(cuadra / "cuadra_completa_iso.png"),
        "per_lot": per_lot,
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"OK: {glb_path} ({glb_path.stat().st_size / 1024**2:.1f} MB), "
          f"{sum(p['triangles'] for p in per_lot)} tris en {len(order)} lotes.", flush=True)


if __name__ == "__main__":
    main()
