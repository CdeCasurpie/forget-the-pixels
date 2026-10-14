"""Load editable grammar specifications emitted by the Step 10 experiment."""

import json
from pathlib import Path
from domain.models import (
    BuildingSpecification,
    FacadeSpecification,
    Opening,
    HeightEstimate,
    SetbackSpecification,
    RoofSpecification,
    MaterialSpecification,
    BuildingAppearance,
    ExteriorStairSpecification,
    FacadeMaterialRegion,
    FacadeProjection,
)


def read_specification(path):
    data = json.loads(Path(path).read_text())
    version = data.pop("schema_version", 1)
    if version not in (1, 2, 3):
        raise ValueError("Unsupported building specification version")
    data["height"] = HeightEstimate(**data["height"])
    facades = []
    for f in data.get("facade_edges", []):
        f["openings"] = tuple(Opening(**o) for o in f.get("openings", []))
        f["material_regions"] = tuple(
            FacadeMaterialRegion(**region) for region in f.get("material_regions", [])
        )
        f["projections"] = tuple(
            FacadeProjection(**projection) for projection in f.get("projections", [])
        )
        f["exterior_stairs"] = tuple(
            ExteriorStairSpecification(**stair) for stair in f.get("exterior_stairs", [])
        )
        facades.append(FacadeSpecification(**f))
    data["facade_edges"] = tuple(facades)
    data["roof"] = RoofSpecification(**data.get("roof", {}))
    data["setback"] = (
        SetbackSpecification(**data["setback"]) if data.get("setback") else None
    )
    appearance = data.get("appearance", {})
    data["appearance"] = BuildingAppearance(
        materials=tuple(
            MaterialSpecification(**material)
            for material in appearance.get("materials", ())
        ),
        source=appearance.get("source", "grammar_default"),
    )
    return BuildingSpecification(**data)
