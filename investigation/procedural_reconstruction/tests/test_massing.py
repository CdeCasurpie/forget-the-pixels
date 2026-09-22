"""Volumetric massing: patterns, degeneracy guards and exposure compatibility."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import numpy as np
from shapely.affinity import rotate
from shapely.geometry import Polygon, box

from domain.architecture import BuildingProgram, ParcelContext, SitePlan
from modeling.exposure import calculate_mass_exposures
from modeling.massing import (
    PATTERNS,
    floor_ladder,
    generate_masses,
    lot_depth,
    usable,
)


def context_for(polygon, fronts=(0,)):
    return ParcelContext(
        polygon=tuple((float(x), float(y)) for x, y in polygon.exterior.coords),
        explicit_fronts=tuple(fronts),
    )


def program_for(use="residential", corner=False, seed=7, setback=0.0):
    return BuildingProgram(
        use=use,
        occupancy="medium",
        placement="front_setback" if setback else "flush",
        architectural_language="informal",
        finish_profile="standard",
        maintenance="average",
        construction_state="completed",
        seed=seed,
        front_setback=setback,
        is_corner=corner,
    )


# Written out rather than built with box(), whose first edge is the east side:
# edge 0 must be the street front for these fixtures to mean anything.
DEEP = Polygon([(-5, -14), (5, -14), (5, 14), (-5, 14)])
SMALL = Polygon([(-4, -5), (4, -5), (4, 5), (-4, 5)])


class MassingTests(unittest.TestCase):
    def test_every_pattern_produces_valid_volumes_inside_the_lot(self):
        from modeling.geometry_constraints import CADASTRAL_GRID_M, parcel_polygon

        parcel = parcel_polygon(context_for(DEEP)).buffer(CADASTRAL_GRID_M)
        for pattern in PATTERNS:
            with self.subTest(pattern=pattern):
                masses = generate_masses(
                    context_for(DEEP),
                    program_for(use="mixed", corner=True),
                    14.0,
                    2.8,
                    pattern=pattern,
                    allow_rooftop_addition=False,
                )
                self.assertGreaterEqual(len(masses), 1)
                for mass in masses:
                    footprint = Polygon(mass.footprint)
                    self.assertTrue(usable(footprint))
                    self.assertLess(footprint.difference(parcel).area, 1e-9)
                    self.assertGreater(mass.roof_z, mass.base_z)

    def test_patterns_that_do_not_fit_degrade_to_a_single_block(self):
        masses = generate_masses(
            context_for(SMALL),
            program_for(),
            2.8,
            2.8,
            pattern="podium_tower",
            allow_rooftop_addition=False,
        )
        self.assertEqual(len(masses), 1)
        self.assertEqual(masses[0].role, "main")

    def test_volumes_never_overlap_in_both_plan_and_height(self):
        for seed in (1, 7, 23, 41, 99):
            with self.subTest(seed=seed):
                masses = generate_masses(
                    context_for(DEEP), program_for(seed=seed, corner=True), 14.0, 2.8
                )
                for first in range(len(masses)):
                    for second in range(first + 1, len(masses)):
                        a, b = masses[first], masses[second]
                        z_overlap = min(a.roof_z, b.roof_z) - max(a.base_z, b.base_z)
                        if z_overlap <= 1e-6:
                            continue
                        shared = Polygon(a.footprint).intersection(Polygon(b.footprint))
                        self.assertLess(
                            shared.area, 1e-6, f"{a.id} and {b.id} interpenetrate"
                        )

    def test_exposure_accepts_generated_masses(self):
        masses = generate_masses(
            context_for(DEEP), program_for(use="mixed"), 14.0, 2.8, pattern="podium_tower"
        )
        plan = SitePlan(
            masses=masses,
            free_space=(),
            access_nodes=(),
            boundaries=(),
            exclusion_zones=(),
        )
        exposures = calculate_mass_exposures(plan)
        self.assertEqual(set(exposures), {mass.id for mass in masses})
        for mass in masses:
            self.assertTrue(exposures[mass.id]["walls"])

    def test_same_seed_gives_the_same_volumes(self):
        first = generate_masses(context_for(DEEP), program_for(seed=5), 11.2, 2.8)
        second = generate_masses(context_for(DEEP), program_for(seed=5), 11.2, 2.8)
        self.assertEqual(
            [(m.id, m.footprint, m.roof_z) for m in first],
            [(m.id, m.footprint, m.roof_z) for m in second],
        )

    def test_rotated_lots_are_handled(self):
        from modeling.geometry_constraints import CADASTRAL_GRID_M, parcel_polygon

        rotated = rotate(DEEP, 37, origin=(0, 0))
        context = context_for(rotated)
        masses = generate_masses(context, program_for(), 11.2, 2.8)
        # Snapping to the cadastral grid can move a vertex half a grid step, so
        # containment holds to the grid, not to floating-point exactness.
        limit = parcel_polygon(context).buffer(CADASTRAL_GRID_M)
        for mass in masses:
            self.assertLess(Polygon(mass.footprint).difference(limit).area, 1e-9)

    def test_front_setback_carves_a_garden_before_the_pattern_applies(self):
        flush = generate_masses(
            context_for(DEEP), program_for(), 8.4, 2.8, pattern="single_block"
        )
        setback = generate_masses(
            context_for(DEEP),
            program_for(setback=3.0),
            8.4,
            2.8,
            pattern="single_block",
        )
        self.assertLess(
            Polygon(setback[0].footprint).area, Polygon(flush[0].footprint).area - 20.0
        )

    def test_rejects_impossible_inputs(self):
        for height, floor_h in ((0.0, 2.8), (float("nan"), 2.8), (8.4, 0.0)):
            with self.subTest(height=height, floor_h=floor_h):
                with self.assertRaises(ValueError):
                    generate_masses(context_for(DEEP), program_for(), height, floor_h)
        with self.assertRaises(ValueError):
            generate_masses(context_for(DEEP), program_for(), 8.4, 2.8, pattern="nope")


class HelperTests(unittest.TestCase):
    def test_floor_ladder_spans_the_volume_exactly(self):
        levels = floor_ladder(3.0, 11.4, 2.8)
        self.assertEqual(levels[0], 3.0)
        self.assertEqual(levels[-1], 11.4)
        self.assertEqual(len(levels), 4)
        steps = np.diff(levels)
        self.assertTrue(np.allclose(steps, steps[0]))

    def test_lot_depth_measures_from_the_street(self):
        from modeling.geometry_constraints import front_lines

        context = context_for(DEEP)
        self.assertAlmostEqual(lot_depth(DEEP, front_lines(context)), 28.0, places=6)

    def test_usable_rejects_slivers_and_crumbs(self):
        self.assertTrue(usable(box(0, 0, 4, 4)))
        self.assertFalse(usable(box(0, 0, 0.5, 0.5)))
        self.assertFalse(usable(box(0, 0, 40, 0.2)))
        self.assertFalse(usable(None))


if __name__ == "__main__":
    unittest.main()
