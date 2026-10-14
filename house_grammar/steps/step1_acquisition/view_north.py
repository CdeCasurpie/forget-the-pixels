#!/usr/bin/env python3
"""Visor interactivo: recorre panoramas mostrando siempre el norte."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import cv2
import numpy as np


def extract_rectilinear(equirectangular: np.ndarray, yaw_deg: float,
                        pitch_deg: float = 0.0, fov_deg: float = 90.0,
                        width: int = 960, height: int = 640) -> np.ndarray:
    """Extrae una vista pinhole desde una equirectangular.

    yaw=0 apunta al centro horizontal de la equirectangular. El eje horizontal
    aumenta hacia la derecha y el eje vertical de la equirectangular apunta
    del cenit al nadir.
    """
    pano_h, pano_w = equirectangular.shape[:2]
    focal = (width / 2.0) / math.tan(math.radians(fov_deg) / 2.0)

    x, y = np.meshgrid(np.arange(width), np.arange(height))
    x_camera = x - width / 2.0
    y_camera = y - height / 2.0
    z_camera = np.full_like(x_camera, focal, dtype=np.float32)
    points = np.stack((x_camera, y_camera, z_camera), axis=-1).reshape(-1, 3)

    yaw = math.radians(yaw_deg)
    pitch = math.radians(pitch_deg)
    rotation_y = np.array([
        [math.cos(yaw), 0.0, math.sin(yaw)],
        [0.0, 1.0, 0.0],
        [-math.sin(yaw), 0.0, math.cos(yaw)],
    ], dtype=np.float32)
    rotation_x = np.array([
        [1.0, 0.0, 0.0],
        [0.0, math.cos(pitch), -math.sin(pitch)],
        [0.0, math.sin(pitch), math.cos(pitch)],
    ], dtype=np.float32)

    rotated = points @ (rotation_y @ rotation_x).T
    longitude = np.arctan2(rotated[:, 0], rotated[:, 2])
    latitude = np.arcsin(np.clip(
        rotated[:, 1] / np.linalg.norm(rotated, axis=1), -1.0, 1.0
    ))

    map_x = ((longitude / (2.0 * math.pi)) + 0.5) * pano_w
    # La cámara pinhole usa +Y hacia abajo. Por eso un punto con y_camera<0
    # está arriba, pero su latitud equirectangular debe aumentar hacia el cenit.
    # En la imagen resultante, y=0 es el cenit y y=H es el nadir.
    map_y = (0.5 + latitude / math.pi) * pano_h
    map_x = np.mod(map_x, pano_w).astype(np.float32).reshape(height, width)
    map_y = np.clip(map_y, 0, pano_h - 1).astype(np.float32).reshape(height, width)

    return cv2.remap(
        equirectangular,
        map_x,
        map_y,
        interpolation=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_WRAP,
    )


def load_dataset(dataset: Path) -> list[tuple[str, dict, np.ndarray]]:
    with (dataset / "metadata.json").open() as file:
        metadata = json.load(file)["panoramas"]

    entries = []
    for filename, entry in sorted(metadata.items()):
        image_path = dataset / entry["image"]
        image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
        if image is None:
            print(f"[WARN] No se pudo leer {image_path}; se omite.")
            continue
        entries.append((filename, entry, image))
    return entries


def add_orientation_overlay(image: np.ndarray, entry: dict) -> np.ndarray:
    overlay = image.copy()
    north_x = int(round(entry["north_pixel_x"]))
    center_x = image.shape[1] // 2
    cv2.line(overlay, (north_x, 0), (north_x, image.shape[0] - 1), (0, 255, 0), 4)
    cv2.line(overlay, (center_x, 0), (center_x, image.shape[0] - 1), (0, 0, 255), 2)
    cv2.putText(overlay, "NORTE calculado", (north_x + 8, 42),
                cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2, cv2.LINE_AA)
    cv2.putText(overlay, "centro de la equirectangular", (center_x + 8, 78),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2, cv2.LINE_AA)
    return overlay


def make_route_map(index: int, entries: list[tuple[str, dict, np.ndarray]],
                   width: int = 900, height: int = 650) -> np.ndarray:
    """Dibuja la posición GPS y el orden de adquisición de cada panorama."""
    canvas = np.full((height, width, 3), 248, dtype=np.uint8)
    coords = [(float(entry["lon"]), float(entry["lat"])) for _, entry, _ in entries]
    lons = np.array([coord[0] for coord in coords], dtype=np.float64)
    lats = np.array([coord[1] for coord in coords], dtype=np.float64)

    lon_span = max(float(lons.max() - lons.min()), 1e-8)
    lat_span = max(float(lats.max() - lats.min()), 1e-8)
    padding = 70
    usable_w = width - 2 * padding
    usable_h = height - 2 * padding
    scale = min(usable_w / lon_span, usable_h / lat_span)
    map_w = lon_span * scale
    map_h = lat_span * scale
    origin_x = (width - map_w) / 2.0
    origin_y = (height - map_h) / 2.0

    def to_pixel(lon: float, lat: float) -> tuple[int, int]:
        px = int(round(origin_x + (lon - lons.min()) * scale))
        py = int(round(origin_y + (lats.max() - lat) * scale))
        return px, py

    pixels = [to_pixel(lon, lat) for lon, lat in coords]
    for prev, current in zip(pixels, pixels[1:]):
        cv2.line(canvas, prev, current, (170, 170, 170), 2, cv2.LINE_AA)

    for point_index, point in enumerate(pixels):
        color = (40, 40, 210) if point_index == index else (80, 130, 40)
        radius = 11 if point_index == index else 7
        cv2.circle(canvas, point, radius, color, -1, cv2.LINE_AA)
        cv2.circle(canvas, point, radius + 1, (40, 40, 40), 1, cv2.LINE_AA)
        cv2.putText(canvas, str(point_index + 1), (point[0] + 10, point[1] - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (30, 30, 30), 2, cv2.LINE_AA)

    current_entry = entries[index][1]
    current_point = pixels[index]
    cv2.putText(canvas, "ROJO = panorama actual", (24, 38),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (40, 40, 210), 2, cv2.LINE_AA)
    cv2.putText(canvas, f"Orden de adquisicion: {index + 1}/{len(entries)}",
                (24, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (30, 30, 30), 2, cv2.LINE_AA)
    cv2.putText(canvas, f"lat={float(current_entry['lat']):.7f}  lon={float(current_entry['lon']):.7f}",
                (24, height - 28), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (30, 30, 30), 2, cv2.LINE_AA)
    cv2.drawMarker(canvas, current_point, (0, 0, 255), cv2.MARKER_CROSS, 34, 2)
    return canvas


def show_entry(index: int, entries: list[tuple[str, dict, np.ndarray]]) -> None:
    filename, entry, panorama = entries[index]
    heading = float(entry["heading_deg"])

    # Para mirar al norte: yaw relativo = bearing_norte - heading.
    north_view = extract_rectilinear(panorama, yaw_deg=-heading, pitch_deg=0.0)
    cv2.putText(north_view, "VISTA FIJA: NORTE", (24, 42),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2, cv2.LINE_AA)
    cv2.putText(north_view, f"{index + 1}/{len(entries)}  heading={heading:.2f} deg",
                (24, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2,
                cv2.LINE_AA)

    overlay = add_orientation_overlay(panorama, entry)
    overlay = cv2.resize(overlay, (1024, 512), interpolation=cv2.INTER_AREA)
    route_map = make_route_map(index, entries)
    cv2.imshow("Recorrido mirando al Norte", north_view)
    cv2.imshow("Equirectangular y orientacion", overlay)
    cv2.imshow("Mapa GPS del recorrido", route_map)
    print(f"[{index + 1}/{len(entries)}] {filename} | heading={heading:.3f}° | "
          f"north_pixel_x={entry['north_pixel_x']:.1f}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset",
        type=Path,
        default=None,
    )
    args = parser.parse_args()
    dataset = args.dataset or (Path(__file__).resolve().parent / "data/sample_route")
    entries = load_dataset(dataset)
    if not entries:
        raise SystemExit("No hay panoramas válidos en el dataset.")

    print("Controles: N/→ siguiente | B/← anterior | Q/Esc salir")
    index = 0
    show_entry(index, entries)
    while True:
        key = cv2.waitKey(0) & 0xFF
        if key in (ord("q"), 27):
            break
        if key in (ord("n"), ord(" "), 83):
            index = (index + 1) % len(entries)
            show_entry(index, entries)
        elif key in (ord("b"), 81):
            index = (index - 1) % len(entries)
            show_entry(index, entries)

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
