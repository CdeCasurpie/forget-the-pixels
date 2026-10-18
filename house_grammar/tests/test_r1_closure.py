"""R1 closure: the facade surface is the anchor, not a mass edge ring.

The R1 bridge placed catalogue pieces on a :class:`domain.surfaces.SurfaceChart`.
The first cut still read the footprint of the mass and filtered by ``mass.id``,
so a recessed plane, a hidden facade or the storey below were invisible to it.
These tests pin the corrected contract:

* a piece anchors to the built plane (``plane_offset_m``), never the cadastral
  line;
* a piece whose span falls on a hidden domain is rejected;
* storeys are separate bodies, so the storey below is a real neighbour;
* the building style is inherited, and a local exception is honored, not
  rejected;
* the palette the resolvers validate is the palette the builder paints;
* the pieces are the catalogue meshes, emitted by the catalogue assemblers.

They also exercise the chart on the geometry R1 never touched: a courtyard, a
setback storey, two contiguous bodies whose join is hidden, an irregular parcel,
and a partially shared floor edge on which a balcony may sit only where it is
exposed.
"""
from dataclasses import replace

import numpy as np
import pytest
from shapely.geometry import Polygon
from shapely.ops import unary_union

from domain.architecture import MassSpec
from domain.balconies import BalconyControls
from domain.crowns import CrownControls, CrownDesign
from domain.models import FacadeSpecification, Opening
from domain.surfaces import SurfaceChart, WallSurface
from modeling.balcony_resolver import _same_plane, resolve_balconies
from modeling.crown_resolver import resolve_crowns
from planning import catalogue as catalogue_module
from planning.catalogue import catalogue_materials, materialize
from planning.chart import permitted_envelope, surface_chart
from planning.envelope import plan_envelope

PARCEL = Polygon([(-6, -6), (16, -6), (16, 24), (-6, 24)])
MATERIALS = catalogue_materials()


# --- hand-built charts: precision over a full planning run -----------------

def _face(edge_id, a, b, normal, *, openings=(), height=3.0, is_front=True):
    width = float(np.linalg.norm(np.asarray(b, float) - np.asarray(a, float)))
    return FacadeSpecification(
        edge_id=edge_id, vertex_a=tuple(a), vertex_b=tuple(b), width_m=width,
        normal_xy=(float(normal[0]), float(normal[1])), floor_levels_m=(0., height),
        openings=tuple(openings), is_front=is_front, program_enabled=is_front)


def _wall(mass_role, base, height, facade, *, visible=(), offset=0.0, thickness=.18):
    return WallSurface(mass_role=mass_role, edge=0, base_z=base, height_m=height, axes_m=(),
                       facade=facade, visible_domains=tuple(visible), plane_offset_m=offset,
                       thickness_m=thickness)


def _scene(*, offset=0.0, visible=(), openings=(), height=3.0):
    """One 10x10 storey whose street edge spans ``(0,0) -> (10,0)``."""
    body = MassSpec(id='main', footprint=((0., 0.), (10., 0.), (10., 10.), (0., 10.)),
                    base_z=0., roof_z=height, floor_levels=(0., height), role='main',
                    roof_spec=None)
    facade = _face('main/edge0', (0., 0.), (10., 0.), (0., -1.), openings=openings,
                   height=height)
    surface = _wall('main', 0., height, facade, visible=visible, offset=offset)
    return SurfaceChart((body,), (surface,)), surface


def _stacked(lower_openings=()):
    """Two storeys stacked on the same plan, so the facades share one plane."""
    def body(mid, base, roof):
        return MassSpec(id=mid, footprint=((0., 0.), (10., 0.), (10., 10.), (0., 10.)),
                        base_z=base, roof_z=roof, floor_levels=(base, roof), role=mid,
                        roof_spec=None)

    def wall(mid, base, height, openings=()):
        facade = _face(f'{mid}/edge0', (0., 0.), (10., 0.), (0., -1.), openings=openings,
                       height=height)
        return _wall(mid, base, height, facade, visible=((0., 0., 10., height),))

    return SurfaceChart((body('low', 0., 3.), body('high', 3., 6.)),
                        (wall('low', 0., 3., lower_openings), wall('high', 3., 3.)))


