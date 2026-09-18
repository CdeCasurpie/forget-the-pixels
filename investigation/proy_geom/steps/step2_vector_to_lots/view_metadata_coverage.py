"""Mapa de cobertura de la metadata GSV disponible sobre Barranco."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
from pyproj import Transformer
from shapely.geometry import MultiPoint, Point


TARGET_CRS = "EPSG:32718"
LOT_SHP_NAME = "BARRANCO_LM_geogpsperu_SuyoPomalia.shp"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def main() -> None:
    root = repo_root()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--shapefile", type=Path, default=root / "investigation/Lotes/shp_files" / LOT_SHP_NAME)
    parser.add_argument("--output", type=Path, default=root / "investigation/proy_geom/steps/step2_vector_to_lots/outputs/barranco_camera_coverage.png")
    args = parser.parse_args()

    payload = json.loads(args.metadata.read_text(encoding="utf-8"))
    panoramas = payload.get("panoramas", {})
    entries = list(panoramas.values()) if isinstance(panoramas, dict) else panoramas
    if not entries:
        raise RuntimeError(f"No hay panoramas en {args.metadata}")

    transformer = Transformer.from_crs("EPSG:4326", TARGET_CRS, always_xy=True)
    points = [Point(*transformer.transform(float(item["lon"]), float(item["lat"]))) for item in entries]
    lots = gpd.read_file(args.shapefile).to_crs(TARGET_CRS)
    lots_union = lots.geometry.union_all()
    inside_count = sum(lots_union.covers(point) for point in points)

    fig, ax = plt.subplots(figsize=(11, 14))
    lots.boundary.plot(ax=ax, color="#c9d1d9", linewidth=0.22, zorder=1)
    cameras = gpd.GeoSeries(points, crs=TARGET_CRS)
    cameras.plot(ax=ax, color="#d62728", markersize=10, alpha=0.85, zorder=4)
    if len(points) >= 3:
        hull = MultiPoint(points).convex_hull
        gpd.GeoSeries([hull], crs=TARGET_CRS).boundary.plot(
            ax=ax, color="#ff7f0e", linewidth=1.7, linestyle="--", zorder=3
        )
    ax.set_aspect("equal")
    ax.set_title(
        f"Cobertura GSV disponible en Barranco — {len(points)} panoramas\n"
        f"Rojo: posiciones guardadas · Dentro de lotes por desfase: {inside_count}"
    )
    ax.set_xlabel("UTM Este (m), EPSG:32718")
    ax.set_ylabel("UTM Norte (m), EPSG:32718")
    fig.tight_layout()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output, dpi=180)
    plt.close(fig)
    print(f"Panoramas únicos mostrados: {len(points)}")
    print(f"Posiciones dentro de lotes por desalineamiento: {inside_count}")
    print(f"Mapa: {args.output}")


if __name__ == "__main__":
    main()
