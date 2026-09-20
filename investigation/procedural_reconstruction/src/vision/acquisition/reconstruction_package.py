"""Versioned package adapter for one lot and its selected panorama views."""
from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd

from domain import Alignment2D, CameraPose, LotGeometry, PanoramaView, ReconstructionInput


def build_reconstruction_input(shapefile: Path, manifest: Path, objectid: int, *, views: int | None = None) -> ReconstructionInput:
    """Create the canonical package from a Step 5 manifest and cadastral lot."""
    data = json.loads(manifest.read_text())
    if int(data["target_objectid"]) != int(objectid):
        raise ValueError("El manifiesto debe pertenecer al lote solicitado; genera sus vistas primero")
    if views is not None and views < 1:
        raise ValueError("views debe ser positivo")
    crs = "EPSG:32718"
    gdf = gpd.read_file(shapefile).to_crs(crs)
    matches = gdf[gdf["objectid"].astype(int) == int(objectid)]
    if matches.empty:
        raise ValueError(f"No existe OBJECTID={objectid} en {shapefile}")
    row = matches.iloc[0]
    footprint = tuple((float(x), float(y)) for x, y in row.geometry.exterior.coords)
    lot = LotGeometry(
        objectid=int(row["objectid"]), crs=crs, footprint_xy=footprint,
        source_row=int(matches.index[0]),
    )
    manifest_root = manifest.parent
    selected = data["cameras"][:views] if views else data["cameras"]
    panorama_views = tuple(
        PanoramaView(
            pano_id=str(item["pano_id"]),
            image_path=(manifest_root / item["raw_image"]).resolve(),
            cylindrical_path=(manifest_root / item["cylindrical_view"]).resolve()
            if (manifest_root / item["cylindrical_view"]).is_file() else None,
            pose=CameraPose(
                float(item["lat"]), float(item["lon"]), float(item["heading_deg"]),
                float(item["pitch_deg"]) if item.get("pitch_deg") is not None else None,
                float(item["roll_deg"]) if item.get("roll_deg") is not None else None,
            ),
            capture_date=item.get("date"), capture_year=int(item["capture_year"])
            if item.get("capture_year") else None,
            target_bearing_deg=float(item["target_bearing_deg"])
            if item.get("target_bearing_deg") is not None else None,
            relative_yaw_deg=float(item["relative_yaw_deg"])
            if item.get("relative_yaw_deg") is not None else None,
            camera_to_lot_m=float(item["camera_to_lot_m"])
            if item.get("camera_to_lot_m") is not None else None,
        )
        for item in selected
    )
    if not panorama_views:
        raise ValueError("El input multivista debe contener al menos una cámara")
    for view in panorama_views:
        if not view.image_path.is_file():
            raise FileNotFoundError(f"Imagen 360 ausente: {view.image_path}")
    projection = {
        "type": data.get("projection"),
        "horizontal_fov_deg": data.get("horizontal_fov_deg"),
        "vertical_range_deg": data.get("vertical_range_deg"),
        "pitch_center_deg": data.get("pitch_center_deg"),
        "source_manifest": str(manifest.resolve()),
    }
    return ReconstructionInput(lot=lot, views=panorama_views, alignment=Alignment2D(), projection=projection)


def _package_payload(value: ReconstructionInput) -> dict:
    return {
        "schema_version": 2,
        "lot": {
            "objectid": value.lot.objectid, "crs": value.lot.crs,
            "footprint_xy": value.lot.footprint_xy, "source_row": value.lot.source_row,
            "attributes": value.lot.attributes,
        },
        "alignment": {
            "east_m": value.alignment.east_m, "north_m": value.alignment.north_m,
            "camera_height_m": value.alignment.camera_height_m, "source": value.alignment.source,
        },
        "projection": value.projection,
        "satellite_image_path": str(value.satellite_image_path) if value.satellite_image_path else None,
        "views": [
            {
                "pano_id": view.pano_id, "image_path": str(view.image_path),
                "cylindrical_path": str(view.cylindrical_path) if view.cylindrical_path else None,
                "capture_date": view.capture_date, "capture_year": view.capture_year,
                "target_bearing_deg": view.target_bearing_deg, "relative_yaw_deg": view.relative_yaw_deg,
                "camera_to_lot_m": view.camera_to_lot_m,
                "pose": {
                    "latitude": view.pose.latitude, "longitude": view.pose.longitude,
                    "heading_deg": view.pose.heading_deg, "pitch_deg": view.pose.pitch_deg,
                    "roll_deg": view.pose.roll_deg, "camera_height_m": view.pose.camera_height_m,
                },
            }
            for view in value.views
        ],
    }


def write_reconstruction_input(value: ReconstructionInput, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(_package_payload(value), indent=2, ensure_ascii=False) + "\n")


def read_reconstruction_input(path: Path) -> ReconstructionInput:
    data = json.loads(path.read_text())
    if data.get("schema_version") != 2:
        raise ValueError("Expected reconstruction package schema_version=2")
    lot_data = data["lot"]
    lot = LotGeometry(lot_data["objectid"], lot_data["crs"], tuple(map(tuple, lot_data["footprint_xy"])), lot_data.get("source_row"), lot_data.get("attributes", {}))
    alignment_data = data["alignment"]
    alignment = Alignment2D(**alignment_data)
    views = []
    for item in data["views"]:
        pose = CameraPose(**item["pose"])
        views.append(PanoramaView(
            pano_id=item["pano_id"], image_path=Path(item["image_path"]),
            cylindrical_path=Path(item["cylindrical_path"]) if item.get("cylindrical_path") else None,
            pose=pose, capture_date=item.get("capture_date"), capture_year=item.get("capture_year"),
            target_bearing_deg=item.get("target_bearing_deg"), relative_yaw_deg=item.get("relative_yaw_deg"),
            camera_to_lot_m=item.get("camera_to_lot_m"),
        ))
    return ReconstructionInput(lot=lot, views=tuple(views), alignment=alignment,
                               projection=data.get("projection", {}),
                               satellite_image_path=Path(data["satellite_image_path"]) if data.get("satellite_image_path") else None)
