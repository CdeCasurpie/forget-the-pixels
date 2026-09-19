"""Headless CPU z-buffer and shadow-map renderer of actual mesh geometry."""

import numpy as np
import cv2


def frame(direction):
    direction = np.asarray(direction, float)
    direction /= np.linalg.norm(direction)
    right = np.cross([0, 0, 1], direction)
    right /= np.linalg.norm(right)
    return np.array([right, np.cross(direction, right), direction])


def raster(vertices, faces, size, direction):
    basis = frame(direction)
    q = vertices @ basis.T
    low = q[:, :2].min(0)
    high = q[:, :2].max(0)
    scale = (size - 50) / max(high - low)
    mid = (low + high) / 2
    p = np.column_stack(
        (
            (q[:, 0] - mid[0]) * scale + size / 2,
            size / 2 - (q[:, 1] - mid[1]) * scale,
            q[:, 2],
        )
    )
    depth = np.full((size, size), -np.inf)
    ids = np.full((size, size), -1, int)
    for fi, f in enumerate(faces):
        a, b, c = p[f]
        x0 = max(0, int(np.floor(min(a[0], b[0], c[0]))))
        x1 = min(size - 1, int(np.ceil(max(a[0], b[0], c[0]))))
        y0 = max(0, int(np.floor(min(a[1], b[1], c[1]))))
        y1 = min(size - 1, int(np.ceil(max(a[1], b[1], c[1]))))
        denom = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(denom) < 1e-8 or x1 < x0 or y1 < y0:
            continue
        yy, xx = np.mgrid[y0 : y1 + 1, x0 : x1 + 1]
        u = ((b[1] - c[1]) * (xx - c[0]) + (c[0] - b[0]) * (yy - c[1])) / denom
        v = ((c[1] - a[1]) * (xx - c[0]) + (a[0] - c[0]) * (yy - c[1])) / denom
        w = 1 - u - v
        z = u * a[2] + v * b[2] + w * c[2]
        target = depth[y0 : y1 + 1, x0 : x1 + 1]
        mask = (u >= -1e-7) & (v >= -1e-7) & (w >= -1e-7) & (z > target)
        target[mask] = z[mask]
        ids[y0 : y1 + 1, x0 : x1 + 1][mask] = fi
    return depth, ids, basis, mid, scale


def render(mesh, path, direction=(1, -1.7, 1.1), size=900, clay=True):
    light = np.array([-1.0, -1.4, 2.5])
    light /= np.linalg.norm(light)
    depth, ids, basis, mid, scale = raster(mesh.vertices, mesh.faces, size, direction)
    shadow, _, lb, lmid, ls = raster(mesh.vertices, mesh.faces, 900, light)
    tri = mesh.vertices[mesh.faces]
    normals = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    normals /= np.linalg.norm(normals, axis=1)[:, None]
    diffuse = np.maximum(0, normals @ light)
    colors = np.array([m["color"] for m in mesh.materials])[mesh.face_materials]
    if clay:
        colors = np.repeat((0.62 + 0.28 * np.mean(colors, axis=1))[:, None], 3, axis=1)
    rgb = np.full((size, size, 3), 0.93)
    yy, xx = np.where(ids >= 0)
    indices = ids[yy, xx]
    camera = np.column_stack(
        (
            (xx - size / 2) / scale + mid[0],
            (size / 2 - yy) / scale + mid[1],
            depth[yy, xx],
        )
    )
    lq = (camera @ basis) @ lb.T
    lx = np.rint((lq[:, 0] - lmid[0]) * ls + 450).astype(int).clip(0, 899)
    ly = np.rint(450 - (lq[:, 1] - lmid[1]) * ls).astype(int).clip(0, 899)
    occluded = lq[:, 2] < shadow[ly, lx] - 0.055
    illumination = 0.42 + 0.58 * diffuse[indices] * np.where(occluded, 0.28, 1.0)
    rgb[yy, xx] = colors[indices] * illumination[:, None]
    normal_image = np.zeros((size, size, 3), np.float32)
    normal_image[yy, xx] = normals[indices]
    edges = (
        np.linalg.norm(normal_image - np.roll(normal_image, 1, axis=0), axis=2) > 0.7
    )
    edges |= (
        np.linalg.norm(normal_image - np.roll(normal_image, 1, axis=1), axis=2) > 0.7
    )
    rgb[edges & (ids >= 0)] *= 0.78
    image = np.uint8(np.clip(rgb, 0, 1) ** (1 / 1.5) * 255)
    cv2.imwrite(str(path), cv2.cvtColor(image, cv2.COLOR_RGB2BGR))
