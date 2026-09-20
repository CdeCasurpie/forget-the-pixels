import sys
import numpy as np
from pathlib import Path
from shapely.geometry import Polygon

sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))
sys.path.insert(0, '.')

from domain.architecture import BuildingProgram, ParcelContext, SitePlan, MassSpec, BuildingSpecificationV4
from modeling.grammar import generate_v4_mesh
from steps.step12_city_generation.render import render

def main():
    output_dir = Path("steps/step14_random_houses/outputs")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    seed = 884  # Magic seed for good window placement
    
    # Lot: 10m wide x 20m deep
    ctx = ParcelContext(polygon=((0,0), (10,0), (10,20), (0,20)))
    
    # Ground floor (Podium): Set back by 5 meters to leave space for the garage
    ground_poly = Polygon([(0, 5), (10, 5), (10, 20), (0, 20)])
    mass_ground = MassSpec(
        id="ground", 
        footprint=tuple(ground_poly.buffer(-0.1).exterior.coords),
        base_z=0.0, roof_z=3.5, 
        floor_levels=(0.0, 3.5),
        role="podium", roof_spec=None
    )
    
    # Upper floors (Tower): Cantilevers forward over the garage by 1.5m (starts at y=3.5)
    # Total 4 floors on top (3.5m to 15.5m)
    upper_poly = Polygon([(0, 3.5), (10, 3.5), (10, 20), (0, 20)])
    mass_upper = MassSpec(
        id="upper", 
        footprint=tuple(upper_poly.buffer(-0.1).exterior.coords),
        base_z=3.5, roof_z=15.5, 
        floor_levels=(3.5, 6.5, 9.5, 12.5, 15.5),
        role="tower", roof_spec=None
    )
    
    site = SitePlan(
        masses=(mass_ground, mass_upper), 
        free_space=(), access_nodes=(), boundaries=(), exclusion_zones=()
    )
    
    # Matching the colors (Peach/Terracotta + White/Grey accents)
    # The API will use primary_color for the main walls. 
    # Modern profile gives slim windows without thick legacy frames.
    spec = BuildingSpecificationV4(
        program=BuildingProgram(
            use="residential", occupancy="medium", placement="front_setback", 
            architectural_language="modern", finish_profile="premium", 
            maintenance="average", construction_state="finished", 
            front_setback=5.0, side_setback=0.0,
            primary_color=(0.85, 0.55, 0.40), # Salmón / Terracota claro
            side_wall_finish="plastered", # Paredes laterales lisas blancas/grises
            seed=seed
        ),
        context=ctx, site_plan=site, facades=(), components=(), seed=seed
    )
    
    name = "lima_reference_building"
    print(f"Generating {name}...")
    mesh_data = generate_v4_mesh(spec)
    render(mesh_data, str(output_dir / f"{name}.png"), clay=False)

if __name__ == "__main__":
    main()
