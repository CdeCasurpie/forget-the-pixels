#!/usr/bin/env python3
"""Paso 1: descarga de panoramas GSV y normalización de orientación.

Reutiliza streetlevel, ya usado por los experimentos existentes en
investigation/street_view/. No realiza todavía ninguna proyección hacia lotes.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import deque
from pathlib import Path
from typing import Any

import streetlevel.streetview as sv


DEFAULT_LAT = -12.137248
DEFAULT_LON = -77.020423


def angle_to_degrees(value: Any) -> tuple[float | None, str]:
    """Normaliza heading/pitch/roll, conservando la unidad detectada."""
    if value is None:
        return None, "missing"
    value = float(value)
    if abs(value) <= 2.0 * math.pi + 1e-6:
        return math.degrees(value) % 360.0, "radians"
    return value % 360.0, "degrees"


def get_attr(obj: Any, name: str, default: Any = None) -> Any:
    value = getattr(obj, name, default)
    return value() if callable(value) else value


def orientation_metadata(pano: Any, width: int, height: int) -> dict[str, Any]:
    raw_heading = get_attr(pano, "heading")
    heading_deg, heading_unit = angle_to_degrees(raw_heading)
    if heading_deg is None:
        north_fraction = None
        north_pixel_x = None
    else:
        # Hipótesis explícita: x=W/2 es el heading de la panorámica y x crece
        # hacia la derecha. Se validará visualmente en el siguiente experimento.
        north_fraction = (0.5 - heading_deg / 360.0) % 1.0
        north_pixel_x = north_fraction * width

    pitch_deg, pitch_unit = angle_to_degrees(get_attr(pano, "pitch"))
    roll_deg, roll_unit = angle_to_degrees(get_attr(pano, "roll"))

    return {
        "heading_raw": raw_heading,
        "heading_deg": heading_deg,
        "heading_input_unit": heading_unit,
        "pitch_raw": get_attr(pano, "pitch"),
        "pitch_deg": pitch_deg,
        "pitch_input_unit": pitch_unit,
        "roll_raw": get_attr(pano, "roll"),
        "roll_deg": roll_deg,
        "roll_input_unit": roll_unit,
        "orientation_convention": "center_heading_plus_rightward_yaw",
        "north_fraction": north_fraction,
        "north_pixel_x": north_pixel_x,
        "image_width": width,
        "image_height": height,
    }


def pano_date_year(pano: Any) -> int | None:
    date = get_attr(pano, "date")
    return getattr(date, "year", None) if date else None


def load_route(path: Path) -> list[dict[str, Any]]:
    with path.open() as file:
        route = json.load(file)
    if not isinstance(route, list):
        raise ValueError("La ruta debe ser un JSON con una lista de panoramas.")
    return route


def collect_from_coordinate(lat: float, lon: float, count: int, year: int | None) -> list[Any]:
    first = sv.find_panorama(lat, lon)
    if not first:
        raise RuntimeError(f"No se encontró panorama cerca de ({lat}, {lon}).")

    first = sv.find_panorama_by_id(first.id)
    if not first:
        raise RuntimeError(f"No se pudo cargar la metadata de {first.id}.")

    selected: list[Any] = []
    queue: deque[Any] = deque([first])
    seen: set[str] = set()
    target_year = year if year is not None else pano_date_year(first)

    while queue and len(selected) < count:
        candidate = queue.popleft()
        pano_id = str(candidate.id)
        if pano_id in seen:
            continue
        seen.add(pano_id)

        candidate_year = pano_date_year(candidate)
        if target_year is None or candidate_year is None or candidate_year == target_year:
            selected.append(candidate)

        for neighbor in get_attr(candidate, "neighbors", []) or []:
            if str(neighbor.id) not in seen:
                full = sv.find_panorama_by_id(neighbor.id)
                if full:
                    queue.append(full)

    return selected


def collect_from_route(route: list[dict[str, Any]]) -> list[Any]:
    selected = []
    for item in route:
        pano_id = item.get("id") or item.get("pano_id")
        if not pano_id:
            continue
        pano = sv.find_panorama_by_id(pano_id)
        if pano:
            selected.append(pano)
    return selected


def download(panos: list[Any], output: Path) -> None:
    image_dir = output / "panoramas"
    image_dir.mkdir(parents=True, exist_ok=True)
    metadata: dict[str, Any] = {
        "experiment": "gsv_step1_acquisition",
        "library": "streetlevel.streetview",
        "zoom": None,
        "orientation_note": "north_pixel_x assumes panorama center equals heading",
        "panoramas": {},
    }

    for index, pano in enumerate(panos):
        print(f"[{index + 1}/{len(panos)}] {pano.id}")
        image = sv.get_panorama(pano, zoom=2)
        if image is None:
            print("  [WARN] No se pudo descargar la imagen; se omite.")
            continue

        image_path = image_dir / f"{index:03d}_{pano.id}.jpg"
        image.save(image_path, "JPEG", quality=95)
        width, height = image.size
        metadata["zoom"] = 2

        entry = {
            "pano_id": pano.id,
            "lat": get_attr(pano, "lat"),
            "lon": get_attr(pano, "lon"),
            "date": str(get_attr(pano, "date")) if get_attr(pano, "date") else None,
            "image": str(image_path.relative_to(output)),
            "image_sha_hint": f"{width}x{height}",
        }
        entry.update(orientation_metadata(pano, width, height))
        metadata["panoramas"][image_path.name] = entry
        print(f"  -> {image_path} ({width}x{height}), heading={entry['heading_deg']:.3f}°")

    with (output / "metadata.json").open("w") as file:
        json.dump(metadata, file, indent=2, ensure_ascii=False)
    print(f"Metadata guardada en {output / 'metadata.json'}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lat", type=float, default=DEFAULT_LAT)
    parser.add_argument("--lon", type=float, default=DEFAULT_LON)
    parser.add_argument("--count", type=int, default=10)
    parser.add_argument("--year", type=int, default=None)
    parser.add_argument("--route-json", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=Path("data/sample_route"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    route = load_route(args.route_json) if args.route_json else None
    panos = collect_from_route(route) if route is not None else collect_from_coordinate(args.lat, args.lon, args.count, args.year)
    if not panos:
        raise SystemExit("No se encontraron panoramas para descargar.")
    download(panos, args.output)


if __name__ == "__main__":
    main()
