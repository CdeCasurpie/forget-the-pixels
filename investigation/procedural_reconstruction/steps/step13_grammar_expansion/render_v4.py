import sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path("src").resolve()))
from domain.architecture import SitePlan, MassSpec, BuildingSpecificationV4, BuildingProgram, ParcelContext, FacadeSpecV4
from procedural_modeling.v4_grammar import generate_v4_mesh
from exporters.glb_exporter import MaterialLibrary, export_glb

def main():
    out_dir = Path("steps/step13_grammar_expansion/outputs")
    out_dir.mkdir(exist_ok=True, parents=True)
    
    # Push podium and tower back by 3 meters (Y=3 to Y=20 instead of 0 to 20)
    mass_podium = MassSpec(
        id="podium",
        footprint=((0,3), (10,3), (10,20), (0,20)),
        base_z=0.0,
        roof_z=4.0,
        floor_levels=(0.0, 4.0),
        role="podium",
        roof_spec=None
    )
    
    mass_tower = MassSpec(
        id="tower",
        footprint=((0,10), (10,10), (10,20), (0,20)),
        base_z=4.0,
        roof_z=20.0,
        floor_levels=(4.0, 8.0, 12.0, 16.0, 20.0),
        role="tower",
        roof_spec=None
    )
    
    site = SitePlan(
        masses=(mass_podium, mass_tower),
        free_space=(), access_nodes=(), boundaries=(), exclusion_zones=()
    )
    
    spec = BuildingSpecificationV4(
        program=BuildingProgram(
            use="mixed", occupancy="high", placement="front_setback", 
            architectural_language="modern", finish_profile="premium", 
            maintenance="good", construction_state="finished", 
            front_setback=3.0, side_setback=0.0,
            primary_color=(0.1, 0.4, 0.8), # Blue color!
            side_wall_finish="plastered", # Plastered sides instead of raw brick!
            seed=42
        ),
        context=ParcelContext(polygon=((0,0), (10,0), (10,20), (0,20))),
        site_plan=site,
        facades=(),
        components=(),
        seed=42
    )
    
    mesh = generate_v4_mesh(spec)
    catalog = MaterialLibrary(Path("assets/pbr/catalog.json"))
    
    out_path = out_dir / "multimass_test.glb"
    export_glb(mesh, str(out_path), library=catalog)
    import sys; sys.path.insert(0, "."); from steps.step12_city_generation.render import render
    render(mesh, str(out_dir / "multimass_render.png"), clay=False)
    print(f"GLB exportado a {out_path}")

if __name__ == "__main__":
    main()
