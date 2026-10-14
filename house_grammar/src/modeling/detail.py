"""How much geometry a building is allowed to spend, by viewing distance.

Every repeated element is a cylinder or a box of its own — a balustrade bar costs
32 triangles, a course of mortar costs 12 — so a block of twenty lots at
close-up detail runs to hundreds of thousands of triangles for relief that is
sub-pixel at that distance. The budget scales the repeats without removing any
architectural element, so the silhouette and the composition never change.
"""

from __future__ import annotations

from dataclasses import dataclass

BLOCK = 1  # whole cuadra on a map
STREET = 2  # walking past
CLOSE_UP = 3  # single building, inspected

_LEVELS = (BLOCK, STREET, CLOSE_UP)


@dataclass(frozen=True)
class DetailBudget:
    level: int = STREET

    def __post_init__(self):
        if self.level not in _LEVELS:
            raise ValueError(f"Detail level must be one of {_LEVELS}")

    def _pick(self, block, street, close_up):
        return {BLOCK: block, STREET: street, CLOSE_UP: close_up}[self.level]

    @property
    def balustrade_spacing_m(self) -> float:
        return self._pick(0.65, 0.22, 0.10)

    @property
    def fence_bar_spacing_m(self) -> float:
        return self._pick(0.55, 0.22, 0.12)

    @property
    def roof_prop_density(self) -> float:
        return self._pick(0.06, 0.16, 0.22)

    @property
    def roof_prop_limit(self) -> int:
        return self._pick(5, 14, 20)

    @property
    def grille_spacing_m(self) -> float:
        return self._pick(0.50, 0.22, 0.11)

    @property
    def curtain_fold_m(self) -> float:
        return self._pick(0.30, 0.25, 0.045)

    @property
    def shutter_pitch_m(self) -> float:
        return self._pick(0.30, 0.16, 0.085)

    def emits(self, semantic: str) -> bool:
        """Microgeometry only; never reject a shell, opening or major prop."""
        return self.level != BLOCK or semantic not in {
            'curtain_fold', 'shutter_slat', 'sign_letter', 'door_flute',
            'gate_flute', 'garage_slat', 'gate_seam', 'roller_slat',
            'louver_slat', 'door_raised_panel', 'condenser_louver',
            'hvac_louver', 'corrugation', 'mortar', 'cladding_joint',
            'downpipe_clamp', 'grille_diamond', 'balcony_ornament', 'tank_rib',
        }

    @property
    def cladding_joint_m(self) -> float:
        return self._pick(0.72, 0.24, 0.24)

    @property
    def wants_curtains(self) -> bool:
        return self.level >= STREET

    @property
    def wants_mortar_courses(self) -> bool:
        return self.level >= CLOSE_UP

    @property
    def wants_shutters(self) -> bool:
        return self.level >= STREET

    @property
    def wants_sill_bands(self) -> bool:
        return self.level >= STREET

    @property
    def wants_lettering(self) -> bool:
        return self.level >= STREET


DEFAULT_BUDGET = DetailBudget()
