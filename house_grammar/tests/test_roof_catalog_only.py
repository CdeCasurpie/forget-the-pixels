"""No public/basic entry point can silently emit a legacy covering."""
from dataclasses import replace
import json
from pathlib import Path

import numpy as np
import pytest
from shapely.geometry import box

from domain.architecture import RoofPlan, RoofSurface
from domain.theta import (ThetaCandidate, ReconstructionContext, MassingControls,
    MassComponent, PlanRegion, RoofControls, RoofOverride, RoofBody, from_json)
from modeling.mesh_builder import MeshBuilder
from modeling.roofscape import build_roof, plan_roof
from modeling.roof_planes import geometry
from modeling.theta import resolve_theta
from test_volumetric_crowns import request


@pytest.mark.parametrize('kind', ['tile_shed', 'gable', 'corrugated', 'shed'])
@pytest.mark.parametrize('entry', ['global', 'component', 'override', 'body'])
def test_legacy_rejected_at_every_theta_entry(kind, entry):
    p=ReconstructionContext(((0.,0.),(12.,0.),(12.,20.),(0.,20.)),(0,))
    component=MassComponent('house',PlanRegion(),(0.,3.,6.))
    t=ThetaCandidate(schema_version='0.3',massing=MassingControls(components=(component,)))
    controls=RoofControls(kind=kind)
    if entry=='global':t=replace(t,roof=controls)
    elif entry=='component':t=replace(t,massing=replace(t.massing,components=(replace(component,roof=controls),)))
    elif entry=='override':t=replace(t,roofs=(RoofOverride('house:0',kind=kind),))
    else:t=replace(t,roof_bodies=(RoofBody('upper','house',PlanRegion(u=(.2,.8),depth=(.2,.8)),roof=controls),))
    with pytest.raises(ValueError,match='roof_assemblies'):resolve_theta(p,t)


@pytest.mark.parametrize('kind', ['tile_shed','gable','corrugated','unknown'])
def test_low_level_emitter_rejects_legacy_even_without_theta(kind):
    poly=box(0,0,5,5)
    surface=RoofSurface(tuple(poly.exterior.coords),kind,3.)
    with pytest.raises(ValueError,match='catalog'):
        build_roof(MeshBuilder(poly),RoofPlan('house',(surface,),()),np.random.default_rng(1))


def test_crown_cut_does_not_reorient_or_move_roof_planes():
    data=request()
    data['theta']['roof_assemblies']=[dict(id='roof',mass_ref='house:0',
        design=dict(form='gable',rotation_deg=90))]
    req=from_json(json.dumps(data))
    full=resolve_theta(req.context,req.theta).roof_assemblies[0]
    data['theta']['roof_assemblies'][0].update(crown_ref='crown',junction='behind')
    req=from_json(json.dumps(data))
    cut=resolve_theta(req.context,req.theta).roof_assemblies[0]
    assert {f.plane for f in full.faces}=={f.plane for f in cut.faces}
    assert sum(geometry(f).area for f in cut.faces)<sum(geometry(f).area for f in full.faces)


def test_v4_explicit_old_roof_is_not_silently_flattened():
    from test_roofscape import mass_for, program_for, LOT, CONTEXT
    from domain.models import RoofSpecification
    from modeling.geometry_constraints import front_lines
    mass=replace(mass_for(),roof_spec=RoofSpecification(kind='gable'))
    with pytest.raises(ValueError,match='roof_assemblies'):
        plan_roof(mass,program_for(),LOT,front_lines(CONTEXT),LOT,1)


def test_flush_catalog_cover_and_real_overhang_have_distinct_validation():
    from domain.roof_details import RoofAssemblyControls, RoofDesign, EaveDesign
    p=ReconstructionContext(((0.,0.),(12.,0.),(12.,20.),(0.,20.)),(0,))
    a=RoofAssemblyControls('cover','house:0',design=RoofDesign(form='flat',covering='corrugated',
        eave=EaveDesign(kind='clean',overhang_m=0.,fascia=False)))
    t=ThetaCandidate(schema_version='0.3',massing=MassingControls(components=(
        MassComponent('house',PlanRegion(),(0.,3.)),)),roof_assemblies=(a,))
    assert resolve_theta(p,t).roof_assemblies
    a=replace(a,design=replace(a.design,eave=replace(a.design.eave,overhang_m=.2)))
    with pytest.raises(ValueError,match='envelope'):
        resolve_theta(p,replace(t,roof_assemblies=(a,)))


def test_corrugated_cover_on_cadastral_precision_boundary_generates():
    from domain.roof_details import RoofAssemblyControls, RoofDesign, EaveDesign
    from modeling.theta import generate_resolved
    from modeling.validation import validate_mesh
    from modeling.grammar import street_envelope
    from domain.architecture import ParcelContext
    from shapely.geometry import Polygon
    # Real oblique boundary: sub-grid differences used to create zero-length
    # cap loops in GEOS while clipping the corrugated catalog strips.
    p=ReconstructionContext(((25.106,2.154),(.683,0.),(.669,.154),(0.,7.394),(24.669,9.654)),(2,))
    a=RoofAssemblyControls('cover','house:0',design=RoofDesign(form='flat',covering='corrugated',
        rotation_deg=5.279328393121386,eave=EaveDesign(kind='clean',overhang_m=0.,fascia=False)))
    t=ThetaCandidate(schema_version='0.3',massing=MassingControls(components=(
        MassComponent('house',PlanRegion(front_edge=0,depth_m=(0.,8.5),width_reference='edge'),(0.,3.)),)),
        roof_assemblies=(a,))
    result=resolve_theta(p,t)
    mesh=generate_resolved(result)
    assert 'roof_corrugation' in {part['name'] for part in mesh.parts}
    env=street_envelope(ParcelContext(result.context.parcel,explicit_fronts=result.context.fronts))
    assert validate_mesh(mesh,Polygon(result.context.parcel),envelope=env)['envelope_test']=='passed'


CATALOG=Path(__file__).resolve().parents[1]/'steps/step23_fresh_theta/catalogo_techos'


@pytest.mark.parametrize('path',sorted(CATALOG.glob('*/request.json')),ids=lambda p:p.parent.name)
def test_catalog_requests_resolve(path):
    req=from_json(path.read_text())
    result=resolve_theta(req.context,req.theta)
    assert result.roofs
    assert all(s.kind=='flat' for roof in result.roofs for s in roof.surfaces)
