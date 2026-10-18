"""Tests for the depth-tested software preview renderer (R0).

The point of these tests is to pin the two defects that made the previous
matplotlib previews untrustworthy: per-triangle paint order and a camera that
did not match the culling direction.  A correct z-buffer must be order
independent and must frame orthographic elevations exactly.
"""
import numpy as np
import pytest
import trimesh
from PIL import Image

from modeling.software_render import DEFAULT_PALETTE, render

BACKGROUND = np.array([255, 255, 255], dtype=int)


def _box(lo, hi):
    return trimesh.creation.box(bounds=[lo, hi])


def _load(path):
    return np.asarray(Image.open(path).convert('RGB'))


def _foreground(image):
    return np.any(np.abs(image.astype(int) - BACKGROUND) > 8, axis=2)


def _tone(pixel):
    """Channel ratios, so flat shading brightness does not change the match."""
    p = np.asarray(pixel, dtype=float)
    return p / max(p.max(), 1.0)


def test_near_solid_wins_regardless_of_order(tmp_path):
    """A brick shell in front of a green core must stay visible from either order."""
    shell = ('shell', 'brick', _box([-5, -5, -5], [5, 5, 5]))
    core = ('core', 'leaf', _box([-2, -2, -2], [2, 2, 2]))
    brick, leaf = _tone(DEFAULT_PALETTE['brick']), _tone(DEFAULT_PALETTE['leaf'])
    for order in ([shell, core], [core, shell]):
        out = tmp_path / 'x.png'
        render(order, out, direction=(1, 0, 0), ortho=True, size=200)
        center = _tone(_load(out)[100, 100])
        assert np.linalg.norm(center - brick) < np.linalg.norm(center - leaf)


def test_depth_buffer_hides_surface_behind_a_wall(tmp_path):
    """Two piers and a lintel leave a doorway; nothing is drawn inside it."""
    left = ('l', 'plaster', _box([-2, -.1, 0], [-.5, .1, 3]))
    right = ('r', 'plaster', _box([.5, -.1, 0], [2, .1, 3]))
    lintel = ('t', 'plaster', _box([-.5, -.1, 2.2], [.5, .1, 3]))
    out = tmp_path / 'doorway.png'
    render([left, right, lintel], out, direction=(0, -1, 0), ortho=True, size=200)
    image = _load(out)
    assert not _foreground(image)[190, 100]  # below the lintel, inside the gap
    assert _foreground(image)[60, 100]      # the lintel is solid


def test_orthographic_elevation_keeps_aspect(tmp_path):
    """A 4 x 3 m wall must project to a 4:3 foreground rectangle."""
    wall = ('wall', 'plaster', _box([-2, -.1, 0], [2, .1, 3]))
    out = tmp_path / 'wall.png'
    render([wall], out, direction=(0, -1, 0), ortho=True, size=400)
    rows, cols = np.where(_foreground(_load(out)))
    aspect = (cols.max() - cols.min() + 1) / (rows.max() - rows.min() + 1)
    assert aspect == pytest.approx(4 / 3, abs=.05)


def test_orthographic_camera_matches_direction(tmp_path):
    """Rotating the view direction rotates the facade, as the camera dictates."""
    wall = ('wall', 'plaster', _box([-2, -.1, 0], [2, .1, 3]))
    front = tmp_path / 'front.png'
    render([wall], front, direction=(0, -1, 0), ortho=True, size=200)
    side = tmp_path / 'side.png'
    render([wall], side, direction=(-1, 0, 0), ortho=True, size=200)
    front_pixels = _foreground(_load(front)).sum()
    side_pixels = _foreground(_load(side)).sum()
    # The side view is the 0.2 m thickness, far narrower than the 4 m front.
    assert side_pixels < front_pixels * .2


def test_empty_scene_is_background(tmp_path):
    out = tmp_path / 'empty.png'
    stats = render([], out, size=64)
    assert stats['empty'] and stats['triangles'] == 0
    assert np.all(_load(out) == BACKGROUND)


def test_render_is_deterministic(tmp_path):
    scene = [('wall', 'plaster', _box([-2, -.1, 0], [2, .1, 3])),
             ('core', 'leaf', _box([-.5, -.1, .5], [.5, .1, 2]))]
    a, b = tmp_path / 'a.png', tmp_path / 'b.png'
    render(scene, a, view=(27, -125), size=200)
    render(scene, b, view=(27, -125), size=200)
    assert np.array_equal(_load(a), _load(b))


def test_perspective_and_orthographic_both_nonempty(tmp_path):
    scene = [('wall', 'plaster', _box([-2, -.1, 0], [2, .1, 3]))]
    for ortho in (False, True):
        out = tmp_path / f'{ortho}.png'
        stats = render(scene, out, view=(27, -125), ortho=ortho, size=150)
        assert stats['triangles'] == 12 and stats['ortho'] is ortho
        assert _foreground(_load(out)).sum() > 0
