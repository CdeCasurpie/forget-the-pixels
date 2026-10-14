"""Rooftop objects, in world XY metres with Z absolute. No random choices here.

A Lima azotea is never an empty slab: it carries tanks, antennas, ducts,
condensers, service rooms, laundry lines and planters. Each builder below emits
one of those around a placement point, so `modeling.roofscape` only has to decide
where things go.
"""

import numpy as np
from shapely.geometry import Point


def frame(rotation_deg):
    """Local (tangent, normal) axes for a prop rotated about its own centre."""
    angle = np.radians(rotation_deg)
    tangent = np.array([np.cos(angle), np.sin(angle)])
    return tangent, np.array([tangent[1], -tangent[0]])


# Plan footprint of each prop in metres (along tangent, along normal), before
# scaling. roofscape uses these to reserve space and avoid collisions.
FOOTPRINTS = {
    "water_tank": (0.95, 0.95),
    "tank_elevated": (1.15, 1.15),
    "antenna": (1.30, 0.55),
    "hvac": (1.25, 0.95),
    "duct_run": (3.40, 0.70),
    "skylight": (1.30, 1.30),
    "caseta": (2.70, 2.30),
    "laundry": (2.60, 0.45),
    "planter": (0.80, 0.80),
    "stair_bulkhead": (2.10, 1.50),
    "rebar_cluster": (0.45, 0.45),
}


def _box(mb, origin, tangent, normal, u1, u2, z1, z2, w1, w2, material, semantic):
    mb.box(origin, tangent, normal, u1, u2, z1, z2, w1, w2, material, semantic)


def water_tank(mb, xy, z, rotation, scale, rng):
    """Black plastic cistern on a low masonry plinth."""
    tangent, normal = frame(rotation)
    radius = 0.34 * scale
    _box(mb, xy, tangent, normal, -radius - 0.08, radius + 0.08, z, z + 0.14,
         -radius - 0.08, radius + 0.08, "brick", "tank_base")
    barrel = Point(xy).buffer(radius, quad_segs=8)
    top = z + 0.14 + 0.82 * scale
    mb.solid(barrel, z + 0.14, top, "plastic", "water_tank")
    for fraction in (0.18, 0.5, 0.82):
        rib_z = z + 0.14 + (top - z - 0.14) * fraction
        mb.solid(barrel.buffer(0.02), rib_z, rib_z + 0.03, "plastic", "tank_rib")
    mb.solid(Point(xy).buffer(radius * 0.42, quad_segs=6), top, top + 0.05,
             "plastic", "tank_lid")


def tank_elevated(mb, xy, z, rotation, scale, rng):
    """Cistern lifted on a light steel stand, for gravity pressure."""
    tangent, normal = frame(rotation)
    stand = 1.35 * scale
    radius = 0.34 * scale
    leg = (radius + 0.10)
    for du, dw in ((-leg, -leg), (leg, -leg), (leg, leg), (-leg, leg)):
        foot = np.asarray(xy) + tangent * du + normal * dw
        mb.beam((*foot, z), (*foot, z + stand), 0.035, material="metal",
                semantic="tank_leg")
    _box(mb, xy, tangent, normal, -leg - 0.05, leg + 0.05, z + stand, z + stand + 0.07,
         -leg - 0.05, leg + 0.05, "metal", "tank_platform")
    barrel = Point(xy).buffer(radius, quad_segs=8)
    base = z + stand + 0.07
    mb.solid(barrel, base, base + 0.78 * scale, "plastic", "water_tank")
    for fraction in (0.25, 0.7):
        rib_z = base + 0.78 * scale * fraction
        mb.solid(barrel.buffer(0.02), rib_z, rib_z + 0.03, "plastic", "tank_rib")


