from dataclasses import replace
import pytest
from domain.theta import RoofBody, RoofControls, PlanRegion, ThetaCandidate, MassingControls
from modeling.top_composition import expand_roof_bodies
from test_facade_zones import body, P
from modeling.theta import resolve_theta, generate_resolved
from domain.roof_details import RoofAssemblyControls, RoofDesign


def request():
    return ThetaCandidate(schema_version='0.3',massing=MassingControls(components=(body(),)),
        roof_bodies=(RoofBody('upper','body',PlanRegion(u=(.2,.8),depth=(.2,.8)),
                              roof=RoofControls(kind='flat',parapet_m=0.)),),
        roof_assemblies=(RoofAssemblyControls('upper_roof','upper:0',design=RoofDesign(form='gable',slope_deg=25.)),))


def test_roof_body_anchor():
    t=request()
    t=replace(t,roof_bodies=(replace(t.roof_bodies[0],parent=t.massing.components[0].id),))
    expanded=expand_roof_bodies(t)
    assert expanded.massing.components[-1].levels_m==(6.,8.4)
    result=resolve_theta(P,t)
    assert len(result.masses)==2
    assert result.roof_assemblies[0].mass_ref=='upper:0'
    assert len(generate_resolved(result).faces)>0


def test_empty_preserved():
    t=ThetaCandidate()
    assert expand_roof_bodies(t) is t


def test_invalid_parent():
    with pytest.raises(ValueError):expand_roof_bodies(replace(request(),roof_bodies=(RoofBody('u','missing',PlanRegion()),)))
