import sys
import numpy as np
from pathlib import Path
from shapely.geometry import Polygon

sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))
sys.path.insert(0, '.')

from domain.architecture import BuildingProgram, ParcelContext, SitePlan, MassSpec, BuildingSpecificationV4
from modeling.grammar import generate_v4_mesh
from steps.step12_city_generation.render import render
from modeling.exporters.glb_exporter import export_glb

def main():
    output_dir = Path("steps/step14_random_houses/outputs")
    output_dir.mkdir(parents=True, exist_ok=True)
    seed = 777

    # Corner lot: 12m x 18m (two street frontages)
    ctx = ParcelContext(polygon=((0,0), (12,0), (12,18), (0,18)))

    # Ground floor: slightly recessed (dark base, like the reference)
    ground = MassSpec(
        id="ground",
        footprint=((0.3, 0.0), (12, 0.0), (12, 18), (0.3, 18)),
        base_z=0.0, roof_z=4.0,
        floor_levels=(0.0, 4.0),
        role="podium", roof_spec=None
    )

    # 2nd-3rd floor: full width
    mid = MassSpec(
        id="mid",
        footprint=((0.0, 0.0), (12, 0.0), (12, 18), (0.0, 18)),
        base_z=4.0, roof_z=11.0,
        floor_levels=(4.0, 7.5, 11.0),
        role="tower", roof_spec=None
    )

    # 4th floor: stepped back on one side (like the reference)
    top = MassSpec(
        id="top",
        footprint=((0.0, 0.0), (9.0, 0.0), (9.0, 18), (0.0, 18)),
        base_z=11.0, roof_z=14.5,
        floor_levels=(11.0, 14.5),
        role="tower", roof_spec=None
    )

    site = SitePlan(
        masses=(ground, mid, top),
        free_space=(), access_nodes=(), boundaries=(), exclusion_zones=()
    )

    spec = BuildingSpecificationV4(
        program=BuildingProgram(
            use="mixed", occupancy="medium", placement="flush",
            architectural_language="modern", finish_profile="premium",
            maintenance="average", construction_state="finished",
            front_setback=0.0, side_setback=0.0,
            primary_color=(0.92, 0.90, 0.88),  # Blanco humo
            side_wall_finish="plastered",
            seed=seed
        ),
        context=ctx, site_plan=site, facades=(), components=(), seed=seed
    )

    name = "corner_white_building"
    print(f"Generating {name}...")
    mesh_data = generate_v4_mesh(spec)
    render(mesh_data, str(output_dir / f"{name}.png"), clay=False)
    export_glb(mesh_data, str(output_dir / f"{name}.glb"))

if __name__ == "__main__":
    main()
