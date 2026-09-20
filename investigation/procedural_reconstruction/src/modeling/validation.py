"""Geometry checks on generated triangles rather than vertex-only containment."""

import numpy as np
import shapely


def validate_mesh(mesh, parcel):
    if not np.isfinite(mesh.vertices).all():
        raise ValueError("Nonfinite vertices")
    if (
        not len(mesh.faces)
        or mesh.faces.min() < 0
        or mesh.faces.max() >= len(mesh.vertices)
    ):
        raise ValueError("Invalid indices")
    tri = mesh.vertices[mesh.faces]
    areas = (
        np.linalg.norm(np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]), axis=1)
        / 2
    )
    if (areas < 1e-13).any():
        raise ValueError("Degenerate faces")
    projected = shapely.polygons(tri[:, :, :2])
    outside = shapely.area(shapely.difference(projected, parcel))
    # Vertical triangles have zero projected area: separately check their edges.
    lines = shapely.linestrings(np.concatenate([tri[:, :, :2], tri[:, :1, :2]], axis=1))
    violations = shapely.length(shapely.difference(lines, parcel.buffer(1e-7)))
    if outside.max() > 1e-7 or violations.max() > 1e-6:
        raise ValueError("Geometry outside cadastral envelope")
    if mesh.face_materials is None or len(mesh.face_materials) != len(mesh.faces):
        raise ValueError("Missing material assignments")
    if mesh.face_materials.min() < 0 or mesh.face_materials.max() >= len(
        mesh.materials
    ):
        raise ValueError("Invalid material indices")
    return {
        "vertices": len(mesh.vertices),
        "triangles": len(mesh.faces),
        "parts": len(mesh.parts),
        "semantic_types": sorted({p["name"] for p in mesh.parts}),
        "max_outside_triangle_area_m2": float(outside.max()),
        "min_triangle_area_m2": float(areas.min()),
        "envelope_test": "passed",
        "topology": "assembly of intersecting closed components; not Boolean-unioned",
    }