def _balcony(**changes):
    base = dict(id='balcon', mass_ref='main', edge=0, floor_m=0., u_m=1., width_m=2.,
                depth_m=.85, kind='projecting', style='auto')
    return BalconyControls(**{**base, **changes})


def _crown(**changes):
    base = dict(id='fronton', mass_ref='main', edge=0, u_m=3., width_m=2., height_m=1.,
                anchor='wall_top', base_m=0.,
                design=CrownDesign(family='triangular', style='auto'))
    return CrownControls(**{**base, **changes})


# --- the anchor is the built plane -----------------------------------------

def test_balcony_anchors_to_the_built_plane_not_the_cadastral_line():
    chart, surface = _scene(offset=-.30)
    resolved = resolve_balconies((_balcony(),), 'republicano', chart, PARCEL, MATERIALS)[0]
    origin, tangent, normal = surface.frame()
    expected = np.asarray(origin) + np.asarray(tangent) * 1.
    assert np.allclose(np.asarray(resolved.origin), expected)
    cadastral = np.asarray(surface.facade.vertex_a) + np.asarray(tangent) * 1.
    assert not np.allclose(np.asarray(resolved.origin), cadastral)


def test_balcony_must_stay_on_an_exposed_domain():
    chart, _ = _scene(visible=((0., 0., 1.5, 3.),))
    with pytest.raises(ValueError, match='hidden facade'):
        resolve_balconies((_balcony(u_m=2., width_m=1.),), 'republicano', chart, PARCEL,
                          MATERIALS)
    chart, _ = _scene(visible=((0., 0., 1.5, 3.),))
    assert resolve_balconies((_balcony(u_m=.2, width_m=1.),), 'republicano', chart, PARCEL,
                             MATERIALS)


def test_an_ambiguous_facade_surface_is_rejected():
    chart, surface = _scene()
    doubled = SurfaceChart(chart.bodies, (*chart.surfaces, surface))
    with pytest.raises(ValueError, match='unambiguous facade surface'):
        resolve_balconies((_balcony(),), 'republicano', doubled, PARCEL, MATERIALS)


# --- storeys are separate bodies -------------------------------------------

def test_a_balcony_sees_the_opening_on_the_storey_below():
    tall = Opening(kind='window', u_m=1., v_m=1.6, width_m=1., height_m=1.3)
    chart = _stacked(lower_openings=(tall,))
    balcony = _balcony(mass_ref='high', u_m=1., width_m=1.)
    with pytest.raises(ValueError, match='intersects an opening'):
        resolve_balconies((balcony,), 'republicano', chart, PARCEL, MATERIALS)


def test_the_same_balcony_is_clean_without_the_lower_opening():
    chart = _stacked()
    balcony = _balcony(mass_ref='high', u_m=1., width_m=1.)
    assert resolve_balconies((balcony,), 'republicano', chart, PARCEL, MATERIALS)
    low, high = chart.surfaces
    assert _same_plane(high, low)


# --- style is inherited, a local exception is honored ----------------------

def test_auto_inherits_the_building_style():
    chart, _ = _scene()
    crown = resolve_crowns((_crown(),), 'republicano', chart, PARCEL, MATERIALS)[0]
    balcony = resolve_balconies((_balcony(),), 'republicano', chart, PARCEL, MATERIALS)[0]
    assert crown.controls.design.style == 'republicano'
    assert balcony.controls.style == 'republicano'


def test_a_local_style_replaces_the_building_style_without_rejection():
    chart, _ = _scene()
    crown = resolve_crowns((_crown(design=CrownDesign(family='triangular', style='barroco')),),
                           'republicano', chart, PARCEL, MATERIALS)[0]
    balcony = resolve_balconies((_balcony(style='moderno'),), 'republicano', chart, PARCEL,
                                MATERIALS)[0]
    assert crown.controls.design.style == 'barroco'
    assert balcony.controls.style == 'moderno'


# --- one palette, and the catalogue assemblers -----------------------------

