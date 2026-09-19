"""Cosecha reanudable de metadata Street View de Barranco, sin imágenes.

Usa una cuadrícula para descubrir componentes de cobertura y luego recorre el
grafo de vecinos. Guarda checkpoints atómicos para poder interrumpir con Ctrl+C
y continuar más tarde.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import deque
from pathlib import Path

import geopandas as gpd
import requests
import streetlevel.streetview as sv
from pyproj import Transformer
from shapely.geometry import Point

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from gsv_acquisition.acquisition import get_attr, pano_date_year  # noqa: E402
from select_candidates import TimeoutSession, metadata_entry  # noqa: E402


TARGET_CRS = "EPSG:32718"
LOT_SHP_NAME = "BARRANCO_LM_geogpsperu_SuyoPomalia.shp"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def atomic_json(path: Path, payload: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


def grid_points(bounds, spacing: float, coverage) -> list[Point]:
    min_x, min_y, max_x, max_y = bounds
    points = []
    y = min_y
    while y <= max_y:
        x = min_x
        while x <= max_x:
            point = Point(x, y)
            if coverage.covers(point):
                points.append(point)
            x += spacing
        y += spacing
    return points


def initial_state(args, seed_count: int) -> dict:
    return {
        "version": 1,
        "images_downloaded": False,
        "grid_spacing_m": args.grid_spacing_m,
        "seed_radius_m": args.seed_radius_m,
        "year_range": [args.min_year, args.max_year],
        "seed_count": seed_count,
        "next_seed_index": 0,
        "pending": [],
        "queued_ids": [],
        "processed_ids": [],
        "failed_ids": [],
        "panoramas": {},
        "finished": False,
    }


def save(output: Path, state: dict) -> None:
    output.mkdir(parents=True, exist_ok=True)
    atomic_json(output / "harvest_state.json", state)
    metadata = {
        "experiment": "gsv_barranco_metadata_harvest",
        "library": "streetlevel.streetview",
        "images_downloaded": False,
        "finished": state["finished"],
        "grid_spacing_m": state["grid_spacing_m"],
        "year_range": state.get("year_range"),
        "seed_progress": [state["next_seed_index"], state["seed_count"]],
        "panorama_count": len(state["panoramas"]),
        "panoramas": state["panoramas"],
    }
    atomic_json(output / "metadata.json", metadata)


def enqueue(state: dict, pano_id: str, kind: str, queued_ids: set[str], processed_ids: set[str]) -> bool:
    if pano_id in queued_ids or pano_id in processed_ids:
        return False
    state["pending"].append({"pano_id": pano_id, "discovered_as": kind})
    state["queued_ids"].append(pano_id)
    queued_ids.add(pano_id)
    return True


def main() -> None:
    root = repo_root()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shapefile", type=Path, default=root / "investigation/Lotes/shp_files" / LOT_SHP_NAME)
    parser.add_argument("--output", type=Path, default=root / "investigation/proy_geom/steps/step2_vector_to_lots/data/barranco_metadata")
    parser.add_argument("--grid-spacing-m", type=float, default=180.0)
    parser.add_argument("--seed-radius-m", type=int, default=120)
    parser.add_argument("--road-buffer-m", type=float, default=45.0)
    parser.add_argument("--checkpoint-every", type=int, default=10)
    parser.add_argument("--delay-s", type=float, default=0.15)
    parser.add_argument("--max-panoramas", type=int, default=0, help="0 significa sin límite.")
    parser.add_argument("--include-historical", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--min-year", type=int, default=2020)
    parser.add_argument("--max-year", type=int, default=2025)
    args = parser.parse_args()

    lots = gpd.read_file(args.shapefile).to_crs(TARGET_CRS)
    district = lots.geometry.union_all()
    coverage = district.buffer(args.road_buffer_m)
    seeds = grid_points(lots.total_bounds, args.grid_spacing_m, coverage)
    to_wgs84 = Transformer.from_crs(TARGET_CRS, "EPSG:4326", always_xy=True)
    from_wgs84 = Transformer.from_crs("EPSG:4326", TARGET_CRS, always_xy=True)

    state_path = args.output / "harvest_state.json"
    if state_path.exists():
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if (
            state.get("seed_count") != len(seeds)
            or state.get("grid_spacing_m") != args.grid_spacing_m
            or state.get("year_range") != [args.min_year, args.max_year]
        ):
            raise RuntimeError("El checkpoint usa otra cuadrícula. Cambia --output o conserva los parámetros anteriores.")
        print(f"Reanudando: {len(state['panoramas'])} panoramas guardados.", flush=True)
    else:
        state = initial_state(args, len(seeds))
        save(args.output, state)

    queued_ids = set(state["queued_ids"])
    processed_ids = set(state["processed_ids"])

    session = TimeoutSession()
    requests_done = 0
    try:
        # Fase 1: semillas espaciales. Encuentra cobertura desconectada sin JPG.
        for seed_index in range(state["next_seed_index"], len(seeds)):
            point = seeds[seed_index]
            lon, lat = to_wgs84.transform(point.x, point.y)
            print(f"[semilla {seed_index + 1}/{len(seeds)}] {lat:.6f}, {lon:.6f}", flush=True)
            try:
                pano = sv.find_panorama(lat, lon, radius=args.seed_radius_m, session=session)
                if pano:
                    enqueue(state, str(pano.id), "grid_seed", queued_ids, processed_ids)
            except requests.RequestException as error:
                print(f"  [WARN] {error}", flush=True)
            state["next_seed_index"] = seed_index + 1
            requests_done += 1
            if requests_done % args.checkpoint_every == 0:
                save(args.output, state)
            time.sleep(args.delay_s)

        # Fase 2: grafo de vecinos e históricos dentro de Barranco.
        pending = deque(state["pending"])
        processed = processed_ids
        while pending:
            if args.max_panoramas and len(state["panoramas"]) >= args.max_panoramas:
                print(f"Límite de {args.max_panoramas} panoramas alcanzado.", flush=True)
                break
            item = pending.popleft()
            state["pending"] = list(pending)
            pano_id = item["pano_id"]
            if pano_id in processed:
                continue
            print(
                f"[panorama {len(state['panoramas']) + 1}] {pano_id} "
                f"(pendientes={len(pending)})",
                flush=True,
            )
            try:
                pano = sv.find_panorama_by_id(pano_id, session=session)
            except requests.RequestException as error:
                print(f"  [WARN] {error}", flush=True)
                state["failed_ids"].append(pano_id)
                processed.add(pano_id)
                state["processed_ids"].append(pano_id)
                continue
            processed.add(pano_id)
            state["processed_ids"].append(pano_id)
            if not pano or get_attr(pano, "lat") is None or get_attr(pano, "lon") is None:
                continue

            x, y = from_wgs84.transform(float(pano.lon), float(pano.lat))
            if not coverage.covers(Point(x, y)):
                continue
            year = pano_date_year(pano)
            if year is not None and not (args.min_year <= year <= args.max_year):
                continue
            entry = metadata_entry(pano)
            entry["capture_year"] = year
            entry["discovered_as"] = item["discovered_as"]
            entry["neighbor_ids"] = [str(neighbor.id) for neighbor in get_attr(pano, "neighbors", []) or []]
            entry["historical_ids"] = [str(old.id) for old in get_attr(pano, "historical", []) or []]
            state["panoramas"][pano_id] = entry

            discovered = [(neighbor, "neighbor") for neighbor in get_attr(pano, "neighbors", []) or []]
            if args.include_historical:
                discovered += [(old, "historical") for old in get_attr(pano, "historical", []) or []]
            for candidate, kind in discovered:
                if candidate.lat is not None and candidate.lon is not None:
                    cx, cy = from_wgs84.transform(float(candidate.lon), float(candidate.lat))
                    if not coverage.covers(Point(cx, cy)):
                        continue
                if enqueue(state, str(candidate.id), kind, queued_ids, processed):
                    pending.append(state["pending"][-1])

            requests_done += 1
            if requests_done % args.checkpoint_every == 0:
                state["pending"] = list(pending)
                save(args.output, state)
            time.sleep(args.delay_s)
        else:
            state["finished"] = True
    except KeyboardInterrupt:
        print("\nInterrumpido: guardando checkpoint para continuar después...", flush=True)
    finally:
        state["pending"] = list(pending) if "pending" in locals() else state["pending"]
        save(args.output, state)

    print(f"Panoramas guardados: {len(state['panoramas'])}", flush=True)
    print(f"Metadata: {args.output / 'metadata.json'}", flush=True)
    print(f"Checkpoint: {args.output / 'harvest_state.json'}", flush=True)


if __name__ == "__main__":
    main()
