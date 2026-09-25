"""Generate the central cadastral block first, publishing one cumulative GLB per house.

Run from any directory:
    python scripts/step3_generate_full_block.py --max-lots 2
    python scripts/step3_generate_full_block.py

The final GLB is rewritten atomically after each successful building. GLB is not
an appendable format, so exporting becomes slower as the scene grows; timing and
memory reports make that cost visible.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
import random
import resource
import sys
import time

import numpy as np
import psutil
from shapely.geometry.polygon import orient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "steps/step10_procedural_generation_test"))

from domain.models import MeshData
from domain.theta import FacadeControls, NuisanceParameters, ReconstructionContext, ThetaCandidate
from modeling.exporters.glb_exporter import export_glb
from modeling.theta import generate_from_theta
from render import render
from spatial.street_fronts import annotate_street_fronts
from scripts.glb_incremental import append_glb
from scripts.step1_select_block import clean_geometry, load_lots, plot_selection, select_block_lots


CSV_FIELDS = (
    "order", "lot_index", "zone", "status", "front_source", "fronts", "facade_mode", "family",
    "floors", "height_m", "vertices", "faces", "wall_parts", "opening_parts",
    "generation_s", "house_glb_s", "merge_s", "total_s", "rss_mb", "peak_rss_mb",
    "glb_mb", "error",
)


def combine_meshes(meshes: list[tuple[object, MeshData]]) -> MeshData:
    """Keep positions, per-corner UVs, materials and component face ranges aligned."""
    vertices, faces, corner_uvs, face_materials = [], [], [], []
    parts, components, materials = [], [], []
    material_ids = {}
    vertex_offset = face_offset = 0
    for lot_index, mesh in meshes:
        vertices.append(mesh.vertices)
        faces.append(mesh.faces + vertex_offset)
        corner_uvs.append(mesh.corner_uv if mesh.corner_uv is not None else np.zeros((len(mesh.faces), 3, 2)))
        mapped = np.empty(len(mesh.face_materials), dtype=int)
        for local_id, material in enumerate(mesh.materials):
            key = json.dumps(material, sort_keys=True)
            if key not in material_ids:
                material_ids[key] = len(materials)
                materials.append(material)
            mapped[mesh.face_materials == local_id] = material_ids[key]
        face_materials.append(mapped)
        for source, target in ((mesh.parts, parts), (mesh.components, components)):
            for part in source:
                record = dict(part)
                record["face_start"] += face_offset
                record["assembly_id"] = f"lot_{lot_index}/{record.get('assembly_id', '')}"
                target.append(record)
        vertex_offset += len(mesh.vertices)
        face_offset += len(mesh.faces)
    return MeshData(
        vertices=np.vstack(vertices),
        faces=np.vstack(faces),
        corner_uv=np.vstack(corner_uvs),
        face_materials=np.concatenate(face_materials),
        materials=tuple(materials),
        parts=tuple(parts),
        components=tuple(components),
    )


def choose_theta(seed: int, lot_index: object) -> tuple[ThetaCandidate, NuisanceParameters]:
    """Stable per-lot exploratory choices; failures on one lot do not shift the next."""
    rng = random.Random(f"{seed}:{lot_index}")
    floors = rng.choices([1, 2, 3, 4, 5, 7], weights=[13, 30, 28, 16, 9, 4])[0]
    height = round(floors * rng.uniform(2.75, 3.15), 3)
    family = rng.choice(("quiet_house", "republicano", "balcony_apartments", "mixed_use"))
    color = tuple(round(rng.uniform(0.58, 0.90), 3) for _ in range(3))
    theta = ThetaCandidate(height_m=height, floors=floors, family=family,
                           primary_color=color, schema_version="0.2")
    return theta, NuisanceParameters(seed=rng.randrange(2**31))


def generate_house(context, theta, nuisance):
    """Try compact repeat controls when a narrow parcel defeats the default bays."""
    attempts = (
        ("default", theta),
        ("narrow_repeat", ThetaCandidate(**{**vars(theta), "facade": FacadeControls(
            bay_count=1, window_ratio=0.5, window_height_m=1.1,
            sill_m=0.65, balconies=False)})),
        ("blank_facade", ThetaCandidate(**{**vars(theta), "facade": FacadeControls(
            mode="explicit", openings=())})),
    )
    for name, candidate in attempts:
        try:
            mesh = generate_from_theta(context, candidate, nuisance)
            wall_parts = sum(part.get("name") == "wall" for part in mesh.parts)
            if not wall_parts or len(mesh.faces) == 0 or mesh.vertices[:, 2].min() > 0.05:
                raise ValueError("Generated mesh has no ground-level walls")
            return mesh, name
        except ValueError as error:
            # Only opening-fit failures justify changing the facade controls.
            if "Openings cannot fit" not in str(error):
                raise
            last_error = error
    raise last_error


def select_fronts(row) -> tuple[tuple[int, ...], str]:
    """Use measured clear edges; for internal lots mark a guessed longest edge."""
    fronts = tuple(int(index) for index in row.street_edge_indices)
    if fronts:
        return fronts, "street_inferred"
    edges = row.street_edges
    if not edges:
        return (), "none"
    # This is an exploratory structural fill, not an observed street frontage.
    best = max(edges, key=lambda edge: (edge["minimum_clearance_m"], edge["length_m"]))
    return (int(best["edge_index"]),), "fallback_unverified"


def progress(order, total, zone, lot_index, phase, fraction, start, done):
    overall = ((order - 1) + fraction) / total * 100
    eta = (time.perf_counter() - start) / done * (total - done) if done else None
    eta_text = f" ETA {eta/60:.1f} min" if eta is not None else ""
    print(f"[{overall:5.1f}%] {order}/{total} {zone} lote={lot_index} {phase}{eta_text}", flush=True)


def memory_mb() -> tuple[float, float]:
    rss = psutil.Process().memory_info().rss / 1024**2
    # Linux reports ru_maxrss in KiB.
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    return round(rss, 1), round(peak, 1)


def write_reports(output_dir, rows, *, started, total, centre_count, seed_index, glb_path):
    csv_path = output_dir / "timings_per_house.csv"
    tmp_csv = output_dir / ".timings_per_house.csv.tmp"
    with tmp_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    os.replace(tmp_csv, csv_path)
    report = {
        "selected_lots": total,
        "centre_lots": centre_count,
        "seed_lot_index": str(seed_index),
        "processed": len(rows),
        "generated": sum(row["status"] == "generated" for row in rows),
        "failed": sum(row["status"] == "failed" for row in rows),
        "skipped": sum(row["status"] == "skipped" for row in rows),
        "elapsed_s": round(time.perf_counter() - started, 2),
        "glb": str(glb_path),
        "rss_mb": memory_mb()[0],
        "peak_rss_mb": memory_mb()[1],
        "schema_version": "0.2",
        "results": rows,
    }
    tmp_json = output_dir / ".progress.json.tmp"
    tmp_json.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp_json, output_dir / "progress.json")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=123, help="lot selection and per-house style seed")
    parser.add_argument("--surrounding-m", type=float, default=20.0)
    parser.add_argument("--max-lots", type=int, default=None, help="small smoke test; centre lots run first")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "outputs/cuadras_completas")
    parser.add_argument("--textures", action="store_true", help="embed PBR textures; slower and larger than structural preview")
    parser.add_argument("--no-render", action="store_true", help="skip the final CPU isometric preview")
    args = parser.parse_args()
    if args.max_lots is not None and args.max_lots < 1:
        parser.error("--max-lots must be positive")
    if args.surrounding_m < 0:
        parser.error("--surrounding-m cannot be negative")

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    lots = load_lots()
    centre, selected, seed_index = select_block_lots(
        lots, seed=args.seed, surrounding_m=args.surrounding_m
    )
    plot_selection(selected, centre, output_dir / "lot_selection.png")

    # One shared local metric origin prevents UTM float precision loss in GLB.
    origin = selected.geometry.union_all().centroid
    selected.geometry = selected.translate(xoff=-origin.x, yoff=-origin.y)
    # Exposure uses a 1e-4 m precision grid. Translation from large UTM values
    # adds floating-point noise; snap again so mass edges overlap exposed lines.
    selected.geometry = selected.geometry.apply(clean_geometry)
    selected = annotate_street_fronts(selected)
    seed_point = selected.loc[seed_index].geometry.centroid
    centre_polygon = selected.loc[sorted(centre)].geometry.union_all()
    order = sorted(selected.index, key=lambda idx: (
        idx not in centre,
        selected.loc[idx].geometry.centroid.distance(seed_point if idx in centre else centre_polygon),
        str(idx),
    ))
    if args.max_lots is not None:
        order = order[:args.max_lots]
    total = len(order)
    glb_path = output_dir / "cuadra_completa.glb"
    print(f"Centro: {len(centre)} lotes; seleccion: {len(selected)}; a procesar: {total}", flush=True)
    print(f"GLB acumulado: {glb_path}", flush=True)
    preview_meshes = [] if total <= 10 and not args.no_render else None
    generated_count = 0
    rows = []
    for number, index in enumerate(order, 1):
        row = selected.loc[index]
        zone = "centro" if index in centre else "alrededor"
        item_start = time.perf_counter()
        fronts, front_source = select_fronts(row)
        result = dict.fromkeys(CSV_FIELDS, "")
        result.update(order=number, lot_index=index, zone=zone, front_source=front_source,
                      fronts=json.dumps(fronts), status="failed")
        progress(number, total, zone, index, "iniciando", 0.0, started, len(rows))
        try:
            if row.geometry.geom_type != "Polygon" or not fronts:
                result["status"] = "skipped"
                result["error"] = "unsupported geometry or no frontage candidate"
                continue
            # street_facing_edges uses an oriented CCW ring; keep its edge IDs aligned.
            polygon = orient(row.geometry, sign=1.0)
            context = ReconstructionContext(parcel=tuple(polygon.exterior.coords), fronts=fronts)
            theta, nuisance = choose_theta(args.seed, index)
            result.update(family=theta.family, floors=theta.floors, height_m=theta.height_m)
            progress(number, total, zone, index, "geometria", 0.15, started, len(rows))
            build_start = time.perf_counter()
            mesh, mode = generate_house(context, theta, nuisance)
            result["facade_mode"] = mode
            result["generation_s"] = round(time.perf_counter() - build_start, 3)
            result["wall_parts"] = sum(p.get("name") == "wall" for p in mesh.parts)
            result["opening_parts"] = sum("opening" in str(p.get("component_id", "")) for p in mesh.parts)
            result["vertices"] = len(mesh.vertices)
            result["faces"] = len(mesh.faces)
            progress(number, total, zone, index, "malla lista", 0.65, started, len(rows))

            progress(number, total, zone, index, "exportando casa", 0.78, started, len(rows))
            house_path = output_dir / ".house.tmp.glb"
            export_start = time.perf_counter()
            export_glb(mesh, house_path, library=None if args.textures else False)
            result["house_glb_s"] = round(time.perf_counter() - export_start, 3)
            progress(number, total, zone, index, "actualizando GLB acumulado", 0.90, started, len(rows))
            merge_start = time.perf_counter()
            temporary = output_dir / ".cuadra_completa.tmp.glb"
            append_glb(glb_path if generated_count else None, house_path, temporary, lot_id=index)
            os.replace(temporary, glb_path)
            result["merge_s"] = round(time.perf_counter() - merge_start, 3)
            result["glb_mb"] = round(glb_path.stat().st_size / 1024**2, 2)
            result["status"] = "generated"
            generated_count += 1
            if preview_meshes is not None:
                preview_meshes.append((index, mesh))
            print(f"  casa #{generated_count}: {len(mesh.faces):,} caras, "
                  f"generacion {result['generation_s']}s, casa GLB {result['house_glb_s']}s, "
                  f"acumulado {result['merge_s']}s, GLB {result['glb_mb']} MB", flush=True)
        except Exception as error:
            result["error"] = f"{type(error).__name__}: {error}"
            print(f"  FALLÓ lote {index}: {result['error']}", flush=True)
        finally:
            result["total_s"] = round(time.perf_counter() - item_start, 3)
            result["rss_mb"], result["peak_rss_mb"] = memory_mb()
            rows.append(result)
            write_reports(output_dir, rows, started=started, total=total,
                          centre_count=len(centre), seed_index=seed_index, glb_path=glb_path)
            progress(number, total, zone, index, result["status"], 1.0, started, len(rows))

    if preview_meshes:
        render(combine_meshes(preview_meshes), output_dir / "cuadra_completa_iso.png",
               direction=(1, -1, 1), size=1200, clay=True)
    print(f"Terminado: {sum(r['status'] == 'generated' for r in rows)}/{total} casas. "
          f"Tiempos: {output_dir / 'timings_per_house.csv'}", flush=True)


if __name__ == "__main__":
    main()
