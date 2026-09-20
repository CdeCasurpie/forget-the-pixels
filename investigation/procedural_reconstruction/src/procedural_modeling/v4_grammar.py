"""V4 procedural grammar — delegates rich detail to the battle-tested legacy functions.

Instead of reimplementing windows/facades/roofs from scratch, this module
translates V4 contracts (MassSpec, SitePlan, exposure Z-bands) into legacy
FacadeSpecification objects and calls grammar.facade() / grammar.roof_details()
directly.  This preserves every millimetre of detail (jambs, curtains, mullions,
structural columns, cladding, water tanks, rebars) while gaining the multi-mass
and exposure capabilities of the V4 architecture.
"""
import numpy as np
from domain.architecture import BuildingSpecificationV4
from domain.models import (
    MeshData, Opening, FacadeSpecification, RoofSpecification,
)
from procedural_modeling.mesh_builder import MeshBuilder
from procedural_modeling.exposure import calculate_mass_exposures
from procedural_modeling.materials import appearance_for_style
from procedural_modeling.grammar import facade, roof_details, boundary_and_garden
from shapely.geometry import Polygon, LineString, Point


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
    Create legacy Opening objects for a wall segment.
    Uses program.use to pick commercial vs residential distribution.
    """
    openings = []
    if not is_front:
        return tuple(openings)

    for fi in range(len(floor_levels) - 1):
        z_floor = floor_levels[fi]
        z_ceil = floor_levels[fi + 1]
        fh = z_ceil - z_floor
        is_ground = (z_floor < 0.5)
        # v_m is relative to the BAND bottom (which equals 0 for legacy facade())
        v_base = z_floor - floor_levels[0]

        if program.use in ("commercial", "mixed") and is_ground:
            # Large shopfront openings
            margin = 0.6
            bay_w = min(3.0, length - margin * 2)
            num_bays = max(1, int((length - margin * 2) / bay_w))
            start = (length - num_bays * bay_w) / 2.0
            for b in range(num_bays):
                u = start + b * bay_w + 0.1
                w = bay_w - 0.2
                if w < 1.0 or u + w > length - 0.12:
                    continue
                openings.append(Opening(
                    kind="gate", u_m=u, v_m=v_base + 0.0,
                    width_m=w, height_m=min(fh - 0.3, 3.0),
                    frame_width_m=0.06, recess_m=0.10,
                    mullion_columns=max(1, int(w / 1.5)),
                    mullion_rows=1, style="paneled",
                    prefab="legacy", curtain=0.0, grille=False,
                ))
        else:
            # Residential windows
            win_w, win_h = 1.2, 1.4
            sill_v = 0.9
            spacing = 2.5

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
                has_grille = rng.random() < 0.3
                curtain_frac = float(rng.uniform(0.15, 0.6)) if rng.random() < 0.7 else 0.0
                openings.append(Opening(
                    kind="window", u_m=u, v_m=v,
                    width_m=win_w, height_m=win_h,
                    frame_width_m=0.06, recess_m=0.08,
                    mullion_columns=2, mullion_rows=2,
                    style="sliding", prefab="legacy",
                    curtain=curtain_frac, grille=has_grille,
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
                        floor_levels_m=floor_levels,
                        openings=ops,
                        is_front=is_front,
                        wall_material=wall_mat,
                        ornamented=is_front,
                        services=(is_front and rng.random() < 0.3),
                        cladding="horizontal" if (is_front and rng.random() < 0.2) else "stucco",
                    )

                    # Delegate to the rich legacy function!
                    facade(builder, facade_spec, band_height)

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
