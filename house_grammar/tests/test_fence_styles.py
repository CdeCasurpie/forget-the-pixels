from types import SimpleNamespace
import pytest
import numpy as np
from modeling.fences import STYLES, build_fence
from dataclasses import replace
from shapely.geometry import box
from domain.theta import (
    ReconstructionContext, ThetaCandidate, MassingControls, FacadeControls,
    RoofControls, SiteControls, FenceRun,
)
from modeling.theta import resolve_theta, generate_resolved
from modeling.layout import propose_building
from modeling.grammar import generate_mesh
from test_site import context_for, program_for, plan_for
from modeling.boundaries import generate_boundaries


CONTEXT = ReconstructionContext(((0.,0.),(10.,0.),(10.,16.),(0.,16.)), (0,))
THETA = ThetaCandidate(
    height_m=3., floors=1, massing=MassingControls(front_setback_m=3.),
    facade=FacadeControls(mode='explicit', openings=()),
    roof=RoofControls(kind='flat', parapet_m=0., props=()),
)
LEGACY = ('reja', 'concreto', 'ladrillos', 'concreto_bajo', 'solid_wall',
          'wall', 'fence', 'unknown')


class Recorder:
    def __init__(self):self.parts=[]
    def box(self,*args,**kwargs):self.parts.append(args[-1])
    def beam(self,*args,**kwargs):self.parts.append(kwargs['semantic'])
    def panel(self,*args,**kwargs):self.parts.append(args[-1])


@pytest.mark.parametrize('style',STYLES)
@pytest.mark.parametrize('mode,height',[('low',1.1),('high',2.8)])
def test_access_leaves_use_style_and_open_mode(style,mode,height):
    b=SimpleNamespace(kind=style,height=height,height_mode=mode,wall_material='brick',
                      gate_u=1.,gate_width=1.1,garage_u=3.,garage_width=3.,
                      gate_mode='auto',garage_mode='auto',openness=.3,planters=False)
    r=Recorder()
    build_fence(r,np.array([0.,0.]),np.array([1.,0.]),np.array([0.,-1.]),8.,b)
    assert r.parts.count('gate_handle')==3
    if style in ('republicano','barroco'):
        assert 'gate_panel' not in r.parts
        assert ('fence_spear' in r.parts)==(mode=='high')
    b.gate_mode=b.garage_mode='open'
    r=Recorder()
    build_fence(r,np.array([0.,0.]),np.array([1.,0.]),np.array([0.,-1.]),8.,b)
    assert 'gate_handle' not in r.parts


@pytest.mark.parametrize('kind', LEGACY)
def test_non_catalog_fences_rejected_at_every_entry_point(kind):
    run = FenceRun(0, 0., 10., kind, 2.1)
    for site in (SiteControls(fence=kind), SiteControls(runs=(run,))):
        with pytest.raises(ValueError, match='fence catalog style'):
            resolve_theta(CONTEXT, replace(THETA, site=site))
    with pytest.raises(ValueError, match='fence catalog style'):
        generate_boundaries(context_for(), program_for(kind), plan_for())
    with pytest.raises(ValueError, match='fence catalog style'):
        propose_building(box(0, 0, 10, 16), boundary=kind)
    spec = propose_building(box(0, 0, 10, 16), boundary='open')
    with pytest.raises(ValueError, match='fence catalog style'):
        generate_mesh(replace(spec, setback=replace(spec.setback, boundary=kind)))
    recorder = Recorder()
    with pytest.raises(ValueError, match='fence catalog style'):
        build_fence(recorder, (0,0), (1,0), (0,-1), 8., SimpleNamespace(kind=kind))
    assert recorder.parts == []


@pytest.mark.parametrize('style', STYLES)
@pytest.mark.parametrize('mode,height', [('low', 1.1), ('high', 2.8)])
def test_theta_catalog_runs_keep_design_accesses_and_material(style, mode, height):
    run = FenceRun(0, .5, 9.5, style, height, height_mode=mode,
                   wall_material='stone', gate_u=1., gate_width=1.1,
                   garage_u=3., garage_width=3.)
    resolved = resolve_theta(CONTEXT, replace(THETA, site=SiteControls(runs=(run,))))
    boundary, = resolved.boundaries
    assert (boundary.kind, boundary.height_mode, boundary.wall_material) == (style, mode, 'stone')
    mesh = generate_resolved(resolved)
    parts = [p for p in mesh.parts if p['assembly_id'] == 'site/fence/0']
    names = [p['name'] for p in parts]
    assert names.count('gate_handle') == 3
    expected = dict(republicano='fence_ring', barroco='fence_scroll',
                    moderno='fence_louver', clasico='gate_panel', madera='gate_brace')
    assert expected[style] in names
    assert not {'pedestrian_gate', 'garage_door', 'gate_flute'} & set(names)
    masonry = [p for p in parts if p['name'] == 'boundary_base']
    if style != 'madera':
        stone = next(i for i, mat in enumerate(mesh.materials) if mat['name'] == 'stone')
        assert masonry and all(np.all(mesh.face_materials[p['face_start']:p['face_start']+p['face_count']] == stone)
                               for p in masonry)


@pytest.mark.parametrize('style', STYLES)
def test_automatic_theta_fences_use_catalog_and_preserve_party_wall_material(style):
    resolved = resolve_theta(CONTEXT, replace(THETA, site=SiteControls(fence=style)))
    street = [b for b in resolved.boundaries if b.is_street]
    party = [b for b in resolved.boundaries if not b.is_street]
    assert street and all(b.kind == style for b in street)
    assert party and all(b.kind == 'clasico' and b.wall_material == 'brick' for b in party)
    assert len(generate_resolved(resolved).faces) > 0


def test_none_does_not_fall_back_to_a_fence():
    assert generate_boundaries(context_for(), program_for('none'), plan_for()) == []
    assert resolve_theta(CONTEXT, replace(THETA, site=SiteControls(fence='none'))).boundaries == ()
