"""Visual and numeric regression gallery for the building grammar.

Renders a fixed matrix of lot shapes, architectural families and seeds, and
writes a JSON fingerprint of every mesh. Run it before and after a grammar
change: the PNGs show what moved, and the fingerprint says by how much.

    python steps/step17_grammar_gallery/run.py            # street detail
    python steps/step17_grammar_gallery/run.py --detail 1 # block detail
"""

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

from domain.architecture import BuildingProgram, BuildingSpecificationV4, ParcelContext, SitePlan
from modeling.exporters.glb_exporter import export_glb
from modeling.facade_program import FAMILY_RULES
from modeling.grammar import generate_v4_mesh, street_envelope
from modeling.massing import generate_masses
from modeling.validation import validate_mesh
from render import render

OUTPUTS = Path(__file__).resolve().parent / "outputs"

# True isometric: equal weight on all three axes, which is the projection the
# reference block illustrations are drawn in.
ISOMETRIC = (1.0, -1.0, 1.0)


def contact_sheet(labels, suffix, columns=6):
    """Tile every render of one view into a single sheet for side-by-side reading."""
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

SEEDS = (7, 23, 41)
FLOOR_HEIGHT_M = 2.8


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


def _random_jobs(count, seed):
    """N fully random (lot, family, seed, setback) combos. The picker seed is
    printed so any run stays reproducible."""
    import random as _random

    rng = _random.Random(seed)
    print(f"random picker seed: {seed if seed is not None else '(entropy)'}")
    names = sorted(LOTS)
    families = sorted(FAMILY_RULES)
    jobs = []
    for i in range(count):
        lot_name = rng.choice(names)
        lot = LOTS[lot_name]
        family = rng.choice(families)
        pick = rng.randint(0, 2 ** 31 - 1)
        setback = round(rng.uniform(1.8, 3.2), 2) if rng.random() < 0.5 else 0.0
        jobs.append((f"random{i:02d}_{lot_name}_{family}_s{pick}", lot, family,
                     pick, setback))
    return jobs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--detail", type=int, default=2, choices=(1, 2, 3))
    parser.add_argument("--size", type=int, default=720)
    parser.add_argument("--no-render", action="store_true")
    parser.add_argument("--no-glb", action="store_true",
                        help="skip the GLB export (renders only)")
    parser.add_argument("--random", type=int, default=0, metavar="N",
                        help="generate N fully random examples instead of the "
                             "fixed regression matrix")
    parser.add_argument("--random-seed", type=int, default=None,
                        help="seed for the random picker (default: entropy)")
    args = parser.parse_args()

    OUTPUTS.mkdir(parents=True, exist_ok=True)
    families = sorted(FAMILY_RULES)
    fingerprint = {}

    if args.random:
        jobs = _random_jobs(args.random, args.random_seed)
    else:
        jobs = []
        for index, (lot_name, lot) in enumerate(LOTS.items()):
            for seed in SEEDS:
                family = families[(index + seed) % len(families)]
                setback = 2.6 if (seed + index) % 3 == 0 else 0.0
                jobs.append((f"{lot_name}_{family}_s{seed}", lot, family, seed,
                             setback))

    for label, lot, family, seed, setback in jobs:
        spec = build(lot, family, seed, setback)
        mesh = generate_v4_mesh(spec, detail=args.detail)
        report = validate_mesh(
            mesh, Polygon(spec.context.polygon),
            envelope=street_envelope(spec.context),
        )
        fingerprint[label] = {
            "family": family,
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

    path = OUTPUTS / f"fingerprint_lod{args.detail}.json"
    path.write_text(json.dumps(fingerprint, indent=2, sort_keys=True))
    total = sum(item["triangles"] for item in fingerprint.values())
    print(f"\n{len(fingerprint)} buildings, {total} triangles total")
    print(f"fingerprint written to {path}")
    if not args.no_render:
        sheet = contact_sheet(sorted(fingerprint), "_iso")
        if sheet is not None:
            print(f"contact sheet written to {sheet}")


if __name__ == "__main__":
    main()
