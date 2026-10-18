"""Materialize catalogue pieces for the new planning pipeline.

This is the bridge R1 introduces: the planning stages produce a
:class:`domain.surfaces.SurfaceChart`, the catalog resolvers place the pieces on
it, and the catalog assemblers emit them into the same :class:`MeshBuilder` the
legacy pipeline uses. No piece is drawn twice and no alternative constructor is
written here: a crown is a crown mesh and a balcony is a balcony mesh.
"""
from domain import BuildingAppearance
from modeling.balcony_assembly import build_balcony
from modeling.balcony_resolver import resolve_balconies
from modeling.crown_assembly import aperture_shape, build_crown
from modeling.crown_resolver import resolve_crowns
from modeling.detail import DEFAULT_BUDGET
from modeling.materials import resolve_materials
from modeling.mesh_builder import MeshBuilder


def catalogue_materials(appearance=None, extra=()):
    """Material slots the catalogue accepts, keyed by slot name.

    The resolvers only test membership, so a mapping keeps the appearance
    usable for the builder while letting a caller add request-declared slots.
    """
    appearance = appearance or BuildingAppearance()
    materials = {m.slot: m for m in resolve_materials(appearance)}
    for slot in extra:
        if slot not in materials:
            raise ValueError(f'Unknown material slot: {slot}')
    return materials


def resolve_pieces(chart, *, crowns=(), balconies=(), style=None, envelope=None,
                   appearance=None, materials=None):
    """Place crowns and balconies on ``chart`` through the catalog resolvers."""
    materials = materials or catalogue_materials(appearance)
    resolved_crowns = (resolve_crowns(tuple(crowns), style, chart, envelope, materials)
                       if crowns else ())
    resolved_balconies = (resolve_balconies(tuple(balconies), style, chart, envelope, materials)
                          if balconies else ())
    return resolved_crowns, resolved_balconies


def build_pieces(builder, resolved_crowns=(), resolved_balconies=(), envelope=None):
    """Emit already-resolved pieces into ``builder`` (same calls as theta)."""
    for crown in resolved_crowns:
        c = crown.controls
        hole = aperture_shape(c.aperture, c.aperture_width_m, c.aperture_height_m,
                              c.aperture_sill_m, c.width_m / 2)
        with builder.assembly('crown/' + c.id):
            build_crown(builder, crown.origin, crown.tangent, crown.normal, c.u_m,
                        crown.base_z, c.width_m, c.height_m, c.design, hole)
    for balcony in resolved_balconies:
        build_balcony(builder, balcony, envelope)
    return builder


def materialize(chart, *, crowns=(), balconies=(), style=None, envelope=None, parcel=None,
                appearance=None, materials=None, budget=DEFAULT_BUDGET):
    """Resolve and build catalogue pieces; returns MeshData plus the placements."""
    appearance = appearance or BuildingAppearance()
    materials = materials or catalogue_materials(appearance)
    resolved_crowns, resolved_balconies = resolve_pieces(
        chart, crowns=crowns, balconies=balconies, style=style, envelope=envelope,
        appearance=appearance, materials=materials)
    builder = MeshBuilder(parcel, appearance, envelope=envelope, budget=budget)
    build_pieces(builder, resolved_crowns, resolved_balconies, envelope)
    return builder.finish(), resolved_crowns, resolved_balconies
