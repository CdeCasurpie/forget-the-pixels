"""Closed component solids clipped in XY to their cadastral envelope.

Components form an architectural assembly, not a Boolean-unioned manifold.
Constrained triangulation preserves concavities and courtyard holes.

Topology model: every primitive emits into a *component* whose geometric
positions are shared by index from construction time. Two faces of the same
component that meet at the same (x, y, z) reuse one vertex id; nothing is
merged afterwards. UV coordinates stay metric (UV = world_distance /
texture_scale) but live *per face corner*, decoupled from the topology, so a
UV seam never forces a topological split. The export adapters (GLB/OBJ)
duplicate render vertices only where an attribute seam requires it.

Identity model: each component carries ``semantic`` (what it is),
``component_id`` (which instance) and ``assembly_id`` (which logical group,
e.g. one window). Parts index faces; components index instances.
"""

import numpy as np
import shapely
from contextlib import contextmanager
from shapely import constrained_delaunay_triangles
from shapely.geometry import LineString, Point, Polygon
from shapely.geometry.polygon import orient
from domain import BuildingAppearance, MeshData
from .detail import DEFAULT_BUDGET
from .materials import material_to_dict, resolve_materials


# Triangles below this are numerical debris, not geometry: clipping a solid
# against a rotated cadastral boundary routinely produces slivers of ~1e-20 m².
# Emitting them corrupts normals and fails mesh validation downstream.
MIN_TRIANGLE_AREA_M2 = 1e-12

# Position identity quantum inside one component. Two corners computed for the
# same geometric point share one vertex id from birth; points closer than this
# without being the same construction point do not occur in our generators.
VERTEX_QUANTUM_M = 1e-9

# Attachments allowed to reach past the cadastral line into the street overhang
# envelope. Structural mass (walls, slabs, parapets, roofs, boundaries) is never
# in this set and stays clipped to the parcel.
PROJECTING_SEMANTICS = frozenset({
    # balconies and galleries
    "balcony_slab", "balcony_handrail", "balcony_bar", "balcony_return",
    "balcony_ornament", "balustrade", "baluster", "balustrade_cap",
    "gallery_slab", "gallery_post", "gallery_rail", "gallery_roof",
    "gallery_beam", "gallery_bracket",
    # facade projections
    "facade_projection_panel", "facade_projection_frame",
    "facade_projection_ledge", "facade_projection_canopy",
    "facade_projection_curved_canopy", "sign_letter", "sign_box",
    "sign_bracket",
    # horizontal mouldings and slab edges
    "floor_slab", "top_cornice", "floor_band", "plinth", "corner_pilaster",
    "cladding_joint", "cornice", "cornice_step", "cornice_drip", "sill_band",
    "pilaster", "pilaster_base", "pilaster_cap",
    # opening trim
    "window_sill", "opening_surround", "opening_lintel", "threshold",
    "door_handle", "security_bar", "security_crossbar", "grille_diamond",
    "shutter_leaf", "shutter_slat",
    # eaves and awnings
    "eave", "eave_fascia", "rafter_tail", "awning", "awning_arm",
    "awning_valance", "tile_eave_course", "tile_roof", "tile_ridge",
    # bay windows
    "bay_window_wall", "bay_window_slab", "bay_window_roof", "glazing",
    # services
    "air_conditioner", "condenser_louver", "service_bracket", "drainpipe",
    "downpipe", "downpipe_clamp", "gutter", "meter_box", "cable",
})


def _subdivide_ring(coords, max_len):
    """Insert collinear Steiner vertices so no straight run exceeds max_len.
    Points lie exactly on the boundary: geometry unchanged, ears stay local."""
    pts = list(coords)
    if len(pts) < 2:
        return pts
    out = [pts[0]]
    for a, b in zip(pts, pts[1:]):
        a = (float(a[0]), float(a[1]))
        b = (float(b[0]), float(b[1]))
        dist = float(np.hypot(b[0] - a[0], b[1] - a[1]))
        n = max(1, int(np.ceil(dist / max_len))) if max_len > 0 else 1
        for k in range(1, n):
            f = k / n
            out.append((a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f))
        out.append(b)
    return out


def _is_rectilinear(poly, tol=1e-9):
    """All edges axis-aligned in (u, z): wall rectangles with rectangular
    holes always satisfy this."""
    rings = [poly.exterior] + list(poly.interiors)
    for ring in rings:
        coords = list(ring.coords)
        for (x0, z0), (x1, z1) in zip(coords, coords[1:]):
            if abs(x1 - x0) > tol and abs(z1 - z0) > tol:
                return False
    return True


def _refine(axis, max_step):
    """Split every interval above max_step so shared grid lines stay
    identical for all neighbor cells on both sides."""
    out = [axis[0]]
    for lo, hi in zip(axis, axis[1:]):
        n = max(1, int(np.ceil((hi - lo) / max_step)))
        # Interior splits only: endpoints appended exactly, so exact cut
        # values (material edges, hole edges) survive bit-identically.
        out.extend(lo + (hi - lo) * k / n for k in range(1, n))
        out.append(hi)
    return out


def _rectilinear_cells(poly, cuts_u=(), cuts_z=(), max_step=0.5):
    """Grid tiling that is exact: grid lines contain every hole edge plus
    every caller-supplied cut (material edges, depth steps), so kept cells
    (by center) union to the domain with no slivers and no gaps.
    Intervals above max_step split uniformly, so neighbor cells always share
    identical edges and every quad stays aspect-bounded."""
    xs = {poly.bounds[0], poly.bounds[2]}
    zs = {poly.bounds[1], poly.bounds[3]}
    holes = []
    for ring in poly.interiors:
        hx0, hz0, hx1, hz1 = Polygon(ring).bounds
        xs.update((hx0, hx1))
        zs.update((hz0, hz1))
        holes.append(Polygon(ring))
    xs.update(cuts_u)
    zs.update(cuts_z)
    # Snap to nanometres: interval subdivision (x0 + w*k/n) lands a few ulps
    # off exact cuts, which would read as sliver cells and split shared
    # edges. Geometry moves < 1nm; validation tolerates 0.2mm.
    xs = sorted({round(float(x), 9) for x in xs})
    zs = sorted({round(float(z), 9) for z in zs})
    xs = _refine(sorted(xs), max_step)
    zs = _refine(sorted(zs), max_step)
    cells = []
    for x0, x1 in zip(xs, xs[1:]):
        if x1 - x0 <= 1e-12:
            continue
        for z0, z1 in zip(zs, zs[1:]):
            if z1 - z0 <= 1e-12:
                continue
            cx, cz = (x0 + x1) / 2.0, (z0 + z1) / 2.0
            if any(hole.covers(Point(cx, cz)) for hole in holes):
                continue
            cells.append((x0, x1, z0, z1))
    return cells


