"""Selecciona un lote aleatorio y consulta candidatos GSV sin descargar imágenes."""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import deque
from pathlib import Path
from typing import Any

import geopandas as gpd
import requests
import streetlevel.streetview as sv
from pyproj import Transformer
from shapely.geometry import Point

# Permite ejecutar este experimento directamente desde el Makefile sin
# instalar todavía el paquete reusable del pipeline.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from vision.acquisition.acquisition import angle_to_degrees, get_attr


LOT_SHP_NAME = "BARRANCO_LM_geogpsperu_SuyoPomalia.shp"
TARGET_CRS = "EPSG:32718"
DEFAULT_LAT = -12.137248
DEFAULT_LON = -77.020423


class TimeoutSession(requests.Session):
    def request(self, method, url, **kwargs):
        kwargs.setdefault("timeout", 20)
        return super().request(method, url, **kwargs)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def metadata_entry(pano: Any) -> dict[str, Any]:
    heading, heading_unit = angle_to_degrees(get_attr(pano, "heading"))
    pitch, pitch_unit = angle_to_degrees(get_attr(pano, "pitch"))
    roll, roll_unit = angle_to_degrees(get_attr(pano, "roll"))
    return {
        "pano_id": str(pano.id),
        "lat": float(get_attr(pano, "lat")),
        "lon": float(get_attr(pano, "lon")),
        "date": str(get_attr(pano, "date")) if get_attr(pano, "date") else None,
        "heading_deg": heading,
        "heading_raw": get_attr(pano, "heading"),
        "heading_input_unit": heading_unit,
        "pitch_deg": pitch,
        "pitch_raw": get_attr(pano, "pitch"),
        "pitch_input_unit": pitch_unit,
        "roll_deg": roll,
        "roll_raw": get_attr(pano, "roll"),
        "roll_input_unit": roll_unit,
        "image_downloaded": False,
    }


def choose_lot(shapefile: Path, lat: float, lon: float, radius_m: float, seed: int | None):
    gdf = gpd.read_file(shapefile).to_crs(TARGET_CRS)
    transformer = Transformer.from_crs("EPSG:4326", TARGET_CRS, always_xy=True)
    x, y = transformer.transform(lon, lat)
    center = Point(x, y)
    candidates = gdf[gdf.geometry.centroid.distance(center) <= radius_m]
    if candidates.empty:
        raise RuntimeError("No hay lotes dentro del área solicitada.")
    rng = random.Random(seed)
    index = rng.choice(list(candidates.index))
    row = gdf.loc[index]
    centroid = row.geometry.centroid
    lon_target, lat_target = Transformer.from_crs(TARGET_CRS, "EPSG:4326", always_xy=True).transform(centroid.x, centroid.y)
    return gdf, int(index), row, float(lat_target), float(lon_target)


def collect_nearby_metadata(lat: float, lon: float, target_geometry, gdf, max_distance_m: float, max_nodes: int):
    session = TimeoutSession()
    print("[GSV] Buscando panorama inicial...", flush=True)
    first = sv.find_panorama(lat, lon, session=session)
    if not first:
        raise RuntimeError(f"No se encontró Street View cerca de ({lat}, {lon}).")
    transformer = Transformer.from_crs("EPSG:4326", TARGET_CRS, always_xy=True)
    queue = deque([str(first.id)])
    queued = {str(first.id)}
    seen: set[str] = set()
    selected: dict[str, dict] = {}
    visited = 0
    while queue and visited < max_nodes:
        pano_id = queue.popleft()
        if pano_id in seen:
            continue
        print(f"[GSV {visited + 1}/{max_nodes}] metadata {pano_id}", flush=True)
        try:
            candidate = sv.find_panorama_by_id(pano_id, session=session)
        except requests.RequestException as error:
            print(f"  [WARN] {error}", flush=True)
            seen.add(pano_id)
            continue
        if not candidate:
            seen.add(pano_id)
            continue
        seen.add(pano_id)
        visited += 1
        lat_pano = float(get_attr(candidate, "lat"))
        lon_pano = float(get_attr(candidate, "lon"))
        x, y = transformer.transform(lon_pano, lat_pano)
        camera = Point(x, y)
        if camera.distance(target_geometry) <= max_distance_m:
            selected[pano_id] = metadata_entry(candidate)
        for neighbor in get_attr(candidate, "neighbors", []) or []:
            neighbor_id = str(neighbor.id)
            if neighbor_id not in seen and neighbor_id not in queued:
                queue.append(neighbor_id)
                queued.add(neighbor_id)
    return selected, visited


def main() -> None:
    root = repo_root()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lat", type=float, default=DEFAULT_LAT, help="Centro del área aleatoria.")
    parser.add_argument("--lon", type=float, default=DEFAULT_LON)
    parser.add_argument("--area-radius-m", type=float, default=250.0)
    parser.add_argument("--max-camera-distance-m", type=float, default=100.0)
    parser.add_argument("--max-nodes", type=int, default=80)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--shapefile", type=Path, default=root / "investigation/Lotes/shp_files" / LOT_SHP_NAME)
    parser.add_argument("--output", type=Path, default=root / "investigation/proy_geom/steps/step2_vector_to_lots/data/random_candidates")
    args = parser.parse_args()

    gdf, lot_index, lot, lot_lat, lot_lon = choose_lot(args.shapefile, args.lat, args.lon, args.area_radius_m, args.seed)
    selected, visited = collect_nearby_metadata(lot_lat, lot_lon, lot.geometry, gdf, args.max_camera_distance_m, args.max_nodes)
    if not selected:
        raise RuntimeError(
            f"El lote aleatorio row={lot_index} no tiene cámaras a menos de "
            f"{args.max_camera_distance_m:.1f} m. Aumenta el radio o cambia el área."
        )

    args.output.mkdir(parents=True, exist_ok=True)
    metadata = {
        "experiment": "gsv_step2_metadata_candidates",
        "library": "streetlevel.streetview",
        "images_downloaded": False,
        "area_center": {"lat": args.lat, "lon": args.lon, "radius_m": args.area_radius_m},
        "target_lot": {
            "row": lot_index,
            "objectid": int(lot.objectid),
            "centroid_lat": lot_lat,
            "centroid_lon": lot_lon,
        },
        "max_camera_distance_m": args.max_camera_distance_m,
        "streetview_nodes_visited": visited,
        "panoramas": {f"{index:03d}_{pano_id}": entry for index, (pano_id, entry) in enumerate(sorted(selected.items()))},
    }
    (args.output / "metadata.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    (args.output / "selection.json").write_text(json.dumps({
        "lot_row": lot_index,
        "objectid": int(lot.objectid),
        "lot_centroid_lat": lot_lat,
        "lot_centroid_lon": lot_lon,
        "candidate_count": len(selected),
        "images_downloaded": False,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Lote aleatorio: row={lot_index}, objectid={int(lot.objectid)}")
    print(f"Centroide: lat={lot_lat:.7f}, lon={lot_lon:.7f}")
    print(f"Candidatos GSV cercanos: {len(selected)}; imágenes descargadas: 0")
    print(f"Metadata: {args.output / 'metadata.json'}")


if __name__ == "__main__":
    main()
