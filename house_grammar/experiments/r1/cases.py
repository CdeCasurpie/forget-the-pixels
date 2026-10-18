"""R1 reference cases: new masses dressed with real catalogue pieces.

Each case is a plain intent request, the same currency the planning stages
already speak. The placements are authored against the chart the planning
pipeline exposes, never against a legacy theta candidate.
"""
from __future__ import annotations

from domain.balconies import BalconyControls
from domain.crowns import CrownControls, CrownDesign
from domain.surfaces import SurfaceChart


def _request(floors, style, profile='barranco_residential', parcel=None, fronts=None,
             windows=2, organization='compact', seed=17):
    levels = [round(3.2 * index, 2) for index in range(floors + 1)]
    return {
        'version': 'intent-v1',
        'seed': seed,
        'context': {
            'parcel': parcel or [[0, 0], [10, 0], [10, 18], [0, 18]],
            'fronts': fronts or {'F1': 0},
            'levels_m': levels,
        },
        'building': {
            'profile': profile,
            'organization': organization,
            'style': style,
            'facades': [{'body': 'main', 'front': 'F1', 'floors': list(range(1, floors + 1)),
                         'windows': {'count': windows, 'proportion': 'vertical'}}],
        },
    }


CASES = (
    ('r1_republicano_two_floors', _request(2, 'republicano'), 'republicano'),
    ('r1_moderno_three_floors', _request(3, 'moderno'), 'moderno'),
    ('r1_clasico_two_floors', _request(2, 'clasico', profile='barranco_incremental'), 'clasico'),
    ('r1_barroco_three_floors', _request(3, 'barroco', profile='barranco_casona', windows=3), 'barroco'),
)

# A case is correct when the catalog emitted both a crown and a balcony body;
# the tokens are matched as substrings against the mesh semantics.
EXPECTED = ('crown_', 'balcony_')


def _front_stores(chart: SurfaceChart):
    """Front surfaces grouped by storey, ordered from the ground up."""
    fronts = [surface for surface in chart.surfaces if surface.facade.is_front]
    if not fronts:
        raise ValueError('case has no street-facing storey to dress')
    grouped = {}
    for surface in fronts:
        current = grouped.get(surface.mass_role)
        if current is None or surface.base_z > current.base_z:
            grouped[surface.mass_role] = surface
    return sorted(grouped.values(), key=lambda surface: surface.base_z)


def placements(chart: SurfaceChart, style: str):
    """Return the crown and balcony controls for one chart.

    The frontón crowns the top street storey (a wall-top crown, so it keeps its
    volume and its relation to the roof). The balcony projects from the storey
    below it when one exists, and from the top storey otherwise, always centred
    on its facade and never overlapping a reserved opening.
    """
    stores = _front_stores(chart)
    top = stores[-1]
    # The balcony projects from the lowest street storey above the ground, so a
    # two-storey house is not given a balcony standing on the sidewalk; a
    # single-storey body keeps it on its only front.
    above_ground = [surface for surface in stores if surface.base_z > 1e-6]
    below = above_ground[0] if above_ground else top

    crown_width = min(2.4, max(1.2, top.width_m * .40))
    crown = CrownControls(
        id='fronton', mass_ref=top.mass_role, edge=top.edge,
        u_m=max(0., (top.width_m - crown_width) / 2), width_m=crown_width, height_m=1.0,
        anchor='wall_top', base_m=0.,
        design=CrownDesign(family='triangular', style=style, thickness_m=.30,
                           projection_m=.18, moulding_width_m=.14,
                           material='plaster', moulding_material='cornice'))

    balcony_width = min(3.0, max(1.2, below.width_m * .35))
    balcony = BalconyControls(
        id='balcon', mass_ref=below.mass_role, edge=below.edge, floor_m=0.,
        u_m=max(0., (below.width_m - balcony_width) / 2), width_m=balcony_width,
        depth_m=.85, kind='projecting', style=style)

    return (crown,), (balcony,)
