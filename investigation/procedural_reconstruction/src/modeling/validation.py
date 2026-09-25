"""Geometry checks on generated triangles rather than vertex-only containment."""

import numpy as np
import shapely

from modeling.geometry_constraints import CADASTRAL_GRID_M

# Cadastral polygons are snapped to a 0.1 mm grid, and a vertex sitting on a lot
# edge can only round to the grid point nearest it — which may be just outside a
# boundary that does not itself run through grid points. Containment is therefore
# asserted to twice the grid, not to floating-point exactness.
CONTAINMENT_TOLERANCE_M = 2 * CADASTRAL_GRID_M


def validate_mesh(mesh, parcel, *, envelope=None, tolerance_m=CONTAINMENT_TOLERANCE_M):
    """Check a mesh against its cadastral limit.

    `envelope` is the widened limit used when attachments are allowed to
    overhang the sidewalk; it defaults to the parcel itself.
    """
    limit = parcel if envelope is None else envelope
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
    slack = limit.buffer(max(tolerance_m, 1e-9))
    projected = shapely.polygons(tri[:, :, :2])
    outside = shapely.area(shapely.difference(projected, slack))
    # Vertical triangles have zero projected area: separately check their edges.
    lines = shapely.linestrings(np.concatenate([tri[:, :, :2], tri[:, :1, :2]], axis=1))
    violations = shapely.length(shapely.difference(lines, slack))
    if outside.max() > 1e-7 or violations.max() > 1e-6:
        raise ValueError("Geometry outside cadastral envelope")
    if mesh.face_materials is None or len(mesh.face_materials) != len(mesh.faces):
        raise ValueError("Missing material assignments")
    if mesh.face_materials.min() < 0 or mesh.face_materials.max() >= len(
        mesh.materials
    ):
        raise ValueError("Invalid material indices")
    faces_by_semantic = {}
    for part in mesh.parts:
        faces_by_semantic[part["name"]] = (
            faces_by_semantic.get(part["name"], 0) + part["face_count"]
        )
    return {
        "vertices": len(mesh.vertices),
        "triangles": len(mesh.faces),
        "parts": len(mesh.parts),
        "semantic_types": sorted({p["name"] for p in mesh.parts}),
        # Face counts per element, so a regression run can compare what changed
        # rather than only whether the total moved.
        "faces_by_semantic": dict(
            sorted(faces_by_semantic.items(), key=lambda item: -item[1])
        ),
        "max_outside_triangle_area_m2": float(outside.max()),
        "min_triangle_area_m2": float(areas.min()),
        "envelope_test": "passed",
        "topology": "assembly of intersecting closed components; not Boolean-unioned",
    }


def component_topology(vertices, faces, face_start=0, face_count=None):
    """Topology metrics for one closed-component candidate.

    A geometric edge must have incidence exactly 2 on a closed orientable
    shell; incidence 1 marks a boundary (open shell) and >2 a non-manifold
    junction. Orientation coherence additionally requires the two incident
    faces to traverse every shared edge in opposite directions. Duplicate
    faces (same corners, any order) and degenerate triangles are reported
    separately. Pure analysis: never modifies the mesh.
    """
    verts = np.asarray(vertices, float).reshape(-1, 3)
    all_tris = np.asarray(faces, int).reshape(-1, 3)
    tris = (all_tris if face_count is None
            else all_tris[face_start:face_start + face_count])
    used = np.unique(tris)
    remap = np.full(len(verts), -1, int)
    remap[used] = np.arange(len(used))
    local = remap[tris]
    parent = list(range(len(used)))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    incidence = {}
    oriented = {}
    for a, b, c in local:
        parent[find(a)] = find(b)
        parent[find(b)] = find(c)
        for u, v in ((a, b), (b, c), (c, a)):
            key = (min(u, v), max(u, v))
            incidence[key] = incidence.get(key, 0) + 1
            oriented.setdefault(key, []).append((u, v))
    boundary = sum(1 for n in incidence.values() if n == 1)
    non_manifold = sum(1 for n in incidence.values() if n > 2)
    incoherent = sum(
        1 for key, count in incidence.items() if count == 2
        and oriented[key][0] == oriented[key][1]
    )
    seen, duplicates = set(), 0
    for a, b, c in local:
        key = tuple(sorted((a, b, c)))
        if key in seen:
            duplicates += 1
        seen.add(key)
    referenced = set()
    for a, b, c in local:
        referenced.update((a, b, c))
    areas = (np.linalg.norm(np.cross(verts[tris[:, 1]] - verts[tris[:, 0]],
                                     verts[tris[:, 2]] - verts[tris[:, 0]]),
                            axis=1) / 2.0)
    return {
        "vertices": int(len(used)),
        "faces": int(len(local)),
        "connected": int(len({find(i) for i in range(len(used))})),
        "boundary_edges": int(boundary),
        "non_manifold_edges": int(non_manifold),
        "incoherent_edges": int(incoherent),
        "duplicate_faces": int(duplicates),
        "degenerate_faces": int((areas < 1e-13).sum()),
        "unused_vertices": int(len(used) - len(referenced)),
        "min_area_m2": float(areas.min()) if len(areas) else 0.0,
    }


def analyze_topology(mesh, open_semantics=()):
    """Per-component topology over the face ranges in ``mesh.parts``.

    A physically volumetric component (``closed_solid``) is expected to
    report ``connected == 1``, ``boundary_edges == 0``,
    ``non_manifold_edges == 0`` and ``incoherent_edges == 0``. Semantics
    listed in ``open_semantics`` (e.g. an intentionally infinitely thin
    glazing sheet, if the grammar ever emits one) are classified as
    ``open_surface`` instead: connected, no non-manifold edges, boundary
    allowed and reported. Anything else failing closed criteria lands in
    ``violations``. Today every emitted piece is a closed solid; the glass
    panes are thin boxes with real thickness.
    """
    parts = list(mesh.parts)
    components = []
    for part in parts:
        stats = component_topology(mesh.vertices, mesh.faces,
                                   part["face_start"], part["face_count"])
        stats["semantic"] = part.get("name", "")
        stats["component_id"] = part.get("component_id", "")
        stats["assembly_id"] = part.get("assembly_id", "")
        closed = (stats["connected"] == 1 and not stats["boundary_edges"]
                  and not stats["non_manifold_edges"]
                  and not stats["incoherent_edges"]
                  and not stats["degenerate_faces"] and not stats["duplicate_faces"])
        if closed:
            stats["expectation"] = "closed_solid"
        elif (stats["semantic"] in open_semantics and stats["connected"] == 1
              and not stats["non_manifold_edges"]):
            stats["expectation"] = "open_surface"
        else:
            stats["expectation"] = "violation"
        components.append(stats)
    closed = sum(1 for c in components if c["expectation"] == "closed_solid")
    return {
        "components": components,
        "component_count": len(components),
        "closed_components": closed,
        "open_components": [c for c in components
                            if c["expectation"] == "open_surface"],
        "violations": [c for c in components
                       if c["expectation"] == "violation"],
        "total_boundary_edges": sum(c["boundary_edges"] for c in components),
        "total_non_manifold_edges": sum(c["non_manifold_edges"] for c in components),
    }
