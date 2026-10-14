import sys
import numpy as np
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src')); sys.path.insert(0, '.')

from domain.architecture import BuildingProgram, ParcelContext, SitePlan, MassSpec, BuildingSpecificationV4
# from domain.models import ...
from modeling.v4_grammar import generate_v4_mesh
from steps.step12_city_generation.render import render

def render_case(spec, output_path):
    # Generar la malla
    mesh_data = generate_v4_mesh(spec)
    # Renderizar
    render(mesh_data, str(output_path), clay=False)
    print(f"Rendered {output_path}")

def main():
    # Contexto común
    ctx = ParcelContext(polygon=((0,0), (10,0), (10,20), (0,20)))
    
    # CASO 1: Standard con ladrillos
    mass_podium = MassSpec(id='podium', footprint=((0,3),(10,3),(10,20),(0,20)), base_z=0.0, roof_z=4.0, floor_levels=(0.0, 4.0), role='podium', roof_spec=None)
    mass_tower = MassSpec(id='tower', footprint=((0,10),(10,10),(10,20),(0,20)), base_z=4.0, roof_z=20.0, floor_levels=(4.0,8.0,12.0,16.0,20.0), role='tower', roof_spec=None)
    mass_podium_flush = MassSpec(id='podium', footprint=((0,0),(10,0),(10,20),(0,20)), base_z=0.0, roof_z=4.0, floor_levels=(0.0, 4.0), role='podium', roof_spec=None)
    site_flush = SitePlan(masses=(mass_podium_flush, mass_tower), free_space=(), access_nodes=(), boundaries=(), exclusion_zones=())
    
    site = SitePlan(masses=(mass_podium, mass_tower), free_space=(), access_nodes=(), boundaries=(), exclusion_zones=())
    
    spec_1 = BuildingSpecificationV4(
        program=BuildingProgram(
            use="mixed", occupancy="high", placement="flush", 
            architectural_language="modern", finish_profile="standard", 
            maintenance="average", construction_state="finished", 
            front_setback=0.0, side_setback=0.0,
            primary_color=(0.65, 0.35, 0.28), # Ladrillo terracota apagado
            side_wall_finish="raw", # <--- LADRILLO CON VIGAS
            seed=101
        ),
        context=ctx, site_plan=site_flush, facades=(), components=(), seed=101
    )
    
    # CASO 2: Premium tarrajeado (Gris plomo en los lados)
    spec_2 = BuildingSpecificationV4(
        program=BuildingProgram(
            use="mixed", occupancy="high", placement="front_setback", 
            architectural_language="modern", finish_profile="premium", 
            maintenance="good", construction_state="finished", 
            front_setback=3.0, side_setback=0.0,
            primary_color=(0.35, 0.45, 0.55), # Azul pizarra grisáceo
            side_wall_finish="plastered", # <--- CONCRETO PLANO
            seed=202
        ),
        context=ctx, site_plan=site, facades=(), components=(), seed=202
    )
    
    # CASO 3: Pequeña casa residencial (Ladrillos)
    mass_small = MassSpec(id='house', footprint=((0,3),(10,3),(10,15),(0,15)), base_z=0.0, roof_z=8.0, floor_levels=(0.0, 4.0, 8.0), role='tower', roof_spec=None)
    site_small = SitePlan(masses=(mass_small,), free_space=(), access_nodes=(), boundaries=(), exclusion_zones=())
    
    spec_3 = BuildingSpecificationV4(
        program=BuildingProgram(
            use="residential", occupancy="low", placement="front_setback", 
            architectural_language="vernacular", finish_profile="standard", 
            maintenance="average", construction_state="finished", 
            front_setback=3.0, side_setback=0.0,
            primary_color=(0.75, 0.70, 0.55), # Ocre apagado
            side_wall_finish="raw", # <--- LADRILLO CON VIGAS
            seed=303
        ),
        context=ctx, site_plan=site_small, facades=(), components=(), seed=303
    )
    
    output_dir = Path("steps/step13_grammar_expansion/outputs")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    render_case(spec_1, output_dir / "example_1_raw.png")
    render_case(spec_2, output_dir / "example_2_premium.png")
    render_case(spec_3, output_dir / "example_3_small.png")

if __name__ == "__main__":
    main()
