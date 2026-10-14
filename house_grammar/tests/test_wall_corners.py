"""Butt-jointed wall corners: no visible coplanar overlap between wall faces.

At every convex corner the starting wall begins buried one thickness inside
its neighbour, while the arriving wall runs full to the vertex. Caps hidden
inside the neighbouring solid are harmless; faces sharing one visible plane
are not. These tests therefore compare only outward-facing wall surfaces.
"""
import json
import numpy as np
import pytest
from collections import defaultdict
from shapely.geometry import Polygon

from domain.theta import from_json
from modeling.theta import resolve_theta, generate_resolved
from test_volumetric_crowns import request


def _basis(n):
    n = np.asarray(n, float)
    u = np.array([1., 0, 0]) if abs(n[0]) < .9 else np.array([0, 1., 0])
    u = u - n * (u @ n)
    u /= np.linalg.norm(u)
    return u, np.cross(n, u)


def outer_face_overlap(mesh, walls, tol=0.003):
    """Overlap area of outward-facing wall triangles from different walls."""
    outward = {}
    for w in walls:
        n = np.asarray(w.facade.normal_xy, float)
        outward[w.facade.edge_id] = n / np.linalg.norm(n)
    tris = mesh.vertices[mesh.faces]
    n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
    part_of = np.empty(len(tris), dtype=object)
    comp_of = np.empty(len(tris), dtype=object)
    for p, c in zip(mesh.parts, mesh.components):
        part_of[p['face_start']:p['face_start'] + p['face_count']] = p['name']
        comp_of[p['face_start']:p['face_start'] + p['face_count']] = c['component_id']
    cells = defaultdict(list)
    for i in range(len(tris)):
        if part_of[i] != 'wall':
            continue
        edge = next((e for e in outward if comp_of[i].startswith(e + '/')), None)
        if edge is None or n[i][:2] @ outward[edge] < 0.99:
            continue
        if abs(n[i][2]) > 0.01:
            continue
        nn = n[i]
        d = nn @ tris[i, 0]
        cells[(round(nn[0] / tol), round(nn[1] / tol), round(d / tol))].append(i)
    total = 0.0
    for idx in cells.values():
        if len({comp_of[i] for i in idx}) < 2:
            continue
        key = next(iter(idx))
        nn = n[key]
        u, v = _basis(nn)
        polys = {}
        for i in idx:
            polys.setdefault(comp_of[i], []).append(
                Polygon([(t @ u, t @ v) for t in tris[i]]))
        names = list(polys)
        for a in range(len(names)):
            for b in range(a + 1, len(names)):
                for pa in polys[names[a]]:
                    for pb in polys[names[b]]:
                        if (pa.bounds[2] < pb.bounds[0] or pb.bounds[2] < pa.bounds[0]
                                or pa.bounds[3] < pb.bounds[1] or pb.bounds[3] < pa.bounds[1]):
                            continue
                        total += pa.intersection(pb).area
    return total


def solve_bare():
    r = request()
    r['theta']['crowns'] = []
    req = from_json(json.dumps(r))
    resolved = resolve_theta(req.context, req.theta)
    return resolved, generate_resolved(resolved)


def test_convex_corners_have_no_shared_visible_plane():
    resolved, mesh = solve_bare()
    assert outer_face_overlap(mesh, resolved.walls) < 0.01


def test_abutting_mass_does_not_share_visible_plane():
    r = request()
    t = r['theta']
    t['crowns'] = []
    t['masses'] = [dict(role='house', footprint=[[6, 8], [14, 8], [14, 14], [6, 14]], levels_m=[0, 3.6, 7.2]),
                   dict(role='wing', footprint=[[6, 4], [10, 4], [10, 8], [6, 8]], levels_m=[0, 3.6, 6.0])]
    t['facades'] = []
    t['roof_assemblies'] = [dict(id='a', mass_ref='house:0', design=dict(form='hip', detail='light')),
                            dict(id='b', mass_ref='wing:0', design=dict(form='gable', detail='light'))]
    req = from_json(json.dumps(r))
    resolved = resolve_theta(req.context, req.theta)
    assert outer_face_overlap(generate_resolved(resolved), resolved.walls) < 0.01


def test_corner_opening_falls_back_without_breaking_wall():
    from domain.models import Opening
    from modeling.grammar import facade
    from modeling.mesh_builder import MeshBuilder
    from domain.models import FacadeSpecification
    from shapely.geometry import box

    def build(ops, **kw):
        spec = FacadeSpecification('edge_0', (0., 0.), (14., 0.), 14., (0., -1.), (0., 4.),
                                   openings=tuple(ops), is_front=True)
        mb = MeshBuilder(box(-2, -2, 16, 6))
        facade(mb, spec, 4., **kw)
        return mb.finish()

    mesh = build((), trim_start=True)
    umin = min(mesh.vertices[f][:, 0].min()
               for p in mesh.parts if p['name'] == 'wall'
               for f in mesh.faces[p['face_start']:p['face_start'] + p['face_count']])
    assert umin == pytest.approx(0.20)
    # A constrained start still covers the opening instead of cutting it off.
    mesh = build((Opening('window', 0.12, 1., 1.5, 1.6),), trim_start=True, extend_end=True)
    assert any(p['name'] == 'wall' for p in mesh.parts)
    umin = min(mesh.vertices[f][:, 0].min()
               for p in mesh.parts if p['name'] == 'wall'
               for f in mesh.faces[p['face_start']:p['face_start'] + p['face_count']])
    assert umin == pytest.approx(0.115)
    umax = max(mesh.vertices[f][:, 0].max()
               for p in mesh.parts if p['name'] == 'wall'
               for f in mesh.faces[p['face_start']:p['face_start'] + p['face_count']])
    assert umax == pytest.approx(14.20)


def test_t_junction_extends_into_neighbour_without_slot():
    from collections import defaultdict
    r = request()
    t = r['theta']
    t['crowns'] = []
    t['masses'] = [dict(role='house', footprint=[[6, 8], [14, 8], [14, 14], [6, 14]], levels_m=[0, 3.6, 7.2]),
                   dict(role='wing', footprint=[[6, 4], [10, 4], [10, 8], [6, 8]], levels_m=[0, 3.6, 6.0])]
    t['facades'] = []
    t['roof_assemblies'] = [dict(id='a', mass_ref='house:0', design=dict(form='hip', detail='light')),
                            dict(id='b', mass_ref='wing:0', design=dict(form='gable', detail='light'))]
    req = from_json(json.dumps(r))
    resolved = resolve_theta(req.context, req.theta)
    mesh = generate_resolved(resolved)
    assert outer_face_overlap(mesh, resolved.walls) < 0.01
    # The abutting wall continues past the vertex into the neighbouring solid.
    for p, c in zip(mesh.parts, mesh.components):
        if p['name'] == 'wall' and 'wing:0/edge1' in c['component_id']:
            v = mesh.vertices[mesh.faces[p['face_start']:p['face_start'] + p['face_count']]]
            assert v[:, :, 1].max() >= 8.15
    # Fully closed shells: no open slot anywhere in the assembly.
    counts = defaultdict(int)
    for f in mesh.faces:
        for a, b in ((f[0], f[1]), (f[1], f[2]), (f[2], f[0])):
            key = tuple(sorted((tuple(np.round(mesh.vertices[a], 4)), tuple(np.round(mesh.vertices[b], 4)))))
            counts[key] += 1
    assert sum(1 for v in counts.values() if v == 1) == 0
