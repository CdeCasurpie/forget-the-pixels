"""Selecciona un lote aleatorio con cámaras cercanas desde metadata local."""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

import geopandas as gpd
from pyproj import Transformer
from shapely.geometry import Point


TARGET_CRS = "EPSG:32718"
LOT_SHP_NAME = "BARRANCO_LM_geogpsperu_SuyoPomalia.shp"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def main() -> None:
    root = repo_root()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, default=root / "investigation/proy_geom/steps/step2_vector_to_lots/data/barranco_metadata/metadata.json")
    parser.add_argument("--shapefile", type=Path, default=root / "investigation/Lotes/shp_files" / LOT_SHP_NAME)
    parser.add_argument("--output", type=Path, default=root / "investigation/proy_geom/steps/step2_vector_to_lots/data/random_candidates")
    parser.add_argument("--max-camera-distance-m", type=float, default=150.0)
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()

    if not args.archive.exists():
        raise RuntimeError("No existe el archivo maestro. Ejecuta primero: make download-gsv-metadata-barranco")
    archive = json.loads(args.archive.read_text(encoding="utf-8"))
    panoramas = archive.get("panoramas", {})
    if not panoramas:
        raise RuntimeError("El archivo maestro todavía no contiene panoramas.")

    lots = gpd.read_file(args.shapefile).to_crs(TARGET_CRS)
    transformer = Transformer.from_crs("EPSG:4326", TARGET_CRS, always_xy=True)
    camera_rows = []
    for key, entry in panoramas.items():
        x, y = transformer.transform(float(entry["lon"]), float(entry["lat"]))
        camera_rows.append({"key": key, "entry": entry, "geometry": Point(x, y)})
    cameras = gpd.GeoDataFrame(camera_rows, crs=TARGET_CRS)
    spatial_index = cameras.sindex

    lot_indices = list(lots.index)
    random.Random(args.seed).shuffle(lot_indices)
    selected_lot = None
    selected_entries = {}
    for lot_index in lot_indices:
        lot = lots.loc[lot_index]
        nearby_positions = spatial_index.query(lot.geometry.buffer(args.max_camera_distance_m), predicate="intersects")
        nearby = {}
        for position in nearby_positions:
            camera = cameras.iloc[int(position)]
            if camera.geometry.distance(lot.geometry) <= args.max_camera_distance_m:
                nearby[camera["key"]] = camera["entry"]
        if nearby:
            selected_lot = (int(lot_index), lot)
            selected_entries = nearby
            break
    if selected_lot is None:
        raise RuntimeError("No hay ningún lote con cámaras cercanas en la metadata disponible.")

    lot_index, lot = selected_lot
    args.output.mkdir(parents=True, exist_ok=True)
    output_metadata = {
        "experiment": "gsv_step2_candidates_from_barranco_archive",
        "source_archive": str(args.archive),
        "images_downloaded": False,
        "max_camera_distance_m": args.max_camera_distance_m,
        "panoramas": selected_entries,
    }
    selection = {
        "lot_row": lot_index,
        "objectid": int(lot.objectid),
        "candidate_count": len(selected_entries),
        "images_downloaded": False,
    }
    (args.output / "metadata.json").write_text(json.dumps(output_metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    (args.output / "selection.json").write_text(json.dumps(selection, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Lote aleatorio elegible: row={lot_index}, objectid={int(lot.objectid)}")
    print(f"Cámaras cercanas desde archivo local: {len(selected_entries)}")
    print("Consultas a Google: 0; imágenes descargadas: 0")


if __name__ == "__main__":
    main()
