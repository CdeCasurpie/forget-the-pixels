import sys; sys.path.insert(0, 'src')
from domain.architecture import *
from procedural_modeling.boundaries import generate_boundaries

mass_small = MassSpec(id='small', footprint=((0,3),(8,3),(8,12),(0,12)), base_z=0.0, roof_z=6.0, floor_levels=(0.0, 3.0, 6.0), role='tower', roof_spec=None)
site_small = SitePlan(masses=(mass_small,), free_space=(), access_nodes=(), boundaries=(), exclusion_zones=())
ctx = ParcelContext(polygon=((0,0), (10,0), (10,20), (0,20)))

program = BuildingProgram(
    use="residential", occupancy="low", placement="front_setback", 
    architectural_language="vernacular", finish_profile="standard", 
    maintenance="average", construction_state="finished", 
    front_setback=3.0, side_setback=0.0,
    primary_color=(0.9, 0.8, 0.4), seed=303
)

bnds = generate_boundaries(ctx, program, site_small)
for b in bnds:
    print(b.kind, list(b.line.coords))
