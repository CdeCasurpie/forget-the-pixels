import sys; sys.path.insert(0, 'src')
from domain.architecture import *
from procedural_modeling.v4_grammar import generate_v4_mesh

mass_podium = MassSpec(id='podium', footprint=((0,3),(10,3),(10,20),(0,20)), base_z=0.0, roof_z=4.0, floor_levels=(0.0, 4.0), role='podium', roof_spec=None)
mass_tower = MassSpec(id='tower', footprint=((0,10),(10,10),(10,20),(0,20)), base_z=4.0, roof_z=20.0, floor_levels=(4.0, 8.0, 12.0, 16.0, 20.0), role='tower', roof_spec=None)
site = SitePlan(masses=(mass_podium, mass_tower), free_space=(), access_nodes=(), boundaries=(), exclusion_zones=())
spec = BuildingSpecificationV4(
    program=BuildingProgram(
        use="commercial", occupancy=5, placement="front_setback",
        architectural_language="modern", finish_profile="premium", 
        maintenance="good", construction_state="finished", 
        front_setback=3.0, side_setback=0.0,
        primary_color=(0.1, 0.4, 0.8),
        side_wall_finish="plastered", seed=42
    ),
    context=ParcelContext(polygon=((0,0), (10,0), (10,20), (0,20))),
    site_plan=site, facades=(), components=(), seed=42
)
mesh = generate_v4_mesh(spec)
print(f"Total faces: {len(mesh.faces)}")
concrete_mat_idx = mesh.materials.index(next(m for m in mesh.materials if m['name'] == 'concrete'))
concrete_faces = sum(1 for f in mesh.face_materials if f == concrete_mat_idx)
print(f"Concrete faces: {concrete_faces}")
brick_mat_idx = mesh.materials.index(next(m for m in mesh.materials if m['name'] == 'brick'))
plaster_mat_idx = mesh.materials.index(next(m for m in mesh.materials if m['name'] == 'plaster'))
print(f"Brick faces: {sum(1 for f in mesh.face_materials if f == brick_mat_idx)}")
print(f"Plaster faces: {sum(1 for f in mesh.face_materials if f == plaster_mat_idx)}")