def test_materialize_paints_the_palette_the_resolvers_validated():
    chart, _ = _scene()
    materials = catalogue_materials()
    materials['plaster'] = replace(materials['plaster'], base_color_rgb=(0.9, 0.1, 0.2))
    mesh, _, _ = materialize(chart, crowns=[_crown()], balconies=[_balcony()],
                             style='republicano', envelope=PARCEL, parcel=PARCEL,
                             materials=materials)
    painted = next(m for m in mesh.materials if m['name'] == 'plaster')
    assert painted['color'] == (0.9, 0.1, 0.2)


def test_pieces_go_through_the_catalogue_assemblers(monkeypatch):
    calls = {'crown': 0, 'balcony': 0}
    real_crown = catalogue_module.build_crown
    real_balcony = catalogue_module.build_balcony

    def spy_crown(builder, *args, **kwargs):
        calls['crown'] += 1
        return real_crown(builder, *args, **kwargs)

    def spy_balcony(builder, resolved, envelope):
        calls['balcony'] += 1
        assert resolved.controls.id == 'balcon'
        return real_balcony(builder, resolved, envelope)

    monkeypatch.setattr(catalogue_module, 'build_crown', spy_crown)
    monkeypatch.setattr(catalogue_module, 'build_balcony', spy_balcony)
    chart, _ = _scene()
    mesh, _, _ = materialize(chart, crowns=[_crown()], balconies=[_balcony()],
                             style='republicano', envelope=PARCEL, parcel=PARCEL)
    assert calls == {'crown': 1, 'balcony': 1}
    names = {part['name'] for part in mesh.parts}
    assert 'crown_body' in names
    assert any(name.startswith('balcony_platform') for name in names)


# --- the chart on geometry R1 never touched --------------------------------

BASE = {
    'version': 'intent-v1', 'seed': 17,
    'context': {'parcel': [[0, 0], [10, 0], [10, 18], [0, 18]], 'fronts': {'F1': 0},
                'levels_m': [0, 3.2, 6.]},
    'building': {'profile': 'barranco_residential', 'organization': 'compact',
                 'style': 'republicano',
                 'facades': [{'body': 'main', 'front': 'F1', 'floors': [1, 2],
                              'windows': {'count': 2, 'proportion': 'vertical'}}]},
}


def _request(**building):
    return {**BASE, 'building': {**BASE['building'], **building}}


def _op(kind, **changes):
    return {'id': kind, 'kind': kind, 'body': 'main', 'front': 'F1', **changes}


def _chart(request):
    plan = plan_envelope(request)
    return plan, surface_chart(plan), permitted_envelope(plan)


def test_chart_declares_the_built_wall_thickness():
    _, chart, _ = _chart(_request())
    assert chart.surfaces
    for surface in chart.surfaces:
        assert surface.thickness_m == pytest.approx(.18)


def test_chart_charts_a_courtyard_wall():
    _, chart, _ = _chart(_request(operations=[_op('courtyard')]))
    holed = [b for b in chart.bodies if b.footprint_holes]
    assert holed
    body = holed[0]
    inner = [s for s in chart.surfaces
             if s.mass_role == body.id and s.edge >= len(body.footprint)]
    assert len(inner) == len(body.footprint_holes[0])
    assert all(not s.facade.is_front for s in inner)
    assert all('/ring1/' in s.facade.edge_id for s in inner)


def test_chart_keeps_each_setback_storey_as_its_own_body():
    _, chart, _ = _chart(_request(operations=[_op('setback', floors=[2], position='right',
                                                  width='narrow')]))
    storeys = sorted(chart.bodies, key=lambda b: b.base_z)
    assert len(storeys) == 2
    assert Polygon(storeys[0].footprint).area > Polygon(storeys[1].footprint).area
    per_storey = {b.id: [s for s in chart.surfaces if s.mass_role == b.id] for b in storeys}
    assert all(per_storey.values())
    assert storeys[0].id != storeys[1].id