def antenna(mb, xy, z, rotation, scale, rng):
    """Yagi TV aerial: mast, boom and a diminishing run of elements."""
    tangent, normal = frame(rotation)
    origin = np.asarray(xy, float)
    mast_top = z + 2.3 * scale
    mb.beam((*origin, z), (*origin, mast_top), 0.026, material="metal",
            semantic="antenna_mast")
    for du, dw in ((-0.22, -0.22), (0.22, 0.22)):
        foot = origin + tangent * du + normal * dw
        mb.beam((*foot, z), (*origin, z + 0.55 * scale), 0.014, material="metal",
                semantic="antenna_guy")
    boom_start = origin - tangent * 0.55 * scale
    boom_end = origin + tangent * 0.60 * scale
    mb.beam((*boom_start, mast_top), (*boom_end, mast_top), 0.016, material="metal",
            semantic="antenna_boom")
    for index in range(7):
        along = -0.52 * scale + index * 0.18 * scale
        half = (0.42 - index * 0.035) * scale
        centre = origin + tangent * along
        left = centre + normal * half
        right = centre - normal * half
        mb.beam((*left, mast_top), (*right, mast_top), 0.010, material="metal",
                semantic="antenna_element")


def hvac(mb, xy, z, rotation, scale, rng):
    """Condenser box with a louvered face and a fan grille on top."""
    tangent, normal = frame(rotation)
    half_u, half_w = 0.55 * scale, 0.40 * scale
    height = 0.72 * scale
    _box(mb, xy, tangent, normal, -half_u, half_u, z + 0.06, z + height,
         -half_w, half_w, "metal", "hvac_unit")
    for du in (-half_u + 0.05, half_u - 0.09):
        _box(mb, xy, tangent, normal, du, du + 0.04, z, z + 0.08, -half_w, half_w,
             "metal", "hvac_foot")
    for level in np.arange(z + 0.16, z + height - 0.10, 0.075):
        _box(mb, xy, tangent, normal, -half_u + 0.06, half_u - 0.06, level,
             level + 0.035, half_w, half_w + 0.02, "metal", "hvac_louver")
    fan = Point(xy).buffer(min(half_u, half_w) * 0.78, quad_segs=8)
    mb.solid(fan, z + height, z + height + 0.04, "metal", "hvac_fan")


def duct_run(mb, xy, z, rotation, scale, rng):
    """Extract duct on stub supports, turning once through a mitred elbow."""
    tangent, normal = frame(rotation)
    origin = np.asarray(xy, float)
    half = 0.22 * scale
    ride = z + 0.38 * scale
    run = 1.55 * scale
    _box(mb, origin, tangent, normal, -run, 0.0, ride - half, ride + half,
         -half, half, "metal", "duct")
    _box(mb, origin, tangent, normal, -half, half, ride - half, ride + half,
         -half, run, "metal", "duct_elbow")
    for offset in (-run + 0.25, -0.25):
        foot = origin + tangent * offset
        mb.beam((*foot, z), (*foot, ride - half), 0.030, material="metal",
                semantic="duct_support")
    cowl = origin + normal * run
    mb.solid(Point(cowl).buffer(half * 1.25, quad_segs=6), ride + half,
             ride + half + 0.18 * scale, "metal", "duct_cowl")


def skylight(mb, xy, z, rotation, scale, rng):
    """Low kerb with a translucent pane, as over a stairwell."""
    tangent, normal = frame(rotation)
    half = 0.55 * scale
    _box(mb, xy, tangent, normal, -half, half, z, z + 0.22, -half, half,
         "concrete", "skylight_kerb")
    _box(mb, xy, tangent, normal, -half + 0.05, half - 0.05, z + 0.22, z + 0.27,
         -half + 0.05, half - 0.05, "glass", "skylight_glazing")


def caseta(mb, xy, z, rotation, scale, rng):
    """Service room: masonry walls, a door and a light corrugated cover."""
    tangent, normal = frame(rotation)
    half_u, half_w = 1.25 * scale, 1.05 * scale
    height = 2.05 * scale
    for du in (-half_u, half_u - 0.12):
        _box(mb, xy, tangent, normal, du, du + 0.12, z, z + height, -half_w, half_w,
             "plaster", "caseta_wall")
    for dw in (-half_w, half_w - 0.12):
        _box(mb, xy, tangent, normal, -half_u, half_u, z, z + height, dw, dw + 0.12,
             "plaster", "caseta_wall")
    _box(mb, xy, tangent, normal, -0.38, 0.38, z + 0.03, z + 1.95, -half_w - 0.02,
         -half_w + 0.03, "metal", "caseta_door")
    _box(mb, xy, tangent, normal, -half_u - 0.10, half_u + 0.10, z + height,
         z + height + 0.05, -half_w - 0.10, half_w + 0.10, "roof", "caseta_roof")
    for du in np.arange(-half_u - 0.06, half_u + 0.06, 0.14):
        _box(mb, xy, tangent, normal, du, du + 0.04, z + height + 0.05,
             z + height + 0.08, -half_w - 0.10, half_w + 0.10, "roof", "corrugation")


