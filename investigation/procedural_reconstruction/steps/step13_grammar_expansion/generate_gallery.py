import sys
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))
sys.path.insert(0, '.')

from domain.architecture import BuildingProgram, ParcelContext, SitePlan, MassSpec, BuildingSpecificationV4
from procedural_modeling.v4_grammar import generate_v4_mesh
from steps.step12_city_generation.render import render
from exporters.glb_exporter import export_glb

def create_case(i, seed, width, depth, use, placement, finish_profile, side_wall_finish, color, masses_desc):
    ctx = ParcelContext(polygon=((0,0), (width,0), (width,depth), (0,depth)))
    
    masses = []
    for m in masses_desc:
        fx1, fy1, fx2, fy2 = m["footprint"]
        bz, rz = m["z"]
        floors = tuple(np.linspace(bz, rz, m["floors"] + 1))
        masses.append(MassSpec(
            id=m["id"], 
            footprint=((fx1,fy1),(fx2,fy1),(fx2,fy2),(fx1,fy2)),
            base_z=bz, roof_z=rz, floor_levels=floors, role=m["role"], roof_spec=None
        ))
        
    site = SitePlan(masses=tuple(masses), free_space=(), access_nodes=(), boundaries=(), exclusion_zones=())
    
    spec = BuildingSpecificationV4(
        program=BuildingProgram(
            use=use, occupancy="medium", placement=placement, 
            architectural_language="modern" if finish_profile=="premium" else "vernacular",
            finish_profile=finish_profile, 
            maintenance="average", construction_state="finished", 
            front_setback=3.0 if placement=="front_setback" else 0.0, side_setback=0.0,
            primary_color=color, 
            side_wall_finish=side_wall_finish,
            seed=seed
        ),
        context=ctx, site_plan=site, facades=(), components=(), seed=seed
    )
    return spec

def main():
    output_dir = Path("steps/step13_grammar_expansion/outputs/gallery")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    rng = np.random.default_rng(42)
    
    colors = [
        (0.65, 0.35, 0.28), # Terracotta
        (0.75, 0.70, 0.55), # Ochre
        (0.35, 0.45, 0.55), # Blue grey
        (0.6, 0.65, 0.6),   # Sage green
        (0.8, 0.8, 0.75),   # Off white
        (0.4, 0.3, 0.3),    # Dark brown
        (0.7, 0.5, 0.4),    # Coral dust
        (0.5, 0.5, 0.5),    # Concrete grey
    ]
    
    scenarios = []
    
    # 1-5: Small houses (Residential, Setback, Standard)
    for i in range(5):
        w = rng.uniform(6.0, 10.0)
        d = rng.uniform(15.0, 20.0)
        c = colors[rng.integers(len(colors))]
        scenarios.append(create_case(i+1, 100+i, w, d, "residential", "front_setback", "standard", "raw", c, [
            {"id": "house", "footprint": (0, 3, w, 12), "z": (0, 8), "floors": 2, "role": "tower"}
        ]))
        
    # 6-10: Commercial flush standard (Ladrillo)
    for i in range(5):
        w = rng.uniform(5.0, 8.0)
        d = rng.uniform(15.0, 25.0)
        c = colors[rng.integers(len(colors))]
        scenarios.append(create_case(6+i, 200+i, w, d, "commercial", "flush", "standard", "raw", c, [
            {"id": "store", "footprint": (0, 0, w, d-3), "z": (0, 12), "floors": 3, "role": "tower"}
        ]))
        
    # 11-15: Mixed use Premium (Plastered side walls, multi-mass)
    for i in range(5):
        w = rng.uniform(8.0, 12.0)
        d = rng.uniform(20.0, 30.0)
        c = colors[rng.integers(len(colors))]
        scenarios.append(create_case(11+i, 300+i, w, d, "mixed", "flush", "premium", "plastered", c, [
            {"id": "podium", "footprint": (0, 0, w, d), "z": (0, 4), "floors": 1, "role": "podium"},
            {"id": "tower", "footprint": (0, d*0.4, w, d), "z": (4, 20), "floors": 4, "role": "tower"}
        ]))
        
    # 16-20: L-shaped residential blocks
    for i in range(5):
        w = 15.0
        d = 20.0
        c = colors[rng.integers(len(colors))]
        scenarios.append(create_case(16+i, 400+i, w, d, "residential", "front_setback", "standard", "raw", c, [
            {"id": "main", "footprint": (0, 3, w, 8), "z": (0, 12), "floors": 3, "role": "tower"},
            {"id": "wing", "footprint": (0, 8, 6, 18), "z": (0, 12), "floors": 3, "role": "tower"}
        ]))

    for idx, spec in enumerate(scenarios):
        num = idx + 1
        name = f"building_{num:02d}_{spec.program.use}_{spec.program.finish_profile}"
        print(f"Generating {name}...")
        mesh_data = generate_v4_mesh(spec)
        render(mesh_data, str(output_dir / f"{name}.png"), clay=False)
        export_glb(mesh_data, str(output_dir / f"{name}.glb"))

if __name__ == "__main__":
    main()
