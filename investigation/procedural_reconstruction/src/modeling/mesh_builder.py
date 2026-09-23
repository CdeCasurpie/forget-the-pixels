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
from shapely.geometry import Polygon
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

                exterior = [tuple(p[:2]) for p in poly.exterior.coords[:-1]]
                hole_rings = [[tuple(p[:2]) for p in ring.coords[:-1]]
                              for ring in poly.interiors]

                # One shared id per ring corner per level: caps and swept
                # walls meet at the same positions.
                exterior_bot, exterior_top = self._level_ids(
                    exterior, bottom, top, height)
                holes_bot_top = [self._level_ids(hole, bottom, top, height)
                                 for hole in hole_rings]

                def cap_uv(corners):
                    return self._cap_uvs(corners, uv_scale)

                # Caps follow the constrained triangulation (holes stay holes).
                # Corner order matches the legacy emission — top as
                # triangulated, bottom reversed — so winding is unchanged.
                for tri in triangles(poly):
                    top_ids = self._map_tri(tri, "top", bottom, top, height)
                    pts_top = [self._open.positions[v] for v in top_ids]
                    self.tri(*top_ids, cap_uv(pts_top), mat_idx)
                    bot_ids = self._map_tri(tri[::-1], "bottom", bottom, top,
                                            height)
                    pts_bot = [self._open.positions[v] for v in bot_ids]
                    self.tri(*bot_ids, cap_uv(pts_bot), mat_idx)

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

    def _map_tri(self, tri, level, bottom, top, height):
        """Ids for triangulation corners, reusing ring positions when the
        corner is one (the common case: constrained Delaunay only emits input
        vertices), else creating the corner (legacy behavior per triangle)."""
        field = bottom if level == "bottom" else top
        ids = []
        for x, y in tri:
            key = _pos_key((x, y, height(field, (x, y))))
            known = self._open.pos_index.get(key)
            ids.append(known if known is not None
                       else self.vert((x, y, height(field, (x, y)))))
        return ids[0], ids[1], ids[2]

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