def laundry(mb, xy, z, rotation, scale, rng):
    """Two posts and strung lines — the most common thing on a Lima roof."""
    tangent, normal = frame(rotation)
    origin = np.asarray(xy, float)
    span = 1.25 * scale
    height = 1.55 * scale
    for sign in (-1, 1):
        foot = origin + tangent * span * sign
        mb.beam((*foot, z), (*foot, z + height), 0.035, material="metal",
                semantic="laundry_post")
        _box(mb, foot, tangent, normal, -0.10, 0.10, z, z + 0.08, -0.10, 0.10,
             "concrete", "laundry_base")
    left = origin - tangent * span
    right = origin + tangent * span
    for level in (height - 0.10, height - 0.38, height - 0.66):
        mb.beam((*left, z + level), (*right, z + level), 0.008, material="metal",
                semantic="laundry_line")


def planter(mb, xy, z, rotation, scale, rng):
    """Pot with foliage; roofs in Barranco carry bougainvillea and cactus."""
    tangent, normal = frame(rotation)
    half = 0.30 * scale
    _box(mb, xy, tangent, normal, -half, half, z, z + 0.34 * scale, -half, half,
         "stone", "planter")
    _box(mb, xy, tangent, normal, -half + 0.04, half - 0.04, z + 0.34 * scale,
         z + 0.37 * scale, -half + 0.04, half - 0.04, "soil", "planting_soil")
    centre = (float(xy[0]), float(xy[1]), z + 0.34 * scale + 0.26 * scale)
    mb.foliage(centre, (0.30 * scale, 0.30 * scale, 0.28 * scale), rng,
               semantic="roof_shrub")


def stair_bulkhead(mb, xy, z, rotation, scale, rng):
    """Head of the stair that reaches the roof, with its own door and cap."""
    tangent, normal = frame(rotation)
    half_u, half_w = 1.0 * scale, 0.70 * scale
    height = 2.25 * scale
    _box(mb, xy, tangent, normal, -half_u, half_u, z, z + height, -half_w, half_w,
         "plaster", "stair_bulkhead")
    _box(mb, xy, tangent, normal, -0.42, 0.42, z + 0.02, z + 2.0, -half_w - 0.03,
         -half_w + 0.04, "metal", "bulkhead_door")
    _box(mb, xy, tangent, normal, -half_u - 0.07, half_u + 0.07, z + height,
         z + height + 0.09, -half_w - 0.07, half_w + 0.07, "stone", "bulkhead_cap")


def rebar_cluster(mb, xy, z, rotation, scale, rng):
    """Starter bars left standing for the floor that may never be built."""
    origin = np.asarray(xy, float)
    tangent, normal = frame(rotation)
    for du, dw in ((-0.10, -0.10), (0.10, -0.10), (0.10, 0.10), (-0.10, 0.10)):
        foot = origin + tangent * du + normal * dw
        mb.beam((*foot, z), (*foot, z + float(rng.uniform(0.55, 1.15)) * scale),
                0.009, material="rebar", semantic="rebar")


BUILDERS = {
    "water_tank": water_tank,
    "tank_elevated": tank_elevated,
    "antenna": antenna,
    "hvac": hvac,
    "duct_run": duct_run,
    "skylight": skylight,
    "caseta": caseta,
    "laundry": laundry,
    "planter": planter,
    "stair_bulkhead": stair_bulkhead,
    "rebar_cluster": rebar_cluster,
}
