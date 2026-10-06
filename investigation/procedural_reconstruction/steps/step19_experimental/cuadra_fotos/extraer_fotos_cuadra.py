"""Extrae, para cada lote de UNA cuadra, su geometria lista-para-gramatica + fotos GSV.

Reutiliza exactamente las piezas de src que ya usan los steps:
  - scripts.step1_select_block: load_lots + select_block_lots (elige la cuadra;
    aqui solo se conserva el centro, sin alrededores).
  - spatial.street_fronts.annotate_street_fronts: frentes de calle por lote.
  - vision.cameras.select_cameras: ranking de panoramas visibles (oclusion +
    frontalidad) por lote.
  - vision.projection.extract_full_vertical_strip: franja cilindrica centrada
    en el lote = la "foto" que usara la gramatica.
  - vision.acquisition.acquisition.get_attr/angle_to_degrees: metadata GSV.

Uso:
    python steps/step19_experimental/cuadra_fotos/extraer_fotos_cuadra.py --seed 123 --fotos-por-lote 2
    python steps/step19_experimental/cuadra_fotos/extraer_fotos_cuadra.py --seed 123 --simplify-tolerance-m 0.15

Salida (por defecto en steps/step19_experimental/cuadra_fotos/cuadra_seed_<seed>/):
    manifest.json, mapa_cuadra.png, panoramas/<pano_id>.jpg (cache unica),
    lote_<index>/lot.json + lote_<index>/fotos/vista_01.jpg ...

Todavia NO genera gramatica ni GLB: solo organiza lote + fotos por lote para
poder generar cada casa despues y unirlas en un unico modelo.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import deque
from pathlib import Path

import cv2
import geopandas as gpd
import matplotlib.pyplot as plt
import requests
import streetlevel.streetview as sv
from pyproj import Transformer
from shapely.geometry import Point
from shapely.affinity import translate
from shapely.geometry.polygon import orient

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "steps" / "step19_experimental"))

from step1_select_block import clean_geometry, load_lots, select_block_lots  # noqa: E402
from spatial import bearing_from_north, signed_angle  # noqa: E402
from spatial.street_fronts import annotate_street_fronts  # noqa: E402
from vision.acquisition.acquisition import angle_to_degrees, get_attr  # noqa: E402
from vision.cameras import select_cameras  # noqa: E402
from vision.projection import extract_full_vertical_strip  # noqa: E402

TARGET_CRS = "EPSG:32718"


def _jsonable(value):
    """Convierte escalares numpy (int64 de street_edges, etc.) a tipos JSON."""
    import numpy as np
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, np.ndarray):
        return [_jsonable(item) for item in value.tolist()]
    return value


# ── geometria del lote ──────────────────────────────────────────────────────

def simplify_lot(geometry, tolerance_m: float):
    """Funde vertices casi-duplicados y simplifica con el threshold dado."""
    coords = list(geometry.exterior.coords)
    kept = [coords[0]]
    for point in coords[1:]:
        if Point(point).distance(Point(kept[-1])) >= 0.01:
            kept.append(point)
    if len(kept) < 4:
        return geometry, {"vertices_in": len(coords) - 1, "vertices_out": len(coords) - 1, "simplified": False}
    cleaned = type(geometry)(kept)
    before = len(coords) - 1
    if tolerance_m and tolerance_m > 0:
        simplified = cleaned.simplify(tolerance_m, preserve_topology=True)
        if simplified.is_empty or simplified.geom_type != "Polygon":
            simplified = cleaned
    else:
        simplified = cleaned
    if not simplified.is_valid:
        simplified = simplified.buffer(0)
    after = len(list(simplified.exterior.coords)) - 1
    return simplified, {"vertices_in": before, "vertices_out": after, "simplified": after < before}


def front_selection(row) -> tuple[tuple[int, ...], str]:
    """Misma regla que step3: bordes medidos, o el de mayor separacion."""
    fronts = tuple(int(i) for i in row.street_edge_indices)
    if fronts:
        return fronts, "street_inferred"
    edges = row.street_edges
    if not edges:
        return (), "none"
    best = max(edges, key=lambda e: (e["minimum_clearance_m"], e["length_m"]))
    return (int(best["edge_index"]),), "fallback_unverified"


# ── candidatos GSV para toda la cuadra (una sola caminata BFS) ──────────────

def collect_block_panos(block_union, seed_points, *, max_distance_m: float, max_nodes: int):
    session = requests.Session()
    to_wgs = Transformer.from_crs(TARGET_CRS, "EPSG:4326", always_xy=True)
    first = None
    for seed in list(seed_points) + [block_union.centroid]:
        lon0, lat0 = to_wgs.transform(seed.x, seed.y)
        first = sv.find_panorama(lat0, lon0, session=session)
        if first is not None:
            print(f"[GSV] panorama inicial {first.id} cerca de ({lat0:.6f}, {lon0:.6f}).", flush=True)
            break
    if first is None:
        raise RuntimeError("No se encontro Street View cerca de la cuadra.")
    to_utm = Transformer.from_crs("EPSG:4326", TARGET_CRS, always_xy=True)
    queue, queued, seen, archive = deque([str(first.id)]), {str(first.id)}, set(), {}
    visited = 0
    while queue and visited < max_nodes:
        pano_id = queue.popleft()
        if pano_id in seen:
            continue
        seen.add(pano_id)
        visited += 1
        try:
            pano = sv.find_panorama_by_id(pano_id, session=session)
        except requests.RequestException as error:
            print(f"  [WARN] metadata {pano_id}: {error}", flush=True)
            continue
        if pano is None:
            continue
        print(f"[GSV {visited}/{max_nodes}] {pano_id}", flush=True)
        for neighbor in get_attr(pano, "neighbors", []) or []:
            nid = str(neighbor.id)
            if nid not in seen and nid not in queued:
                queue.append(nid)
                queued.add(nid)
        try:
            x, y = to_utm.transform(float(get_attr(pano, "lon")), float(get_attr(pano, "lat")))
        except (TypeError, ValueError):
            continue
        if Point(x, y).distance(block_union) > max_distance_m:
            continue
        heading, _ = angle_to_degrees(get_attr(pano, "heading"))
        archive[pano_id] = {
            "pano_id": pano_id,
            "lat": float(get_attr(pano, "lat")),
            "lon": float(get_attr(pano, "lon")),
            "date": str(get_attr(pano, "date")) if get_attr(pano, "date") else None,
            "heading_deg": heading,
        }
    print(f"[GSV] {len(archive)} panoramas a <= {max_distance_m} m de la cuadra.", flush=True)
    return archive


def ensure_panorama(pano_id: str, cache_dir: Path, zoom: int) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    raw_path = cache_dir / f"{pano_id}.jpg"
    if raw_path.exists():
        return raw_path
    print(f"  descargando panorama {pano_id} (zoom {zoom})...", flush=True)
    pano = sv.find_panorama_by_id(pano_id)
    image = sv.get_panorama(pano, zoom=zoom)
    if image is None:
        raise RuntimeError(f"No se pudo descargar el panorama {pano_id}")
    image.save(raw_path, "JPEG", quality=95)
    return raw_path


# ── main ────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=123)
    parser.add_argument("--fotos-por-lote", type=int, default=2)
    parser.add_argument("--simplify-tolerance-m", type=float, default=0.10,
                        help="threshold que funde vertices cercanos del lote")
    parser.add_argument("--zoom", type=int, default=3)
    parser.add_argument("--fov", type=float, default=120.0)
    parser.add_argument("--strip-width", type=int, default=1600)
    parser.add_argument("--max-camera-distance-m", type=float, default=60.0)
    parser.add_argument("--fallback-distance-m", type=float, default=150.0)
    parser.add_argument("--max-nodes", type=int, default=100)
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()
    if args.fotos_por_lote < 1:
        parser.error("--fotos-por-lote debe ser >= 1")

    output_dir = (args.output_dir or (ROOT / "steps" / "step19_experimental" / "cuadra_fotos" / f"cuadra_seed_{args.seed}")).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    pano_cache = output_dir / "panoramas"

    lots = load_lots()
    # select_block_lots devuelve (centro, seleccion_con_alrededores, semilla);
    # aqui solo se conserva el centro: la cuadra, sin alrededores.
    centre, _, seed_index = select_block_lots(lots, seed=args.seed)
    centre = sorted(centre)
    print(f"Cuadra central (seed {args.seed}, lote semilla {seed_index}): {len(centre)} lotes, sin alrededores.", flush=True)

    block_abs = lots.loc[centre].copy()
    origin = block_abs.geometry.union_all().centroid
    to_wgs = Transformer.from_crs(TARGET_CRS, "EPSG:4326", always_xy=True)
    _to_utm = Transformer.from_crs("EPSG:4326", TARGET_CRS, always_xy=True)

    translated, simplify_report = {}, {}
    for index in centre:
        geom = block_abs.loc[index].geometry
        geom = clean_geometry(geom.__class__(geom.exterior.coords))
        simplified, report = simplify_lot(geom, args.simplify_tolerance_m)
        simplify_report[index] = report
        translated[index] = translate(simplified, xoff=-origin.x, yoff=-origin.y)
    lots_local = gpd.GeoDataFrame({"geometry": [translated[i] for i in centre]},
                                  index=centre, crs=TARGET_CRS)
    lots_local.geometry = lots_local.geometry.apply(clean_geometry)
    lots_local = annotate_street_fronts(lots_local)

    archive = collect_block_panos(
        block_abs.geometry.union_all(),
        [block_abs.loc[i].geometry.centroid for i in centre],
        max_distance_m=args.fallback_distance_m,
        max_nodes=args.max_nodes)
    (output_dir / "panoramas_metadata.json").write_text(
        json.dumps(archive, indent=2, ensure_ascii=False), encoding="utf-8")
    archive_list = list(archive.values())

    results = []
    for order, index in enumerate(centre, 1):
        lot_dir = output_dir / f"lote_{index}"
        fotos_dir = lot_dir / "fotos"
        fotos_dir.mkdir(parents=True, exist_ok=True)
        record = {"order": order, "lot_index": index, "status": "failed",
                  "fronts": [], "front_source": "none", "cameras": [], "error": ""}
        print(f"[{order}/{len(centre)}] lote={index} ...", flush=True)
        try:
            row = lots_local.loc[index]
            if row.geometry.geom_type != "Polygon":
                raise ValueError("geometria no poligonal")
            fronts, source = front_selection(row)
            record["fronts"], record["front_source"] = list(fronts), source
            abs_geom = block_abs.loc[index].geometry.__class__(
                [(x + origin.x, y + origin.y) for x, y in translated[index].exterior.coords])
            abs_geom = clean_geometry(abs_geom)
            cameras = select_cameras(lots, index, abs_geom, archive_list,
                                     args.max_camera_distance_m, args.fotos_por_lote)
            if len(cameras) < args.fotos_por_lote and args.fallback_distance_m > args.max_camera_distance_m:
                cameras = select_cameras(lots, index, abs_geom, archive_list,
                                         args.fallback_distance_m, args.fotos_por_lote)
            for camera in cameras:
                camera["visibility"] = "verificada"
            # Los que no se ven (interiores/pasajes): completar con las mas
            # cercanas, marcadas sin_visibilidad. Sirven para inspeccion
            # manual, no como evidencia de fachada.
            if len(cameras) < args.fotos_por_lote:
                used = {c["pano_id"] for c in cameras}
                centroid_xy = abs_geom.centroid
                nearest = []
                for entry in archive_list:
                    if entry["pano_id"] in used:
                        continue
                    try:
                        x, y = _to_utm.transform(float(entry["lon"]), float(entry["lat"]))
                    except (TypeError, ValueError):
                        continue
                    dist = Point(x, y).distance(abs_geom)
                    if dist <= args.fallback_distance_m:
                        nearest.append((dist, entry, x, y))
                nearest.sort(key=lambda item: item[0])
                for dist, entry, x, y in nearest[:args.fotos_por_lote - len(cameras)]:
                    bearing = bearing_from_north(Point(x, y), centroid_xy)
                    cameras.append({
                        **entry,
                        "camera_x": x, "camera_y": y,
                        "camera_to_lot_m": dist,
                        "target_edge_index": None,
                        "target_x": centroid_xy.x, "target_y": centroid_xy.y,
                        "target_bearing_deg": bearing,
                        "relative_yaw_deg": signed_angle(
                            bearing - float(entry["heading_deg"]) % 360.0),
                        "visibility": "sin_visibilidad",
                    })
            if not cameras:
                raise ValueError("sin panoramas cercanos para este lote")
            verified = sum(c["visibility"] == "verificada" for c in cameras)
            record["status"] = ("ok" if verified == len(cameras)
                                else "parcial" if verified else "sin_visibilidad")
            polygon = orient(row.geometry, sign=1.0)
            for rank, camera in enumerate(cameras, 1):
                raw_path = ensure_panorama(camera["pano_id"], pano_cache, args.zoom)
                panorama = cv2.imread(str(raw_path), cv2.IMREAD_COLOR)
                if panorama is None:
                    raise RuntimeError(f"No se pudo leer {raw_path}")
                view = extract_full_vertical_strip(
                    panorama, center_yaw_deg=camera["relative_yaw_deg"],
                    horizontal_fov_deg=args.fov, width=args.strip_width)
                view_name = f"vista_{rank:02d}_{camera['pano_id']}.jpg"
                cv2.imwrite(str(fotos_dir / view_name), view, [cv2.IMWRITE_JPEG_QUALITY, 92])
                record["cameras"].append({
                    "rank": rank, "pano_id": camera["pano_id"],
                    "lat": camera["lat"], "lon": camera["lon"], "date": camera.get("date"),
                    "camera_to_lot_m": round(camera["camera_to_lot_m"], 2),
                    "target_edge_index": camera["target_edge_index"],
                    "target_bearing_deg": round(camera["target_bearing_deg"], 2),
                    "relative_yaw_deg": round(camera["relative_yaw_deg"], 2),
                    "visibility": camera.get("visibility", "verificada"),
                    "raw_panorama": str(raw_path.relative_to(output_dir)),
                    "vista": str((fotos_dir / view_name).relative_to(output_dir)),
                })
            centroid = row.geometry.centroid
            lon_c, lat_c = to_wgs.transform(centroid.x + origin.x, centroid.y + origin.y)
            (lot_dir / "lot.json").write_text(json.dumps(_jsonable({
                "lot_index": index,
                "crs": TARGET_CRS,
                "local_origin_utm": [origin.x, origin.y],
                "centroid_lat": lat_c,
                "centroid_lon": lon_c,
                "parcel_local_m": [list(map(float, xy)) for xy in polygon.exterior.coords],
                "fronts": list(fronts),
                "front_source": source,
                "street_edges": row.street_edges,
                "area_m2": round(float(row.geometry.area), 2),
                "simplify_tolerance_m": args.simplify_tolerance_m,
                "simplify": simplify_report[index],
                "seed": args.seed,
                "status": record["status"],
                "cameras": record["cameras"],
            }), indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"  {record['status']}: frentes={list(fronts)} ({source}), "
                  f"fotos={len(record['cameras'])}", flush=True)
        except Exception as error:  # un lote no tumba la cuadra
            record["error"] = f"{type(error).__name__}: {error}"
            print(f"  FALLO lote {index}: {record['error']}", flush=True)
        results.append(record)

    (output_dir / "manifest.json").write_text(json.dumps(_jsonable({
        "seed": args.seed,
        "seed_lot_index": str(seed_index),
        "lots": len(centre),
        "ok": sum(r["status"] == "ok" for r in results),
        "parcial": sum(r["status"] == "parcial" for r in results),
        "sin_visibilidad": sum(r["status"] == "sin_visibilidad" for r in results),
        "failed": sum(r["status"] == "failed" for r in results),
        "params": {"fotos_por_lote": args.fotos_por_lote,
                   "simplify_tolerance_m": args.simplify_tolerance_m,
                   "zoom": args.zoom, "fov": args.fov,
                   "max_camera_distance_m": args.max_camera_distance_m,
                   "fallback_distance_m": args.fallback_distance_m},
        "results": results,
    }), indent=2, ensure_ascii=False), encoding="utf-8")

    fig, ax = plt.subplots(figsize=(10, 10))
    lots_local.plot(ax=ax, edgecolor="black", facecolor="lightgray")
    lots_local.plot(ax=ax, edgecolor="red", facecolor="salmon", alpha=0.45)
    for index in centre:
        centroid = lots_local.loc[index].geometry.centroid
        ax.text(centroid.x, centroid.y, str(index), fontsize=8, ha="center")
    ax.set_title(f"Cuadra seed={args.seed} ({len(centre)} lotes, solo centro)")
    fig.savefig(output_dir / "mapa_cuadra.png", dpi=130, bbox_inches="tight")
    plt.close(fig)
    print(f"Listo: {sum(r['status'] == 'ok' for r in results)}/{len(centre)} lotes ok. {output_dir}", flush=True)


if __name__ == "__main__":
    main()
