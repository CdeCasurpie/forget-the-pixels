"""Opt-in balconies and reusable railings, in an existing mass-edge chart."""
from dataclasses import dataclass, field
from domain.vertical_members import MemberDesign


@dataclass(frozen=True)
class RailingControls:
    enabled: bool = True
    pattern: str = 'auto'
    height_m: float = 1.05
    spacing_m: float = .14
    post_spacing_m: float = 1.6
    post_width_m: float = .075
    handrail: bool = True
    material: str = 'auto'
    glass_material: str = 'glass'


@dataclass(frozen=True)
class BalconyControls:
    id: str
    mass_ref: str
    edge: int
    floor_m: float  # relative to mass base, at a floor/roof level
    u_m: float
    width_m: float
    enabled: bool = True
    style: str = 'auto'
    variant: str = 'auto'
    kind: str = 'projecting'  # projecting | terrace | juliet | gallery | box | stair
    depth_m: float = .85
    slab: bool = True
    slab_m: float = .18
    slab_material: str = 'plaster'
    brackets: bool = False
    cover: bool = False
    enclosure_height_m: float = 2.5
    railing: RailingControls = field(default_factory=RailingControls)
    sides: tuple[str, ...] = ('left','front','right')
    # Optional local (u, outward depth, vertical delta) railing route. Stair
    # routes refer to existing stair geometry, never synthesize stair slabs.
    path: tuple[tuple[float,float,float], ...] = ()
    curved_front_m: float = 0.
    corner_return_m: float = 0.  # wrap the following orthogonal mass edge
    planters: bool = False
    fascia: bool = True
    opening_index: int | None = None  # anchors the centre, not a new opening
    support_mass: str | None = None  # existing floor/roof for terrace/stair rail
    stair_index: int | None = None  # kind=stair: derive routes from existing stair
    column_member: MemberDesign | None = None
