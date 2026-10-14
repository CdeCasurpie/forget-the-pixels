"""Precalcula el panorama de NUESTRO modelo desde cada camara GSV de la cuadra.

Monta los 24 lotes en una escena open3d (raytracing CPU, sin GPU) y para cada
panorama dispara rayos equirectangulares desde su misma posicion, centrados en
su mismo heading: el PNG resultante se compara pixel a pixel con el GSV.

Uso:
    python steps/step19_experimental/cuadra_fotos/recorrido/generar_panoramas_modelo.py --cuadra scripts/cuadra_fotos/cuadra_seed_123
    # luego:
    python steps/step19_experimental/cuadra_fotos/recorrido/ver_recorrido.py --recorrido steps/step19_experimental/cuadra_fotos/recorrido/recorrido_seed_123
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

CUADRA_SCRIPTS = Path(__file__).resolve().parent
ROOT = CUADRA_SCRIPTS.parents[3]
sys.path.insert(0, str(ROOT / "src"))

import cv2  # noqa: E402
import numpy as np  # noqa: E402
import open3d as o3d  # noqa: E402
import streetlevel.streetview as sv  # noqa: E402
from pyproj import Transformer  # noqa: E402

from domain.theta import from_json  # noqa: E402
from pipeline.theta import reconstruct  # noqa: E402

CAM_HEIGHT_M = 2.5
EQUI_W, EQUI_H = 2048, 1024
SUN = np.array([-0.45, -0.55, 0.70], dtype=np.float64)
SUN /= np.linalg.norm(SUN)


def build_scene(cuadra: Path):
    manifest = json.loads((cuadra / "manifest.json").read_text())
    all_v, all_c = [], []
    for entry in manifest["results"]:
        request = from_json((cuadra / f"lote_{entry['lot_index']}" / "request.json").read_text())
        mesh = reconstruct(request).mesh
        colors = np.array([m["color"] for m in mesh.materials], dtype=np.float64)[mesh.face_materials]
        verts = np.asarray(mesh.vertices, dtype=np.float64).reshape(-1, 3)
        faces = np.asarray(mesh.faces, dtype=np.int64).reshape(-1, 3)
        all_v.append(verts[faces.reshape(-1)].reshape(-1, 3))
        all_c.append(np.repeat(colors, 3, axis=0).reshape(-1, 3))
    VV = np.vstack(all_v).astype(np.float32)
    CC = np.vstack(all_c).astype(np.float32)
    legacy = o3d.geometry.TriangleMesh(
        o3d.utility.Vector3dVector(VV.astype(np.float64)),
        o3d.utility.Vector3iVector(np.arange(len(VV), dtype=np.int64).reshape(-1, 3)))
    legacy.vertex_colors = o3d.utility.Vector3dVector(CC.astype(np.float64))
    scene = o3d.t.geometry.RaycastingScene()
    scene.add_triangles(o3d.t.geometry.TriangleMesh.from_legacy(legacy))
    return scene, CC.astype(np.float64)


def render_equirect(scene, face_colors, cam_xyz, heading_deg, width=EQUI_W, height=EQUI_H):
    us = (np.arange(width) + .5) / width
    vs = (np.arange(height) + .5) / height
    uu, vv = np.meshgrid(us, vs)  # (H, W): indice = v*W + u
    yaw = math.radians(heading_deg) + (uu - .5) * 2 * math.pi
    pitch = (.5 - vv) * math.pi
    sy, cy, sp, cp = np.sin(yaw), np.cos(yaw), np.sin(pitch), np.cos(pitch)
    dirs = np.stack([cp * sy, cp * cy, sp], -1).reshape(-1, 3).astype(np.float32)
    origins = np.broadcast_to(np.asarray(cam_xyz, dtype=np.float32), dirs.shape).copy()
    ans = scene.cast_rays(o3d.core.Tensor(np.concatenate([origins, dirs.astype(np.float32)], axis=1)))
    t_hit = ans["t_hit"].numpy()
    hit = t_hit < 1e10
    prim = ans["primitive_ids"].numpy()
    img = np.zeros((height, width, 3), dtype=np.float32)
    if hit.any():
        nrm = -ans["primitive_normals"].numpy()[hit].astype(np.float64)
        nrm /= np.linalg.norm(nrm, axis=1, keepdims=True) + 1e-12
        col = face_colors[(prim[hit] * 3).astype(np.int64)]
        shade = 0.35 + 0.65 * np.maximum(0.0, nrm @ SUN)
        img[hit.reshape(height, width)] = col.reshape(-1, 3) * shade[:, None]
    # cielo: degradado segun elevacion para los rayos que no tocan nada
    miss = ~hit.reshape(height, width)
    sky_v = (np.arange(height) + .5) / height
    sky = (np.stack([0.75 + 0.18 * sky_v, 0.80 + 0.15 * sky_v, 0.86 + 0.10 * sky_v], -1)
           [:, None, :].repeat(width, axis=1))
    img[miss] = sky[miss]
    ground = (vs < .5)[:, None]
    img[miss & np.broadcast_to(ground, miss.shape)] = (0.55, 0.55, 0.53)
    return (np.clip(img, 0, 1) * 255).astype(np.uint8)


def ensure_gsv(pano_id: str, cache: Path, zoom: int = 3) -> Path:
    cache.mkdir(parents=True, exist_ok=True)
    raw = cache / f"{pano_id}.jpg"
    if raw.exists():
        return raw
    image = sv.get_panorama(sv.find_panorama_by_id(pano_id), zoom=zoom)
    if image is None:
        raise RuntimeError(f"sin imagen {pano_id}")
    image.save(raw, "JPEG", quality=92)
    return raw


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cuadra", type=Path, required=True)
    parser.add_argument("--salida", type=Path, default=None)
    parser.add_argument("--zoom", type=int, default=3)
    parser.add_argument("--max-panos", type=int, default=0)
    args = parser.parse_args()
    cuadra = args.cuadra.resolve()
    out = (args.salida or (CUADRA_SCRIPTS / "recorrido" / f"recorrido_{cuadra.name}")).resolve()
    (out / "panos_modelo").mkdir(parents=True, exist_ok=True)
    gsv_cache = out / "panos_gsv"

    manifest = json.loads((cuadra / "manifest.json").read_text())
    origin = manifest["results"] and json.loads(
        (cuadra / f"lote_{manifest['results'][0]['lot_index']}" / "lot.json").read_text())["local_origin_utm"]
    to_utm = Transformer.from_crs("EPSG:4326", "EPSG:32718", always_xy=True)
    archive = json.loads((cuadra / "panoramas_metadata.json").read_text())

    scene, face_colors = build_scene(cuadra)
    print(f"escena: {len(face_colors)//3} tris", flush=True)

    entries = []
    for pano_id, entry in archive.items():
        x, y = to_utm.transform(float(entry["lon"]), float(entry["lat"]))
        entries.append({**entry, "local_x": x - origin[0], "local_y": y - origin[1]})
    # vuelta a la cuadra: orden angular alrededor del centroide (origen local)
    entries.sort(key=lambda e: math.atan2(e["local_x"], e["local_y"]))
    if args.max_panos:
        entries = entries[:args.max_panos]

    route = []
    for rank, entry in enumerate(entries):
        pano_id = entry["pano_id"]
        raw = ensure_gsv(pano_id, gsv_cache, args.zoom)
        img = render_equirect(scene, face_colors, (entry["local_x"], entry["local_y"], CAM_HEIGHT_M),
                              float(entry["heading_deg"]) % 360.0)
        modelo = out / "panos_modelo" / f"{pano_id}.jpg"
        cv2.imwrite(str(modelo), cv2.cvtColor(img, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 88])
        route.append({"rank": rank, "pano_id": pano_id, "date": entry.get("date"),
                      "heading_deg": entry["heading_deg"],
                      "gsv": str(raw.relative_to(out)), "modelo": str(modelo.relative_to(out))})
        print(f"  [{rank + 1}/{len(entries)}] {pano_id}", flush=True)
    (out / "route.json").write_text(json.dumps(
        {"cuadra": str(cuadra), "origin_utm": origin, "panos": route},
        indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"OK: {len(route)} pares en {out}", flush=True)


if __name__ == "__main__":
    main()
