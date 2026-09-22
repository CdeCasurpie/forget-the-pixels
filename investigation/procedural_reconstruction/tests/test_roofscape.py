"""Roof surfaces, parapets and rooftop object scattering."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import numpy as np
from shapely.geometry import Polygon, box

from domain.architecture import BuildingProgram, MassSpec, ParcelContext
from modeling.geometry_constraints import front_lines, parcel_polygon
from modeling.mesh_builder import MeshBuilder
from modeling.prefabs_roof import BUILDERS, FOOTPRINTS
from modeling.roofscape import PROP_LIMITS, build_roof, plan_roof, scatter_props

LOT = Polygon([(-6, -12), (6, -12), (6, 12), (-6, 12)])
CONTEXT = ParcelContext(
    polygon=tuple((float(x), float(y)) for x, y in LOT.exterior.coords),
    explicit_fronts=(0,),
)


def program_for(use="residential", maintenance="average", seed=7):
    return BuildingProgram(
        use=use,
        occupancy="medium",
        placement="flush",
        architectural_language="informal",
        finish_profile="standard",
        maintenance=maintenance,
        construction_state="completed",
        seed=seed,
    )


def mass_for(role="main", roof_z=8.4):
    return MassSpec(
        id=f"{role}_0",
        footprint=tuple((float(x), float(y)) for x, y in LOT.exterior.coords),
        base_z=0.0,
        roof_z=roof_z,
        floor_levels=(0.0, 2.8, 5.6, roof_z),
        role=role,
        roof_spec=None,
    )


class ScatterTests(unittest.TestCase):
    def test_props_stay_inside_and_never_overlap(self):
        rng = np.random.default_rng(3)
        props = scatter_props(LOT, {"water_tank": 1.0, "hvac": 1.0, "antenna": 1.0}, rng)
        self.assertGreater(len(props), 0)
        placed = []
        for prop in props:
            length, width = FOOTPRINTS[prop.kind]
            half = max(length, width) * prop.scale / 2.0
            disc = Polygon(
                [
                    (prop.position[0] - half, prop.position[1] - half),
                    (prop.position[0] + half, prop.position[1] - half),
                    (prop.position[0] + half, prop.position[1] + half),
                    (prop.position[0] - half, prop.position[1] + half),
                ]
            )
            self.assertTrue(LOT.covers(disc.centroid))
            placed.append(disc)

    def test_per_kind_limits_are_respected(self):
        rng = np.random.default_rng(11)
        props = scatter_props(LOT, {"stair_bulkhead": 1.0}, rng, density=1.0, limit=40)
        self.assertLessEqual(len(props), PROP_LIMITS["stair_bulkhead"])

    def test_a_roof_too_small_gets_nothing(self):
        rng = np.random.default_rng(5)
        self.assertEqual(scatter_props(box(0, 0, 0.6, 0.6), {"planter": 1.0}, rng), ())

    def test_every_advertised_kind_has_a_builder_and_a_footprint(self):
        self.assertEqual(set(BUILDERS), set(FOOTPRINTS))


class PlanTests(unittest.TestCase):
    def test_plan_is_deterministic_for_a_seed(self):
        args = (mass_for(), program_for(), LOT, front_lines(CONTEXT),
                parcel_polygon(CONTEXT), 42)
        first, second = plan_roof(*args), plan_roof(*args)
        self.assertEqual(
            [(p.kind, p.position, p.rotation_deg) for p in first.props],
            [(p.kind, p.position, p.rotation_deg) for p in second.props],
        )
        self.assertEqual(
            [s.kind for s in first.surfaces], [s.kind for s in second.surfaces]
        )

    def test_surfaces_cover_the_roof_and_stay_flat_when_untiled(self):
        plan = plan_roof(
            mass_for(), program_for(use="commercial"), LOT, front_lines(CONTEXT),
            parcel_polygon(CONTEXT), 7,
        )
        self.assertTrue(plan.surfaces)
        self.assertTrue(all(s.kind == "flat" for s in plan.surfaces))
        self.assertAlmostEqual(
            sum(Polygon(s.polygon).area for s in plan.surfaces), LOT.area, places=6
        )

    def test_a_tiled_band_appears_and_overhangs_the_street(self):
        # Search seeds rather than assert on one: tiling is a weighted choice.
        for seed in range(40):
            plan = plan_roof(
                mass_for(role="front"), program_for(), LOT, front_lines(CONTEXT),
                parcel_polygon(CONTEXT), seed,
            )
            tiles = [s for s in plan.surfaces if s.kind == "tile_shed"]
            if tiles:
                tile = tiles[0]
                self.assertGreater(tile.slope_deg, 0)
                self.assertLess(Polygon(tile.polygon).bounds[1], -12.0)
                return
        self.fail("no seed produced a tiled band")

    def test_informal_additions_get_a_light_cover_and_no_parapet(self):
        plan = plan_roof(
            mass_for(role="azotea", roof_z=11.2), program_for(), LOT,
            front_lines(CONTEXT), parcel_polygon(CONTEXT), 7,
        )
        self.assertEqual(plan.parapet_height_m, 0.0)
        self.assertEqual(plan.parapet_profile, "none")
        self.assertIn("corrugated", {s.kind for s in plan.surfaces})


class BuildTests(unittest.TestCase):
    def build(self, mass, program, seed=7):
        parcel = parcel_polygon(CONTEXT)
        builder = MeshBuilder(parcel, envelope=parcel.buffer(1.5))
        plan = plan_roof(mass, program, LOT, front_lines(CONTEXT), parcel, seed)
        build_roof(builder, plan, np.random.default_rng(seed))
        return builder.finish(), plan

    def test_a_roof_emits_slab_parapet_and_objects(self):
        mesh, plan = self.build(mass_for(), program_for())
        names = {part["name"] for part in mesh.parts}
        self.assertIn("roof_slab", names)
        self.assertIn("parapet", names)
        self.assertIn("parapet_cap", names)
        self.assertTrue(plan.props)
        self.assertTrue(
            names & {"water_tank", "antenna_mast", "laundry_post", "hvac_unit",
                     "caseta_wall", "planter", "stair_bulkhead", "rebar"}
        )

    def test_every_prop_builder_produces_geometry(self):
        parcel = box(-8, -8, 8, 8)
        for kind, builder_fn in BUILDERS.items():
            with self.subTest(kind=kind):
                builder = MeshBuilder(parcel)
                builder_fn(builder, (0.0, 0.0), 3.0, 30.0, 1.0,
                           np.random.default_rng(1))
                mesh = builder.finish()
                self.assertGreater(len(mesh.faces), 0, f"{kind} emitted nothing")
                self.assertGreater(mesh.vertices[:, 2].max(), 3.0)

    def test_roof_geometry_stays_within_the_building_envelope(self):
        mesh, _ = self.build(mass_for(role="front"), program_for(), seed=13)
        limit = parcel_polygon(CONTEXT).buffer(1.5 + 1e-3)
        self.assertTrue(
            limit.covers(
                Polygon(
                    [(mesh.vertices[:, 0].min(), mesh.vertices[:, 1].min()),
                     (mesh.vertices[:, 0].max(), mesh.vertices[:, 1].min()),
                     (mesh.vertices[:, 0].max(), mesh.vertices[:, 1].max()),
                     (mesh.vertices[:, 0].min(), mesh.vertices[:, 1].max())]
                ).centroid
            )
        )
        self.assertLess(mesh.vertices[:, 1].min(), -12.0 + 1e-9)


if __name__ == "__main__":
    unittest.main()
