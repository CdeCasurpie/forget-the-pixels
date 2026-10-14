"""Twenty-five designs, independent of placement and physical dimensions."""
from dataclasses import dataclass


@dataclass(frozen=True)
class MemberPreset:
    section: str
    shaft: str = 'plain'
    capital: str = 'moulded'
    base: bool = True
    taper: float = .04


CATALOG = {
    'republicano': {
        'smooth_moulded': MemberPreset('rectangle'),
        'recessed_panel': MemberPreset('rectangle','panel'),
        'restrained_fluted': MemberPreset('rectangle','fluted'),
        'rusticated': MemberPreset('rectangle','rusticated'),
        'portico_column': MemberPreset('circle',taper=.10),
    },
    'barroco': {
        'scroll_pilaster': MemberPreset('rectangle','panel','volutes'),
        'leaf_pilaster': MemberPreset('rectangle','plain','leaves'),
        'salomonic': MemberPreset('circle','twisted','composite'),
        'estipite': MemberPreset('rectangle','estipite','volutes'),
        'composite_column': MemberPreset('circle','fluted','composite'),
    },
    'clasico': {
        'tuscan': MemberPreset('circle',taper=.10),
        'doric': MemberPreset('circle','fluted','doric',False,.10),
        'ionic': MemberPreset('circle','fluted','volutes'),
        'corinthian': MemberPreset('circle','fluted','leaves'),
        'panel_pilaster': MemberPreset('rectangle','panel'),
    },
    'madera': {
        'chamfered_post': MemberPreset('chamfered','plain','none',False,0.),
        'turned_post': MemberPreset('circle','turned'),
        'octagonal_post': MemberPreset('octagon','plain','moulded',True,0.),
        'joinery_pilaster': MemberPreset('rectangle','panel'),
        'saddle_post': MemberPreset('chamfered','plain','saddle',False,0.),
    },
    'moderno': {
        'plain_prism': MemberPreset('rectangle','plain','none',False,0.),
        'plain_cylinder': MemberPreset('circle','plain','none',False,0.),
        'oval_column': MemberPreset('ellipse','plain','none',False,0.),
        'grooved_pilaster': MemberPreset('rectangle','fluted','none',False,0.),
        'tapered_column': MemberPreset('rounded','plain','none',False,.25),
    },
}
SECTIONS = frozenset(('rectangle','rounded','chamfered','octagon','circle','ellipse'))


def member_preset(design):
    if design.style not in CATALOG:raise ValueError('Unknown vertical member style')
    family=CATALOG[design.style]
    name=next(iter(family)) if design.variant=='auto' else design.variant
    if name not in family:raise ValueError('Vertical member variant does not belong to style')
    return name,family[name]
