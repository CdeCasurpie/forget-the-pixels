"""Shared design and placement contracts for pilasters and columns."""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class MemberDesign:
    style: str = 'moderno'
    variant: str = 'auto'
    section: str = 'auto'
    base: bool | None = None
    capital: bool | None = None
    collar: bool = True
    abacus: bool = True
    base_profile: str = 'auto'  # auto | attic | simple | minimal
    pedestal_m: float = 0.
    base_height_m: float | None = None
    capital_height_m: float | None = None
    taper: float | None = None
    entasis: float = .025
    turns: float = 1.5
    flute_count: int = 12
    ornament: bool = True
    detail: int = 2  # 1, 2, 3; physical proportions do not change
    material: str = 'plaster'
    base_material: str | None = None
    capital_material: str | None = None


@dataclass(frozen=True)
class VerticalMemberControls:
    id: str
    mass_ref: str
    edge: int
    u_m: float
    bottom_m: float
    height_m: float
    width_m: float = .45
    depth_m: float = .30
    placement: str = 'attached'  # attached | embedded | freestanding | corner
    offset_m: float = 0.
    embed_ratio: float = .5
    enabled: bool = True
    design: MemberDesign = field(default_factory=lambda: MemberDesign(style='auto'))
