"""Golden regression set for Grammar V1.

Generates exactly 3 deterministic buildings through the public grammar API
(parcel + fronts + height + program + seed -> assemblies -> GLB) and writes
them to outputs/generations_tests_v1.0/ with renders, fingerprint and a
contact sheet.

The lot/family/seed picker mirrors the Step-17 gallery matrix (provenance:
steps/step17_grammar_gallery/run.py) but this script is standalone: the
golden set must not depend on experiment harnesses. Regenerate with:

    python scripts/golden_v1/generate_golden_v1.py --detail 2 --random-seed 20260923
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "steps" / "step10_procedural_generation_test"))

import numpy as np
from shapely.affinity import rotate
from shapely.geometry import Polygon

from domain.architecture import (
    BuildingProgram,
    BuildingSpecificationV4,
    ParcelContext,
    SitePlan,
)
from modeling.exporters.glb_exporter import export_glb
from modeling.facade_program import FAMILY_RULES
from modeling.grammar import generate_v4_mesh, street_envelope
from modeling.massing import generate_masses
from modeling.validation import validate_mesh
from render import render

OUTPUTS = ROOT / "outputs" / "generations_tests_v1.0"
GOLDEN_SEED = 20260923
GOLDEN_COUNT = 3
ISOMETRIC = (1.0, -1.0, 1.0)
FLOOR_HEIGHT_M = 2.8


def rectangle(width, depth):
    return Polygon([(-width / 2, -depth / 2), (width / 2, -depth / 2),
                    (width / 2, depth / 2), (-width / 2, depth / 2)])


def corner(width, depth):
    half_w, half_d = width / 2, depth / 2
    return Polygon([(-half_w, -half_d), (half_w, -half_d), (half_w, half_d * 0.45),
                    (half_w * 0.1, half_d * 0.45), (half_w * 0.1, half_d),
                    (-half_w, half_d)])


LOTS = {
    "row_narrow": dict(polygon=rectangle(6.0, 18.0), fronts=(0,), floors=3,
                       use="residential", is_corner=False),
    "row_wide": dict(polygon=rectangle(11.0, 20.0), fronts=(0,), floors=4,
                     use="mixed", is_corner=False),
    "corner": dict(polygon=corner(14.0, 22.0), fronts=(0, 1), floors=5,
                   use="mixed", is_corner=True),
    "small": dict(polygon=rectangle(8.0, 10.0), fronts=(0,), floors=1,
                  use="residential", is_corner=False),
    "deep": dict(polygon=rectangle(10.0, 28.0), fronts=(0,), floors=4,
                 use="residential", is_corner=False),
    "rotated": dict(polygon=rotate(rectangle(9.0, 20.0), 37, origin=(0, 0)),
                    fronts=(0,), floors=3, use="commercial", is_corner=False),
}


def pick_jobs(count, seed):
    import random as _random

    rng = _random.Random(seed)
    names = sorted(LOTS)
    families = sorted(FAMILY_RULES)
    jobs = []
    for i in range(count):
        lot_name = rng.choice(names)
        jobs.append({
            "label": f"random{i:02d}_{lot_name}_{(f := rng.choice(families))}_s{(s := rng.randint(0, 2 ** 31 - 1))}",
            "lot_name": lot_name,
            "family": f,
            "seed": s,
            "setback": round(rng.uniform(1.8, 3.2), 2) if rng.random() < 0.5 else 0.0,
        })
    return jobs


def build(lot, family, seed, setback):
    coords = tuple((float(x), float(y)) for x, y in lot["polygon"].exterior.coords)
    context = ParcelContext(polygon=coords, explicit_fronts=tuple(lot["fronts"]))
    program = BuildingProgram(
        use=lot["use"],
        occupancy="medium",
        placement="front_setback" if setback else "flush",
        architectural_language=family,
        finish_profile="standard",
        maintenance="average",
        construction_state="completed",
        seed=seed,
        front_setback=setback,
        primary_color=(0.85, 0.84, 0.78),
        side_wall_finish="raw",
        is_corner=lot["is_corner"],
        has_fence=bool(setback),
        fence_type="reja",
    )
    masses = generate_masses(
        context, program, lot["floors"] * FLOOR_HEIGHT_M, FLOOR_HEIGHT_M
    )
    plan = SitePlan(masses=masses, free_space=(), access_nodes=(), boundaries=(),
                    exclusion_zones=())
    return BuildingSpecificationV4(context=context, program=program, site_plan=plan,
                                   facades=(), components=(), seed=seed)


def contact_sheet(labels, suffix, columns=3):
    import cv2

    tiles = []
    for label in labels:
        path = OUTPUTS / f"{label}{suffix}.png"
        if not path.exists():
            continue
        image = cv2.imread(str(path))
        if image is None:
            continue
        cv2.putText(image, label, (14, image.shape[0] - 16),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.52, (40, 40, 40), 1, cv2.LINE_AA)
        tiles.append(image)
    if not tiles:
        return None
    height, width = tiles[0].shape[:2]
    rows = []
    for start in range(0, len(tiles), columns):
        row = tiles[start:start + columns]
        while len(row) < columns:
            row.append(np.full((height, width, 3), 245, np.uint8))
        rows.append(np.hstack(row))
    sheet = OUTPUTS / f"contact_sheet{suffix}.png"
    cv2.imwrite(str(sheet), np.vstack(rows))
    return sheet


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--detail", type=int, default=2, choices=(1, 2, 3))
    parser.add_argument("--size", type=int, default=720)
    parser.add_argument("--count", type=int, default=GOLDEN_COUNT)
    parser.add_argument("--random-seed", type=int, default=GOLDEN_SEED)
    parser.add_argument("--no-render", action="store_true")
    parser.add_argument("--no-glb", action="store_true")
    args = parser.parse_args()

    OUTPUTS.mkdir(parents=True, exist_ok=True)
    jobs = pick_jobs(args.count, args.random_seed)
    print(f"golden picker seed: {args.random_seed}")
    (OUTPUTS / "golden_jobs.json").write_text(
        json.dumps(jobs, indent=2) + "\n")
    fingerprint = {}
    for job in jobs:
        label = job["label"]
        lot = LOTS[job["lot_name"]]
        spec = build(lot, job["family"], job["seed"], job["setback"])
        mesh = generate_v4_mesh(spec, detail=args.detail)
        report = validate_mesh(
            mesh, Polygon(spec.context.polygon),
            envelope=street_envelope(spec.context),
        )
        fingerprint[label] = {
            "lot": job["lot_name"],
            "family": job["family"],
            "seed": job["seed"],
            "setback": job["setback"],
            "masses": [mass.role for mass in spec.site_plan.masses],
            "triangles": report["triangles"],
            "semantics": len(report["semantic_types"]),
            "faces_by_semantic": report["faces_by_semantic"],
        }
        print(f"{label:46s} {report['triangles']:7d} tris  "
              f"{len(report['semantic_types']):3d} semantics  "
              f"{[m.role for m in spec.site_plan.masses]}")
        if not args.no_glb:
            export_glb(mesh, OUTPUTS / f"{label}.glb")
        if not args.no_render:
            render(mesh, OUTPUTS / f"{label}_iso.png",
                   direction=ISOMETRIC, size=args.size, clay=True)
            render(mesh, OUTPUTS / f"{label}_aerial.png",
                   direction=(1, -1.7, 1.1), size=args.size, clay=True)
            render(mesh, OUTPUTS / f"{label}_street.png",
                   direction=(0.45, -1.0, 0.30), size=args.size, clay=True)
    (OUTPUTS / "fingerprint_lod2.json").write_text(
        json.dumps(fingerprint, indent=2, sort_keys=True) + "\n")
    total = sum(item["triangles"] for item in fingerprint.values())
    print(f"\n{len(fingerprint)} buildings, {total} triangles total")
    if not args.no_render:
        sheet = contact_sheet(sorted(fingerprint), "_iso")
        if sheet is not None:
            print(f"contact sheet written to {sheet}")
    print(f"outputs written to {OUTPUTS}")


if __name__ == "__main__":
    main()
