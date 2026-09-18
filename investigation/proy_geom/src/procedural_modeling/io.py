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
)


def read_specification(path):
    data = json.loads(Path(path).read_text())
    version = data.pop("schema_version", 1)
    if version not in (1, 2):
        raise ValueError("Unsupported building specification version")
    data["height"] = HeightEstimate(**data["height"])
    facades = []
    for f in data.get("facade_edges", []):
        f["openings"] = tuple(Opening(**o) for o in f.get("openings", []))
        facades.append(FacadeSpecification(**f))
    data["facade_edges"] = tuple(facades)
    data["roof"] = RoofSpecification(**data.get("roof", {}))
    data["setback"] = (
        SetbackSpecification(**data["setback"]) if data.get("setback") else None
    )
    return BuildingSpecification(**data)
