"""R1: the new masses are dressed by the existing catalogue, on a shared chart.

These are capability tests. They drive the planning stages and the catalogue
only; they never read a historical theta sample, so a regression in the old
serialized pipeline cannot make them pass or fail.
"""
import pytest
import numpy as np
from shapely.geometry import LineString, Polygon, shape

from domain.balconies import BalconyControls
from domain.crowns import CrownControls, CrownDesign
from domain.surfaces import SurfaceChart, WallSurface
from modeling.crown_resolver import resolve_crowns
from modeling.balcony_resolver import resolve_balconies
from planning.catalogue import catalogue_materials, materialize, resolve_pieces
from planning.chart import permitted_envelope, surface_chart
from planning.envelope import plan_envelope

REQUEST = {
    'version': 'intent-v1', 'seed': 17,
    'context': {'parcel': [[0, 0], [10, 0], [10, 18], [0, 18]], 'fronts': {'F1': 0},
                'levels_m': [0, 3.2, 6]},
    'building': {'profile': 'barranco_residential', 'organization': 'compact', 'style': 'republicano',
                 'facades': [{'body': 'main', 'front': 'F1', 'floors': [1, 2],
                              'windows': {'count': 2, 'proportion': 'vertical'}}]},
}


def build():
    plan = plan_envelope(REQUEST, interiors=True)
    chart = surface_chart(plan)
    envelope = permitted_envelope(plan)
    parcel = Polygon(REQUEST['context']['parcel'])
    return plan, chart, envelope, parcel


def front_surfaces(chart):
    return sorted((w for w in chart.surfaces if w.facade.is_front), key=lambda w: w.base_z)


def controls(chart):
    fronts = front_surfaces(chart)
    top = fronts[-1]
    below = fronts[0] if fronts[0].base_z > 1e-6 else (fronts[1] if len(fronts) > 1 else top)
    width = min(2.4, top.width_m * .4)
    crown = CrownControls(id='fronton', mass_ref=top.mass_role, edge=top.edge,
                          u_m=(top.width_m - width) / 2, width_m=width, height_m=1.0,
                          anchor='wall_top', base_m=0.,
                          design=CrownDesign(family='triangular', style='republicano',
                                             material='plaster', moulding_material='cornice'))
    balcony_width = min(3.0, below.width_m * .35)
    balcony = BalconyControls(id='balcon', mass_ref=below.mass_role, edge=below.edge, floor_m=0.,
                              u_m=(below.width_m - balcony_width) / 2, width_m=balcony_width,
                              depth_m=.85, kind='projecting', style='republicano')
    return crown, balcony


def semantics(mesh):
    return sorted({part['name'] for part in mesh.parts})


# --- the contract ---------------------------------------------------------

def test_chart_exposes_one_body_per_storey_with_its_silhouette():
    plan, chart, _, _ = build()
    storeys = plan.to_dict()['interior']['massing']['storeys']
    assert {body.id for body in chart.bodies} == {storey['id'] for storey in storeys}
    for body in chart.bodies:
        storey = next(s for s in storeys if s['id'] == body.id)
        assert Polygon(body.footprint).area == pytest.approx(shape(storey['geometry']).area)
        assert body.base_z == pytest.approx(storey['bottom_m'])
        assert body.roof_z == pytest.approx(storey['top_m'])


def test_chart_surfaces_carry_a_local_frame_and_mapped_openings():
    _, chart, _, _ = build()
    fronts = front_surfaces(chart)
    assert fronts
    for surface in fronts:
        assert isinstance(surface, WallSurface)
        origin, tangent, normal = surface.frame()
        assert abs(float((normal @ normal))) == pytest.approx(1.0)
        assert float(tangent @ normal) == pytest.approx(0.0, abs=1e-9)
        for opening in surface.facade.openings:
            assert 0. <= opening.u_m
            assert opening.u_m + opening.width_m <= surface.width_m + 1e-6
            assert 0. <= opening.v_m < surface.height_m


def test_chart_edge_index_names_the_same_edge_as_the_body_footprint():
    _, chart, _, _ = build()
    for surface in chart.surfaces:
        body = chart.body(surface.mass_role)
        a = body.footprint[surface.edge]
        b = body.footprint[(surface.edge + 1) % len(body.footprint)]
        assert LineString([a, b]).length == pytest.approx(surface.width_m)


# --- the resolvers consume the chart, not theta ---------------------------

def test_resolvers_take_a_chart_and_return_catalogue_placements():
    _, chart, envelope, _ = build()
    crown, balcony = controls(chart)
    materials = catalogue_materials()
    crowns = resolve_crowns((crown,), 'republicano', chart, envelope, materials)
    balconies = resolve_balconies((balcony,), 'republicano', chart, envelope, materials)
    assert [c.controls.id for c in crowns] == ['fronton']
    assert [b.controls.id for b in balconies] == ['balcon']
    top = front_surfaces(chart)[-1]
    assert crowns[0].base_z == pytest.approx(top.base_z + top.height_m)
    assert balconies[0].floor_z > 0


def test_a_placement_on_a_missing_body_is_rejected():
    _, chart, envelope, _ = build()
    crown, _ = controls(chart)
    with pytest.raises(ValueError):
        resolve_pieces(chart, crowns=[CrownControls(**{**crown.__dict__, 'mass_ref': 'ghost'})],
                       style='republicano', envelope=envelope)


# --- real catalogue pieces, not alternative constructors ------------------

def test_fronton_and_balcony_are_the_catalogue_meshes():
    _, chart, envelope, parcel = build()
    crown, balcony = controls(chart)
    mesh, crowns, balconies = materialize(chart, crowns=[crown], balconies=[balcony],
                                          style='republicano', envelope=envelope, parcel=parcel)
    found = semantics(mesh)
    assert any(name == 'crown_body' for name in found)
    assert any(name == 'crown_moulding' for name in found)
    assert any(name.startswith('balcony_platform') for name in found)
    assert any(name.startswith('balcony_handrail') for name in found)


def test_no_placement_emits_no_piece():
    _, chart, envelope, parcel = build()
    mesh, crowns, balconies = materialize(chart, style='republicano', envelope=envelope, parcel=parcel)
    assert not crowns and not balconies
    assert semantics(mesh) == []


def test_placement_is_read_from_the_chart_geometry():
    """Moving the crown along the facade moves the emitted origin; the massing
    body itself never moves."""
    _, chart, envelope, _ = build()
    crown, _ = controls(chart)
    top = front_surfaces(chart)[-1]
    body_before = Polygon(chart.body(top.mass_role).footprint).area
    origin, tangent, normal = top.frame()
    before = resolve_crowns((crown,), 'republicano', chart, envelope, catalogue_materials())[0]
    moved = CrownControls(**{**crown.__dict__, 'u_m': crown.u_m + .5})
    after = resolve_crowns((moved,), 'republicano', chart, envelope, catalogue_materials())[0]
    before_world = np.asarray(before.origin) + np.asarray(before.tangent) * before.controls.u_m
    after_world = np.asarray(after.origin) + np.asarray(after.tangent) * after.controls.u_m
    delta = after_world - before_world
    assert float(delta @ tangent) == pytest.approx(.5)
    assert float(delta @ normal) == pytest.approx(0.0, abs=1e-9)
    assert after_world == pytest.approx(tuple(top.local_point(moved.u_m, after.base_z)[:2]))
    assert Polygon(chart.body(top.mass_role).footprint).area == pytest.approx(body_before)
