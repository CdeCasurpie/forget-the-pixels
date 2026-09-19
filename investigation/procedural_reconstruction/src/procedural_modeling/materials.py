"""Deterministic PBR material vocabulary owned by the building grammar."""
from __future__ import annotations

from dataclasses import replace
import numpy as np

from domain.models import BuildingAppearance, MaterialSpecification


DEFAULT_MATERIALS = (
    MaterialSpecification("plaster", "stucco", (0.79, 0.80, 0.77), 0.82, texture_set="stucco_smooth", real_scale_m=1.0),
    MaterialSpecification("accent", "painted_stucco", (0.38, 0.48, 0.43), 0.75, texture_set="stucco_smooth", real_scale_m=1.0),
    MaterialSpecification("stone", "concrete", (0.56, 0.58, 0.56), 0.78, texture_set="concrete_clean", real_scale_m=0.8),
    MaterialSpecification("frame", "painted_aluminium", (0.80, 0.81, 0.78), 0.32, metallic=0.65, texture_set="painted_metal", real_scale_m=0.5),
    MaterialSpecification("glass", "glass", (0.12, 0.20, 0.23), 0.08, opacity=0.34, texture_set="glass_clean", real_scale_m=1.0),
    MaterialSpecification("metal", "painted_steel", (0.19, 0.22, 0.23), 0.30, metallic=0.75, texture_set="painted_metal", real_scale_m=0.5),
    MaterialSpecification("wood", "wood", (0.38, 0.28, 0.19), 0.55, texture_set="wood_vertical", real_scale_m=1.2),
    MaterialSpecification("brick", "brick", (0.60, 0.43, 0.31), 0.88, texture_set="brick_running_bond", real_scale_m=0.55),
    MaterialSpecification("roof", "corrugated_metal", (0.49, 0.53, 0.54), 0.42, metallic=0.72, texture_set="galvanized_corrugated", real_scale_m=1.0),
    # Shrub foliage: parameter-only (leaf_cluster is ground grass, not bush texture)
    MaterialSpecification("leaf", "foliage", (0.30, 0.40, 0.27), 0.88, texture_set=None, real_scale_m=0.7),
    MaterialSpecification("soil", "soil", (0.29, 0.27, 0.23), 0.96, texture_set="dry_soil", real_scale_m=1.0),
    MaterialSpecification("concrete", "concrete", (0.64, 0.65, 0.62), 0.86, texture_set="concrete_clean", real_scale_m=1.0),
    MaterialSpecification("pavement", "paving", (0.58, 0.59, 0.56), 0.90, texture_set="concrete_pavers", real_scale_m=1.2),
)


def validate_material(material: MaterialSpecification) -> None:
    if not material.slot or not material.family:
        raise ValueError("Material slot and family are required")
    values = (*material.base_color_rgb, material.roughness, material.metallic,
              material.opacity, material.real_scale_m, material.normal_strength,
              material.weathering, material.confidence)
    if not np.isfinite(values).all():
        raise ValueError(f"Nonfinite PBR material: {material.slot}")
    if any(channel < 0 or channel > 1 for channel in material.base_color_rgb):
        raise ValueError(f"Invalid base color: {material.slot}")
    if not (0 <= material.roughness <= 1 and 0 <= material.metallic <= 1 and
            0 <= material.opacity <= 1 and material.real_scale_m > 0 and
            material.normal_strength >= 0 and 0 <= material.weathering <= 1 and
            0 <= material.confidence <= 1):
        raise ValueError(f"Invalid PBR range: {material.slot}")


def resolve_materials(appearance: BuildingAppearance) -> tuple[MaterialSpecification, ...]:
    """Merge explicit grammar materials over backwards-compatible defaults."""
    merged = {material.slot: material for material in DEFAULT_MATERIALS}
    seen = set()
    for material in appearance.materials:
        if material.slot in seen:
            raise ValueError(f"Duplicate material slot: {material.slot}")
        validate_material(material)
        merged[material.slot] = material
        seen.add(material.slot)
    return tuple(merged.values())


def appearance_for_style(style: str, wall_rgb: tuple[int, int, int], seed: int) -> BuildingAppearance:
    """Create a coherent building-wide palette; later image priors can replace it."""
    rng = np.random.default_rng(seed)
    wall = tuple(float(np.clip(channel / 255 + rng.uniform(-.018, .018), 0, 1)) for channel in wall_rgb)
    accent = tuple(float(np.clip(channel * .72, 0, 1)) for channel in wall)
    plaster = replace(DEFAULT_MATERIALS[0], base_color_rgb=wall)
    accent_material = replace(DEFAULT_MATERIALS[1], base_color_rgb=accent)
    if style == "narrow":
        accent_material = replace(accent_material, family="painted_concrete", roughness=.80)
    return BuildingAppearance((plaster, accent_material), source="procedural_hypothesis")


def material_to_dict(material: MaterialSpecification) -> dict:
    return {
        "name": material.slot,
        "family": material.family,
        "color": tuple(material.base_color_rgb),
        "roughness": material.roughness,
        "metallic": material.metallic,
        "opacity": material.opacity,
        "texture_set": material.texture_set,
        "real_scale_m": material.real_scale_m,
        "normal_strength": material.normal_strength,
        "weathering": material.weathering,
        "source": material.source,
        "confidence": material.confidence,
    }
