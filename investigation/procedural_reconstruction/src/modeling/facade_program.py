"""Composition of one wall: bay rhythm, opening programme and applied relief.

The previous generator sorted windows floor by floor and nudged each one by a
random offset, which broke the vertical axes that make a facade read as designed
rather than generated. It also emitted openings and nothing else: no sills, no
cornices, no balconies, no shopfront awnings, because the caller passed empty
projection and material tuples.

Here the bay axes are fixed once for the whole wall and every floor hangs off
them, and the relief that belongs to a rhythm is emitted together with it.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

import numpy as np

from domain.models import FacadeMaterialRegion, FacadeProjection, Opening
from modeling.detail import DEFAULT_BUDGET

# Bay rhythm, opening programme and relief per architectural family. Read as
# data: no family may reach into the geometry, and the grammar may not infer a
# family from the shape of the lot.
FAMILY_RULES = {
    "quiet_house": dict(
        pitch=3.0, window_ratio=0.46, window_h=1.55, sill=0.95, grille=True,
        ground="entrance", upper="repetitive", cornice=0.22, sill_band=False,
        pilasters=False, shutters=False, balcony_every=0, balcony_style="bars",
        ground_material=None, prefab="slim_window",
    ),
    "ribbon_windows": dict(
        pitch=3.6, window_ratio=0.74, window_h=1.55, sill=0.85, grille=False,
        ground="entrance", upper="ribbon", cornice=0.18, sill_band=True,
        pilasters=False, shutters=False, balcony_every=0, balcony_style="bars",
        ground_material=None, prefab="slim_window",
    ),
    "balcony_apartments": dict(
        pitch=3.1, window_ratio=0.56, window_h=1.95, sill=0.30, grille=False,
        ground="entrance", upper="balcony_column", cornice=0.26, sill_band=False,
        pilasters=False, shutters=False, balcony_every=2, balcony_style="bars",
        ground_material="stone", prefab="slim_window",
    ),
    "mixed_use": dict(
        pitch=3.3, window_ratio=0.58, window_h=1.60, sill=0.90, grille=False,
        ground="shopfront", upper="repetitive", cornice=0.24, sill_band=True,
        pilasters=False, shutters=False, balcony_every=3, balcony_style="bars",
        ground_material="stone", prefab="slim_window", awning=True, sign="TIENDA",
    ),
    "workshop": dict(
        pitch=3.8, window_ratio=0.42, window_h=1.30, sill=1.45, grille=True,
        ground="garage", upper="repetitive", cornice=0.14, sill_band=False,
        pilasters=False, shutters=False, balcony_every=0, balcony_style="bars",
        ground_material="concrete", prefab="slim_window", sign="TALLER",
    ),
    "brick_courtyard": dict(
        pitch=2.9, window_ratio=0.48, window_h=1.45, sill=1.00, grille=True,
        ground="entrance", upper="repetitive", cornice=0.20, sill_band=False,
        pilasters=False, shutters=False, balcony_every=0, balcony_style="bars",
        ground_material="brick", prefab="slim_window", crown="brick",
    ),
    # Barranco-specific languages the generic families could not express.
    "republicano": dict(
        pitch=2.8, window_ratio=0.42, window_h=2.25, sill=0.75, grille=True,
        ground="entrance", upper="repetitive", cornice=0.42, sill_band=True,
        pilasters=True, shutters=True, balcony_every=3, balcony_style="balusters",
        ground_material="stone", prefab="legacy",
    ),
    "galeria_madera": dict(
        pitch=3.0, window_ratio=0.62, window_h=1.85, sill=0.25, grille=False,
        ground="shopfront", upper="gallery", cornice=0.20, sill_band=False,
        pilasters=False, shutters=True, balcony_every=0, balcony_style="balusters",
        ground_material="wood", prefab="legacy", awning=True,
    ),
    "esquina_comercial": dict(
        pitch=3.2, window_ratio=0.54, window_h=1.70, sill=0.80, grille=False,
        ground="shopfront", upper="balcony_column", cornice=0.30, sill_band=True,
        pilasters=True, shutters=False, balcony_every=2, balcony_style="solid",
        ground_material="stone", prefab="slim_window", awning=True, sign="LOCAL",
    ),
    "quinta": dict(
        pitch=2.7, window_ratio=0.50, window_h=1.40, sill=1.00, grille=True,
        ground="entrance", upper="repetitive", cornice=0.16, sill_band=False,
        pilasters=False, shutters=True, balcony_every=0, balcony_style="bars",
        ground_material=None, prefab="wood_panel",
    ),
}

# Which families suit which use, so a workshop is never dressed as a mansion.
FAMILIES_BY_USE = {
    "residential": ("quiet_house", "republicano", "quinta", "balcony_apartments",
                    "ribbon_windows"),
    "commercial": ("mixed_use", "workshop", "esquina_comercial", "galeria_madera"),
    "mixed": ("mixed_use", "esquina_comercial", "galeria_madera",
              "balcony_apartments", "brick_courtyard"),
}

MARGIN_M = 0.32
MIN_BAY_M = 2.2
MAX_BAY_M = 4.2


@dataclass(frozen=True)
class WallComposition:
    openings: tuple = ()
    projections: tuple = ()
    material_regions: tuple = ()
    dropped: tuple = field(default=())


def resolve_family(program, rng):
    """Family for a building: explicit if named, otherwise drawn from its use."""
    named = getattr(program, "architectural_language", "auto")
    if named in FAMILY_RULES:
        return named
    pool = FAMILIES_BY_USE.get(program.use, FAMILIES_BY_USE["residential"])
    return str(rng.choice(pool))


def bay_axes(length):
    """Centres of the bays, fixed once so every floor shares the same axes."""
    usable = length - 2 * MARGIN_M
    if usable < MIN_BAY_M:
        return (), 0.0
    count = max(1, int(round(usable / 3.1)))
    pitch = usable / count
    while pitch > MAX_BAY_M and count < 24:
        count += 1
        pitch = usable / count
    while pitch < MIN_BAY_M and count > 1:
        count -= 1
        pitch = usable / count
    return tuple(MARGIN_M + (index + 0.5) * pitch for index in range(count)), pitch


def _opening(kind, u, v, width, height, rules, *, prefab=None, grille=None,
             columns=2, rows=1, balcony_depth=0.75, curtain=0.0):
    return Opening(
        kind=kind,
        u_m=u,
        v_m=v,
        width_m=width,
        height_m=height,
        frame_width_m=0.07,
        recess_m=0.12,
        style="sliding",
        grille=rules["grille"] if grille is None else grille,
        mullion_columns=max(1, columns),
        mullion_rows=max(1, rows),
        balcony_depth_m=balcony_depth,
        prefab=prefab or rules["prefab"],
        curtain=curtain,
        grille_pattern="grid",
        source="family_rule",
    )


def _ground_openings(axes, pitch, z0, z1, length, rules, rng, dropped):
    """Openings for the storey that meets the street."""
    height = min(rules["window_h"] + 0.9, z1 - z0 - 0.35)
    if height <= 0.6:
        dropped.append("ground_storey_too_low")
        return []
    programme = rules["ground"]
    openings = []
    for index, centre in enumerate(axes):
        if programme == "blind":
            break
        if programme == "shopfront" or programme == "gallery":
            width = min(pitch * 0.78, 3.0)
            kind, prefab, grille = "window", "storefront", False
            if index == 0:
                width = min(width, 1.25)
                kind, prefab = "door", "wood_panel"
        elif programme == "garage":
            if index == 0:
                width = min(pitch * 0.86, 3.2)
                kind, prefab, grille = "gate", "roller", False
            else:
                width = min(pitch * rules["window_ratio"], 1.6)
                kind, prefab, grille = "window", rules["prefab"], True
        else:  # entrance
            if index == 0:
                width = min(pitch * 0.42, 1.2)
                kind, prefab, grille = "door", rules["prefab"], False
                if prefab == "slim_window":
                    prefab = "wood_panel"
            else:
                width = min(pitch * rules["window_ratio"], 2.0)
                kind, prefab, grille = "window", rules["prefab"], rules["grille"]
        u = centre - width / 2.0
        if u < 0.14 or u + width > length - 0.14:
            dropped.append(f"ground_bay_{index}_outside_wall")
            continue
        if kind == "window":
            # One sill value, used for both the position and the remaining
            # height. Clamping only the position let the height overrun the
            # storey on a low band.
            sill = max(0.4, min(rules["sill"], z1 - z0 - height - 0.2))
            available = z1 - z0 - sill - 0.3
            if available < 0.5:
                dropped.append(f"ground_bay_{index}_window_does_not_fit")
                continue
            openings.append(
                _opening(kind, u, z0 + sill, width,
                         min(rules["window_h"], available),
                         rules, prefab=prefab, grille=grille,
                         columns=max(2, int(width / 0.8)))
            )
        else:
            openings.append(
                _opening(kind, u, z0 + 0.04, width, height, rules,
                         prefab=prefab, grille=grille,
                         columns=max(1, int(width / 1.1)), rows=3)
            )
    return openings


def _upper_openings(axes, pitch, z0, z1, length, floor_index, rules, rng, dropped):
    """Openings for one storey above the ground, on the shared axes."""
    pattern = rules["upper"]
    height = min(rules["window_h"], z1 - z0 - 0.75)
    if height <= 0.5:
        dropped.append(f"floor_{floor_index}_too_low")
        return []
    sill = min(rules["sill"], z1 - z0 - height - 0.25)
    openings = []
    for index, centre in enumerate(axes):
        width = pitch * rules["window_ratio"]
        kind, columns, rows = "window", 2, 1
        balcony = False
        if pattern == "ribbon":
            width = pitch * 0.82
            columns = max(3, int(width / 0.7))
        elif pattern == "alternating" and index % 2:
            width *= 0.72
        elif pattern == "balcony_column" and rules["balcony_every"]:
            balcony = index % rules["balcony_every"] == 0
        elif pattern == "gallery":
            width = pitch * 0.66
            kind = "window"
        if rules["balcony_every"] and not balcony and pattern != "balcony_column":
            balcony = (index % rules["balcony_every"] == 1) and floor_index >= 1
        width = float(np.clip(width, 0.7, 2.8))
        if balcony:
            kind = "balcony_window"
            sill_used = 0.18
        else:
            sill_used = sill
        u = centre - width / 2.0
        if u < 0.14 or u + width > length - 0.14:
            dropped.append(f"floor_{floor_index}_bay_{index}_outside_wall")
            continue
        top = z0 + sill_used + (height + 0.5 if balcony else height)
        if top > z1 - 0.12:
            sill_used = max(0.12, z1 - 0.12 - z0 - height)
        openings.append(
            _opening(kind, u, z0 + sill_used, width,
                     min(height + (0.5 if balcony else 0.0), z1 - z0 - sill_used - 0.15),
                     rules, columns=columns, rows=rows,
                     balcony_depth=float(rng.uniform(0.75, 1.05)),
                     curtain=float(rng.uniform(0.2, 0.55)) if rng.random() < 0.6 else 0.0)
        )
    return openings


def compose_wall(length, floor_levels, *, is_front, family, program, rng,
                 band_height, is_ground_band=True, is_top_band=True,
                 mass_role="main", budget=DEFAULT_BUDGET):
    """Openings, relief and finish zones for one exposed wall band."""
    if not is_front:
        return WallComposition()
    if length < MIN_BAY_M or len(floor_levels) < 2:
        return WallComposition(dropped=("wall_too_narrow_for_a_bay",))
    rules = FAMILY_RULES.get(family) or FAMILY_RULES["quiet_house"]
    axes, pitch = bay_axes(length)
    if not axes:
        return WallComposition(dropped=("wall_too_narrow_for_a_bay",))

    dropped, openings = [], []
    levels = list(floor_levels)
    for floor_index, (z0, z1) in enumerate(zip(levels[:-1], levels[1:])):
        if z1 - z0 < 1.9:
            dropped.append(f"floor_{floor_index}_below_minimum_storey")
            continue
        ground = is_ground_band and floor_index == 0
        made = (
            _ground_openings(axes, pitch, z0, z1, length, rules, rng, dropped)
            if ground
            else _upper_openings(axes, pitch, z0, z1, length, floor_index, rules,
                                 rng, dropped)
        )
        openings.extend(made)

    # Nothing may leave this function that the wall builder would reject: one
    # bad opening used to abort the whole lot with an exception. Filtered before
    # the relief pass, so a dropped window cannot leave a balcony hanging on a
    # blank wall.
    fitted = []
    for opening in openings:
        if opening.u_m < 0.12 or opening.u_m + opening.width_m > length - 0.12:
            dropped.append(f"opening_at_{opening.u_m:.2f}_outside_wall")
            continue
        if opening.v_m < 0 or opening.v_m + opening.height_m > band_height - 0.12:
            dropped.append(f"opening_at_{opening.v_m:.2f}_above_band")
            continue
        if opening.width_m <= 0 or opening.height_m <= 0.4:
            dropped.append(f"opening_at_{opening.u_m:.2f}_degenerate")
            continue
        fitted.append(opening)
    openings = fitted

    projections, regions = _relief(
        length, levels, axes, pitch, openings, rules, band_height,
        is_ground_band, is_top_band, rng, dropped, budget
    )

    # The balcony projection carries the slab and its railing. Leaving the
    # opening marked as a balcony window would make the opening builder draw a
    # second slab and a second railing on top of it — the single largest source
    # of duplicate geometry in the model.
    resolved = tuple(
        replace(opening, kind="window") if opening.kind == "balcony_window" else opening
        for opening in openings
    )
    return WallComposition(
        openings=resolved,
        projections=tuple(projections),
        material_regions=tuple(regions),
        dropped=tuple(dropped),
    )


def _relief(length, levels, axes, pitch, openings, rules, band_height,
            is_ground_band, is_top_band, rng, dropped, budget):
    """Applied mouldings, cantilevers and finish zones implied by the rhythm."""
    projections, regions = [], []

    def add(kind, u, v, width, height, depth, material="stone", border=0.14,
            label=""):
        if width <= 0 or height <= 0 or depth <= 0:
            return
        if u < 0 or u + width > length or v < 0 or v + height > band_height + 0.4:
            dropped.append(f"{kind}_outside_wall")
            return
        projections.append(
            FacadeProjection(kind, u, v, width, height, depth, material, border,
                             source="family_rule", label=label)
        )

    if rules["sill_band"] and budget.wants_sill_bands:
        for level in levels[1:-1] if len(levels) > 2 else []:
            add("sill_band", 0.06, level + 0.02, length - 0.12, 0.10, 0.13)

    if rules["pilasters"] and length > 4.0:
        for u in (0.05, length - 0.39):
            add("pilaster", u, 0.0, 0.34, min(band_height - 0.1, levels[-1]), 0.09)

    if is_top_band and rules["cornice"] > 0:
        depth = float(np.clip(rules["cornice"], 0.12, 0.42))
        add("cornice", 0.04, max(0.0, band_height - rules["cornice"] - 0.06),
            length - 0.08, rules["cornice"], depth)

    for opening in openings:
        if opening.kind != "balcony_window":
            continue
        add("balcony", max(0.0, opening.u_m - 0.22),
            opening.v_m, min(opening.width_m + 0.44, length - opening.u_m + 0.22),
            1.05, opening.balcony_depth_m, material="concrete",
            label=rules["balcony_style"])

    if rules["upper"] == "gallery" and len(levels) > 2 and length > 4.0:
        add("gallery", 0.10, levels[1] + 0.20, length - 0.20, 2.35,
            float(rng.uniform(1.0, 1.3)), material="wood")

    if is_ground_band and rules.get("awning") and len(levels) > 1:
        head = min(levels[1] - 0.45, band_height - 0.5)
        if head > 1.9:
            add("awning", 0.25, head, length - 0.5, 0.40,
                float(rng.uniform(0.9, 1.25)), material="roof")

    if is_ground_band and rules.get("sign") and len(levels) > 1:
        head = min(levels[1] - 0.30, band_height - 0.35)
        width = min(length - 0.9, 3.6)
        if head > 2.1 and width > 1.6:
            add("sign_box", (length - width) / 2.0, head, width, 0.46, 0.10,
                material="sign",
                label=rules["sign"] if budget.wants_lettering else "")

    if rules["shutters"] and budget.wants_shutters:
        for opening in openings:
            if opening.kind != "window" or opening.v_m < levels[0] + 1.0:
                continue
            add("shutter", opening.u_m, opening.v_m, opening.width_m,
                opening.height_m, 0.05, material="wood", border=0.32)

    if length > 3.0:
        add("downpipe", length - 0.28, 0.15, 0.12,
            max(1.0, band_height - 0.3), 0.10, material="metal")

    if is_ground_band and rules["ground_material"] and len(levels) > 1:
        regions.append(
            FacadeMaterialRegion(0.0, 0.0, length, min(levels[1], band_height),
                                 rules["ground_material"], source="family_rule")
        )
    if is_top_band and rules.get("crown"):
        regions.append(
            FacadeMaterialRegion(0.0, max(0.0, band_height - 0.55), length, 0.55,
                                 rules["crown"], source="family_rule")
        )
    return projections, regions
