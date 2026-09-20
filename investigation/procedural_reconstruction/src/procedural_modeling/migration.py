from domain.models import BuildingSpecification
from domain.architecture import (
    BuildingSpecificationV4, BuildingProgram, ParcelContext, SitePlan, MassSpec, FacadeSpecV4, EdgeRef
)
import numpy as np

def migrate_to_v4(legacy: BuildingSpecification) -> BuildingSpecificationV4:
    """Migrates a legacy V1-V3 BuildingSpecification to V4, keeping geometry locked."""
    
    # 1. Map legacy source/family into a V4 BuildingProgram
    program = BuildingProgram(
        use=getattr(legacy, 'source', 'inferred'),
        occupancy="unknown",
        placement="unknown",
        architectural_language=getattr(legacy, 'family', 'quiet_house'),
        finish_profile="standard",
        maintenance="standard",
        construction_state="completed",
        seed=legacy.seed
    )
    
    # 2. Map legacy footprint to a single MassSpec
    # For baseline compatibility, we treat the entire building as one mass (mass_0)
    mass_id = "mass_0"
    base_z = 0.0
    roof_z = float(legacy.height.continuous_height_m)
    
    # Floor levels were usually derived during generation; we can approximate or leave empty for the migrator
    # Let's derive them safely if we have facade specs, otherwise generate a simple distribution
    if legacy.facade_edges and legacy.facade_edges[0].floor_levels_m:
        levels = legacy.facade_edges[0].floor_levels_m
    else:
        floors = legacy.height.floor_count
        levels = tuple(float(z) for z in np.linspace(0, roof_z, floors + 1))
        
    mass = MassSpec(
        id=mass_id,
        footprint=tuple(tuple(float(c) for c in pt) for pt in legacy.footprint_xy),
        base_z=base_z,
        roof_z=roof_z,
        floor_levels=tuple(levels),
        role="main",
        roof_spec=legacy.roof
    )
    
    site_plan = SitePlan(
        masses=(mass,),
        free_space=(),
        access_nodes=(),
        boundaries=(),
        exclusion_zones=()
    )
    
    # 3. Map legacy FacadeSpecification to FacadeSpecV4
    # We preserve openings exactly as they are in legacy.
    v4_facades = []
    for f in legacy.facade_edges:
        edge = EdgeRef(
            id=f.edge_id,
            endpoints=(f.vertex_a, f.vertex_b),
            ring_id=0,
            orientation=1
        )
        v4_f = FacadeSpecV4(
            mass_id=mass_id,
            edge_ref=edge,
            exposed_intervals=((0.0, float(np.linalg.norm(np.array(f.vertex_b) - np.array(f.vertex_a)))),),
            floor_ranges=((0, len(levels)-1),),
            bays=(),
            openings=tuple(f.openings),
            material_regions=tuple(f.material_regions)
        )
        v4_facades.append(v4_f)
        
    return BuildingSpecificationV4(
        program=program,
        context=ParcelContext(polygon=tuple(tuple(float(c) for c in pt) for pt in legacy.parcel_xy)),
        site_plan=site_plan,
        facades=tuple(v4_facades),
        components=(),
        seed=legacy.seed
    )
