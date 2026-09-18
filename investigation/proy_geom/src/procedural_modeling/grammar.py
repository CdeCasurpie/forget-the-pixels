"""Deterministic architectural assembly: facade grammar + roof + selected fences.

Input geometry is local XY in metres, Z up. The parcel is an immutable envelope.
All decorative solids are clipped to it; beam placements are checked entirely.
"""

import numpy as np
from shapely.geometry import Polygon, Point, LineString, box
from shapely.geometry.polygon import orient
from domain import BuildingSpecification
from .mesh_builder import MeshBuilder, triangles, polygons


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


def facade(mb, f, total_height):
    a, end = np.asarray(f.vertex_a), np.asarray(f.vertex_b)
    t = end - a
    length = np.linalg.norm(t)
    t /= length
    n = np.array([t[1], -t[0]])
    color = tuple(c / 255 for c in f.wall_color_rgb)
    name = "wall_" + f.edge_id
    if name not in mb.material_index:
        mb.material_index[name] = len(mb.materials)
        mb.materials.append({"name": name, "color": color})
    ops = list(f.openings) if f.is_front else []
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
    us = sorted(
        set([0.0, length] + [x for op in ops for x in [op.u_m, op.u_m + op.width_m]])
    )
    zs = sorted(
        set(
            [0.0, total_height]
            + [z for op in ops for z in [op.v_m, op.v_m + op.height_m]]
        )
    )
    for u1, u2 in zip(us[:-1], us[1:]):
        for z1, z2 in zip(zs[:-1], zs[1:]):
            if any(r.contains(Point((u1 + u2) / 2, (z1 + z2) / 2)) for r in rectangles):
                continue
            mb.box(a, t, n, u1, u2, z1, z2, -0.20, 0, name, "wall")
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
    mb.box(a, t, n, 0, length, 0, 0.28, -0.03, 0.025, "stone", "plinth")
    if f.is_front:
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
                "stone",
                "corrugation",
            )
        for x in [x0 + 0.05, x1 - 0.05]:
            for y in [y0 + 0.05, y1 - 0.05]:
                mb.beam((x, y, h), (x, y, z(x, y)), 0.025, semantic="canopy_post")
    if roof.water_tank:
        center = Point(x1 - 0.36, y1 - 0.38)
        radius = min(0.30, (x1 - x0) / 5)
        tank = center.buffer(radius, quad_segs=8)
        mb.solid(tank, h + 0.12, h + 0.92, "metal", "water_tank")
        for z in [h + 0.18, h + 0.44, h + 0.72, h + 0.90]:
            mb.solid(tank.buffer(0.018), z, z + 0.025, "stone", "tank_rib")


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
    if not parcel.covers(poly):
        raise ValueError("Building footprint leaves parcel")
    poly = orient(poly, sign=1)
    parcel = orient(parcel, sign=1)
    height = spec.height.regularized_height_m or spec.height.continuous_height_m
    if not np.isfinite(height) or height <= 0:
        raise ValueError("Invalid height")
    mb = MeshBuilder(parcel)
    rng = np.random.default_rng(spec.seed)
    mb.solid(parcel, 0, 0.025, "concrete", "lot_paving")
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
