"""Data model and manifest builder for the per-lot multiview pipeline.

The manifest deliberately references images instead of copying them.  This
keeps the input reproducible while avoiding a second, silently diverging image
dataset.  Geometry is stored in the local metric CRS used by the cadastral
data and also in WGS84 for inspection and interchange.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any

import geopandas as gpd
from pyproj import Transformer


SCHEMA_VERSION = 1


@dataclass(frozen=True)
class ViewMetadata:
    """One Street View panorama and its derived projection assets."""

    pano_id: str
    image_path: str
    cylindrical_path: str | None
    lat: float
    lon: float
    heading_deg: float
    pitch_deg: float | None
    roll_deg: float | None
    capture_year: int | None
    date: str | None
    relative_yaw_deg: float | None
    target_bearing_deg: float | None
    camera_to_lot_m: float | None


@dataclass(frozen=True)
class LotMultiviewInput:
    """Complete, JSON-serializable context for one lot reconstruction."""

    schema_version: int
    objectid: int
    source_row: int
    crs: str
    polygon_utm: list[list[float]]
    polygon_wgs84: list[list[float]]
    centroid_utm: list[float]
    target_coordinate: dict[str, float]
    projection: dict[str, Any]
    views: list[ViewMetadata]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _ring_coordinates(geometry) -> list[list[float]]:
    if geometry.geom_type != "Polygon":
        raise ValueError(f"Se esperaba Polygon, se recibió {geometry.geom_type}")
    return [[float(x), float(y)] for x, y in geometry.exterior.coords]


def build_lot_input(
    shapefile: Path,
    manifest: Path,
    objectid: int,
    *,
    views: int | None = None,
) -> LotMultiviewInput:
    """Build a lot input from the cadastral polygon and Step 5 manifest.

    The manifest is authoritative for image paths and camera pose.  Images
    absent on disk are rejected early, so later height estimation cannot mix a
    valid pose with a missing or stale raster.
    """
    data = json.loads(manifest.read_text())
    if int(data['target_objectid']) != int(objectid):
        raise ValueError('El manifiesto debe pertenecer al lote solicitado; genera sus vistas primero')
    if views is not None and views < 1:
        raise ValueError('views debe ser positivo')
    gdf = gpd.read_file(shapefile).to_crs("EPSG:32718")
    matches = gdf[gdf["objectid"].astype(int) == int(objectid)]
    if matches.empty:
        raise ValueError(f"No existe OBJECTID={objectid} en {shapefile}")
    row = matches.iloc[0]
    geometry = row.geometry
    polygon_utm = _ring_coordinates(geometry)
    to_wgs84 = Transformer.from_crs("EPSG:32718", "EPSG:4326", always_xy=True)
    polygon_wgs84 = [[float(lon), float(lat)] for lon, lat in
                     (to_wgs84.transform(x, y) for x, y in polygon_utm)]
    centroid = geometry.centroid
    centroid_lon, centroid_lat = to_wgs84.transform(centroid.x, centroid.y)

    manifest_root = manifest.parent
    selected = data["cameras"][:views] if views else data["cameras"]
    view_models: list[ViewMetadata] = []
    for camera in selected:
        image = manifest_root / camera["raw_image"]
        if not image.is_file():
            raise FileNotFoundError(f"Imagen 360 ausente: {image}")
        cylindrical = manifest_root / camera["cylindrical_view"]
        view_models.append(ViewMetadata(
            pano_id=str(camera["pano_id"]),
            image_path=str(image.resolve()),
            cylindrical_path=str(cylindrical.resolve()) if cylindrical.is_file() else None,
            lat=float(camera["lat"]), lon=float(camera["lon"]),
            heading_deg=float(camera["heading_deg"]),
            pitch_deg=float(camera["pitch_deg"]) if camera.get("pitch_deg") is not None else None,
            roll_deg=float(camera["roll_deg"]) if camera.get("roll_deg") is not None else None,
            capture_year=int(camera["capture_year"]) if camera.get("capture_year") else None,
            date=camera.get("date"),
            relative_yaw_deg=float(camera["relative_yaw_deg"]) if camera.get("relative_yaw_deg") is not None else None,
            target_bearing_deg=float(camera["target_bearing_deg"]) if camera.get("target_bearing_deg") is not None else None,
            camera_to_lot_m=float(camera["camera_to_lot_m"]) if camera.get("camera_to_lot_m") is not None else None,
        ))
    if not view_models:
        raise ValueError("El input multivista debe contener al menos una cámara")

    return LotMultiviewInput(
        schema_version=SCHEMA_VERSION,
        objectid=int(row["objectid"]),
        source_row=int(matches.index[0]),
        crs="EPSG:32718",
        polygon_utm=polygon_utm,
        polygon_wgs84=polygon_wgs84,
        centroid_utm=[float(centroid.x), float(centroid.y)],
        target_coordinate={"lat": float(centroid_lat), "lon": float(centroid_lon)},
        projection={
            "type": data.get("projection"),
            "horizontal_fov_deg": data.get("horizontal_fov_deg"),
            "vertical_range_deg": data.get("vertical_range_deg"),
            "pitch_center_deg": data.get("pitch_center_deg"),
            "source_manifest": str(manifest.resolve()),
        },
        views=view_models,
    )


def write_input(input_data: LotMultiviewInput, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(input_data.to_dict(), indent=2, ensure_ascii=False) + "\n")
