"""Closed component solids clipped in XY to their cadastral envelope.

Components form an architectural assembly, not a Boolean-unioned manifold.
Constrained triangulation preserves concavities and courtyard holes.

UV coordinates are metric: UV = (world_distance / texture_scale).
Vertices are duplicated at UV seams and hard edges so normals and UVs
are independent per face-corner.
"""

import numpy as np
from shapely import constrained_delaunay_triangles
from shapely.geometry import Polygon
from shapely.geometry.polygon import orient
from domain import BuildingAppearance, MeshData
from .materials import material_to_dict, resolve_materials


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
    """Return CCW constrained triangles, including polygons with holes."""
    for triangle in constrained_delaunay_triangles(polygon).geoms:
        yield np.array(orient(triangle, sign=1).exterior.coords)[:3, :2]


class MeshBuilder:
    def __init__(self, parcel, appearance=BuildingAppearance()):
        self.parcel = parcel
        # Per-face-vertex storage: every face gets its own 3 vertex slots.
        # This gives clean UV seams and hard normals at every edge.
        self.vertices = []   # list of (x, y, z)
        self.uvs = []        # list of (u, v) — one per vertex
        self.faces = []      # list of (i, j, k) — indices into vertices/uvs
        self.face_materials = []
        self.parts = []
        self.materials = [material_to_dict(m) for m in resolve_materials(appearance)]
        self.material_index = {m["name"]: i for i, m in enumerate(self.materials)}

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

    # ── Core primitive: emit one triangle with explicit UVs ──────────

    def _emit_face(self, points_xyz, uvs, material_idx):
        """Append one triangle.  Each call duplicates vertices for hard edges."""
        base = len(self.vertices)
        for (x, y, z), (u, v) in zip(points_xyz, uvs):
            self.vertices.append((float(x), float(y), float(z)))
            self.uvs.append((float(u), float(v)))
        self.faces.append((base, base + 1, base + 2))
        self.face_materials.append(material_idx)

    # ── solid() with metric UV ──────────────────────────────────────

    def solid(self, shape, bottom, top, material="plaster", semantic="wall",
              *, facade_origin=None, facade_tangent=None, facade_normal=None, uv_scale=1.0):
        """Extrude polygon between scalar or affine height fields.

        If facade_origin and facade_tangent are given, wall UVs are
        measured along the facade tangent from that origin.  Otherwise,
        wall UVs fall back to edge-local distance.

        Cap UVs (top / bottom) are always world XY / uv_scale.
        """
        if material not in self.material_index:
            raise ValueError(f"Unknown material slot: {material}")
        mat_idx = self.material_index[material]
        start = len(self.faces)

        def height(value, xy):
            return value(*xy) if callable(value) else value

        clipped = shape.intersection(self.parcel)
        for poly in polygons(clipped):
            coords = np.array(poly.exterior.coords)[:, :2]
            if any(height(top, p) <= height(bottom, p) for p in coords):
                raise ValueError("Solid must have positive thickness everywhere")

            # ── Cap faces (top and bottom) ──
            for tri in triangles(poly):
                # Top cap
                pts_top = [(x, y, height(top, (x, y))) for x, y in tri]
                self._emit_face(pts_top, self._cap_uvs(pts_top, uv_scale), mat_idx)

                # Bottom cap (reversed winding)
                pts_bot = [(x, y, height(bottom, (x, y))) for x, y in tri[::-1]]
                self._emit_face(pts_bot, self._cap_uvs(pts_bot, uv_scale), mat_idx)

            # ── Wall faces ──
            for ring in [poly.exterior, *poly.interiors]:
                points = list(ring.coords)
                for a, b in zip(points[:-1], points[1:]):
                    ax, ay = a[:2]
                    bx, by = b[:2]

                    # Compute u_along for this edge
                    if facade_origin is not None and facade_tangent is not None and facade_normal is not None:
                        fo = np.asarray(facade_origin, float)
                        ft = np.asarray(facade_tangent, float)
                        fn = np.asarray(facade_normal, float)
                        edge_vec = np.array([bx - ax, by - ay])
                        
                        # Project onto either tangent or normal depending on which is dominant
                        if abs(np.dot(edge_vec, ft)) > abs(np.dot(edge_vec, fn)):
                            u_a = float(np.dot(np.array([ax, ay]) - fo, ft))
                            u_b = float(np.dot(np.array([bx, by]) - fo, ft))
                        else:
                            u_a = float(np.dot(np.array([ax, ay]) - fo, fn))
                            u_b = float(np.dot(np.array([bx, by]) - fo, fn))
                    else:
                        # Edge-local: a is 0, b is edge length
                        u_a = 0.0
                        u_b = float(np.hypot(bx - ax, by - ay))

                    z_bot_a = height(bottom, (ax, ay))
                    z_bot_b = height(bottom, (bx, by))
                    z_top_a = height(top, (ax, ay))
                    z_top_b = height(top, (bx, by))

                    p = (ax, ay, z_bot_a)
                    q = (bx, by, z_bot_b)
                    r = (bx, by, z_top_b)
                    s = (ax, ay, z_top_a)

                    # Triangle 1: p, q, r
                    self._emit_face(
                        [p, q, r],
                        [
                            self._uv_for_wall(u_a, z_bot_a, uv_scale),
                            self._uv_for_wall(u_b, z_bot_b, uv_scale),
                            self._uv_for_wall(u_b, z_top_b, uv_scale),
                        ],
                        mat_idx,
                    )
                    # Triangle 2: p, r, s
                    self._emit_face(
                        [p, r, s],
                        [
                            self._uv_for_wall(u_a, z_bot_a, uv_scale),
                            self._uv_for_wall(u_b, z_top_b, uv_scale),
                            self._uv_for_wall(u_a, z_top_a, uv_scale),
                        ],
                        mat_idx,
                    )

        if len(self.faces) > start:
            self.parts.append({
                "name": semantic,
                "face_start": start,
                "face_count": len(self.faces) - start,
            })

    # ── box() with facade-aligned UV ────────────────────────────────

    def box(self, a, t, n, u1, u2, z1, z2, w1, w2,
            material="plaster", semantic="wall",
            *, uv_origin_u=None):
        """Axis-aligned box in facade-local coordinates.

        uv_origin_u: if set, UV u-coordinate is measured from this
        facade-absolute value rather than from u1, giving continuity
        across neighbouring boxes that share the same facade.
        """
        if min(u2 - u1, z2 - z1, w2 - w1) <= 1e-7:
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
        )

    def beam(self, a, b, radius=0.018, material="metal", semantic="rail"):
        """Round beam; reject rather than leave any triangle outside the parcel."""
        if material not in self.material_index:
            raise ValueError(f"Unknown material slot: {material}")
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
        angles = np.arange(8) * np.pi / 4
        ring = radius * (np.cos(angles)[:, None] * u + np.sin(angles)[:, None] * v)
        verts = np.vstack((a + ring, b + ring, a[None], b[None]))
        from shapely.geometry import MultiPoint

        if not self.parcel.covers(MultiPoint(verts[:, :2]).convex_hull):
            return

        mat_idx = self.material_index[material]
        mat_dict = self.materials[mat_idx]
        uv_scale = mat_dict.get("real_scale_m", 1.0)
        start = len(self.faces)
        circumference = 2 * np.pi * radius

        for i in range(8):
            j = (i + 1) % 8
            # UV for beam: u = angle fraction * circumference, v = length along beam
            u_i = (i / 8) * circumference / uv_scale
            u_j = (j / 8) * circumference / uv_scale
            v0 = 0.0
            v1 = length / uv_scale

            # Side quad: two triangles
            self._emit_face(
                [tuple(verts[i]), tuple(verts[j]), tuple(verts[j + 8])],
                [(u_i, v0), (u_j, v0), (u_j, v1)],
                mat_idx,
            )
            self._emit_face(
                [tuple(verts[i]), tuple(verts[j + 8]), tuple(verts[i + 8])],
                [(u_i, v0), (u_j, v1), (u_i, v1)],
                mat_idx,
            )
            # End caps
            self._emit_face(
                [tuple(verts[16]), tuple(verts[j]), tuple(verts[i])],
                [(0.5, 0.5), (u_j, 0.0), (u_i, 0.0)],
                mat_idx,
            )
            self._emit_face(
                [tuple(verts[17]), tuple(verts[i + 8]), tuple(verts[j + 8])],
                [(0.5, 0.5), (u_i, 1.0), (u_j, 1.0)],
                mat_idx,
            )

        self.parts.append({
            "name": semantic,
            "face_start": start,
            "face_count": len(self.faces) - start,
        })

    def foliage(self, center, radii, rng, segments=10, rings=5):
        """Closed low-poly ellipsoid with seeded, gently irregular leaf clusters."""
        from shapely.geometry import MultiPoint

        center, radii = np.asarray(center), np.asarray(radii)
        points = [(0.0, 0.0, 1.0)]
        for i in range(1, rings + 1):
            phi = np.pi * i / (rings + 1)
            for j in range(segments):
                theta = 2 * np.pi * j / segments
                r = rng.uniform(0.90, 1.10)
                points.append(
                    tuple(
                        r
                        * np.array([
                            np.sin(phi) * np.cos(theta),
                            np.sin(phi) * np.sin(theta),
                            np.cos(phi),
                        ])
                    )
                )
        points.append((0.0, 0.0, -1.0))
        verts = np.asarray(points) * radii + center
        if not self.parcel.covers(MultiPoint(verts[:, :2]).convex_hull):
            return

        mat_idx = self.material_index["leaf"]
        start = len(self.faces)

        # Spherical UV for foliage
        for j in range(segments):
            k = (j + 1) % segments
            # Top fan
            self._emit_face(
                [tuple(verts[0]), tuple(verts[1 + j]), tuple(verts[1 + k])],
                [(0.5, 1.0), (j / segments, 1 - 1 / (rings + 1)),
                 (k / segments, 1 - 1 / (rings + 1))],
                mat_idx,
            )
            # Middle rings
            for i in range(rings - 1):
                upper = 1 + i * segments
                lower = 1 + (i + 1) * segments
                v_upper = 1 - (i + 1) / (rings + 1)
                v_lower = 1 - (i + 2) / (rings + 1)
                self._emit_face(
                    [tuple(verts[upper + j]), tuple(verts[lower + j]),
                     tuple(verts[lower + k])],
                    [(j / segments, v_upper), (j / segments, v_lower),
                     (k / segments, v_lower)],
                    mat_idx,
                )
                self._emit_face(
                    [tuple(verts[upper + j]), tuple(verts[lower + k]),
                     tuple(verts[upper + k])],
                    [(j / segments, v_upper), (k / segments, v_lower),
                     (k / segments, v_upper)],
                    mat_idx,
                )
            # Bottom fan
            last = 1 + (rings - 1) * segments
            self._emit_face(
                [tuple(verts[len(verts) - 1]), tuple(verts[last + k]),
                 tuple(verts[last + j])],
                [(0.5, 0.0), (k / segments, 1 / (rings + 1)),
                 (j / segments, 1 / (rings + 1))],
                mat_idx,
            )

        self.parts.append(
            {"name": "shrub", "face_start": start,
             "face_count": len(self.faces) - start}
        )

    def finish(self):
        verts = np.asarray(self.vertices, float).reshape(-1, 3)
        uv = np.asarray(self.uvs, float).reshape(-1, 2) if self.uvs else None
        return MeshData(
            verts,
            np.asarray(self.faces, int).reshape(-1, 3),
            uv=uv,
            face_materials=np.asarray(self.face_materials, int),
            materials=tuple(self.materials),
            parts=tuple(self.parts),
        )
