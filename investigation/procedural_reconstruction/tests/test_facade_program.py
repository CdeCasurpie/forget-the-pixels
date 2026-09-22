"""Bay rhythm, opening programme and the relief a family implies."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import numpy as np

from domain.architecture import BuildingProgram
from modeling.facade_program import (
    FAMILIES_BY_USE,
    FAMILY_RULES,
    MIN_BAY_M,
    bay_axes,
    compose_wall,
    resolve_family,
)

LEVELS = (0.0, 2.9, 5.7, 8.5)


def program_for(use="residential", language="auto", seed=7):
    return BuildingProgram(
        use=use,
        occupancy="medium",
        placement="flush",
        architectural_language=language,
        finish_profile="standard",
        maintenance="average",
        construction_state="completed",
        seed=seed,
    )


def compose(family="quiet_house", length=9.0, levels=LEVELS, seed=7, **kwargs):
    options = dict(
        is_front=True,
        family=family,
        program=program_for(),
        rng=np.random.default_rng(seed),
        band_height=levels[-1],
    )
    options.update(kwargs)
    return compose_wall(length, levels, **options)


class BayTests(unittest.TestCase):
    def test_axes_are_evenly_spaced_inside_the_wall(self):
        axes, pitch = bay_axes(12.0)
        self.assertGreater(len(axes), 1)
        gaps = np.diff(axes)
        self.assertTrue(np.allclose(gaps, pitch))
        self.assertGreater(axes[0], 0.0)
        self.assertLess(axes[-1], 12.0)

    def test_bay_width_stays_architecturally_plausible(self):
        for length in (3.0, 5.5, 9.0, 14.0, 22.0, 40.0):
            with self.subTest(length=length):
                axes, pitch = bay_axes(length)
                if axes:
                    self.assertGreaterEqual(pitch, MIN_BAY_M - 1e-9)
                    self.assertLessEqual(pitch, 4.3)

    def test_a_wall_too_narrow_for_a_bay_yields_nothing(self):
        self.assertEqual(bay_axes(1.5), ((), 0.0))
        composition = compose(length=1.6)
        self.assertEqual(composition.openings, ())
        self.assertIn("wall_too_narrow_for_a_bay", composition.dropped)


class AlignmentTests(unittest.TestCase):
    def test_openings_share_vertical_axes_across_floors(self):
        composition = compose(length=11.0)
        by_floor = {}
        for opening in composition.openings:
            floor = int(np.searchsorted(LEVELS, opening.v_m, side="right")) - 1
            centre = round(opening.u_m + opening.width_m / 2.0, 6)
            by_floor.setdefault(floor, set()).add(centre)
        upper = [axes for floor, axes in by_floor.items() if floor > 0]
        self.assertGreater(len(upper), 1)
        for axes in upper[1:]:
            self.assertEqual(axes, upper[0])

    def test_openings_stay_within_the_wall_and_never_overlap(self):
        for family in FAMILY_RULES:
            with self.subTest(family=family):
                composition = compose(family=family, length=10.0)
                spans = []
                for opening in composition.openings:
                    self.assertGreaterEqual(opening.u_m, 0.12)
                    self.assertLessEqual(opening.u_m + opening.width_m, 10.0 - 0.12)
                    self.assertGreater(opening.height_m, 0.0)
                    spans.append(
                        (opening.u_m, opening.u_m + opening.width_m,
                         opening.v_m, opening.v_m + opening.height_m)
                    )
                for first in range(len(spans)):
                    for second in range(first + 1, len(spans)):
                        u0, u1, v0, v1 = spans[first]
                        x0, x1, y0, y1 = spans[second]
                        overlap = min(u1, x1) - max(u0, x0) > 1e-6 and \
                            min(v1, y1) - max(v0, y0) > 1e-6
                        self.assertFalse(overlap, f"{family}: openings overlap")

    def test_the_same_seed_reproduces_the_same_wall(self):
        first, second = compose(seed=19), compose(seed=19)
        self.assertEqual(
            [(o.kind, o.u_m, o.v_m) for o in first.openings],
            [(o.kind, o.u_m, o.v_m) for o in second.openings],
        )


class ProgrammeTests(unittest.TestCase):
    def test_side_walls_and_upper_bands_get_no_street_programme(self):
        self.assertEqual(compose(is_front=False).openings, ())

    def test_a_shopfront_family_opens_the_ground_floor_to_the_street(self):
        composition = compose(family="mixed_use", length=11.0)
        ground = [o for o in composition.openings if o.v_m < LEVELS[1]]
        self.assertTrue(any(o.prefab == "storefront" for o in ground))
        kinds = {p.kind for p in composition.projections}
        self.assertIn("awning", kinds)
        self.assertIn("sign_box", kinds)

    def test_a_workshop_opens_a_vehicle_gate(self):
        composition = compose(family="workshop", length=11.0)
        self.assertTrue(
            any(o.kind == "gate" and o.prefab == "roller" for o in composition.openings)
        )

    def test_a_balcony_family_emits_matching_balcony_projections(self):
        composition = compose(family="balcony_apartments", length=11.0)
        balcony_windows = [o for o in composition.openings if o.kind == "balcony_window"]
        balconies = [p for p in composition.projections if p.kind == "balcony"]
        self.assertTrue(balcony_windows)
        self.assertEqual(len(balconies), len(balcony_windows))

    def test_a_republican_facade_carries_its_order(self):
        composition = compose(family="republicano", length=11.0)
        kinds = {p.kind for p in composition.projections}
        self.assertIn("pilaster", kinds)
        self.assertIn("cornice", kinds)
        self.assertIn("sill_band", kinds)
        self.assertIn("shutter", kinds)

    def test_relief_is_reported_rather_than_silently_dropped(self):
        composition = compose(length=9.0, levels=(0.0, 1.2, 2.4),
                              band_height=2.4)
        self.assertTrue(composition.dropped)

    def test_ground_finish_zones_reach_the_first_floor_only(self):
        composition = compose(family="brick_courtyard", length=10.0)
        regions = [r for r in composition.material_regions if r.v_m == 0.0]
        self.assertTrue(regions)
        self.assertEqual(regions[0].material_slot, "brick")
        self.assertLessEqual(regions[0].height_m, LEVELS[1] + 1e-9)


class FamilyTests(unittest.TestCase):
    def test_an_explicit_family_is_honoured(self):
        rng = np.random.default_rng(1)
        self.assertEqual(
            resolve_family(program_for(language="republicano"), rng), "republicano"
        )

    def test_an_unknown_language_draws_from_the_use(self):
        for use, pool in FAMILIES_BY_USE.items():
            with self.subTest(use=use):
                rng = np.random.default_rng(3)
                self.assertIn(resolve_family(program_for(use=use), rng), pool)

    def test_every_family_in_a_pool_has_rules(self):
        for pool in FAMILIES_BY_USE.values():
            for family in pool:
                self.assertIn(family, FAMILY_RULES)


if __name__ == "__main__":
    unittest.main()
