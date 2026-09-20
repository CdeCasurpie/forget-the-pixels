import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path("src").resolve()))

from modeling.randomness import resolve_seed
from modeling.migration import migrate_to_v4
from domain.models import BuildingSpecification, HeightEstimate, FacadeSpecification
from domain.architecture import BuildingSpecificationV4, EvidenceValue

def test_resolve_seed_is_stable():
    s1 = resolve_seed(42, "lot_123", "mass_0", "window_1", "jitter")
    s2 = resolve_seed(42, "lot_123", "mass_0", "window_1", "jitter")
    s3 = resolve_seed(43, "lot_123", "mass_0", "window_1", "jitter")
    
    assert s1 == s2
    assert s1 != s3
    assert isinstance(s1, int)

def test_evidence_value_locking():
    ev = EvidenceValue(value=3.5, source="user", confidence=1.0, locked=True)
    assert ev.locked is True

def test_migrate_to_v4():
    # Construct a minimal V1 spec
    legacy = BuildingSpecification(
        seed=100,
        crs="EPSG:32718",
        parcel_xy=((0,0), (10,0), (10,10), (0,10)),
        parcel_holes=(),
        footprint_xy=((1,1), (9,1), (9,9), (1,9)),
        height=HeightEstimate(continuous_height_m=10.0, floor_count=3, reprojection_rmse_px=0.0, used_pano_ids=()),
        roof=None,
        facade_edges=(
            FacadeSpecification(
                edge_id="f1",
                vertex_a=(1,1),
                vertex_b=(9,1),
                width_m=8.0,
                normal_xy=(0,-1),
                floor_levels_m=(0.0, 3.0, 6.0, 10.0),
                openings=()
            ),
        )
    )
    
    v4 = migrate_to_v4(legacy)
    assert isinstance(v4, BuildingSpecificationV4)
    assert v4.program.seed == 100
    assert len(v4.site_plan.masses) == 1
    assert v4.site_plan.masses[0].roof_z == 10.0
    assert len(v4.facades) == 1
    assert v4.facades[0].mass_id == "mass_0"