def _split_rect(x0, x1, z0, z1, max_aspect=3.5):
    """Sub-rectangles with bounded aspect, then two triangles each."""
    w, h = x1 - x0, z1 - z0
    nx = max(1, int(np.ceil(w / (max_aspect * h)))) if h > 0 else 1
    nz = max(1, int(np.ceil(h / (max_aspect * w)))) if w > 0 else 1
    rects = []
    for i in range(nx):
        for j in range(nz):
            rects.append((x0 + w * i / nx, x0 + w * (i + 1) / nx,
                          z0 + h * j / nz, z0 + h * (j + 1) / nz))
    return rects


def _clean_ring(coords):
    pts = [(float(x), float(y)) for x, y in coords]
    if len(pts) > 1 and pts[0] == pts[-1]:
        pts.pop()
    out = []
    for p in pts:
        if not out or out[-1] != p:
            out.append(p)
    return out


def triangulate_rings(exterior, holes=()):
    """Constrained triangulation of a polygon with holes (earcut).

    Returns (vertices, indices): vertices concatenates the cleaned exterior
    and hole rings, indices are triples into it. Every triangle lies inside
    the domain, none crosses a hole, none leaves the exterior. Callers orient
    the output for their cap normal.
    """
    import mapbox_earcut as earcut

    rings = []
    outer = _clean_ring(exterior)
    if len(outer) < 3:
        return np.zeros((0, 2)), np.zeros((0, 3), int)
    rings.append(np.asarray(outer, float))
    ends = [len(rings[0])]
    for hole in holes or ():
        cleaned = _clean_ring(hole)
        if len(cleaned) < 3:
            continue
        rings.append(np.asarray(cleaned, float))
        ends.append(ends[-1] + len(rings[-1]))
    verts = np.ascontiguousarray(np.vstack(rings))
    idx = np.asarray(earcut.triangulate_float64(
        verts, np.array(ends, dtype=np.uint32))).reshape(-1, 3)
    return verts, idx


def _oriented(tris, verts, ccw=True):
    """Triangles with guaranteed orientation (signed area sign)."""
    out = []
    for a, b, c in tris:
        area = ((verts[b][0] - verts[a][0]) * (verts[c][1] - verts[a][1])
                - (verts[c][0] - verts[a][0]) * (verts[b][1] - verts[a][1]))
        if (area < 0) == ccw:
            out.append((a, c, b))
        else:
            out.append((a, b, c))
    return out


def _pos_key(point):
    x, y, z = (float(point[0]), float(point[1]), float(point[2]))
    q = VERTEX_QUANTUM_M
    return (round(x / q), round(y / q), round(z / q))


def polygons(geometry):
    if geometry.is_empty:
        return
    if geometry.geom_type == "Polygon":
        if geometry.area > 1e-10:
            yield orient(geometry, sign=1.0)
    elif hasattr(geometry, "geoms"):
        for part in geometry.geoms:
            yield from polygons(part)


def triangles(polygon):
    """Return CCW constrained triangles, including polygons with holes.

    GEOS can return a triangle lying outside a thin or concave input — a plinth
    strip clipped against a rotated L-shaped lot reproduces it — so every
    triangle is checked against its own domain instead of being trusted.
    """
    parts = list(constrained_delaunay_triangles(polygon).geoms)
    if not parts:
        return
    domain = polygon.buffer(1e-9)
    inside = shapely.covered_by(np.asarray(parts, dtype=object), domain)
    for triangle, is_inside in zip(parts, np.atleast_1d(inside)):
        if not is_inside:
            continue
        yield np.array(orient(triangle, sign=1).exterior.coords)[:3, :2]


class _Component:
    """One topological island under construction: shared positions, an index
    buffer, per-corner UVs and per-face materials."""

    __slots__ = ("semantic", "component_id", "assembly_id", "positions",
                 "pos_index", "first_uv", "faces", "corner_uvs",
                 "face_materials", "face_start")

    def __init__(self, semantic, component_id, assembly_id):
        self.semantic = semantic
        self.component_id = component_id
        self.assembly_id = assembly_id
        self.positions = []      # list of (x, y, z)
        self.pos_index = {}      # _pos_key -> position id
        self.first_uv = []       # legacy per-position UV view (first corner wins)
        self.faces = []          # list of (i, j, k) into positions
        self.corner_uvs = []     # list of ((u,v), (u,v), (u,v)) per face
        self.face_materials = []
        self.face_start = 0


