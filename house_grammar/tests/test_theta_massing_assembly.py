import pytest
from shapely.geometry import Polygon
from domain.theta import ThetaCandidate, MassingControls, ReconstructionContext
from modeling.theta import resolve_theta

def make_context(coords):
    return ReconstructionContext(parcel=coords, fronts=(0,))

def test_single_block_invariants():
    coords = ((0, 0), (10, 0), (10, 20), (0, 20), (0, 0))
    ctx = make_context(coords)
    m = MassingControls(pattern="single_block", front_setback_m=3.0)
    theta = ThetaCandidate(height_m=6.0, floors=2, family="mixed_use", massing=m, schema_version="0.2")
    res = resolve_theta(ctx, theta)
    
    assert len(res.masses) == 1
    main = res.masses[0]
    assert main.role == "main"
    assert main.base_z == 0.0
    assert main.roof_z == 6.0
    
    # Distance from parcel front
    footprint = Polygon(main.footprint)
    assert footprint.bounds[1] == pytest.approx(3.0)

def test_stepped_back_invariants():
    coords = ((0, 0), (10, 0), (10, 20), (0, 20), (0, 0))
    ctx = make_context(coords)
    m = MassingControls(pattern="stepped_back", front_setback_m=3.0, upper_setback_m=2.5)
    theta = ThetaCandidate(height_m=6.0, floors=2, family="mixed_use", massing=m, schema_version="0.2")
    res = resolve_theta(ctx, theta)
    
    assert len(res.masses) == 2
    main = next(m for m in res.masses if m.role == "main")
    setback = next(m for m in res.masses if m.role == "setback")
    
    main_poly = Polygon(main.footprint)
    setback_poly = Polygon(setback.footprint)
    
    # Invariant: setback footprint ⊂ main footprint
    assert main_poly.covers(setback_poly)
    
    # Vertical invariant: main.roof_z == setback.base_z
    assert main.roof_z == setback.base_z
    
    # Distance from body
    assert main_poly.bounds[1] == pytest.approx(3.0)
    assert setback_poly.bounds[1] == pytest.approx(5.5)

def test_front_tall_rear_low_invariants():
    coords = ((0, 0), (10, 0), (10, 20), (0, 20), (0, 0))
    ctx = make_context(coords)
    m = MassingControls(pattern="front_tall_rear_low", front_setback_m=3.0, front_depth_m=6.0, low_floors=1)
    theta = ThetaCandidate(height_m=6.0, floors=2, family="mixed_use", massing=m, schema_version="0.2")
    res = resolve_theta(ctx, theta)
    
    assert len(res.masses) == 2
    front = next(m for m in res.masses if m.role == "front")
    rear = next(m for m in res.masses if m.role == "rear")
    
    front_poly = Polygon(front.footprint)
    rear_poly = Polygon(rear.footprint)
    
    # Invariant: front ∪ rear ≈ body
    body_expected = Polygon([(0, 3), (10, 3), (10, 20), (0, 20)])
    union = front_poly.union(rear_poly)
    assert union.equals(body_expected)
    
    # Invariant: intersection(front,rear).area ≈ 0
    assert front_poly.intersection(rear_poly).area < 1e-5
    
    # Shared boundary length > epsilon
    assert front_poly.intersection(rear_poly).length == pytest.approx(10.0)

