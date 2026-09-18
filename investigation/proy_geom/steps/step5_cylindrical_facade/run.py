"""Paso 5: descarga y proyección cilíndrica de las cuatro mejores cámaras."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import cv2
import geopandas as gpd
import matplotlib.pyplot as plt
import streetlevel.streetview as sv
from pyproj import Transformer
from shapely.geometry import Point


THIS_DIR = Path(__file__).resolve().parent
PROY_GEOM = THIS_DIR.parents[1]
REPO_ROOT = THIS_DIR.parents[3]
sys.path.insert(0, str(PROY_GEOM / "src"))

from geometry_projection import extract_full_vertical_strip  # noqa: E402
from cadastral_geometry import find_target_lot
from camera_selection import select_cameras


TARGET_CRS = "EPSG:32718"
LOT_SHP_NAME = "BARRANCO_LM_geogpsperu_SuyoPomalia.shp"


def load_archive(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    panoramas = payload.get("panoramas", {})
    return list(panoramas.values()) if isinstance(panoramas, dict) else panoramas


def annotate(image, camera: dict, rank: int) -> None:
    lines = [
        f"CAMARA {rank} | {camera['pano_id']}",
        f"distancia={camera['camera_to_lot_m']:.2f}m  bearing={camera['target_bearing_deg']:.2f}deg",
        f"heading={float(camera['heading_deg']):.2f}deg  yaw relativo={camera['relative_yaw_deg']:.2f}deg",
        "vertical: cenit (+90) a nadir (-90)",
    ]
    for index, line in enumerate(lines):
        y = 48 + index * 42
        cv2.putText(image, line, (24, y), cv2.FONT_HERSHEY_SIMPLEX, 0.75,
                    (0, 0, 0), 5, cv2.LINE_AA)
        cv2.putText(image, line, (24, y), cv2.FONT_HERSHEY_SIMPLEX, 0.75,
                    (255, 255, 255), 2, cv2.LINE_AA)


def draw_selection_map(gdf, target_index: int, cameras: list[dict], output: Path) -> None:
    fig, ax = plt.subplots(figsize=(10, 9))
    gdf.boundary.plot(ax=ax, color="#c8d1da", linewidth=0.3)
    gpd.GeoSeries([gdf.loc[target_index].geometry], crs=gdf.crs).plot(
        ax=ax, color="#ffe082", edgecolor="#1565c0", linewidth=2.2
    )
    xs, ys = [], []
    for rank, camera in enumerate(cameras, start=1):
        xs.append(camera["camera_x"])
        ys.append(camera["camera_y"])
        ax.plot(
            [camera["camera_x"], camera["target_x"]],
            [camera["camera_y"], camera["target_y"]],
            color="#2ca02c", linewidth=1.5,
        )
        ax.scatter(camera["camera_x"], camera["camera_y"], color="#d62728", s=48, zorder=5)
        ax.text(camera["camera_x"] + 1, camera["camera_y"] + 1, str(rank), fontweight="bold")
    bounds = gdf.loc[target_index].geometry.bounds
    all_x = xs + [bounds[0], bounds[2]]
    all_y = ys + [bounds[1], bounds[3]]
    margin = 30
    ax.set_xlim(min(all_x) - margin, max(all_x) + margin)
    ax.set_ylim(min(all_y) - margin, max(all_y) + margin)
    ax.set_aspect("equal")
    ax.set_title("Paso 5 — cuatro cámaras visibles seleccionadas")
    ax.set_xlabel("UTM Este (m)")
    ax.set_ylabel("UTM Norte (m)")
    fig.tight_layout()
    fig.savefig(output, dpi=180)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lat", type=float, default=-12.135895)
    parser.add_argument("--lon", type=float, default=-77.019184)
    parser.add_argument("--top-k", type=int, default=4)
    parser.add_argument("--max-distance-m", type=float, default=150.0)
    parser.add_argument("--horizontal-fov-deg", type=float, default=120.0)
    parser.add_argument("--width", type=int, default=1600)
    parser.add_argument("--zoom", type=int, default=3)
    parser.add_argument("--lot-tolerance-m", type=float, default=1.0)
    parser.add_argument("--archive", type=Path, default=PROY_GEOM / "steps/step2_vector_to_lots/data/barranco_metadata/metadata.json")
    parser.add_argument("--shapefile", type=Path, default=REPO_ROOT / "investigation/Lotes/shp_files" / LOT_SHP_NAME)
    parser.add_argument("--output", type=Path, default=THIS_DIR / "outputs/lot_-12.135895_-77.019184")
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    raw_dir = args.output / "panoramas"
    views_dir = args.output / "cylindrical_views"
    previews_dir = args.output / "previews"
    for directory in (raw_dir, views_dir, previews_dir):
        directory.mkdir(parents=True, exist_ok=True)

    gdf = gpd.read_file(args.shapefile).to_crs(TARGET_CRS)
    target_index, target_row, query_point, snap_distance = find_target_lot(
        gdf, args.lat, args.lon, args.lot_tolerance_m
    )
    cameras = select_cameras(
        gdf,
        target_index,
        target_row.geometry,
        load_archive(args.archive),
        args.max_distance_m,
        args.top_k,
    )
    if len(cameras) < args.top_k:
        raise RuntimeError(f"Solo se encontraron {len(cameras)} cámaras visibles; se solicitaron {args.top_k}.")

    for rank, camera in enumerate(cameras, start=1):
        pano_id = camera["pano_id"]
        raw_path = raw_dir / f"{rank:02d}_{pano_id}.jpg"
        if not raw_path.exists():
            print(f"[{rank}/{len(cameras)}] descargando panorama {pano_id}...", flush=True)
            pano = sv.find_panorama_by_id(pano_id)
            image = sv.get_panorama(pano, zoom=args.zoom)
            image.save(raw_path, "JPEG", quality=95)
        panorama = cv2.imread(str(raw_path), cv2.IMREAD_COLOR)
        if panorama is None:
            raise RuntimeError(f"No se pudo leer {raw_path}")
        view = extract_full_vertical_strip(
            panorama,
            center_yaw_deg=camera["relative_yaw_deg"],
            horizontal_fov_deg=args.horizontal_fov_deg,
            width=args.width,
        )
        view_path = views_dir / f"{rank:02d}_{pano_id}_cylindrical.jpg"
        preview_path = previews_dir / f"{rank:02d}_{pano_id}_annotated.jpg"
        cv2.imwrite(str(view_path), view, [cv2.IMWRITE_JPEG_QUALITY, 95])
        preview = view.copy()
        annotate(preview, camera, rank)
        cv2.imwrite(str(preview_path), preview, [cv2.IMWRITE_JPEG_QUALITY, 92])
        camera["raw_image"] = str(raw_path.relative_to(args.output))
        camera["cylindrical_view"] = str(view_path.relative_to(args.output))

    report = {
        "step": 5,
        "projection": "full_vertical_angular_cylindrical_strip",
        "target_coordinate": {"lat": args.lat, "lon": args.lon},
        "target_lot_row": target_index,
        "target_objectid": int(target_row.objectid),
        "coordinate_to_lot_distance_m": snap_distance,
        "horizontal_fov_deg": args.horizontal_fov_deg,
        "vertical_range_deg": [-90.0, 90.0],
        "pitch_center_deg": 0.0,
        "cameras": cameras,
    }
    (args.output / "projection_metadata.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    draw_selection_map(gdf, target_index, cameras, args.output / "selected_cameras_map.png")
    print(f"Lote: row={target_index}, objectid={int(target_row.objectid)}")
    print(f"Vistas cilíndricas: {views_dir}")
    print(f"Metadata: {args.output / 'projection_metadata.json'}")


if __name__ == "__main__":
    main()
