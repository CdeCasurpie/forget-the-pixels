"""Volumetric crowns: geometry classification is independent of style."""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class CrownDesign:
    family: str = 'auto'
    style: str = 'auto'
    silhouette: str = 'angular'  # angular | curved | pointed | mixed
    stepped: bool = False
    concave_shoulders: bool = False
    central_block: bool = False
    open_center: bool = False
    thickness_m: float = .30
    recess_m: float = .055
    moulding_width_m: float = .16
    projection_m: float = .16
    base: bool = True
    ornament: str = 'none'  # none | keystone | cartouche | volutes | dentils
    material: str = 'plaster'
    moulding_material: str = 'cornice'
    field_material: str | None = None
    detail: int = 2


@dataclass(frozen=True)
class CrownControls:
    id: str
    mass_ref: str
    edge: int
    u_m: float
    width_m: float
    height_m: float
    design: CrownDesign = field(default_factory=CrownDesign)
    anchor: str = 'wall_top'  # wall_top | opening_top | facade
    opening_index: int | None = None
    base_m: float = 0.  # facade: from mass base; otherwise offset from anchor
    enabled: bool = True
    aperture: str = 'none'  # none | oculus | roundhead | pointed
    aperture_width_m: float = .55
    aperture_height_m: float = .7
    aperture_sill_m: float = .3


@dataclass(frozen=True)
class EntablatureControls:
    id: str
    mass_refs: tuple[str,...] = ()  # empty = all enclosed masses
    anchor: str = 'wall_top'  # wall_top | absolute
    top_m: float = 0.  # absolute top or offset from wall top
    height_m: float = .55
    projection_m: float = .18
    style: str = 'auto'
    material: str = 'cornice'
    frieze_material: str = 'plaster'
    scope: str = 'street'  # street | exposed
    ornament: str = 'none'  # none | dentils
    enabled: bool = True
