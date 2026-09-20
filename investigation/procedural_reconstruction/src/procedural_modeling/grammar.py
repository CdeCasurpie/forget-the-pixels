"""Deterministic architectural assembly: facade grammar + roof + selected fences.

Input geometry is local XY in metres, Z up. The parcel is an immutable envelope.
All decorative solids are clipped to it; beam placements are checked entirely.
"""

import numpy as np
from shapely.geometry import Polygon, Point, LineString, box
from shapely.geometry.polygon import orient
from domain import BuildingSpecification
from .mesh_builder import MeshBuilder, triangles, polygons
from domain.architecture import BuildingSpecificationV4
from domain.models import FacadeSpecification, Opening, RoofSpecification
from procedural_modeling.exposure import calculate_mass_exposures
from procedural_modeling.materials import appearance_for_style
from procedural_modeling.mesh_builder import MeshData


def triangulate_polygon(polygon, z_height):
    coords = [(*p, z_height) for tri in triangles(polygon) for p in tri]
    return np.asarray(coords, float).reshape(-1, 3), np.arange(len(coords)).reshape(
        -1, 3
    )


def railing(mb, a, t, n, left, right, z, depth, pattern="vertical"):
    def p(u, v, w):
        xy = np.asarray(a) + t * u + n * w
        return (*xy, v)

    for v in [z + 0.18, z + 1.02]:
        mb.beam(
            p(left, v, depth), p(right, v, depth), 0.026, semantic="balcony_handrail"
        )
        for u in [left, right]:
            mb.beam(p(u, v, 0.03), p(u, v, depth), 0.026, semantic="balcony_return")
    for u in np.linspace(left, right, max(2, int((right - left) / 0.14) + 1)):
        mb.beam(
            p(u, z + 0.18, depth), p(u, z + 1.02, depth), 0.013, semantic="balcony_bar"
        )
    for u in [left, right]:
        for w in np.arange(0.10, depth, 0.14):
            mb.beam(
                p(u, z + 0.18, w), p(u, z + 1.02, w), 0.013, semantic="balcony_return"
            )
    if pattern == "diamond":
        for u in np.arange(left + 0.18, right - 0.18, 0.36):
            for sign in [-1, 1]:
                (
                    mb.beam(
                        p(u - 0.15, z + 0.25, depth),
                        p(u + 0.15, z + 0.92, depth),
                        0.009,
                        semantic="balcony_ornament",
                    )
                    if sign == 1
                    else mb.beam(
                        p(u + 0.15, z + 0.25, depth),
                        p(u - 0.15, z + 0.92, depth),
                        0.009,
                        semantic="balcony_ornament",
                    )
                )


def opening(mb, a, t, n, op, pattern):
    if op.prefab != "legacy":
        from .prefabs import build_opening
        build_opening(mb, a, t, n, op)
        if op.kind == "balcony_window":
            left, right, depth = op.u_m-.12, op.u_m+op.width_m+.12, op.balcony_depth_m
            shape = Polygon([a+t*x+n*d for x,d in [(left,0),(right,0),(right,depth),(left,depth)]])
            if mb.parcel.covers(shape.buffer(.04, join_style=2)):
                mb.box(a,t,n,left,right,op.v_m-.12,op.v_m,-.02,depth,"concrete","balcony_slab")
                railing(mb,a,t,n,left,right,op.v_m,depth-.04,pattern)
        return
    u, v, w, h = op.u_m, op.v_m, op.width_m, op.height_m
    f, recess = min(op.frame_width_m, w / 5, h / 5), op.recess_m

    def b(u1, u2, z1, z2, d1, d2, mat, part):
        mb.box(a, t, n, u1, u2, z1, z2, d1, d2, mat, part)

    # Deep reveal, jambs, and projecting stone surround.
    for x in [u, u + w - f]:
        b(x, x + f, v, v + h, -recess, 0.045, "frame", "window_jamb")
    for y in [v, v + h - f]:
        b(u + f, u + w - f, y, y + f, -recess, 0.045, "frame", "window_frame")
    for x in [u - 0.075, u + w]:
        b(
            x,
            x + 0.075,
            v - 0.04,
            v + h + 0.085,
            -0.015,
            0.065,
            "stone",
            "opening_surround",
        )
    b(u, u + w, v + h, v + h + 0.085, -0.015, 0.065, "stone", "opening_lintel")
    panel = "wood" if op.kind in ("door", "gate") else "glass"
    b(
        u + f,
        u + w - f,
        v + f,
        v + h - f,
        -recess - 0.025,
        -recess,
        panel,
        op.kind + "_panel",
    )
    cols = max(1, op.mullion_columns)
    rows = max(1, op.mullion_rows)
    for j in range(1, cols):
        x = u + w * j / cols
        b(x - 0.02, x + 0.02, v + f, v + h - f, -recess, 0.005, "frame", "mullion")
    for j in range(1, rows):
        y = v + h * j / rows
        b(u + f, u + w - f, y - 0.018, y + 0.018, -recess, 0.005, "frame", "transom")
    if op.style == "casement" and op.kind == "window":
        # Outward rotated casement leaf; explicit geometry anchored at the jamb.
        angle = np.radians(18)
        st = np.cos(angle) * t + np.sin(angle) * n
        sn = np.array([st[1], -st[0]])
        anchor = np.asarray(a) + t * (u + f) - n * recess
        sw = w / cols - f
        mb.box(
            anchor,
            st,
            sn,
            0,
            sw,
            v + h * 0.52,
            v + h - f,
            -0.02,
            0,
            "glass",
            "open_casement",
        )
        for x in [0, sw - 0.035]:
            mb.box(
                anchor,
                st,
                sn,
                x,
                x + 0.035,
                v + h * 0.52,
                v + h - f,
                -0.03,
                0.012,
                "frame",
                "casement_frame",
            )
        for y in [v + h * 0.52, v + h - f - 0.035]:
            mb.box(
                anchor,
                st,
                sn,
                0,
                sw,
                y,
                y + 0.035,
                -0.03,
                0.012,
                "frame",
                "casement_frame",
            )
    if op.kind in ("door", "gate"):
        for x in np.arange(u + 0.12, u + w - 0.1, 0.15):
            b(
                x,
                x + 0.025,
                v + 0.10,
                v + h - 0.1,
                -recess,
                -recess + 0.04,
                "stone",
                "door_flute",
            )
        b(
            u + w - 0.18,
            u + w - 0.13,
            v + 0.85,
            v + 1.02,
            -0.025,
            0.05,
            "metal",
            "door_handle",
        )
        b(u - 0.04, u + w + 0.04, v, v + 0.035, -0.15, 0.12, "stone", "threshold")
    else:
        b(
            u - 0.12,
            u + w + 0.12,
            v - 0.065,
            v + 0.025,
            -0.04,
            0.16,
            "stone",
            "window_sill",
        )
    if op.grille:
        for x in np.arange(u + 0.08, u + w - 0.04, 0.13):
            b(
                x,
                x + 0.016,
                v + 0.02,
                v + h - 0.02,
                0.075,
                0.10,
                "metal",
                "security_bar",
            )
        for y in [v + 0.15, v + h * 0.5, v + h - 0.15]:
            b(u, u + w, y, y + 0.025, 0.065, 0.105, "metal", "security_crossbar")
    if op.kind == "balcony_window":
        left, right = u - 0.22, u + w + 0.22
        depth = op.balcony_depth_m
        footprint = Polygon(
            [
                np.asarray(a) + t * x + n * d
                for x, d in [(left, 0), (right, 0), (right, depth), (left, depth)]
            ]
        )
        # Do not emit a cut-off balcony with missing rails on a concave corner.
        if mb.parcel.covers(footprint.buffer(0.04, join_style=2)):
            b(left, right, v - 0.13, v + 0.02, -0.04, depth, "stone", "balcony_slab")
            railing(mb, a, t, n, left, right, v, depth - 0.04, pattern)


