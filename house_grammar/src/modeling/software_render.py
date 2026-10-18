"""Order-independent software renderer for constructive previews.

Why this exists
---------------
The constructive exports used to be drawn with ``matplotlib``'s 3D
``Poly3DCollection``.  Two defects made every preview unreliable:

* Drawing order.  Matplotlib sorts whole triangles by a single depth key, so
  large flat walls seen edge-on and thin panels behind them appeared as
  diagonal streaks and floating shards.  A watertight mesh could still look
  broken.
* Camera / culling mismatch.  The elevation path culled faces with
  ``face_normals @ direction`` but only called ``view_init`` for the
  perspective view, so orthographic elevations were rendered from the default
  3D viewpoint while culling assumed a facade-facing camera.  Whole walls
  vanished and interior pieces were drawn on the facade.

This module rasterises triangles into a real depth buffer.  The nearest
surface wins per pixel regardless of submission order, and the projection is
built from the same camera basis used for shading, so elevations are true
orthographic front views.

No GPU or OpenGL binding is required.  ``numpy`` rasterises and ``PIL`` writes
the PNG, so CI and the experiment runners share one code path.
"""
from __future__ import annotations

import numpy as np

DEFAULT_PALETTE = {
    'plaster': (226, 220, 208),
    'concrete': (198, 198, 196),
    'stone': (184, 176, 162),
    'wood': (172, 126, 80),
    'metal': (118, 124, 132),
    'pvc': (242, 242, 242),
    'glass': (176, 206, 218),
    'brick': (176, 91, 62),
    'tile': (176, 91, 62),
    'roof_tile': (176, 91, 62),
    'corrugated': (144, 150, 155),
    'accent': (210, 170, 120),
    'ground': (196, 194, 184),
    'soil': (150, 126, 96),
    'leaf': (120, 156, 104),
}
_FALLBACK = (200, 200, 200)


def _basis(direction, up):
    """Orthonormal camera basis: ``d`` toward the viewer, ``r`` right, ``u`` up."""
    d = np.asarray(direction, dtype=float)
    d = d / np.linalg.norm(d)
    up = np.asarray(up, dtype=float)
    r = np.cross(up, d)
    if np.linalg.norm(r) < 1e-9:  # looking straight along the up axis
        alt = np.array([0., 1., 0.]) if abs(d[2]) > .5 else np.array([0., 0., 1.])
        r = np.cross(alt, d)
    r = r / np.linalg.norm(r)
    u = np.cross(d, r)
    return d, r, u


def direction_from_view(view):
    """Matplotlib-compatible (elev, azim) degrees to a unit view direction."""
    elev, azim = np.deg2rad(view[0]), np.deg2rad(view[1])
    return np.array([np.cos(elev) * np.cos(azim),
                     np.cos(elev) * np.sin(azim),
                     np.sin(elev)])


def _gather(meshes, palette):
    vertices = []
    faces = []
    colors = []
    offset = 0
    for name, material, mesh in meshes:
        verts = np.asarray(mesh.vertices, dtype=float)
        tris = np.asarray(mesh.faces, dtype=int)
        if len(tris) == 0:
            continue
        rgb = np.asarray(palette.get(material, _FALLBACK), dtype=float)[:3] / 255.0
        vertices.append(verts)
        faces.append(tris + offset)
        colors.append(np.tile(rgb, (len(tris), 1)))
        offset += len(verts)
    if not faces:
        return (np.zeros((0, 3)), np.zeros((0, 3), dtype=int), np.zeros((0, 3)))
    return np.vstack(vertices), np.vstack(faces), np.vstack(colors)


def _project(vertices, center, d, r, u, ortho, focal):
    rel = vertices - center
    x = rel @ r
    y = rel @ u
    z = rel @ d
    if ortho:
        # Camera at +infinity along d: larger z is nearer, so depth = -z.
        return x, y, -z
    diag = max(np.linalg.norm(vertices.max(0) - vertices.min(0)), 1e-6)
    distance = focal * diag
    denom = np.maximum(distance - z, 1e-4)
    return x / denom, y / denom, denom


def _fit(x, y, size, margin):
    minx, maxx = float(x.min()), float(x.max())
    miny, maxy = float(y.min()), float(y.max())
    span = max(maxx - minx, maxy - miny, 1e-9)
    pad = margin * size
    usable = max(size - 2 * pad, 1.0)
    scale = usable / span
    ox = pad + (usable - (maxx - minx) * scale) / 2
    oy = pad + (usable - (maxy - miny) * scale) / 2
    px = ox + (x - minx) * scale
    py = size - (oy + (y - miny) * scale)
    return px, py


def _shade(vertices, faces, d, r, u, ambient, light):
    tri = vertices[faces]
    normals = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    lengths = np.linalg.norm(normals, axis=1)
    lengths[lengths < 1e-12] = 1e-12
    normals = normals / lengths[:, None]
    if light is None:
        light = 0.45 * d + 0.75 * u + 0.35 * r
    light = light / np.linalg.norm(light)
    key = np.abs(normals @ light)
    head = np.abs(normals @ d)
    return np.clip(ambient + (1 - ambient) * (0.75 * key + 0.25 * head), 0, 1)


