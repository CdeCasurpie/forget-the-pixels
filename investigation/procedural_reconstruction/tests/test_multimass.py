import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path("src").resolve()))
from domain.architecture import SitePlan, MassSpec
from procedural_modeling.exposure import calculate_mass_exposures
from shapely.geometry import Polygon

def test_multimass_exposure():
    # Lote de 10x20
    # Mass 1: Base (0 a 3m), ocupa todo el lote (10x20)
    # Mass 2: Torre (3 a 12m), ocupa solo la parte de atras (10x10)
    # Mass 3: Adyacente (0 a 6m), ocupa un lote al lado
    
    mass_base = MassSpec(
        id="base",
        footprint=((0,0), (10,0), (10,20), (0,20)),
        base_z=0.0,
        roof_z=3.0,
        floor_levels=(0.0, 3.0),
        role="podium",
        roof_spec=None
    )
    
    mass_tower = MassSpec(
        id="tower",
        footprint=((0,10), (10,10), (10,20), (0,20)), # Solo la mitad trasera
        base_z=3.0,
        roof_z=12.0,
        floor_levels=(3.0, 6.0, 9.0, 12.0),
        role="tower",
        roof_spec=None
    )
    
    site = SitePlan(
        masses=(mass_base, mass_tower),
        free_space=(),
        access_nodes=(),
        boundaries=(),
        exclusion_zones=()
    )
    
    exposures = calculate_mass_exposures(site)
    
    # Eval base walls
    base_walls = exposures["base"]["walls"]
    assert len(base_walls) == 1
    assert base_walls[0]["z_bottom"] == 0.0
    assert base_walls[0]["z_top"] == 3.0
    assert base_walls[0]["exposed_segments"].length == pytest.approx(60.0) # Perimeter of 10x20
    
    # Eval base roof (should be half covered by tower)
    base_roof = exposures["base"]["roof"]["exposed_area"]
    assert base_roof.area == pytest.approx(100.0) # Original 200 - Tower 100
    
    # Eval tower walls
    tower_walls = exposures["tower"]["walls"]
    assert len(tower_walls) == 1
    assert tower_walls[0]["z_bottom"] == 3.0
    assert tower_walls[0]["z_top"] == 12.0
    assert tower_walls[0]["exposed_segments"].length == pytest.approx(40.0) # Perimeter of 10x10