def projection(mb, a, t, n, feature):
    """Build a facade-attached design mass in facade-local coordinates."""
    if feature.kind not in ("panel", "frame", "ledge", "canopy", "curved_canopy"):
        raise ValueError(f"Unknown facade projection kind: {feature.kind}")
    if min(feature.width_m, feature.height_m, feature.depth_m) <= 0:
        raise ValueError("Facade projections require positive dimensions")
    u, v = feature.u_m, feature.v_m
    w, h, d = feature.width_m, feature.height_m, feature.depth_m

    def add(u1, u2, z1, z2, part):
        mb.box(a, t, n, u1, u2, z1, z2, -0.015, d, feature.material_slot, part)

    if feature.kind == "curved_canopy":
        samples = np.linspace(0.0, 1.0, 13)
        outer = [
            np.asarray(a) + t * (u + w * x) + n * (d * np.sin(np.pi * x))
            for x in samples
        ]
        footprint = Polygon(
            [np.asarray(a) + t * u, np.asarray(a) + t * (u + w), *outer[::-1]]
        )
        mb.solid(
            footprint,
            v,
            v + h,
            feature.material_slot,
            "facade_projection_curved_canopy",
        )
    elif feature.kind == "frame":
        border = min(feature.border_width_m, w / 2, h / 2)
        if border <= 0:
            raise ValueError("Facade frame requires a positive border")
        add(u, u + border, v, v + h, "facade_projection_frame")
        add(u + w - border, u + w, v, v + h, "facade_projection_frame")
        add(u + border, u + w - border, v, v + border, "facade_projection_frame")
        add(
            u + border,
            u + w - border,
            v + h - border,
            v + h,
            "facade_projection_frame",
        )
    else:
        add(u, u + w, v, v + h, f"facade_projection_{feature.kind}")
    if feature.label:
        from .prefabs import sign_letters
        sign_letters(mb,a,t,n,feature)


