import sys
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))
sys.path.insert(0, '.')

from domain.architecture import BuildingProgram, ParcelContext, SitePlan, MassSpec, BuildingSpecificationV4
from modeling.grammar import generate_v4_mesh
from steps.step12_city_generation.render import render

def main():
    output_dir = Path("steps/step14_random_houses/outputs")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    seed = 999  # Fix seed for reproducibility
    
    # Lot: 10x15
    ctx = ParcelContext(polygon=((0,0), (10,0), (10,15), (0,15)))
    
    # 2 Floors (8m tall), covering the entire front so there is no space for a fence
    mass = MassSpec(
        id="main", 
        footprint=((0,0), (10,0), (10,15), (0,15)),
        base_z=0.0, roof_z=8.0, 
        floor_levels=(0.0, 4.0, 8.0),
        role="tower", roof_spec=None
    )
    
    site = SitePlan(masses=(mass,), free_space=(), access_nodes=(), boundaries=(), exclusion_zones=())
    
    # We use placement="flush" so it aligns with the street (no yard, no fence)
    # finish_profile="standard" gives a high probability of classic windows
    spec = BuildingSpecificationV4(
        program=BuildingProgram(
            use="residential", occupancy="low", placement="flush", 
            architectural_language="vernacular", finish_profile="standard", 
            maintenance="average", construction_state="finished", 
            front_setback=0.0, side_setback=0.0,
            primary_color=(0.8, 0.7, 0.6), 
            side_wall_finish="raw",
            seed=seed
        ),
        context=ctx, site_plan=site, facades=(), components=(), seed=seed
    )
    
    name = "custom_house_no_fence"
    print(f"Generating {name}...")
    mesh_data = generate_v4_mesh(spec)
    render(mesh_data, str(output_dir / f"{name}.png"), clay=False)

if __name__ == "__main__":
    main()
