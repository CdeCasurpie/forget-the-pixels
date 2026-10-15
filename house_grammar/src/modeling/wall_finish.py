"""Assign finishes to the existing wall surface, never extrude paint.

Partition already clipped triangles in facade coordinates. This preserves the
structural shell, curved aperture reveals and oblique cadastral end caps alike.
Shared edges are cut by the same planes; no internal faces are introduced.
"""
import numpy as np


class WallFinish:
    def __init__(self, a, tangent, regions):
        self.origin = np.array([*a, 0.], float)
        self.u = np.array([*tangent, 0.], float)
        self.regions = tuple(regions)
        self.planes = [(self.u, x) for x in sorted({
            x for r in regions for x in (r.u_m, r.u_m+r.width_m)})]
        self.planes += [(np.array([0., 0., 1.]), z) for z in sorted({
            z for r in regions for z in (r.v_m, r.v_m+r.height_m)})]

    @staticmethod
    def _split(poly, distances):
        """Split a convex polygon carrying XYZ and metric UV attributes."""
        if min(distances) >= -1e-10 or max(distances) <= 1e-10:
            return [poly]
        negative, positive = [], []
        for i, p in enumerate(poly):
            q = poly[(i+1) % len(poly)]
            d, e = distances[i], distances[(i+1) % len(poly)]
            if d <= 1e-10:
                negative.append(p)
            if d >= -1e-10:
                positive.append(p)
            if (d < -1e-10 and e > 1e-10) or (d > 1e-10 and e < -1e-10):
                intersection = p + (q-p)*(d/(d-e))
                negative.append(intersection)
                positive.append(intersection)
        return [np.asarray(p) for p in (negative, positive) if len(p) >= 3]

    def apply(self, builder):
        comp = builder._open
        faces, uvs, materials = comp.faces, comp.corner_uvs, comp.face_materials
        comp.faces, comp.corner_uvs, comp.face_materials = [], [], []
        for face, uv, material in zip(faces, uvs, materials):
            base = builder.materials[material]
            poly = np.column_stack((np.array([comp.positions[i] for i in face]),
                                    np.array(uv)*base['real_scale_m']))
            patches = [poly]
            for normal, cut in self.planes:
                patches = [piece for p in patches for piece in self._split(
                    p, (p[:, :3]-self.origin)@normal-cut)]
            for patch in patches:
                center = patch.mean(axis=0)
                u, z = float((center[:3]-self.origin)@self.u), center[2]
                slot = base['name']
                for r in self.regions:
                    if r.u_m-1e-10 <= u <= r.u_m+r.width_m+1e-10 and \
                            r.v_m-1e-10 <= z <= r.v_m+r.height_m+1e-10:
                        slot = r.material_slot
                mi, scale = builder.mat_index(slot), builder.uv_scale_for(slot)
                # A center fan preserves every boundary vertex, including
                # collinear cuts shared with a neighboring original triangle.
                triangles = [patch] if len(patch) == 3 else [
                    (center, p, patch[(i+1) % len(patch)]) for i, p in enumerate(patch)]
                for tri in triangles:
                    builder.tri(*(builder.vert(p[:3]) for p in tri),
                                tuple(p[3:]/scale for p in tri), mi)
