"""Detail budget: fewer repeats at distance, same building."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import numpy as np
from shapely.geometry import Polygon

from domain.architecture import BuildingProgram, ParcelContext, SitePlan
from modeling.detail import BLOCK, CLOSE_UP, STREET, DetailBudget
from modeling.grammar import generate_v4_mesh
from modeling.massing import generate_masses

LOT = Polygon([(-6, -11), (6, -11), (6, 11), (-6, 11)])


def spec_for(seed=7, family="balcony_apartments"):
    context = ParcelContext(
        polygon=tuple((float(x), float(y)) for x, y in LOT.exterior.coords),
        explicit_fronts=(0,),
    )
    program = BuildingProgram(
        use="residential",
        occupancy="medium",
        placement="flush",
        architectural_language=family,
        finish_profile="standard",
        maintenance="average",
        construction_state="completed",
        seed=seed,
        has_fence=False,
        fence_type="none",
    )
    masses = generate_masses(context, program, 14.0, 2.8, pattern="single_block",
                             allow_rooftop_addition=False)
    return BuildingSpec(context, program, masses, seed)


def BuildingSpec(context, program, masses, seed):
    from domain.architecture import BuildingSpecificationV4

    return BuildingSpecificationV4(
        context=context,
        program=program,
        site_plan=SitePlan(masses=masses, free_space=(), access_nodes=(),
                           boundaries=(), exclusion_zones=()),
        facades=(),
        components=(),
        seed=seed,
    )


class BudgetTests(unittest.TestCase):
    def test_levels_are_ordered_from_coarse_to_fine(self):
        coarse, near = DetailBudget(BLOCK), DetailBudget(CLOSE_UP)
        self.assertGreater(coarse.balustrade_spacing_m, near.balustrade_spacing_m)
        self.assertGreater(coarse.fence_bar_spacing_m, near.fence_bar_spacing_m)
        self.assertGreater(coarse.grille_spacing_m, near.grille_spacing_m)
        self.assertLess(coarse.roof_prop_density, near.roof_prop_density)
        self.assertLess(coarse.roof_prop_limit, near.roof_prop_limit)

    def test_optional_detail_switches_off_at_distance(self):
        self.assertFalse(DetailBudget(BLOCK).wants_mortar_courses)
        self.assertFalse(DetailBudget(BLOCK).wants_shutters)
        self.assertFalse(DetailBudget(BLOCK).wants_curtains)
        self.assertTrue(DetailBudget(CLOSE_UP).wants_mortar_courses)

    def test_an_unknown_level_is_rejected(self):
        for level in (0, 4, -1):
            with self.subTest(level=level):
                with self.assertRaises(ValueError):
                    DetailBudget(level)


class MeshBudgetTests(unittest.TestCase):
    def test_coarser_detail_costs_fewer_triangles(self):
        spec = spec_for()
        counts = {
            level: len(generate_v4_mesh(spec, detail=level).faces)
            for level in (BLOCK, STREET, CLOSE_UP)
        }
        self.assertLess(counts[BLOCK], counts[STREET])
        self.assertLessEqual(counts[STREET], counts[CLOSE_UP])
        self.assertLess(counts[BLOCK], counts[CLOSE_UP] * 0.9)

    def test_the_building_itself_does_not_change(self):
        spec = spec_for()
        coarse = generate_v4_mesh(spec, detail=BLOCK)
        fine = generate_v4_mesh(spec, detail=CLOSE_UP)
        for mesh in (coarse, fine):
            names = {part["name"] for part in mesh.parts}
            self.assertIn("wall", names)
            self.assertIn("roof_slab", names)
            self.assertIn("balcony_slab", names)
        # The built envelope belongs to the massing, not to the budget. Rooftop
        # objects are exempt: thinning them out is what the budget is for, and a
        # dropped aerial legitimately lowers the topmost point in the file.
        def envelope_extent(mesh):
            structural = {"wall", "roof_slab", "parapet", "parapet_cap"}
            faces = np.concatenate([
                mesh.faces[part["face_start"]: part["face_start"] + part["face_count"]]
                for part in mesh.parts
                if part["name"] in structural
            ])
            points = mesh.vertices[faces].reshape(-1, 3)
            return points.min(axis=0), points.max(axis=0)

        np.testing.assert_allclose(
            envelope_extent(coarse), envelope_extent(fine), atol=1e-6
        )

    def test_a_budget_object_is_accepted_directly(self):
        spec = spec_for()
        from_level = len(generate_v4_mesh(spec, detail=BLOCK).faces)
        from_object = len(generate_v4_mesh(spec, detail=DetailBudget(BLOCK)).faces)
        self.assertEqual(from_level, from_object)


if __name__ == "__main__":
    unittest.main()