def exterior_stair(mb, a, t, n, stair, facade_length):
    """Generate a straight or switchback stair, clipped by the parcel envelope."""
    if (
        stair.flight_width_m <= 0
        or stair.run_m <= 0
        or stair.target_z_m <= stair.base_z_m
        or stair.step_count < 4
    ):
        raise ValueError("Invalid exterior stair dimensions")
    occupied_width = stair.flight_width_m * (2.1 if stair.switchback else 1.0)
    if stair.u_m < 0 or stair.u_m + occupied_width > facade_length:
        raise ValueError("Exterior stair outside facade width")

    def xyz(u, z, depth):
        xy = np.asarray(a) + t * u + n * depth
        return (*xy, z)

    def flight(u0, z0, z1, count, reverse=False):
        rise = (z1 - z0) / count
        tread = stair.run_m / count
        for i in range(count):
            if reverse:
                d1, d2 = stair.run_m - (i + 1) * tread, stair.run_m - i * tread
            else:
                d1, d2 = i * tread, (i + 1) * tread
            mb.box(
                a,
                t,
                n,
                u0,
                u0 + stair.flight_width_m,
                z0,
                z0 + (i + 1) * rise,
                d1,
                d2,
                stair.material_slot,
                "exterior_stair_step",
            )
        # Sloping rails and regularly spaced posts on both sides.
        for side in (u0 + 0.06, u0 + stair.flight_width_m - 0.06):
            start_d, end_d = ((stair.run_m, 0.0) if reverse else (0.0, stair.run_m))
            mb.beam(
                xyz(side, z0 + 0.92, start_d),
                xyz(side, z1 + 0.92, end_d),
                0.025,
                material=stair.railing_material_slot,
                semantic="stair_handrail",
            )
            for j in range(0, count + 1, max(1, count // 5)):
                frac = j / count
                depth = start_d + (end_d - start_d) * frac
                z = z0 + (z1 - z0) * frac
                mb.beam(
                    xyz(side, z + 0.04, depth),
                    xyz(side, z + 0.92, depth),
                    0.018,
                    material=stair.railing_material_slot,
                    semantic="stair_railing_post",
                )

    if not stair.switchback:
        flight(stair.u_m, stair.base_z_m, stair.target_z_m, stair.step_count)
        return
    first_count = stair.step_count // 2
    second_count = stair.step_count - first_count
    middle_z = stair.base_z_m + (
        stair.target_z_m - stair.base_z_m
    ) * first_count / stair.step_count
    flight(stair.u_m, stair.base_z_m, middle_z, first_count)
    second_u = stair.u_m + stair.flight_width_m * 1.1
    # Landing links both parallel flights at their turning end.
    mb.box(
        a,
        t,
        n,
        stair.u_m,
        second_u + stair.flight_width_m,
        middle_z - 0.14,
        middle_z,
        stair.run_m - stair.flight_width_m,
        stair.run_m,
        stair.material_slot,
        "exterior_stair_landing",
    )
    flight(second_u, middle_z, stair.target_z_m, second_count, reverse=True)


def facade(mb, f, total_height):
    a, end = np.asarray(f.vertex_a), np.asarray(f.vertex_b)
    t = end - a
    length = np.linalg.norm(t)
    t /= length
    n = np.array([t[1], -t[0]])
    ops = list(f.openings) if f.is_front else []
    regions = list(f.material_regions) if f.is_front else []
    features = list(f.projections) if f.is_front else []
    stairs = list(f.exterior_stairs) if f.is_front else []
    rectangles = []
    for op in ops:
        if (
            op.width_m <= 0
            or op.height_m <= 0
            or op.recess_m <= 0
            or op.frame_width_m <= 0
        ):
            raise ValueError("Invalid opening dimensions")
        if op.kind not in ("window", "door", "gate", "balcony_window"):
            raise ValueError("Unknown opening kind")
        if (
            op.u_m < 0.12
            or op.u_m + op.width_m > length - 0.12
            or op.v_m < 0
            or op.v_m + op.height_m > total_height - 0.10
        ):
            raise ValueError(f"Opening outside facade {f.edge_id}")
        rect = box(op.u_m, op.v_m, op.u_m + op.width_m, op.v_m + op.height_m)
        if any(rect.intersection(other).area > 1e-8 for other in rectangles):
            raise ValueError("Overlapping openings")
        rectangles.append(rect)
    for region in regions:
        if region.width_m <= 0 or region.height_m <= 0:
            raise ValueError("Invalid facade material region")
        if (
            region.u_m < 0
            or region.u_m + region.width_m > length
            or region.v_m < 0
            or region.v_m + region.height_m > total_height
        ):
            raise ValueError(f"Material region outside facade {f.edge_id}")
    for feature in features:
        if (
            feature.u_m < 0
            or feature.u_m + feature.width_m > length
            or feature.v_m < 0
            or feature.v_m + feature.height_m > total_height + 0.5
        ):
            raise ValueError(f"Projection outside facade {f.edge_id}")
    structural_us = []
    if not f.is_front and length > 0.5:
        structural_us = [0.25, length - 0.25]
        # Add intermediate columns every ~4 meters
        for inter_u in np.arange(4.0, length - 0.5, 4.0):
            structural_us.extend([inter_u - 0.125, inter_u + 0.125])
            
    us = sorted(
        set(
            [0.0, length]
            + [x for op in ops for x in [op.u_m, op.u_m + op.width_m]]
            + [x for r in regions for x in [r.u_m, r.u_m + r.width_m]]
            + structural_us
        )
    )
    zs = sorted(
        set(
            [0.0, total_height]
            + [z for op in ops for z in [op.v_m, op.v_m + op.height_m]]
            + [z for r in regions for z in [r.v_m, r.v_m + r.height_m]]
            + ([z for fl in f.floor_levels_m[1:] for z in [fl - 0.20, fl]] if not f.is_front else [])
        )
    )
    for u1, u2 in zip(us[:-1], us[1:]):
        for z1, z2 in zip(zs[:-1], zs[1:]):
            if any(r.contains(Point((u1 + u2) / 2, (z1 + z2) / 2)) for r in rectangles):
                continue
            first_floor_top = (
                f.floor_levels_m[1] if len(f.floor_levels_m) > 1 else total_height
            )
            wall_material = (
                f.ground_floor_material
                if f.ground_floor_material and (z1 + z2) / 2 < first_floor_top
                else f.wall_material
            )
            midpoint = Point((u1 + u2) / 2, (z1 + z2) / 2)
            for region in regions:
                area = box(
                    region.u_m,
                    region.v_m,
                    region.u_m + region.width_m,
                    region.v_m + region.height_m,
                )
                if area.covers(midpoint):
                    wall_material = region.material_slot
            
            depth_outer = 0
            if not f.is_front:
                if f.wall_material == "brick":
                    is_concrete = False
                    # Losas horizontales (vigas)
                    for fl in f.floor_levels_m[1:]:
                        if fl - 0.201 < midpoint.y < fl + 0.001:
                            is_concrete = True
                            break
                    # Columnas verticales
                    if midpoint.x < 0.25 or midpoint.x > length - 0.25:
                        is_concrete = True
                    else:
                        for inter_u in np.arange(4.0, length - 0.5, 4.0):
                            if inter_u - 0.126 < midpoint.x < inter_u + 0.126:
                                is_concrete = True
                                break
                                
                    if is_concrete:
                        wall_material = "concrete"
                        depth_outer = 0.0  # Flush with lot boundary
                    else:
                        depth_outer = -0.015  # Brick inset slightly to show concrete frame
                else:
                    # Muro premium tarrajeado: completamente plano y continuo
                    depth_outer = 0.0
            else:
                # ── PHASE B: Recessed ground floor ───────────────────────
                # On front walls of 3+ story buildings, the ground floor is
                # pushed back ~12cm to create a shadow / entrance effect.
                first_floor_z = f.floor_levels_m[1] if len(f.floor_levels_m) > 1 else total_height
                if len(f.floor_levels_m) >= 4 and midpoint.y < first_floor_z:
                    depth_outer = -0.12  # Recessed ground floor
                else:
                    depth_outer = 0.0
                    
            mb.box(a, t, n, u1, u2, z1, z2, -0.20, depth_outer, wall_material, "wall")
            if f.is_front and f.cladding == "horizontal":
                for y in np.arange(np.ceil(z1 / 0.24) * 0.24, z2 - 0.018, 0.24):
                    mb.box(
                        a,
                        t,
                        n,
                        u1,
                        u2,
                        y,
                        y + 0.015,
                        0,
                        0.023,
                        "stone",
                        "cladding_joint",
                    )
    for op in ops:
        opening(mb, a, t, n, op, f.balcony_pattern)
    for feature in features:
        projection(mb, a, t, n, feature)
    for stair in stairs:
        exterior_stair(mb, a, t, n, stair, length)

    # ── PHASE A: Floor slab protrusions (losas de entrepiso voladas) ─────
    # These are the exposed concrete floor slabs that protrude from every
    # inter-floor boundary. This is THE single biggest depth cue on any
    # Peruvian facade, regardless of style.
    if f.is_front and len(f.floor_levels_m) > 2:
        for z in f.floor_levels_m[1:-1]:  # Skip ground (0) and roof
            # Thick concrete slab band: 15cm tall, protrudes 15cm
            mb.box(a, t, n, -0.02, length + 0.02,
                   z - 0.15, z, -0.02, 0.15,
                   "concrete", "floor_slab")
        # Top cornice / alero superior: overhangs 20cm
        mb.box(a, t, n, -0.04, length + 0.04,
               total_height - 0.10, total_height,
               -0.02, 0.20,
               "concrete", "top_cornice")

    # ── Existing ornamentation (plinth, floor bands, pilasters) ──────────
    if f.style != "premium":
        mb.box(a, t, n, 0, length, 0, 0.28, -0.03, 0.025, "stone", "plinth")
        if f.is_front and f.ornamented:
            for z in f.floor_levels_m[1:]:
                mb.box(a, t, n, 0, length, z - 0.13, z, -0.03, 0.09, "accent", "floor_band")
            for u in [0.04, length - 0.16]:
                mb.box(
                    a,
                    t,
                    n,
                    u,
                    u + 0.12,
                    0,
                    total_height,
                    -0.02,
                    0.05,
                    "stone",
                    "corner_pilaster",
                )

    if f.is_front and f.ornamented:
        if f.services and length > 3.5:
            # Air conditioning condenser, louvers, brackets and a drainpipe.
            first_floor = f.floor_levels_m[1] if len(f.floor_levels_m) > 2 else 0
            x, y = length - 0.95, min(total_height - 0.6, first_floor + 0.2)
            mb.box(
                a,
                t,
                n,
                x,
                x + 0.68,
                y,
                y + 0.46,
                0.03,
                0.35,
                "frame",
                "air_conditioner",
            )
            for z in np.arange(y + 0.04, y + 0.43, 0.045):
                mb.box(
                    a,
                    t,
                    n,
                    x + 0.04,
                    x + 0.64,
                    z,
                    z + 0.01,
                    0.35,
                    0.36,
                    "metal",
                    "condenser_louver",
                )
            for u in [x + 0.08, x + 0.58]:
                mb.box(
                    a,
                    t,
                    n,
                    u,
                    u + 0.035,
                    y - 0.10,
                    y,
                    0.01,
                    0.36,
                    "metal",
                    "service_bracket",
                )
            for u in [length - 0.28]:
                xy = a + t * u + n * 0.07
                mb.beam((*xy, 0.12), (*xy, total_height), 0.027, semantic="drainpipe")


def roof_details(mb, poly, h, roof, rng):
    mb.solid(poly, h - 0.15, h, "concrete", "roof_slab")
    parapet = poly.difference(poly.buffer(-0.14, join_style=2))
    if roof.parapet_height_m > 0:
        mb.solid(parapet, h, h + roof.parapet_height_m, "plaster", "parapet")
        mb.solid(
            poly.difference(poly.buffer(-0.19, join_style=2)),
            h + roof.parapet_height_m,
            h + roof.parapet_height_m + 0.065,
            "stone",
            "parapet_cap",
        )
    if roof.kind not in ("flat", "shed", "gable"):
        raise ValueError("Supported roofs: flat, shed, gable")
    if roof.kind in ("shed", "gable"):
        # Height field over clipped footprint, valid for concave lots and holes.
        lo, bot, hi, top = poly.bounds
        slope = np.tan(np.radians(roof.slope_deg or 12.0))
        mid = (lo + hi) / 2
        pieces = (
            [(poly, lambda x, y: h + 0.2 + slope * (x - lo))]
            if roof.kind == "shed"
            else [
                (
                    poly.intersection(box(lo - 1, bot - 1, mid, top + 1)),
                    lambda x, y: h + 0.2 + slope * (x - lo),
                ),
                (
                    poly.intersection(box(mid, bot - 1, hi + 1, top + 1)),
                    lambda x, y: h + 0.2 + slope * (hi - x),
                ),
            ]
        )
        for piece, z in pieces:
            mb.solid(piece, z, lambda x, y, z=z: z(x, y) + 0.07, "roof", "pitched_roof")
        return
    # Search an entirely contained utility platform; never put it across a courtyard.
    safe = poly.buffer(-0.45, join_style=2)
    platform = None
    for p in polygons(safe):
        x0, y0, x1, y1 = p.bounds
        for scale in [1.0, 0.75, 0.5]:
            candidates = []
            for x in np.linspace(x0, x1, 7):
                for y in np.linspace(y0, y1, 7):
                    r = box(
                        x - 1.5 * scale,
                        y - 1.15 * scale,
                        x + 1.5 * scale,
                        y + 1.15 * scale,
                    )
                    if p.covers(r):
                        candidates.append(r)
            if candidates:
                platform = candidates[int(rng.integers(len(candidates)))]
                break
        if platform is not None:
            break
    if platform is None:
        return
    x0, y0, x1, y1 = platform.bounds
    room = box(x0, y0, x0 + (x1 - x0) * 0.45, y1)
    if roof.terrace_room:
        # Walls are a ring, with an explicit inset door panel on the front.
        mb.solid(
            room.difference(room.buffer(-0.10, join_style=2)),
            h,
            h + 1.9,
            "plaster",
            "rooftop_room",
        )
        mb.solid(room, h + 1.9, h + 1.98, "stone", "rooftop_room_cap")
        a = np.array([x0, y0])
        t = np.array([1.0, 0])
        n = np.array([0.0, -1])
        mb.box(
            a,
            t,
            n,
            0.15,
            min(0.80, (x1 - x0) * 0.45 - 0.1),
            h + 0.05,
            h + 1.65,
            0.001,
            0.025,
            "metal",
            "rooftop_door",
        )
    if roof.canopy:
        z = lambda x, y: h + 2.18 + 0.10 * (y - y0)
        mb.solid(platform, z, lambda x, y: z(x, y) + 0.035, "roof", "canopy_sheet")
        for x in np.arange(x0 + 0.04, x1, 0.13):
            strip = box(x - 0.018, y0, x + 0.018, y1).intersection(platform)
            mb.solid(
                strip,
                lambda x, y: z(x, y) + 0.035,
                lambda x, y: z(x, y) + 0.065,
                "roof",
                "corrugation",
            )
        for x in [x0 + 0.05, x1 - 0.05]:
            for y in [y0 + 0.05, y1 - 0.05]:
                mb.beam((x, y, h), (x, y, z(x, y)), 0.025, semantic="canopy_post")
    if roof.water_tank:
        center = Point(x1 - 0.36, y1 - 0.38)
        radius = min(0.30, (x1 - x0) / 5)
        # Brick/Concrete base for the tank
        base_tank = box(center.x - radius - 0.05, center.y - radius - 0.05, center.x + radius + 0.05, center.y + radius + 0.05)
        mb.solid(base_tank, h, h + 0.12, "brick", "tank_base")
        
        tank = center.buffer(radius, quad_segs=8)
        mb.solid(tank, h + 0.12, h + 0.92, "plastic", "water_tank")
        for z_rib in [h + 0.18, h + 0.44, h + 0.72, h + 0.90]:
            mb.solid(tank.buffer(0.018), z_rib, z_rib + 0.025, "plastic", "tank_rib")
            
    # Fierros de espera (Rebars) at lot corners
    for coord in poly.exterior.coords[:-1]:
        # Spawn 2 thin rebars slightly offset at each column corner
        for offset in [(0.05, 0.05), (-0.05, -0.05)]:
            cx, cy = coord[0] + offset[0], coord[1] + offset[1]
            if poly.contains(Point(cx, cy)):
                rebar_h = h + roof.parapet_height_m + rng.uniform(0.6, 1.2)
                mb.beam((cx, cy, h), (cx, cy, rebar_h), 0.008, semantic="rebar")

def boundary_and_garden(mb, spec, poly, rng):
    s = spec.setback
    if s is None or not s.edge_indices:
        return
    coords = list(mb.parcel.exterior.coords)
    garden = mb.parcel.difference(poly).buffer(-0.12)
    # Reserve pedestrian approach corridors: shrubs must not obstruct entrances.
    for f in spec.facade_edges:
        a, b = np.asarray(f.vertex_a), np.asarray(f.vertex_b)
        t = b - a
        t = t / np.linalg.norm(t)
        n = np.array([t[1], -t[0]])
        if poly.contains(Point((a + b) / 2 + n * 0.01)):
            n = -n
        for op in f.openings:
            if op.kind not in ("door", "gate") or op.v_m > 0.3:
                continue
            center = a + t * (op.u_m + op.width_m / 2)
            approach = LineString([center - n * 0.2, center + n * (s.depth_m + 1)])
            garden = garden.difference(
                approach.buffer(op.width_m / 2 + 0.25, cap_style=2)
            )
    for idx in s.edge_indices:
        if not 0 <= idx < len(coords) - 1:
            raise ValueError("Fence edge index out of range")
        a, b = np.array(coords[idx][:2]), np.array(coords[idx + 1][:2])
        t = b - a
        width = np.linalg.norm(t)
        t /= width
        n = np.array([t[1], -t[0]])

        def block(u1, u2, z1, z2, w1, w2, mat, kind):
            mb.box(a, t, n, u1, u2, z1, z2, w1, w2, mat, kind)

        gate = min(s.gate_width_m, width * 0.48)
        if s.boundary != "open" and width > 2:
            block(
                0.10,
                width - gate - 0.12,
                0,
                0.45,
                -0.18,
                -0.02,
                "stone",
                "boundary_base",
            )
            for u in np.arange(0.12, width, 2.4):
                if u > width - gate - 0.25:
                    continue
                block(
                    u,
                    u + 0.16,
                    0,
                    s.boundary_height_m + 0.08,
                    -0.23,
                    -0.015,
                    "stone",
                    "boundary_post",
                )
            if s.boundary == "wall":
                block(
                    0.10,
                    width - gate - 0.12,
                    0.45,
                    s.boundary_height_m,
                    -0.16,
                    -0.04,
                    "brick",
                    "boundary_wall",
                )
                # Staggered visible mortar joints, only on designated street edge.
                for row, z in enumerate(np.arange(0.48, s.boundary_height_m, 0.13)):
                    block(
                        0.12,
                        width - gate - 0.14,
                        z,
                        z + 0.009,
                        -0.04,
                        -0.03,
                        "stone",
                        "mortar",
                    )
                    for u in np.arange(
                        0.14 + (row % 2) * 0.14, width - gate - 0.18, 0.28
                    ):
                        block(
                            u,
                            u + 0.009,
                            z,
                            min(z + 0.13, s.boundary_height_m),
                            -0.04,
                            -0.03,
                            "stone",
                            "mortar",
                        )
            else:
                for u in np.arange(0.15, width - gate - 0.12, 0.13):
                    block(
                        u,
                        u + 0.018,
                        0.45,
                        s.boundary_height_m,
                        -0.09,
                        -0.065,
                        "metal",
                        "fence_bar",
                    )
            block(
                0.10,
                width - gate - 0.10,
                s.boundary_height_m,
                s.boundary_height_m + 0.06,
                -0.20,
                -0.015,
                "stone",
                "boundary_cap",
            )
            block(
                width - gate,
                width - 0.1,
                0.08,
                s.boundary_height_m,
                -0.14,
                -0.09,
                "wood",
                "gate",
            )
            for u in np.arange(width - gate + 0.06, width - 0.1, 0.12):
                block(
                    u,
                    u + 0.02,
                    0.12,
                    s.boundary_height_m - 0.04,
                    -0.09,
                    -0.065,
                    "metal",
                    "gate_flute",
                )
        if s.surface == "garden":
            for u in np.arange(0.65, width - gate - 0.4, 1.1):
                xy = a + t * u - n * 0.65
                plant = Point(xy).buffer(0.42, quad_segs=6)
                if not garden.covers(plant):
                    continue
                mb.solid(plant.buffer(0.05), 0.03, 0.23, "stone", "planter")
                mb.solid(plant, 0.23, 0.25, "soil", "planting_soil")
                for j in range(3):
                    r = 0.28 + float(rng.uniform(-0.035, 0.04))
                    c = xy + np.array(
                        [
                            float(rng.uniform(-0.09, 0.09)),
                            float(rng.uniform(-0.09, 0.09)),
                        ]
                    )
                    mb.foliage((*c, 0.48 + j * 0.09), (r, r, 0.28), rng)


def generate_mesh(spec: BuildingSpecification):
    poly = Polygon(spec.footprint_xy, spec.footprint_holes)
    parcel = Polygon(spec.parcel_xy or spec.footprint_xy, spec.parcel_holes)
    if not poly.is_valid or not parcel.is_valid or poly.is_empty or parcel.is_empty:
        raise ValueError("Valid nonempty footprint and parcel required")
    if not parcel.buffer(1e-4).covers(poly):
        raise ValueError("Building footprint leaves parcel")
    poly = orient(poly, sign=1)
    parcel = orient(parcel, sign=1)
    height = spec.height.regularized_height_m or spec.height.continuous_height_m
    if not np.isfinite(height) or height <= 0:
        raise ValueError("Invalid height")
    mb = MeshBuilder(parcel, spec.appearance)
    rng = np.random.default_rng(spec.seed)
    # Parcel and building footprint are different contracts. The footprint gets
    # a structural slab; only parcel - footprint becomes visible free site.
    mb.solid(poly, 0, 0.025, "concrete", "building_slab")
    free_site = parcel.difference(poly)
    if not free_site.is_empty:
        surface = "soil" if spec.setback and spec.setback.surface == "garden" else "pavement"
        mb.solid(free_site, 0, 0.025, surface, "site_surface")
    # Match facade endpoints independent of original winding; normals recomputed.
    from dataclasses import replace
    from domain.models import FacadeSpecification

    exterior = list(poly.exterior.coords)
    for i, (a, b) in enumerate(zip(exterior[:-1], exterior[1:])):
        length = float(np.linalg.norm(np.array(b) - a))
        found = None
        for f in spec.facade_edges:
            if np.allclose(a, f.vertex_a, rtol=0, atol=1e-6) and np.allclose(
                b, f.vertex_b, rtol=0, atol=1e-6
            ):
                found = f
                break
            if np.allclose(b, f.vertex_a, rtol=0, atol=1e-6) and np.allclose(
                a, f.vertex_b, rtol=0, atol=1e-6
            ):
                found = replace(
                    f,
                    vertex_a=tuple(a),
                    vertex_b=tuple(b),
                    openings=tuple(
                        replace(o, u_m=length - o.u_m - o.width_m) for o in f.openings
                    ),
                    material_regions=tuple(
                        replace(r, u_m=length - r.u_m - r.width_m)
                        for r in f.material_regions
                    ),
                    projections=tuple(
                        replace(p, u_m=length - p.u_m - p.width_m)
                        for p in f.projections
                    ),
                    exterior_stairs=tuple(
                        replace(
                            s,
                            u_m=length
                            - s.u_m
                            - s.flight_width_m * (2.1 if s.switchback else 1.0),
                        )
                        for s in f.exterior_stairs
                    ),
                )
                break
        if found is None:
            found = FacadeSpecification(
                f"blind_{i}", tuple(a), tuple(b), length, (0, 0), (0, height)
            )
        facade(mb, found, height)
    for ring in poly.interiors:
        pts = list(ring.coords)
        for a, b in zip(pts[:-1], pts[1:]):
            t = np.array(b) - a
            length = np.linalg.norm(t)
            t /= length
            n = np.array([t[1], -t[0]])
            mb.box(
                np.array(a),
                t,
                n,
                0,
                length,
                0.025,
                height,
                -0.15,
                0,
                "plaster",
                "courtyard_wall",
            )
    roof_details(mb, poly, height, spec.roof, rng)
    boundary_and_garden(mb, spec, poly, rng)
    return mb.finish()
"""V4 procedural grammar — delegates rich detail to the battle-tested legacy functions.

Instead of reimplementing windows/facades/roofs from scratch, this module
translates V4 contracts (MassSpec, SitePlan, exposure Z-bands) into legacy
FacadeSpecification objects and calls grammar.facade() / grammar.roof_details()
directly.  This preserves every millimetre of detail (jambs, curtains, mullions,
structural columns, cladding, water tanks, rebars) while gaining the multi-mass
and exposure capabilities of the V4 architecture.
"""


# ── helpers ──────────────────────────────────────────────────────────────────

def _outward_normal(p1, p2, footprint_poly):
    """Return (tangent, normal, length) with normal pointing OUT of the polygon."""
    a = np.asarray(p1, float)
    b = np.asarray(p2, float)
    t = b - a
    length = float(np.linalg.norm(t))
    if length < 1e-4:
        return None, None, 0.0
    t /= length
    n = np.array([t[1], -t[0]])
    mid = a + t * (length / 2.0)
    if footprint_poly.contains(Point(mid + n * 0.01)):
        n = -n
    return t, n, length


def _is_front_edge(n_vec, spec):
    """
    Determine whether a wall edge faces the street.
    In the multi-mass V4, we check:
      1. If spec has explicit_fronts — use those.
      2. Fallback: the edge whose outward normal has the largest -Y component.
    For now we keep the simple heuristic (normal pointing roughly towards -Y).
    """
    return n_vec[1] < -0.3


class ZOffsetMeshBuilder:
    """Wraps MeshBuilder to translate Z coordinates for band-local facade logic."""
    def __init__(self, builder, z_offset):
        self._builder = builder
        self._z_offset = z_offset

    def box(self, a, t, n, u1, u2, z1, z2, w1, w2, *args, **kwargs):
        return self._builder.box(a, t, n, u1, u2, z1 + self._z_offset, z2 + self._z_offset, w1, w2, *args, **kwargs)
        
    def beam(self, a, b, *args, **kwargs):
        a_shifted = (a[0], a[1], a[2] + self._z_offset)
        b_shifted = (b[0], b[1], b[2] + self._z_offset)
        return self._builder.beam(a_shifted, b_shifted, *args, **kwargs)

    def __getattr__(self, name):
        return getattr(self._builder, name)


def _floor_levels_for_band(mass, z_bottom, z_top):
    """Extract floor levels that fall within [z_bottom, z_top]."""
    levels = [z for z in mass.floor_levels if z_bottom <= z <= z_top]
    if not levels or levels[0] > z_bottom + 0.01:
        levels.insert(0, z_bottom)
    if levels[-1] < z_top - 0.01:
        levels.append(z_top)
    return tuple(levels)


def _generate_openings_for_wall(length, floor_levels, is_front, program, rng):
    """
    Create highly varied legacy Opening objects for a wall segment.
    Uses program.use to pick commercial vs residential, and randomizes frames heavily.
    """
    openings = []
    if not is_front:
        return tuple(openings)

    # Decide a unified style for this wall to keep some consistency
    wall_residential_prefab = "legacy" if rng.random() < 0.8 else "slim_window"
    
    for fi in range(len(floor_levels) - 1):
        z_floor = floor_levels[fi]
        z_ceil = floor_levels[fi + 1]
        fh = z_ceil - z_floor
        is_ground = (z_floor < 0.5)
        # v_m is relative to the BAND bottom
        v_base = z_floor - floor_levels[0]

        if program.use in ("commercial", "mixed") and is_ground:
            # Large shopfront openings or huge gates
            margin = 0.6
            bay_w = min(3.0, length - margin * 2)
            num_bays = max(1, int((length - margin * 2) / bay_w))
            start = (length - num_bays * bay_w) / 2.0
            for b in range(num_bays):
                u = start + b * bay_w + 0.1
                w = bay_w - 0.2
                if w < 1.0 or u + w > length - 0.12:
                    continue
                # 30% legacy thick gate, 35% roller, 35% storefront
                r = rng.random()
                prefab_type = "legacy" if r < 0.3 else ("roller" if r < 0.65 else "storefront")
                openings.append(Opening(
                    kind="gate" if prefab_type != "storefront" else "window", 
                    u_m=u, v_m=v_base + 0.0,
                    width_m=w, height_m=min(fh - 0.3, 3.0),
                    frame_width_m=0.08, recess_m=0.12 if prefab_type == "legacy" else 0.06,
                    mullion_columns=max(1, int(w / 1.5)),
                    mullion_rows=1, style="paneled",
                    prefab=prefab_type, curtain=0.0, grille=False,
                ))
        else:
            # Residential windows
            win_w = 1.6 if program.finish_profile == "premium" else float(rng.uniform(1.0, 1.4))
            win_h = 1.6 if program.finish_profile == "premium" else float(rng.uniform(1.2, 1.5))
            sill_v = 0.5 if program.finish_profile == "premium" else float(rng.uniform(0.7, 1.0))
            spacing = win_w + float(rng.uniform(0.8, 1.5))

            num_wins = int((length - 0.5) / spacing)
            if num_wins < 1:
                continue
            start_u = (length - num_wins * spacing) / 2.0 + (spacing - win_w) / 2.0

            for wi in range(num_wins):
                u = start_u + wi * spacing
                v = v_base + sill_v
                if u < 0.12 or u + win_w > length - 0.12:
                    continue
                if v + win_h > (z_ceil - floor_levels[0]) - 0.10:
                    continue
                
                # Ground floor door
                if is_ground and wi == 0 and program.use == "residential":
                    door_w = min(1.2, win_w)
                    openings.append(Opening(
                        kind="door", u_m=u, v_m=v_base + 0.0,
                        width_m=door_w, height_m=min(fh - 0.3, 2.4),
                        frame_width_m=0.08, recess_m=0.12,
                        mullion_columns=1, mullion_rows=3,
                        style="paneled", prefab="legacy" if rng.random() < 0.7 else "wood_panel",
                        curtain=0.0, grille=False,
                    ))
                    continue

                has_grille = (rng.random() < 0.6) if program.finish_profile != "premium" else False
                curtain_frac = float(rng.uniform(0.15, 0.6)) if rng.random() < 0.7 else 0.0
                
                # ── PHASE C: Modern balconies on upper floors ────────────
                # Premium buildings with 3+ floors get balcony windows ~40%
                # of the time on floors above ground. This adds a protruding
                # concrete slab + railing for massive depth.
                num_floors = len(floor_levels) - 1
                is_upper = not is_ground
                use_balcony = (
                    is_upper 
                    and num_floors >= 3 
                    and program.finish_profile == "premium"
                    and rng.random() < 0.4
                )
                
                win_kind = "balcony_window" if use_balcony else "window"
                balcony_d = float(rng.uniform(0.6, 1.0)) if use_balcony else 0.75
                
                openings.append(Opening(
                    kind=win_kind, u_m=u, v_m=v,
                    width_m=win_w, height_m=win_h,
                    frame_width_m=0.08 if wall_residential_prefab == "legacy" else 0.04, 
                    recess_m=0.12 if wall_residential_prefab == "legacy" else 0.06,
                    mullion_columns=2, mullion_rows=1 if program.finish_profile == "premium" else 2,
                    style="sliding" if rng.random() < 0.5 else "casement", 
                    prefab=wall_residential_prefab,
                    curtain=curtain_frac, grille=has_grille,
                    balcony_depth_m=balcony_d,
                ))

    return tuple(openings)


# ── main entry point ─────────────────────────────────────────────────────────

def generate_v4_mesh(spec: BuildingSpecificationV4) -> MeshData:
    r, g, b = spec.program.primary_color
    rgb_255 = (int(r * 255), int(g * 255), int(b * 255))
    appearance = appearance_for_style(
        spec.program.architectural_language, rgb_255, spec.seed
    )

    parcel = Polygon(spec.context.polygon)
    builder = MeshBuilder(parcel, appearance)
    rng = np.random.default_rng(spec.seed)

    exposures = calculate_mass_exposures(spec.site_plan)

    for mass in spec.site_plan.masses:
        mass_exposure = exposures[mass.id]
        mass_poly = Polygon(mass.footprint)

        # ── 1. Walls by Z-bands, delegating to legacy facade() ──────────
        for wall_band in mass_exposure["walls"]:
            z_bottom = wall_band["z_bottom"]
            z_top = wall_band["z_top"]
            band_height = z_top - z_bottom
            segments = wall_band["exposed_segments"]

            lines = [segments] if segments.geom_type == 'LineString' else list(segments.geoms)
            for line in lines:
                coords = list(line.coords)
                for i in range(len(coords) - 1):
                    p1, p2 = coords[i], coords[i + 1]
                    t_vec, n_vec, length = _outward_normal(p1, p2, mass_poly)
                    if t_vec is None:
                        continue

                    is_front = _is_front_edge(n_vec, spec)
                    floor_levels = _floor_levels_for_band(mass, z_bottom, z_top)

                    # Choose wall material
                    if is_front:
                        wall_mat = "plaster"
                    else:
                        wall_mat = (
                            "concrete"
                            if spec.program.side_wall_finish == "plastered"
                            else "brick"
                        )

                    # Generate openings (only on front walls)
                    ops = _generate_openings_for_wall(
                        length, floor_levels, is_front, spec.program, rng
                    )

                    # Make floor levels relative to the band's local Z coordinates
                    local_floor_levels = tuple(z - z_bottom for z in floor_levels)

                    # To match legacy grammar.py, we MUST pass CCW vertices (so n points inwards)
                    # AND we must shift them inwards by 0.20m because facade() draws the wall 
                    # 20cm outwards from the line provided.
                    t_grammar = np.array([n_vec[1], -n_vec[0]])
                    # We want t_vec to be CCW. A CCW edge has t x n_out > 0.
                    # Since t_grammar = (n_out_y, -n_out_x), t_grammar is CW.
                    # So we want the edge that goes OPPOSITE to t_grammar.
                    if np.dot(t_grammar, t_vec) > 0:
                        # t_vec is CW, so swap to make it CCW
                        v_a, v_b = p2, p1
                    else:
                        v_a, v_b = p1, p2
                        
                    # Now v_a -> v_b is CCW. The inward normal is -n_vec.
                    inward_n = -n_vec
                    # Shift the line inwards by 0.20m
                    v_a = v_a + inward_n * 0.20
                    v_b = v_b + inward_n * 0.20

                    # Build a legacy FacadeSpecification
                    facade_spec = FacadeSpecification(
                        edge_id=f"{mass.id}_band{z_bottom:.1f}_{i}",
                        vertex_a=tuple(np.asarray(v_a, float)),
                        vertex_b=tuple(np.asarray(v_b, float)),
                        width_m=length,
                        normal_xy=tuple(n_vec),
                        wall_material=wall_mat,
                        floor_levels_m=local_floor_levels,
                        openings=ops,
                        is_front=is_front,
                        material_regions=(),
                        style=spec.program.finish_profile,
                        ornamented=is_front,
                        services=(is_front and rng.random() < 0.3),
                        cladding="horizontal" if (is_front and rng.random() < 0.2) else "stucco",
                    )

                    # Delegate to the rich legacy function!
                    local_mb = ZOffsetMeshBuilder(builder, z_bottom)
                    facade(local_mb, facade_spec, band_height)

        # ── 2. Roofs via legacy roof_details() ───────────────────────────
        roof_data = mass_exposure.get("roof")
        if roof_data and roof_data["exposed_area"]:
            roof_z = roof_data["z"]
            exposed_area = roof_data["exposed_area"]

            polys = (
                [exposed_area]
                if exposed_area.geom_type == 'Polygon'
                else list(exposed_area.geoms)
            )
            for poly in polys:
                if poly.is_empty or poly.area < 0.5:
                    continue
                roof_spec = RoofSpecification(
                    kind="flat",
                    parapet_height_m=0.5 if mass.role != "podium" else 0.3,
                    terrace_room=(mass.role == "tower" and poly.area > 8),
                    canopy=(mass.role == "tower"),
                    water_tank=(mass.role == "tower" and poly.area > 6),
                )
                roof_details(builder, poly, roof_z, roof_spec, rng)

    # ── 3. Boundaries (fences, gates) ────────────────────────────────────
    from procedural_modeling.boundaries import generate_boundaries
    boundaries = generate_boundaries(spec.context, spec.program, spec.site_plan)

    for bnd in boundaries:
        bnd_coords = list(bnd.line.coords)
        a = np.array(bnd_coords[0])
        b_pt = np.array(bnd_coords[-1])
        t_vec, n_vec, length = _outward_normal(
            bnd_coords[0], bnd_coords[-1], parcel
        )
        if t_vec is None:
            continue
        # n_vec from _outward_normal already points outward

        if bnd.kind == "fence":
            _draw_fence(builder, a, t_vec, n_vec, length, bnd, rng)
        else:
            # Solid perimeter wall (muro ciego)
            builder.box(a, t_vec, n_vec, 0.0, length, 0.0, bnd.height,
                        -0.15, 0.0, "brick", "wall")

    return builder.finish()


def _draw_fence(builder, a, t, n, length, bnd, rng):
    """Draw a typical Peruvian front fence: brick base + metal bars + gates."""
    h = bnd.height

    def is_gate(u):
        if bnd.gate_u is not None and bnd.gate_u <= u <= bnd.gate_u + bnd.gate_width:
            return True
        if bnd.garage_u is not None and bnd.garage_u <= u <= bnd.garage_u + bnd.garage_width:
            return True
        return False
        
    # Get segments that are NOT gates
    solid_segments = []
    points = [0.0]
    if bnd.gate_u is not None:
        points.extend([bnd.gate_u, bnd.gate_u + bnd.gate_width])
    if bnd.garage_u is not None:
        points.extend([bnd.garage_u, bnd.garage_u + bnd.garage_width])
    points.append(length)
    points.sort()
    
    for i in range(0, len(points)-1):
        u1, u2 = points[i], points[i+1]
        if u2 - u1 < 0.05: continue
        mid_u = (u1 + u2) / 2.0
        if not is_gate(mid_u):
            solid_segments.append((u1, u2))

    for (u1, u2) in solid_segments:
        # Low brick base
        builder.box(a, t, n, u1, u2, 0.0, 0.8, -0.15, 0.0, "brick", "wall")
        # Cap on brick base
        builder.box(a, t, n, u1, u2, 0.8, 0.85, -0.18, 0.03, "stone", "parapet_cap")
        
        # Top & mid horizontal rails
        builder.box(a, t, n, u1, u2, h - 0.04, h, -0.08, -0.02, "metal", "fence")
        builder.box(a, t, n, u1, u2, 0.85 + (h - 0.85) * 0.5 - 0.012,
                    0.85 + (h - 0.85) * 0.5 + 0.012, -0.07, -0.03, "metal", "security_crossbar")

    # Vertical metal bars (every 12cm)
    for u_bar in np.arange(0.05, length - 0.05, 0.12):
        if not is_gate(u_bar):
            builder.box(a, t, n, u_bar - 0.012, u_bar + 0.012, 0.85, h, -0.06, -0.04, "metal", "security_bar")

    # Garage door (Portón)
    if bnd.garage_u is not None:
        gu, gw = bnd.garage_u, bnd.garage_width
        # Columns
        builder.box(a, t, n, gu - 0.12, gu, 0.0, h, -0.22, 0.06, "concrete", "column")
        builder.box(a, t, n, gu + gw, gu + gw + 0.12, 0.0, h, -0.22, 0.06, "concrete", "column")
        # Header beam
        builder.box(a, t, n, gu - 0.12, gu + gw + 0.12, h - 0.18, h, -0.25, 0.10, "concrete", "header")
        # Horizontal metal panels
        for pz in np.arange(0.02, h - 0.2, 0.35):
            builder.box(a, t, n, gu, gu + gw, pz, pz + 0.33, -0.12, 0.0, "metal", "gate")
        # Door handle
        builder.box(a, t, n, gu + gw - 0.18, gu + gw - 0.13,
                    0.85, 1.02, -0.025, 0.05, "metal", "door_handle")

    # Pedestrian gate
    if bnd.gate_u is not None:
        pu, pw = bnd.gate_u, bnd.gate_width
        # Frame
        builder.box(a, t, n, pu - 0.04, pu, 0.0, h, -0.12, 0.04, "metal", "frame")
        builder.box(a, t, n, pu + pw, pu + pw + 0.04, 0.0, h, -0.12, 0.04, "metal", "frame")
        # Gate panel (vertical bars)
        for u_bar in np.arange(pu + 0.05, pu + pw - 0.03, 0.10):
            builder.box(a, t, n, u_bar, u_bar + 0.016, 0.0, h,
                        -0.06, -0.04, "metal", "security_bar")
        # Threshold
        builder.box(a, t, n, pu - 0.04, pu + pw + 0.04, 0.0, 0.035,
                    -0.15, 0.12, "stone", "threshold")
