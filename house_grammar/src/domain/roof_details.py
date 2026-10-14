"""Independent roof form, covering, construction and edge treatment."""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class EaveDesign:
    kind: str = 'auto'  # auto | clean | closed | exposed | profiled | braces | curved | cornice
    overhang_m: float = .35
    spacing_m: float = .55
    beam_width_m: float = .08
    beam_height_m: float = .14
    fascia: bool = True
    soffit: bool = False
    material: str = 'wood'
    fascia_material: str = 'wood'
    gutter: bool = False


@dataclass(frozen=True)
class RoofDesign:
    form: str = 'gable'  # flat | shed | gable | hip | pavilion | band | compound
    covering: str = 'curved_tile'  # none | curved_tile | flat_tile | corrugated | panel | slats
    construction: str = 'solid'  # solid substrate | frame (open supporting structure)
    style: str = 'auto'
    slope_deg: float = 22.
    rotation_deg: float = 0.
    ridge_fraction: float = .5
    thickness_m: float = .14
    band_depth_m: float = 2.4
    tile_width_m: float = .22
    tile_length_m: float = .40
    overlap_m: float = .08
    detail: str = 'full'  # light | medium | full
    material: str = 'roof_tile'
    substrate_material: str = 'wood'
    eave: EaveDesign = field(default_factory=EaveDesign)
    parapet_m: float = 0.
    cap: str = 'none'  # none | flat | bevel | pitched | moulded | metal
    cap_material: str = 'stone'
    cap_drip: bool = False


@dataclass(frozen=True)
class RoofAssemblyControls:
    id: str
    mass_ref: str
    design: RoofDesign = field(default_factory=RoofDesign)
    # Optional local polygons for an orthogonal L/T compound, in world XY.
    regions: tuple[tuple[tuple[float,float],...],...] = ()
    crown_ref: str | None = None
    junction: str = 'none'  # none | behind | gable
    enabled: bool = True
    join_group: str | None = None  # connected roofs at one datum, common finish
    props_mode: str = 'preserve'  # preserve | auto | off


@dataclass(frozen=True)
class CanopyControls:
    id: str
    mass_ref: str
    edge: int
    u_m: float
    width_m: float
    depth_m: float
    height_m: float  # above mass base, low outer edge
    design: RoofDesign = field(default_factory=lambda: RoofDesign(form='shed',covering='panel'))
    opening_index: int | None = None
    posts: bool = False