def _rasterize(faces, px, py, pz, colors, size, image):
    zbuf = np.full((size, size), np.inf)
    X, Y, Z = px[faces], py[faces], pz[faces]
    lo_x = np.floor(X.min(1)).astype(int)
    hi_x = np.ceil(X.max(1)).astype(int)
    lo_y = np.floor(Y.min(1)).astype(int)
    hi_y = np.ceil(Y.max(1)).astype(int)
    for i in range(len(faces)):
        x0, x1 = max(lo_x[i], 0), min(hi_x[i], size - 1)
        y0, y1 = max(lo_y[i], 0), min(hi_y[i], size - 1)
        if x0 > x1 or y0 > y1:
            continue
        ax, ay = X[i, 0], Y[i, 0]
        bx, by = X[i, 1], Y[i, 1]
        cx, cy = X[i, 2], Y[i, 2]
        det = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(det) < 1e-9:
            continue
        gx = np.arange(x0, x1 + 1)[None, :]
        gy = np.arange(y0, y1 + 1)[:, None]
        w0 = ((by - cy) * (gx - cx) + (cx - bx) * (gy - cy)) / det
        w1 = ((cy - ay) * (gx - cx) + (ax - cx) * (gy - cy)) / det
        w2 = 1 - w0 - w1
        inside = (w0 >= -1e-6) & (w1 >= -1e-6) & (w2 >= -1e-6)
        if not inside.any():
            continue
        depth = w0 * Z[i, 0] + w1 * Z[i, 1] + w2 * Z[i, 2]
        sub = zbuf[y0:y1 + 1, x0:x1 + 1]
        update = inside & (depth < sub)
        if not update.any():
            continue
        sub[update] = depth[update]
        region = image[y0:y1 + 1, x0:x1 + 1]
        region[update] = colors[i]
    return zbuf


def _outline(image, zbuf, strength=0.55):
    valid = np.isfinite(zbuf)
    if not valid.any():
        return
    far = float(zbuf[valid].max())
    fill = far + max(far * .05, 1e-3)
    depth = np.where(valid, zbuf, fill)
    spread = max(far - float(zbuf[valid].min()), 1e-6)
    threshold = 0.04 * spread
    gx = np.zeros_like(depth)
    gy = np.zeros_like(depth)
    gx[:, :-1] = np.abs(depth[:, 1:] - depth[:, :-1])
    gx[:, -1] = gx[:, -2]
    gy[:-1, :] = np.abs(depth[1:, :] - depth[:-1, :])
    gy[-1, :] = gy[-2, :]
    edges = ((gx > threshold) | (gy > threshold)) & valid
    image[edges] *= strength


def _save(image, output):
    from PIL import Image
    data = np.clip(image * 255.0, 0, 255).astype(np.uint8)
    Image.fromarray(data).save(output)


def render(meshes, output, *, view=(27, -125), direction=None, ortho=False,
           size=900, up=(0, 0, 1), background=(255, 255, 255), palette=None,
           ambient=0.34, margin=0.05, outline=True, focal=3.0, light=None):
    """Rasterise ``(name, material, mesh)`` items to a depth-tested PNG.

    ``direction`` points from the object toward the camera.  When omitted it is
    derived from ``view=(elev_deg, azim_deg)`` exactly like the old matplotlib
    code, so existing call sites keep their framing.  ``ortho`` selects an
    orthographic projection (elevations) instead of perspective.
    """
    palette = dict(DEFAULT_PALETTE) if palette is None else dict(palette)
    vertices, faces, colors = _gather(meshes, palette)
    image = np.tile(np.asarray(background, dtype=float) / 255.0, (size, size, 1))
    if len(faces) == 0:
        _save(image, output)
        return dict(triangles=0, vertices=0, size=size, empty=True)
    d = direction_from_view(view) if direction is None else np.asarray(direction, dtype=float)
    d, r, u = _basis(d, up)
    center = (vertices.max(0) + vertices.min(0)) / 2
    x, y, depth = _project(vertices, center, d, r, u, ortho, focal)
    px, py = _fit(x, y, size, margin)
    shade = _shade(vertices, faces, d, r, u, ambient, light)
    face_colors = np.clip(colors * shade[:, None], 0, 1)
    zbuf = _rasterize(faces, px, py, depth, face_colors, size, image)
    if outline:
        _outline(image, zbuf)
    _save(image, output)
    low, high = vertices.min(0), vertices.max(0)
    return dict(triangles=int(len(faces)), vertices=int(len(vertices)), size=size,
                empty=False, ortho=bool(ortho), direction=[round(v, 4) for v in d],
                bounds=[[round(v, 3) for v in low], [round(v, 3) for v in high]])