class MeshBuilder:
    def __init__(self, parcel, appearance=BuildingAppearance(), *, envelope=None,
                 budget=DEFAULT_BUDGET):
        self.parcel = parcel
        # How many repeats the caller is willing to pay for at this distance.
        self.budget = budget
        # Attachments are clipped to this instead of the parcel. Defaults to the
        # parcel, so a caller that does not opt in keeps the old behaviour.
        self.envelope = parcel if envelope is None else envelope
        # Finished components, in emission order. Faces/positions below are the
        # concatenation of every component: positions are shared *within* a
        # component, never across components.
        self.vertices = []   # list of (x, y, z), topology positions
        self.uvs = []        # legacy per-position UV view, one per vertex
        self.faces = []      # list of (i, j, k) — indices into vertices
        self.corner_uvs = []  # one ((u,v)x3) per face, aligned with faces
        self.face_materials = []
        self.parts = []
        self.components = []  # logical identity records, aligned with parts
        self.materials = [material_to_dict(m) for m in resolve_materials(appearance)]
        self.material_index = {m["name"]: i for i, m in enumerate(self.materials)}
        self._open = None
        self._assembly_stack = []
        self._counters = {}

    # ── Clipping envelope ────────────────────────────────────────────

    def limit_for(self, semantic, clip="auto"):
        """Polygon this piece of geometry must stay inside."""
        if clip == "parcel":
            return self.parcel
        if clip == "envelope":
            return self.envelope
        if clip != "auto":
            raise ValueError(f"Unknown clip mode: {clip}")
        return self.envelope if semantic in PROJECTING_SEMANTICS else self.parcel

    def can_attach(self, shape):
        """Whether an attachment footprint fits inside the projection envelope."""
        return self.envelope.covers(shape)

    # ── Component / assembly scope ───────────────────────────────────

    @property
    def _assembly(self):
        return self._assembly_stack[-1] if self._assembly_stack else ""

    def _auto_id(self, semantic):
        key = (self._assembly, semantic)
        self._counters[key] = self._counters.get(key, 0) + 1
        return f"{semantic}#{self._counters[key]:04d}"

    def begin_component(self, semantic, component_id=None, assembly_id=None):
        """Open a component scope. Every vertex created inside is shared by
        position with the other vertices of this component only."""
        if self._open is not None:
            raise RuntimeError("A component is already open; end it first")
        assembly = self._assembly if assembly_id is None else assembly_id
        self._open = _Component(semantic, component_id or self._auto_id(semantic),
                                assembly)
        return self._open.component_id

    def end_component(self):
        """Close the component, freezing one part range over its faces."""
        comp = self._open
        if comp is None:
            raise RuntimeError("No component is open")
        self._open = None
        if not comp.faces:
            return None
        # Prune positions no face references (ring corners whose every face
        # was rejected as degenerate): topology stays tight.
        used = np.zeros(len(comp.positions), bool)
        for a, b, c in comp.faces:
            used[a] = used[b] = used[c] = True
        remap = np.full(len(comp.positions), -1, int)
        remap[used] = np.arange(int(used.sum()))
        positions = [comp.positions[i] for i in np.nonzero(used)[0]]
        first_uv = [comp.first_uv[i] for i in np.nonzero(used)[0]]
        comp.face_start = len(self.faces)
        base = len(self.vertices)
        self.vertices.extend(positions)
        self.uvs.extend(first_uv)
        self.faces.extend([(remap[a] + base, remap[b] + base, remap[c] + base)
                           for a, b, c in comp.faces])
        self.corner_uvs.extend(comp.corner_uvs)
        self.face_materials.extend(comp.face_materials)
        record = {
            "name": comp.semantic,
            "face_start": comp.face_start,
            "face_count": len(comp.faces),
            "component_id": comp.component_id,
            "assembly_id": comp.assembly_id,
        }
        self.parts.append(record)
        self.components.append(dict(record))
        return comp.component_id

    @contextmanager
    def component(self, semantic, component_id=None, assembly_id=None):
        self.begin_component(semantic, component_id, assembly_id)
        try:
            yield self._open.component_id
        finally:
            if self._open is not None:
                self.end_component()

    @contextmanager
    def assembly(self, assembly_id):
        """Group the components emitted inside under one logical assembly
        (e.g. one window: frame + glazing + grille)."""
        self._assembly_stack.append(assembly_id)
        try:
            yield assembly_id
        finally:
            self._assembly_stack.pop()

    def _ensure_component(self, semantic):
        if self._open is None:
            self.begin_component(semantic)
            return True
        return False

    # ── Low-level indexed emission (public for wall/ring builders) ───

    def mat_index(self, material):
        if material not in self.material_index:
            raise ValueError(f"Unknown material slot: {material}")
        return self.material_index[material]

    def uv_scale_for(self, material):
        scale = self.materials[self.mat_index(material)].get("real_scale_m", 1.0)
        if not np.isfinite(scale) or scale <= 0:
            raise ValueError("UV scale must be finite and positive")
        return scale

    def vert(self, point):
        """Position id shared by every corner built at this point inside the
        open component."""
        comp = self._open
        if comp is None:
            raise RuntimeError("vert() needs an open component")
        key = _pos_key(point)
        known = comp.pos_index.get(key)
        if known is not None:
            return known
        vid = len(comp.positions)
        comp.positions.append((float(point[0]), float(point[1]), float(point[2])))
        comp.first_uv.append((0.0, 0.0))
        comp.pos_index[key] = vid
        return vid

    def tri(self, a, b, c, uvs, material_idx):
        """Emit one triangle over shared position ids with per-corner UVs."""
        comp = self._open
        if comp is None:
            raise RuntimeError("tri() needs an open component")
        p0 = np.asarray(comp.positions[a], float)
        p1 = np.asarray(comp.positions[b], float)
        p2 = np.asarray(comp.positions[c], float)
        if not (np.isfinite(p0).all() and np.isfinite(p1).all() and np.isfinite(p2).all()):
            return False
        if np.linalg.norm(np.cross(p1 - p0, p2 - p0)) / 2.0 < MIN_TRIANGLE_AREA_M2:
            return False
        (u0, v0), (u1, v1), (u2, v2) = uvs
        if not np.isfinite((u0, v0, u1, v1, u2, v2)).all():
            return False
        comp.faces.append((a, b, c))
        comp.corner_uvs.append(((float(u0), float(v0)), (float(u1), float(v1)),
                                (float(u2), float(v2))))
        comp.face_materials.append(material_idx)
        for vid, uv in ((a, (u0, v0)), (b, (u1, v1)), (c, (u2, v2))):
            if comp.first_uv[vid] == (0.0, 0.0) and uv != (0.0, 0.0):
                comp.first_uv[vid] = (float(uv[0]), float(uv[1]))
        return True

    def quad(self, a, b, c, d, uvs, material_idx):
        """Two triangles over four shared corners; uvs in corner order."""
        self.tri(a, b, c, (uvs[0], uvs[1], uvs[2]), material_idx)
        self.tri(a, c, d, (uvs[0], uvs[2], uvs[3]), material_idx)

    # ── UV helpers ───────────────────────────────────────────────────

    @staticmethod
    def _cap_uvs(points_3d, scale):
        """Metric UV for a cap triangle, accounting for slope surface distance.
        Uses a consistent basis for coplanar triangles."""
        p0, p1, p2 = [np.array(p) for p in points_3d]
        n = np.cross(p1 - p0, p2 - p0)
        norm = np.linalg.norm(n)
        if norm < 1e-8:
            return [(p[0]/scale, p[1]/scale) for p in points_3d]
        n = n / norm

        # If perfectly flat (n is vertical)
        if abs(n[2]) > 0.9999:
            return [(p[0]/scale, p[1]/scale) for p in points_3d]

        # Sloped: consistent basis. Strike line is horizontal along the plane.
        strike = np.cross(n, np.array([0.0, 0.0, 1.0]))
        strike_len = np.linalg.norm(strike)
        if strike_len < 1e-8:
            u_axis = np.array([1.0, 0.0, 0.0])
        else:
            u_axis = strike / strike_len

        v_axis = np.cross(n, u_axis)

        return [(np.dot(p, u_axis)/scale, np.dot(p, v_axis)/scale) for p in points_3d]

    @staticmethod
    def _uv_for_wall(u_along, z, scale):
        return (u_along / scale, z / scale)

    # ── Indexed extrusion core ───────────────────────────────────────

    def _ring_ids(self, coords, z_bottom, z_top):
        """Bottom/top position ids for one ring. Shared with caps and walls."""
        bots, tops = [], []
        for x, y in coords:
            bots.append(self.vert((float(x), float(y), float(z_bottom))))
            tops.append(self.vert((float(x), float(y), float(z_top))))
        return bots, tops

    # ── solid() with shared topology ─────────────────────────────────

    def solid(self, shape, bottom, top, material="plaster", semantic="wall",
              *, facade_origin=None, facade_tangent=None, facade_normal=None,
              uv_scale=None, clip="auto"):
        """Extrude polygon between scalar or affine height fields.

        If facade_origin and facade_tangent are given, wall UVs are
        measured along the facade tangent from that origin.  Otherwise,
        wall UVs fall back to edge-local distance.

        Cap UVs (top / bottom) are always world XY / uv_scale.

        Positions are shared by index inside one component: a plain box
        closes with 8 positions and 12 triangles, not 36 positions.
        """
        mat_idx = self.mat_index(material)
        if uv_scale is None:
            uv_scale = self.materials[mat_idx].get("real_scale_m", 1.0)
        if not np.isfinite(uv_scale) or uv_scale <= 0:
            raise ValueError("UV scale must be finite and positive")
        auto = self._ensure_component(semantic)
        try:
            def height(value, xy):
                return value(*xy) if callable(value) else value

            clipped = shape.intersection(self.limit_for(semantic, clip))
            for poly in polygons(clipped):
                coords = np.array(poly.exterior.coords)[:, :2]
                if any(height(top, p) <= height(bottom, p) for p in coords):
                    raise ValueError("Solid must have positive thickness everywhere")

                exterior = _clean_ring([tuple(p[:2]) for p in poly.exterior.coords])
                hole_rings = [_clean_ring([tuple(p[:2]) for p in ring.coords])
                              for ring in poly.interiors]
                hole_rings = [h for h in hole_rings if len(h) >= 3]
                if len(exterior) < 3:
                    continue

                # One shared id per ring corner per level: caps and swept
                # walls meet at the same positions.
                exterior_bot, exterior_top = self._level_ids(
                    exterior, bottom, top, height)
                holes_bot_top = [self._level_ids(hole, bottom, top, height)
                                 for hole in hole_rings]
                flat_bot = list(exterior_bot) + [i for hb, _ in holes_bot_top
                                                 for i in hb]
                flat_top = list(exterior_top) + [i for _, ht in holes_bot_top
                                                 for i in ht]

                def cap_uv(corners):
                    return self._cap_uvs(corners, uv_scale)

                # Constrained caps (earcut): top CCW viewed from +Z (normal
                # +Z, same winding as the legacy emission), bottom reversed.
                verts2d, cap_tris = triangulate_rings(exterior, hole_rings)
                for flat, want_ccw in ((flat_top, True), (flat_bot, False)):
                    for a, b, c in _oriented(cap_tris, verts2d, want_ccw):
                        ids = [flat[a], flat[b], flat[c]]
                        corners = [self._open.positions[v] for v in ids]
                        self.tri(*ids, cap_uv(corners), mat_idx)

                # Swept walls, ring by ring. Order (A1,B1,B2)/(A1,B2,A2) keeps
                # the legacy winding: outward normals on exterior rings, faces
                # looking into the void on hole rings.
                rings = ([(exterior, exterior_bot, exterior_top)] +
                         [(hole, hb, ht) for hole, (hb, ht) in
                          zip(hole_rings, holes_bot_top)])
                for pts, bots, tops in rings:
                    n = len(pts)
                    for e in range(n):
                        f = (e + 1) % n
                        A1, B1, B2, A2 = bots[e], bots[f], tops[f], tops[e]
                        (uA, zbA), (uB, zbB), (_, ztB), (_, ztA) = (
                            self._wall_edge_uv(
                                self._open.positions[A1], self._open.positions[B1],
                                self._open.positions[B2], self._open.positions[A2],
                                facade_origin, facade_tangent, facade_normal,
                                uv_scale))
                        self.tri(A1, B1, B2, ((uA, zbA), (uB, zbB), (uB, ztB)),
                                 mat_idx)
                        self.tri(A1, B2, A2, ((uA, zbA), (uB, ztB), (uA, ztA)),
                                 mat_idx)
        finally:
            if auto:
                self.end_component()

    @staticmethod
    def _wall_edge_uv(A1, B1, B2, A2, facade_origin, facade_tangent,
                      facade_normal, uv_scale):
        """Role-based UVs for one swept wall edge: (u along, z) per quad
        corner, matching the legacy per-triangle layout exactly."""
        (x0, y0, z0), (x1, y1, zb1) = tuple(A1)[:3], tuple(B1)[:3]
        z2 = tuple(B2)[2]
        z3 = tuple(A2)[2]
        if facade_origin is None:
            uA, uB = 0.0, float(np.hypot(x1 - x0, y1 - y0))
        else:
            fo = np.asarray(facade_origin, float)
            ft = np.asarray(facade_tangent, float)
            fn = np.asarray(facade_normal, float)
            edge_vec = np.array([x1 - x0, y1 - y0])
            if abs(np.dot(edge_vec, ft)) > abs(np.dot(edge_vec, fn)):
                uA = float(np.dot(np.array([x0, y0]) - fo, ft))
                uB = float(np.dot(np.array([x1, y1]) - fo, ft))
            else:
                uA, uB = 0.0, float(np.linalg.norm(edge_vec))
        uA, uB = uA / uv_scale, uB / uv_scale
        return ((uA, z0 / uv_scale), (uB, zb1 / uv_scale),
                (uB, z2 / uv_scale), (uA, z3 / uv_scale))

    def _level_ids(self, coords, bottom, top, height):
        bots = [self.vert((x, y, height(bottom, (x, y)))) for x, y in coords]
        tops = [self.vert((x, y, height(top, (x, y)))) for x, y in coords]
        return bots, tops

    # ── box() with a true chamfer ───────────────────────────────

    def box(self, a, t, n, u1, u2, z1, z2, w1, w2,
            material="plaster", semantic="wall",
            *, uv_origin_u=None, clip="auto", chamfer=0.0):
        """Axis-aligned box in facade-local coordinates.

        uv_origin_u: accepted for backward compatibility (legacy callers never
        set it to anything the emission path consumed).

        chamfer: breaks the top arris with a real diagonal band. A cornice or
        a coping with a mathematically sharp edge catches no highlight and
        reads as a printed line under flat lighting, which is how a city block
        is viewed. Unlike two stacked boxes, the chamfered shell is closed and
        has no coincident interior faces.
        """
        if min(u2 - u1, z2 - z1, w2 - w1) <= 1e-7:
            return
        if chamfer > 0 and z2 - z1 > 3 * chamfer and \
                min(u2 - u1, w2 - w1) > 3 * chamfer:
            self._chamfered_box(a, t, n, u1, u2, z1, z2, w1, w2,
                                material, semantic, chamfer, clip)
            return

        a = np.asarray(a, float)
        t = np.asarray(t, float)
        n = np.asarray(n, float)

        shape = Polygon([
            a + u * t + w * n
            for u, w in [(u1, w1), (u2, w1), (u2, w2), (u1, w2)]
        ])

        # Get material scale
        mat_dict = self.materials[self.material_index[material]]
        uv_scale = mat_dict.get("real_scale_m", 1.0)

        # Facade origin for UV: the (0,0) point in facade space
        facade_origin = a[:2]
        facade_tangent = t[:2]
        tlen = np.linalg.norm(facade_tangent)
        if tlen > 1e-8:
            facade_tangent = facade_tangent / tlen

        self.solid(
            shape, z1, z2, material, semantic,
            facade_origin=facade_origin,
            facade_tangent=facade_tangent,
            facade_normal=n[:2] / np.linalg.norm(n[:2]) if np.linalg.norm(n[:2]) > 1e-8 else n[:2],
            uv_scale=uv_scale,
            clip=clip,
        )

    def _chamfered_box(self, a, t, n, u1, u2, z1, z2, w1, w2,
                       material, semantic, chamfer, clip):
        """One closed 12-position shell: bottom, four sides, a diagonal bevel
        band and an inset top. No stacked boxes, no interior faces."""
        mat_idx = self.mat_index(material)
        uv_scale = self.uv_scale_for(material)
        auto = self._ensure_component(semantic)
        try:
            a = np.asarray(a, float)
            t = np.asarray(t, float) / np.linalg.norm(t)
            n = np.asarray(n, float) / np.linalg.norm(n)
            c = chamfer
            zt = z2 - c

            def P(u, w, z):
                xy = a + t * u + n * w
                return self.vert((float(xy[0]), float(xy[1]), float(z)))

            B = [P(u1, w1, z1), P(u2, w1, z1), P(u2, w2, z1), P(u1, w2, z1)]
            T = [P(u1, w1, zt), P(u2, w1, zt), P(u2, w2, zt), P(u1, w2, zt)]
            I = [P(u1 + c, w1 + c, z2), P(u2 - c, w1 + c, z2),
                 P(u2 - c, w2 - c, z2), P(u1 + c, w2 - c, z2)]

            def wuv(u, z):
                return self._uv_for_wall(u, z, uv_scale)

            # Bottom (normal -Z).
            self.quad(B[0], B[3], B[2], B[1],
                      [wuv(u1, z1), wuv(u1, z1), wuv(u2, z1), wuv(u2, z1)], mat_idx)
            # Side k spans corner k -> k+1 at (z1..zt). Winding matches the
            # legacy box walls: (low_a, low_b, high_b) / (low_a, high_b, high_a).
            for k in range(4):
                l0, l1, h1, h0 = B[k], B[(k + 1) % 4], T[(k + 1) % 4], T[k]
                uu = (u1, u2, u2, u1)[k], (u2, u2, u1, u1)[k]
                self.quad(l0, l1, h1, h0,
                          [wuv(uu[0], z1), wuv(uu[1], z1),
                           wuv(uu[1], zt), wuv(uu[0], zt)], mat_idx)
            # Bevel band: outer top ring -> inset top ring.
            for k in range(4):
                o0, o1, i1, i0 = T[k], T[(k + 1) % 4], I[(k + 1) % 4], I[k]
                uu = (u1, u2, u2, u1)[k], (u2, u2, u1, u1)[k]
                self.quad(o0, o1, i1, i0,
                          [wuv(uu[0], zt), wuv(uu[1], zt),
                           wuv(uu[1], z2), wuv(uu[0], z2)], mat_idx)
            # Inset top cap.
            tuvs = self._cap_uvs([self._open.positions[v] for v in (I[0], I[1], I[2])],
                                 uv_scale)
            self.tri(I[0], I[1], I[2], tuvs, mat_idx)
            tuvs = self._cap_uvs([self._open.positions[v] for v in (I[0], I[2], I[3])],
                                 uv_scale)
            self.tri(I[0], I[2], I[3], tuvs, mat_idx)
        finally:
            if auto:
                self.end_component()

    def beam(self, a, b, radius=0.018, material="metal", semantic="rail", *, clip="auto"):
        """Closed indexed cylinder between two points; ring vertices are shared
        between the side faces and both end caps. One beam is one component:
        connected, closed and 2-manifold."""
        mat_idx = self.mat_index(material)
        a, b = np.array(a, float), np.array(b, float)
        direction = b - a
        length = np.linalg.norm(direction)
        if length < 1e-8:
            return
        direction /= length
        axis = np.eye(3)[np.argmin(np.abs(direction))]
        u = np.cross(direction, axis)
        u /= np.linalg.norm(u)
        v = np.cross(direction, u)
        from shapely.geometry import MultiPoint

        ring_probe = radius * (np.cos(np.arange(8) * np.pi / 4)[:, None] * u +
                               np.sin(np.arange(8) * np.pi / 4)[:, None] * v)
        hull_points = np.vstack((a + ring_probe, b + ring_probe, a[None], b[None]))
        if not self.limit_for(semantic, clip).covers(
                MultiPoint(hull_points[:, :2]).convex_hull):
            return
        auto = self._ensure_component(semantic)
        try:
            mat_dict = self.materials[mat_idx]
            uv_scale = mat_dict.get("real_scale_m", 1.0)
            angles = np.arange(8) * np.pi / 4
            ring = radius * (np.cos(angles)[:, None] * u + np.sin(angles)[:, None] * v)
            ring_a = [self.vert(tuple(a + off)) for off in ring]
            ring_b = [self.vert(tuple(b + off)) for off in ring]
            cap_a = self.vert(tuple(a))
            cap_b = self.vert(tuple(b))
            circumference = 2 * np.pi * radius

            for i in range(8):
                j = (i + 1) % 8
                u_i = (i / 8) * circumference / uv_scale
                u_j = ((i + 1) / 8) * circumference / uv_scale
                v0, v1 = 0.0, length / uv_scale
                self.quad(ring_a[i], ring_a[j], ring_b[j], ring_b[i],
                          [(u_i, v0), (u_j, v0), (u_j, v1), (u_i, v1)], mat_idx)
                cap_uv_a = (radius * np.cos(angles[i]) / uv_scale,
                            radius * np.sin(angles[i]) / uv_scale)
                cap_uv_j = (radius * np.cos(angles[j]) / uv_scale,
                            radius * np.sin(angles[j]) / uv_scale)
                self.tri(cap_a, ring_a[j], ring_a[i],
                         [(0, 0), cap_uv_j, cap_uv_a], mat_idx)
                self.tri(cap_b, ring_b[i], ring_b[j],
                         [(0, 0), cap_uv_a, cap_uv_j], mat_idx)
        finally:
            if auto:
                self.end_component()

    def foliage(self, center, radii, rng, segments=10, rings=5, *, semantic="shrub",
                clip="auto"):
        """Closed low-poly ellipsoid with seeded, gently irregular leaf clusters.
        Rings share their vertices; poles are single shared ids."""
        from shapely.geometry import MultiPoint

        center, radii = np.asarray(center), np.asarray(radii)
        rows = []
        rows.append([np.array([0.0, 0.0, 1.0])])
        for i in range(1, rings + 1):
            phi = np.pi * i / (rings + 1)
            row = []
            for j in range(segments):
                theta = 2 * np.pi * j / segments
                r = rng.uniform(0.90, 1.10)
                row.append(r * np.array([np.sin(phi) * np.cos(theta),
                                         np.sin(phi) * np.sin(theta),
                                         np.cos(phi)]))
            rows.append(row)
        rows.append([np.array([0.0, 0.0, -1.0])])
        unit = [p for row in rows for p in row]
        verts = np.asarray(unit) * radii + center
        if not self.limit_for(semantic, clip).covers(MultiPoint(verts[:, :2]).convex_hull):
            return
        auto = self._ensure_component(semantic)
        try:
            mat_idx = self.material_index["leaf"]
            ids = [self.vert(tuple(v)) for v in verts]

            def uv_of(k, total):
                return (k / segments, 1 - total / (rings + 1))

            top, bottom = ids[0], ids[-1]
            # Top fan.
            for j in range(segments):
                k = (j + 1) % segments
                self.tri(top, ids[1 + j], ids[1 + k],
                         [(0.5, 1.0), uv_of(j, 1), uv_of(k, 1)], mat_idx)
            # Middle rings.
            for i in range(rings - 1):
                upper = 1 + i * segments
                lower = 1 + (i + 1) * segments
                for j in range(segments):
                    k = (j + 1) % segments
                    self.quad(ids[upper + j], ids[lower + j],
                              ids[lower + k], ids[upper + k],
                              [uv_of(j, i + 1), uv_of(j, i + 2),
                               uv_of(k, i + 2), uv_of(k, i + 1)], mat_idx)
            # Bottom fan.
            last = 1 + (rings - 1) * segments
            for j in range(segments):
                k = (j + 1) % segments
                self.tri(bottom, ids[last + k], ids[last + j],
                         [(0.5, 0.0), uv_of(k, rings), uv_of(j, rings)], mat_idx)
        finally:
            if auto:
                self.end_component()

    def panel(self, a, t, n, polys_uz, w1, w2, mat_fn, semantic,
              component_id=None, assembly_id=None, *, clip="auto",
              max_segment_m=0.0, cuts_u=(), cuts_z=(), depth_fn=None):
        """Extrude (u, z) polygons along the facade normal into a closed shell.

        ``polys_uz`` are shapely Polygons in facade-local metres (u along the
        wall from vertex_a, z up). Holes stay holes: a wall with five openings
        is one shell with five real voids, not a puzzle of boxes. Faces take
        their material from ``mat_fn(kind, u, v, w)`` with kind in
        {"front", "back", "side"} over face midpoints, so one shell can carry
        several finish zones without splitting.

        ``cuts_u``/``cuts_z`` are required grid lines (material edges, depth
        steps): no triangle ever crosses them, so classification by region is
        exact. ``depth_fn(u, v)`` gives the front depth per cell (default
        w2); neighbors at different depths join through step connectors.

        Clipping runs along the facade axis: the wall line at mid-depth is
        intersected with the cadastral limit and the (u, z) domain is cut to
        the covered u-intervals. Exact for thin extrusions and wall shells,
        which only ever overrun at their ends.

        max_segment_m subdivides long straight boundary runs with collinear
        Steiner vertices (wall shells only): triangulation ears stay local
        instead of spanning the whole facade. Geometry is unchanged.
        """
        a = np.asarray(a, float)
        t = np.asarray(t, float) / np.linalg.norm(t)
        n = np.asarray(n, float) / np.linalg.norm(n)
        if w2 - w1 <= 1e-7:
            return None
        doms = [p for p in polys_uz
                if p is not None and not p.is_empty and p.area > 1e-10]
        if not doms:
            return None
        u0 = min(p.bounds[0] for p in doms)
        u1 = max(p.bounds[2] for p in doms)
        wmid = 0.5 * (w1 + w2)
        limit = self.limit_for(semantic, clip)
        probe = LineString([a + t * (u0 - 1.0) + n * wmid,
                            a + t * (u1 + 1.0) + n * wmid])
        hit = probe.intersection(limit)
        if hit.is_empty:
            return None
        origin = a + t * (u0 - 1.0) + n * wmid

        def to_u(point):
            return (u0 - 1.0) + float(np.dot(np.asarray(point[:2]) - origin[:2], t))

        spans = []
        geoms = list(hit.geoms) if hit.geom_type == "MultiLineString" else [hit]
        for g in geoms:
            if g.geom_type != "LineString" or g.length < 1e-9:
                continue
            c = list(g.coords)
            spans.append((to_u(c[0]), to_u(c[-1])))
        spans = [(min(s, e), max(s, e)) for s, e in spans]
        if not spans or max(e for _, e in spans) < u1 - 1e-9 or \
                min(s for s, _ in spans) > u0 + 1e-9:
            clipped = []
            for poly in doms:
                for s, e in spans:
                    if e - s > 1e-9:
                        clipped.append(poly.intersection(
                            Polygon([(s, -1e6), (e, -1e6), (e, 1e6), (s, 1e6)])))
            doms = [p for p in clipped
                    if p is not None and not p.is_empty and p.area > 1e-10]
            if not doms:
                return None

        self.begin_component(semantic, component_id, assembly_id)
        try:
            for poly in polygons(shapely.unary_union(doms)) if len(doms) > 1 \
                    else polygons(doms[0]):
                if max_segment_m > 0:
                    poly = Polygon(
                        _subdivide_ring(list(poly.exterior.coords),
                                        max_segment_m),
                        [_subdivide_ring(list(ring.coords), max_segment_m)
                         for ring in poly.interiors])
                self._panel_poly(a, t, n, poly, w1, w2, mat_fn, cuts_u,
                                 cuts_z, depth_fn)
        finally:
            return self.end_component()

    def _panel_poly(self, a, t, n, poly, w1, w2, mat_fn, cuts_u=(),
                    cuts_z=(), depth_fn=None):
        comp = self._open

        def W(u, w, z):
            xy = a + t * u + n * w
            return self.vert((float(xy[0]), float(xy[1]), float(z)))

        def scale_of(slot):
            return self.uv_scale_for(slot)

        if _is_rectilinear(poly):
            self._panel_rectilinear(a, t, n, poly, w1, w2, mat_fn, W,
                                    scale_of, cuts_u, cuts_z, depth_fn)
            return

        rings = _clean_ring([tuple(p[:2]) for p in poly.exterior.coords])
        holes = [_clean_ring([tuple(p[:2]) for p in ring.coords])
                 for ring in poly.interiors]
        holes = [h for h in holes if len(h) >= 3]
        if len(rings) < 3:
            return
        ids_w1 = [W(u, w1, z) for u, z in rings]
        ids_w2 = [W(u, w2, z) for u, z in rings]
        hole_ids = [([W(u, w1, z) for u, z in h], [W(u, w2, z) for u, z in h])
                    for h in holes]
        flat_w1 = list(ids_w1) + [i for h in hole_ids for i in h[0]]
        flat_w2 = list(ids_w2) + [i for h in hole_ids for i in h[1]]

        def at(u, z, w):
            # vert() shares by position, so corners computed for caps and
            # swept sides resolve to the same ids.
            return W(u, w, z)

        # Constrained caps (earcut): every triangle lies inside the domain,
        # none crosses a hole. Front (w2) CCW in (u, z) faces +n; back
        # reversed. Orientation is enforced, never filtered.
        verts2d, cap_tris = triangulate_rings(rings, holes)
        for w, want_ccw, kind in ((w2, True, "front"), (w1, False, "back")):
            flat = flat_w2 if w == w2 else flat_w1
            for a, b, c in _oriented(cap_tris, verts2d, want_ccw):
                ids = [flat[a], flat[b], flat[c]]
                (ua, va), (ub, vb), (uc, vc) = verts2d[a], verts2d[b], verts2d[c]
                slot = mat_fn(kind, (ua + ub + uc) / 3.0, (va + vb + vc) / 3.0, w)
                mi = self.mat_index(slot)
                s = scale_of(slot)
                self.tri(*ids, ((ua / s, va / s), (ub / s, vb / s),
                                (uc / s, vc / s)), mi)

        # Swept sides: outer boundary and hole reveals. Corners carry
        # (edge distance, w) metric UVs; materials come from the callback
        # evaluated at the edge midpoint.
        for coords, _ in [rings] + holes:
            m = len(coords)
            edge_len = [0.0]
            for (u0, z0), (u1, z1) in zip(coords, coords[1:] + coords[:1]):
                edge_len.append(edge_len[-1] + float(np.hypot(u1 - u0, z1 - z0)))
            for e in range(m):
                (ua, za), (ub, zb) = coords[e], coords[(e + 1) % m]
                sa, sb = edge_len[e], edge_len[e + 1]
                A1, B1, B2, A2 = (at(ua, za, w1), at(ub, zb, w1),
                                  at(ub, zb, w2), at(ua, za, w2))
                slot = mat_fn("side", (ua + ub) / 2.0, (za + zb) / 2.0,
                              0.5 * (w1 + w2))
                mi = self.mat_index(slot)
                s = scale_of(slot)
                self.tri(A1, B1, B2,
                         ((sa / s, w1 / s), (sb / s, w1 / s), (sb / s, w2 / s)),
                         mi)
                self.tri(A1, B2, A2,
                         ((sa / s, w1 / s), (sb / s, w2 / s), (sa / s, w2 / s)),
                         mi)

    def _panel_rectilinear(self, a, t, n, poly, w1, w2, mat_fn, W,
                               scale_of, cuts_u, cuts_z, depth_fn):
        """One stepped shell over an exact grid tiling.

        Grid lines contain hole edges plus caller cuts (material edges, depth
        steps), so no triangle ever crosses a region boundary: material and
        depth are constant per cell. Each cell extrudes from the common back
        plane w1 to its own front depth; neighbors at different depths join
        through a step connector quad, oriented like the shallow side so both
        neighboring caps stay coherent. Shared
        corners resolve through W(): one connected manifold shell carrying
        several materials, with 15 mm steps instead of coincident internal
        walls.
        """
        subs = []
        for x0, x1, z0, z1 in _rectilinear_cells(poly, cuts_u, cuts_z):
            d = depth_fn((x0 + x1) / 2.0, (z0 + z1) / 2.0) if depth_fn else w2
            subs.append((x0, x1, z0, z1, d))
        depths = tuple(sorted({d for _, _, _, _, d in subs}))
        edge_cells = {}
        for i, (xa, xb, za, zb, d) in enumerate(subs):
            for key in (((xa, za), (xb, za)), ((xb, za), (xb, zb)),
                        ((xb, zb), (xa, zb)), ((xa, zb), (xa, za))):
                undirected = key if key[0] <= key[1] else (key[1], key[0])
                edge_cells.setdefault(undirected, []).append((i, key))
        for xa, xb, za, zb, d in subs:
            A, B, C, D = ((xa, za), (xb, za), (xb, zb), (xa, zb))
            for w, flip, kind in ((d, False, "front"), (w1, True, "back")):
                order = (A, B, C) if not flip else (A, C, B)
                order2 = (A, C, D) if not flip else (A, D, C)
                for tri in (order, order2):
                    (ua, va), (ub, vb), (uc, vc) = tri
                    ids = [W(ua, w, va), W(ub, w, vb), W(uc, w, vc)]
                    slot = mat_fn(kind, (ua + ub + uc) / 3.0,
                                  (va + vb + vc) / 3.0, w)
                    s = scale_of(slot)
                    self.tri(*ids, ((ua / s, va / s), (ub / s, vb / s),
                                    (uc / s, vc / s)),
                             self.mat_index(slot))
        for edge, members in edge_cells.items():
            if len(members) == 1:
                (i, key) = members[0]
                self._side_strip(W, mat_fn, scale_of, subs, key[0], key[1],
                                 w1, subs[i][4], depths)
            elif len(members) == 2:
                (i, ki), (j, kj) = members
                di, dj = subs[i][4], subs[j][4]
                if abs(di - dj) <= 1e-12:
                    continue
                # Shallow cell's side direction: the connector traverses
                # E@shallow with it (opposing the shallow cap) and E@deep
                # reversed (opposing the deep cap). Deep direction would
                # agree with both caps instead.
                shallow = j if dj > di else i
                (ua, za), (ub, zb) = self._side_dir(subs[shallow], edge)
                self._side_strip(W, mat_fn, scale_of, subs,
                                 (ua, za), (ub, zb),
                                 max(di, dj), min(di, dj), depths)

    @staticmethod
    def _side_dir(subrect, edge):
        """The subrect's own traversal direction of one of its sides."""
        xa, xb, za, zb, _ = subrect
        sides = [((xa, za), (xb, za)), ((xb, za), (xb, zb)),
                 ((xb, zb), (xa, zb)), ((xa, zb), (xa, za))]
        undirected = edge if edge[0] <= edge[1] else (edge[1], edge[0])
        for side in sides:
            if (side[0] <= side[1] and (side[0], side[1]) == undirected) or \
               (side[1] <= side[0] and (side[1], side[0]) == undirected):
                return side
        return (edge[0], edge[1])

    def _side_strip(self, W, mat_fn, scale_of, subs, pa, pb, w_lo, w_hi,
                      depths=()):
        """Swept strip between two w levels along directed edge pa->pb.

        Stations include every subrect corner on the path, so swept quads
        share all cap corners (no dangling); winding follows pa->pb. Side
        edges additionally split at every intermediate wall depth, so a
        strip abutting a step pairs exactly with the step connector
        instead of dangling over it.
        """
        (ua, za), (ub, zb) = pa, pb
        stations = {pa, pb}
        for xa, xb, zc, zd, _ in subs:
            for cx, cz in ((xa, zc), (xb, zc), (xb, zd), (xa, zd)):
                if abs((ub - ua) * (cz - za) - (zb - za) * (cx - ua)) > 1e-9:
                    continue
                s = ((cx - ua) * (ub - ua) + (cz - za) * (zb - za))
                e = (ub - ua) ** 2 + (zb - za) ** 2
                if -1e-9 <= s <= e + 1e-9:
                    stations.add((cx, cz))
        levels = sorted({w_lo, w_hi} | {w for w in depths
                                        if min(w_lo, w_hi) < w < max(w_lo, w_hi)})
        horizontal = abs(zb - za) <= abs(ub - ua)
        ordered = sorted(stations,
                         key=lambda p: p[0] if horizontal else p[1])
        if (ua, za) != ordered[0]:
            ordered = ordered[::-1]
        for sa, sb in zip(ordered, ordered[1:]):
            for wa, wb in zip(levels, levels[1:]):
                A1, B1 = W(sa[0], wa, sa[1]), W(sb[0], wa, sb[1])
                B2, A2 = W(sb[0], wb, sb[1]), W(sa[0], wb, sa[1])
                slot = mat_fn("side", (sa[0] + sb[0]) / 2.0,
                              (sa[1] + sb[1]) / 2.0, 0.5 * (wa + wb))
                mi = self.mat_index(slot)
                s = scale_of(slot)
                # Metric along the edge from its directed start.
                if horizontal:
                    la, lb = sa[0] - ua, sb[0] - ua
                else:
                    la, lb = sa[1] - za, sb[1] - za
                self.tri(A1, B1, B2,
                         ((la / s, wa / s), (lb / s, wa / s),
                          (lb / s, wb / s)), mi)
                self.tri(A1, B2, A2,
                         ((la / s, wa / s), (lb / s, wb / s),
                          (la / s, wb / s)), mi)
    def finish(self):
        verts = np.asarray(self.vertices, float).reshape(-1, 3)
        uv = np.asarray(self.uvs, float).reshape(-1, 2) if self.uvs else None
        corner = (np.asarray(
            [[uv for uv in face] for face in self.corner_uvs],
            float).reshape(-1, 3, 2) if self.corner_uvs else None)
        return MeshData(
            verts,
            np.asarray(self.faces, int).reshape(-1, 3),
            uv=uv,
            corner_uv=corner,
            face_materials=np.asarray(self.face_materials, int),
            materials=tuple(self.materials),
            parts=tuple(self.parts),
            components=tuple(self.components),
        )
