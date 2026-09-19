"""Author a reproducible facade grammar from explicitly designated street edges.

This is a hypothesis generator, not image inference. A caller may replace any
opening/facade in the resulting dataclasses with observed metadata.
"""

import numpy as np
from shapely.geometry import Polygon, LineString
from shapely.geometry.polygon import orient
from domain.models import (
    BuildingSpecification,
    HeightEstimate,
    FacadeSpecification,
    Opening,
    RoofSpecification,
    SetbackSpecification,
)
from .materials import appearance_for_style
from .composition import compose_facade


def propose_building(
    parcel,
    *,
    footprint=None,
    front_edges=(0,),
    floors=2,
    height_m=None,
    style="courtyard",
    seed=0,
    setback_m=2.0,
    boundary="wall",
    roof_kind="flat",
    objectid=None,
    detail_level="composed",
    architectural_family="auto",
):
    if detail_level not in ("basic", "composed"):
        raise ValueError("detail_level must be basic or composed")
    if style not in ("narrow", "courtyard", "corner"):
        raise ValueError("Unknown grammar style")
    if boundary not in ("open", "wall", "fence") or roof_kind not in (
        "flat",
        "shed",
        "gable",
    ):
        raise ValueError("Unknown boundary or roof kind")
    if not parcel.is_valid or parcel.geom_type != "Polygon" or parcel.area < 2:
        raise ValueError("Valid Polygon of at least 2m² required")
    if (
        not isinstance(floors, (int, np.integer))
        or floors < 1
        or not np.isfinite(setback_m)
        or setback_m < 0
    ):
        raise ValueError("Invalid floor count/setback")
    parcel = orient(parcel, sign=1)
    points = list(parcel.exterior.coords)
    if not front_edges or any(i < 0 or i >= len(points) - 1 for i in front_edges):
        raise ValueError("Explicit valid front edges required")
    fronts = [
        (np.array(points[i][:2]), np.array(points[i + 1][:2])) for i in front_edges
    ]
    footprint_was_explicit = footprint is not None
    if footprint_was_explicit:
        if footprint.geom_type != "Polygon" or not footprint.is_valid or footprint.is_empty:
            raise ValueError("Explicit footprint must be a valid nonempty Polygon")
        if not parcel.covers(footprint):
            raise ValueError("Explicit footprint must be fully inside the parcel")
        footprint = orient(footprint, sign=1)
    else:
        footprint = parcel.buffer(-0.20, join_style=2)
        for a, b in fronts:
            if setback_m:
                footprint = footprint.difference(
                    LineString([a, b]).buffer(setback_m, cap_style=2)
                )
    if footprint.geom_type != "Polygon" or footprint.is_empty or footprint.area < 1:
        raise ValueError(
            "Requested setbacks split/collapse footprint; supply a smaller setback or explicit volumes"
        )
    footprint = orient(footprint, sign=1)
    h = float(height_m if height_m is not None else floors * 2.8)
    if not np.isfinite(h) or h / floors < 2:
        raise ValueError("Floor height below supported grammar envelope")
    levels = tuple(np.linspace(0, h, floors + 1))
    rng = np.random.default_rng(seed)
    palettes = [(211, 211, 202), (190, 205, 190), (222, 213, 196)]
    color = palettes[int(rng.integers(len(palettes)))]
    facade_specs = []
    coords = list(footprint.exterior.coords)
    for i, (pa, pb) in enumerate(zip(coords[:-1], coords[1:])):
        a, b = np.array(pa), np.array(pb)
        width = float(np.linalg.norm(b - a))
        t = (b - a) / width
        n = np.array([t[1], -t[0]])
        front = False
        for sa, sb in fronts:
            st = (sb - sa) / np.linalg.norm(sb - sa)
            sn = np.array([st[1], -st[0]])
            close_to_front = (
                LineString([a, b]).distance(LineString([sa, sb])) <= setback_m + 0.4
            )
            if np.dot(n, sn) > 0.98 and (footprint_was_explicit or close_to_front):
                front = True
        ops = []
        if front and width > 2.0:
            bay_target = (3.4 if style == "courtyard" else 2.8) * float(
                rng.uniform(0.95, 1.05)
            )
            bays = max(1, int(width / bay_target))
            pitch = width / bays
            for floor in range(floors):
                floor_h = levels[floor + 1] - levels[floor]
                for bay in range(bays):
                    center = (bay + 0.5) * pitch
                    w = min(pitch - 0.55, 2.3 if style == "courtyard" else 1.65)
                    kind = "window"
                    v = levels[floor] + 0.85
                    oh = min(1.5, floor_h - 1.1)
                    if floor == 0 and bay == 0:
                        kind = "door"
                        w = min(1.0, w)
                        v = 0.04
                        oh = min(2.25, floor_h - 0.3)
                    elif floor == 0 and style == "courtyard" and bay == bays - 1:
                        kind = "gate"
                        v = 0.04
                        oh = min(2.25, floor_h - 0.3)
                    elif floor > 0 and style == "corner" and bay % 3 == 0:
                        kind = "balcony_window"
                        v = levels[floor] + 0.03
                        oh = min(2.2, floor_h - 0.3)
                    ops.append(
                        Opening(
                            kind,
                            center - w / 2,
                            v,
                            w,
                            oh,
                            style="casement" if floor > 0 and bay % 2 else "sliding",
                            grille=floor == 0 or style == "narrow",
                            mullion_columns=3 if style == "courtyard" else 2,
                            mullion_rows=3 if floor == 0 else 2,
                        )
                    )
            if style == "narrow" and width > 3.3:
                ops = [o for o in ops if o.v_m >= levels[1]]
                ops[:0] = [
                    Opening(
                        "door",
                        0.30,
                        0.04,
                        0.95,
                        min(2.3, levels[1] - 0.3),
                        style="transom",
                        grille=False,
                        mullion_rows=3,
                    ),
                    Opening(
                        "window",
                        1.55,
                        0.85,
                        width - 1.85,
                        min(1.5, levels[1] - 1.1),
                        style="transom",
                        grille=True,
                        mullion_columns=3,
                    ),
                ]
        facade_specs.append(
            FacadeSpecification(
                f"edge_{i}",
                tuple(a),
                tuple(b),
                width,
                tuple(n),
                levels,
                wall_color_rgb=color,
                openings=tuple(ops),
                is_front=front,
                cladding="horizontal" if style == "corner" else "stucco",
                balcony_pattern="diamond" if style == "corner" else "vertical",
                services=front and style == "narrow",
                wall_material="plaster" if front else "brick",
                ground_floor_material="accent" if (front and style == "narrow") else None,
            )
        )
    if detail_level == "composed":
        facade_specs = [compose_facade(f, parcel, style) for f in facade_specs]
    result = BuildingSpecification(
        tuple(map(tuple, coords)),
        "EPSG:32718",
        HeightEstimate(
            h, 0.0, (), h, floors, h / floors, quality="authored_hypothesis"
        ),
        tuple(facade_specs),
        SetbackSpecification(
            setback_m,
            "garden" if style == "corner" else "pavement",
            boundary,
            1.8,
            edge_indices=tuple(front_edges),
        ),
        RoofSpecification(kind=roof_kind, slope_deg=12 if roof_kind != "flat" else 0),
        metadata={
            "objectid": objectid,
            "style": style,
            "detail_level": detail_level,
            "source": "procedural_hypothesis",
            "front_edge_indices": list(front_edges),
            "footprint_source": "explicit" if footprint_was_explicit else "setback_from_parcel",
        },
        parcel_xy=tuple(map(tuple, parcel.exterior.coords)),
        footprint_holes=tuple(tuple(map(tuple, r.coords)) for r in footprint.interiors),
        parcel_holes=tuple(tuple(map(tuple, r.coords)) for r in parcel.interiors),
        appearance=appearance_for_style(style, color, seed),
        seed=seed,
    )
    if architectural_family != "legacy":
        from .families import apply_family
        result = apply_family(result, architectural_family)
    return result