def test_chart_hides_the_join_between_contiguous_bodies():
    request = _request(bodies=[{'id': 'main'}, {'id': 'rear', 'position': 'rear',
                                                'width': 'narrow', 'floors': [1]}])
    _, chart, _ = _chart(request)
    assert {b.role for b in chart.bodies} >= {'main', 'rear'}
    # The two ground bodies touch: their shared edge is exposed on neither side,
    # so the chart never invents a facade there.
    ids = {s.facade.edge_id for s in chart.surfaces}
    assert 'main/floor1/ring0/edge2' not in ids
    assert 'rear/floor1/ring0/edge0' not in ids
    ground = [s for s in chart.surfaces if s.mass_role in ('main/floor1', 'rear/floor1')]
    union = unary_union([Polygon(chart.body(i).footprint)
                         for i in ('main/floor1', 'rear/floor1')])
    assert sum(s.width_m for s in ground) == pytest.approx(union.exterior.length)


def test_a_balcony_on_a_partially_shared_floor_edge_uses_the_exposed_part():
    # Body B covers x in [4, 10] of A's street edge, so [4, 10] is not a facade.
    def body(mid, a):
        return MassSpec(id=mid, footprint=a, base_z=0., roof_z=3., floor_levels=(0., 3.),
                        role=mid, roof_spec=None)
    a = body('a', ((0., 0.), (10., 0.), (10., 10.), (0., 10.)))
    b = body('b', ((4., 0.), (10., 0.), (10., 10.), (4., 10.)))
    facade = _face('a/edge0', (0., 0.), (10., 0.), (0., -1.))
    chart = SurfaceChart((a, b), (_wall('a', 0., 3., facade, visible=((0., 0., 4., 3.),)),))
    exposed = _balcony(mass_ref='a', u_m=1., width_m=1.)
    assert resolve_balconies((exposed,), 'republicano', chart, PARCEL, MATERIALS)
    hidden = _balcony(id='hidden', mass_ref='a', u_m=5., width_m=1.)
    with pytest.raises(ValueError, match='hidden facade'):
        resolve_balconies((hidden,), 'republicano', chart, PARCEL, MATERIALS)


def test_chart_is_stable_on_an_irregular_parcel():
    request = _request()
    request['context']['parcel'] = [[0, 0], [12, 3], [11, 18], [-1, 15]]
    _, chart, _ = _chart(request)
    assert chart.surfaces
    assert any(s.facade.is_front for s in chart.surfaces)
    for surface in chart.surfaces:
        body = chart.body(surface.mass_role)
        a = np.asarray(body.footprint[surface.edge], float)
        b = np.asarray(body.footprint[(surface.edge + 1) % len(body.footprint)], float)
        assert np.linalg.norm(b - a) == pytest.approx(surface.width_m)
        _, tangent, normal = surface.frame()
        assert float(tangent @ normal) == pytest.approx(0., abs=1e-9)
        assert float(normal @ normal) == pytest.approx(1.)


def test_an_irregular_parcel_still_takes_a_catalogue_piece():
    request = _request()
    request['context']['parcel'] = [[0, 0], [12, 3], [11, 18], [-1, 15]]
    plan, chart, envelope = _chart(request)
    fronts = sorted((s for s in chart.surfaces if s.facade.is_front), key=lambda s: s.base_z)
    top, below = fronts[-1], fronts[0]
    crown_width = min(2., top.width_m * .4)
    crown = CrownControls(id='fronton', mass_ref=top.mass_role, edge=top.edge,
                          u_m=max(0., (top.width_m - crown_width) / 2), width_m=crown_width,
                          height_m=1., anchor='wall_top', base_m=0.,
                          design=CrownDesign(family='triangular', style='republicano'))
    balcony_width = min(2., below.width_m * .35)
    balcony = BalconyControls(id='balcon', mass_ref=below.mass_role, edge=below.edge, floor_m=0.,
                              u_m=max(0., (below.width_m - balcony_width) / 2),
                              width_m=balcony_width, depth_m=.85, kind='projecting',
                              style='republicano')
    mesh, resolved_crowns, resolved_balconies = materialize(
        chart, crowns=(crown,), balconies=(balcony,), style='republicano',
        envelope=envelope, parcel=Polygon(request['context']['parcel']))
    assert resolved_crowns and resolved_balconies
    names = {part['name'] for part in mesh.parts}
    assert 'crown_body' in names
    assert any(name.startswith('balcony_platform') for name in names)
