#!/usr/bin/env python3
"""Batch procedural house generation using the refactored 'modeling' library."""

import sys
import random
from pathlib import Path
from shapely.geometry import Polygon

# Ensure src is in the python path
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from domain.architecture import BuildingProgram, ParcelContext, MassSpec, SitePlan, BuildingSpecificationV4
from modeling import generate_v4_mesh, export_glb

def generate_random_houses(count: int, output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. We will use a standard 10x20 rectangular lot for the examples
    lot_w, lot_d = 10, 20
    lot_poly = Polygon([(0, 0), (lot_w, 0), (lot_w, lot_d), (0, lot_d)])
    ctx = ParcelContext(polygon=tuple(lot_poly.exterior.coords))
    
    uses = ["residential", "commercial_podium"]
    finishes = ["raw", "painted", "standard", "premium"]
    fences = ["none", "reja", "ladrillos", "concreto"]
    
    print(f"Generating {count} procedural houses...")
    for i in range(count):
        seed = random.randint(1000, 9999)
        use = random.choice(uses)
        finish = random.choice(finishes)
        fence = random.choice(fences)
        floors = random.randint(1, 5)
        setback = random.choice([0.0, 1.5, 3.0])
        color = (random.random(), random.random(), random.random())
        
        print(f"[{i+1}/{count}] Seed: {seed}, Floors: {floors}, Use: {use}, Finish: {finish}, Fence: {fence}")
        
        program = BuildingProgram(
            use=use, occupancy="medium", placement="front_setback" if setback > 0 else "flush",
            architectural_language="modern", finish_profile=finish,
            maintenance="average", construction_state="finished",
            front_setback=setback, side_setback=0.0,
            primary_color=color, seed=seed,
            is_corner=False,
            has_fence=(fence!="none" and setback >= 1.0),
            fence_type=fence
        )

        inner_poly = lot_poly.buffer(-0.0, join_style=2)
        if setback > 0:
            box_setback = Polygon([(0, 0), (100, 0), (100, setback), (0, setback)])
            inner_poly = inner_poly.difference(box_setback)
        
        footprint = tuple(inner_poly.exterior.coords) if inner_poly.geom_type == "Polygon" else tuple(inner_poly.geoms[0].exterior.coords)
        
        mass = MassSpec(
            id="main", footprint=footprint, base_z=0.0, roof_z=floors * 3.0,
            floor_levels=tuple(f * 3.0 for f in range(floors + 1)),
            role="tower", roof_spec=None
        )
        site = SitePlan(masses=(mass,), free_space=(), access_nodes=(), boundaries=(), exclusion_zones=())
        spec = BuildingSpecificationV4(context=ctx, program=program, site_plan=site, facades=(), components=(), seed=seed)
        
        mesh = generate_v4_mesh(spec)
        out_path = output_dir / f"house_seed{seed}_{use}.glb"
        export_glb(mesh, out_path)
        print(f"   -> Saved to {out_path}")

if __name__ == "__main__":
    out = Path(__file__).resolve().parent / "outputs" / "batch_generation"
    generate_random_houses(5, out)

    gitignore = Path(__file__).resolve().parent / ".gitignore"
    if not gitignore.exists() or "outputs/" not in gitignore.read_text():
        with open(gitignore, "a") as f:
            f.write("\noutputs/\n")
