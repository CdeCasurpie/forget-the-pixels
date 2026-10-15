"""Authoring finishes is independent of orientation, family and geometry."""
import pytest
from domain.theta import (
    ReconstructionContext, ReconstructionRequest, ThetaCandidate, FacadeControls,
    MaterialControl, MassingControls, MassComponent, PlanRegion,
    FacadeMaterialRegion, from_json, canonical,
)
from modeling.theta import resolve_theta, generate_resolved


P=ReconstructionContext(((0.,0.),(10.,0.),(10.,12.),(0.,12.)),(0,))


@pytest.mark.parametrize('side', ['plaster','brick','concrete'])
def test_sides_use_the_selected_finish_even_with_components(side):
    t=ThetaCandidate(schema_version='0.3', side_material=side, massing=MassingControls(components=(
        MassComponent(id='house',region=PlanRegion(depth_m=(0.,10.)),levels_m=(0.,3.,6.)),)))
    r=resolve_theta(P,t)
    assert all(w.facade.wall_material==('plaster' if w.facade.is_front else side) for w in r.walls)


def test_custom_paint_slots_and_uniform_facade_material_roundtrip():
    t=ThetaCandidate(height_m=6.,floors=2,side_material='white_wall',
        materials=(MaterialControl('white_wall','plaster',(.92,.91,.88)),
                   MaterialControl('ochre_wall','plaster',(.8,.55,.12))),
        facade=FacadeControls(mode='explicit',openings=(),wall_material='ochre_wall',
            material_regions=(FacadeMaterialRegion(0.,0.,10.,3.,'white_wall'),)))
    req=from_json(canonical(ReconstructionRequest(P,t)))
    r=resolve_theta(req.context,req.theta)
    assert next(w for w in r.walls if w.facade.is_front).facade.wall_material=='ochre_wall'
    mesh=generate_resolved(r)
    assert not any(p['name']=='material_coating' for p in mesh.parts)
    slots={m['name']:m for m in mesh.materials}
    assert slots['white_wall']['texture_set']==slots['ochre_wall']['texture_set']=='stucco_smooth'
    assert slots['white_wall']['color']==(.92,.91,.88)
    assert slots['ochre_wall']['color']==(.8,.55,.12)


def test_family_does_not_silently_paint_ground_floor():
    r=resolve_theta(P,ThetaCandidate(height_m=6.,floors=2,family='republicano'))
    assert all(not w.facade.material_regions for w in r.walls)


@pytest.mark.parametrize('kwargs', [dict(wall_material='missing'),
    dict(material_regions=(FacadeMaterialRegion(0.,0.,1.,1.,'missing'),)),
    dict(material_regions=(FacadeMaterialRegion(float('nan'),0.,1.,1.,'plaster'),))])
def test_invalid_material_input_rejected_by_resolver(kwargs):
    with pytest.raises(ValueError):
        resolve_theta(P,ThetaCandidate(facade=FacadeControls(mode='explicit',openings=(),**kwargs)))
