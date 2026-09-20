import sys; sys.path.insert(0, 'src')
from domain.architecture import *
from procedural_modeling.exposure import calculate_mass_exposures
from shapely.geometry import Polygon

mass_podium = MassSpec(id='podium', footprint=((0,3),(10,3),(10,20),(0,20)), base_z=0.0, roof_z=4.0, floor_levels=(0.0, 4.0), role='podium', roof_spec=None)
mass_tower = MassSpec(id='tower', footprint=((0,10),(10,10),(10,20),(0,20)), base_z=4.0, roof_z=20.0, floor_levels=(4.0,8.0,12.0,16.0,20.0), role='tower', roof_spec=None)
site = SitePlan(masses=(mass_podium, mass_tower), free_space=(), access_nodes=(), boundaries=(), exclusion_zones=())
exp = calculate_mass_exposures(site)
for mass_id, data in exp.items():
    for w in data['walls']:
        seg = w['exposed_segments']
        print(f"{mass_id} band {w['z_bottom']}-{w['z_top']}: {seg.geom_type}")
        lines = [seg] if seg.geom_type in ('LineString', 'LinearRing') else list(seg.geoms)
        for line in lines:
            print("  Line:", list(line.coords))
