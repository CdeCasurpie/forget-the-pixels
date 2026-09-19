"""Closed component solids clipped in XY to their cadastral envelope.

Components form an architectural assembly, not a Boolean-unioned manifold.
Constrained triangulation preserves concavities and courtyard holes.
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
        self.vertices, self.faces, self.face_materials, self.parts = [], [], [], []
        self.materials = [material_to_dict(material) for material in resolve_materials(appearance)]
        self.material_index = {m["name"]: i for i, m in enumerate(self.materials)}

    def solid(self, shape, bottom, top, material="plaster", semantic="wall"):
        """Extrude polygon between scalar or affine height fields, clipping first."""
        if material not in self.material_index:
            raise ValueError(f"Unknown material slot: {material}")
        start = len(self.faces)
        local_indices = {}

        def vertex(x, y, z):
            key = (float(x), float(y), float(z))
            if key not in local_indices:
                local_indices[key] = len(self.vertices)
                self.vertices.append(key)
            return local_indices[key]

        def height(value, xy):
            return value(*xy) if callable(value) else value

        def face(points):
            self.faces.append(tuple(vertex(*p) for p in points))
            self.face_materials.append(self.material_index[material])

        clipped = shape.intersection(self.parcel)
        for poly in polygons(clipped):
            coords = np.array(poly.exterior.coords)[:, :2]
            if any(height(top, p) <= height(bottom, p) for p in coords):
                raise ValueError("Solid must have positive thickness everywhere")
            for tri in triangles(poly):
                face([(x, y, height(top, (x, y))) for x, y in tri])
                face([(x, y, height(bottom, (x, y))) for x, y in tri[::-1]])
            for ring in [poly.exterior, *poly.interiors]:
                points = list(ring.coords)
                for a, b in zip(points[:-1], points[1:]):
                    p = (*a[:2], height(bottom, a[:2]))
                    q = (*b[:2], height(bottom, b[:2]))
                    r = (*b[:2], height(top, b[:2]))
                    s = (*a[:2], height(top, a[:2]))
                    face([p, q, r])
                    face([p, r, s])
        if len(self.faces) > start:
            self.parts.append(
                {
                    "name": semantic,
                    "face_start": start,
                    "face_count": len(self.faces) - start,
                }
            )

    def box(self, a, t, n, u1, u2, z1, z2, w1, w2, material="plaster", semantic="wall"):
        if min(u2 - u1, z2 - z1, w2 - w1) <= 1e-7:
            return
        shape = Polygon(
            [
                np.asarray(a) + u * t + w * n
                for u, w in [(u1, w1), (u2, w1), (u2, w2), (u1, w2)]
            ]
        )
        self.solid(shape, z1, z2, material, semantic)

    def beam(self, a, b, radius=0.018, material="metal", semantic="rail"):
        """Round beam; reject rather than leave any triangle outside the parcel."""
        if material not in self.material_index:
            raise ValueError(f"Unknown material slot: {material}")
        a, b = np.array(a, float), np.array(b, float)
        direction = b - a
        if np.linalg.norm(direction) < 1e-8:
            return
        direction /= np.linalg.norm(direction)
        axis = np.eye(3)[np.argmin(np.abs(direction))]
        u = np.cross(direction, axis)
        u /= np.linalg.norm(u)
        v = np.cross(direction, u)
        angles = np.arange(8) * np.pi / 4
        ring = radius * (np.cos(angles)[:, None] * u + np.sin(angles)[:, None] * v)
        vertices = np.vstack((a + ring, b + ring, a[None], b[None]))
        from shapely.geometry import MultiPoint

        if not self.parcel.covers(MultiPoint(vertices[:, :2]).convex_hull):
            return
        start, offset = len(self.faces), len(self.vertices)
        self.vertices.extend(vertices.tolist())
        for i in range(8):
            j = (i + 1) % 8
            for f in [(i, j, j + 8), (i, j + 8, i + 8), (16, j, i), (17, i + 8, j + 8)]:
                self.faces.append(tuple(offset + k for k in f))
                self.face_materials.append(self.material_index[material])
        self.parts.append(
            {
                "name": semantic,
                "face_start": start,
                "face_count": len(self.faces) - start,
            }
        )

    def foliage(self, center, radii, rng, segments=10, rings=5):
        """Closed low-poly ellipsoid with seeded, gently irregular leaf clusters."""
        from shapely.geometry import MultiPoint

        center, radii = np.asarray(center), np.asarray(radii)
        points = [(0.0, 0.0, 1.0)]
        for i in range(1, rings + 1):
            phi = np.pi * i / (rings + 1)
            for j in range(segments):
                theta = 2 * np.pi * j / segments
                radius = rng.uniform(0.90, 1.10)
                points.append(
                    tuple(
                        radius
                        * np.array(
                            [
                                np.sin(phi) * np.cos(theta),
                                np.sin(phi) * np.sin(theta),
                                np.cos(phi),
                            ]
                        )
                    )
                )
        points.append((0.0, 0.0, -1.0))
        vertices = np.asarray(points) * radii + center
        if not self.parcel.covers(MultiPoint(vertices[:, :2]).convex_hull):
            return
        faces = []
        for j in range(segments):
            k = (j + 1) % segments
            faces.append((0, 1 + j, 1 + k))
            for i in range(rings - 1):
                upper, lower = 1 + i * segments, 1 + (i + 1) * segments
                faces.extend(
                    [
                        (upper + j, lower + j, lower + k),
                        (upper + j, lower + k, upper + k),
                    ]
                )
            last = 1 + (rings - 1) * segments
            faces.append((len(vertices) - 1, last + k, last + j))
        start, offset = len(self.faces), len(self.vertices)
        self.vertices.extend(vertices.tolist())
        self.faces.extend(tuple(offset + k for k in f) for f in faces)
        self.face_materials.extend([self.material_index["leaf"]] * len(faces))
        self.parts.append(
            {"name": "shrub", "face_start": start, "face_count": len(faces)}
        )

    def finish(self):
        return MeshData(
            np.asarray(self.vertices, float).reshape(-1, 3),
            np.asarray(self.faces, int).reshape(-1, 3),
            face_materials=np.asarray(self.face_materials, int),
            materials=tuple(self.materials),
            parts=tuple(self.parts),
        )
