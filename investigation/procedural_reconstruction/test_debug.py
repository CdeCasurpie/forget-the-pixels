import sys
from pathlib import Path
sys.path.insert(0, str(Path("src").resolve()))
from domain.architecture import SitePlan, MassSpec, BuildingSpecificationV4, BuildingProgram, ParcelContext
from procedural_modeling.v4_grammar import generate_v4_mesh

mass_podium = MassSpec(
    id="podium",
    footprint=((0,0), (10,0), (10,20), (0,20)),
    base_z=0.0,
    roof_z=4.0,
    floor_levels=(0.0, 4.0),
    role="podium",
    roof_spec=None
)
site = SitePlan(
    masses=(mass_podium,),
    free_space=(), access_nodes=(), boundaries=(), exclusion_zones=()
)
spec = BuildingSpecificationV4(
    program=BuildingProgram(use="mixed", occupancy="high", placement="flush", architectural_language="modern", finish_profile="standard", maintenance="good", construction_state="finished", seed=42),
    context=ParcelContext(polygon=((0,0), (10,0), (10,20), (0,20))),
    site_plan=site, facades=(), components=(), seed=42
)

from procedural_modeling.exposure import calculate_mass_exposures
exposures = calculate_mass_exposures(spec.site_plan)
walls = exposures["podium"]["walls"][0]["exposed_segments"]
print(f"Exposed lines: {walls.wkt}")
