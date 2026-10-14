"""Metric access assemblies anchored to an existing doorway."""
from dataclasses import dataclass


@dataclass(frozen=True)
class EntranceControls:
    id: str
    mass_ref: str
    edge: int
    opening_index: int
    kind: str = 'steps'  # steps | ramp | passage
    ground_z_m: float = 0.
    width_m: float = 0.  # zero inherits doorway width
    landing_m: float = .9
    tread_m: float = .30
    max_riser_m: float = .18
    run_m: float = 3.
    transition_m: float = .4
    nosing_m: float = .025
    slab_m: float = .12
    cheek_height_m: float = 0.
    side_width_m: float = .12
    material: str = 'stone'
    side_material: str = 'plaster'
