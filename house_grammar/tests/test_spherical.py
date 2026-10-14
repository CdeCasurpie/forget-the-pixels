import sys
import unittest
from pathlib import Path
import numpy as np
from shapely.geometry import box
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from vision.projection.spherical import PanoramaCamera, strip_pixels, prism_edges, draw_edges


class SphericalTests(unittest.TestCase):
    def test_cardinals_and_elevation(self):
        camera = PanoramaCamera((0, 0, 2), 0)
        angles = camera.angles([[0, 10, 2], [10, 0, 2], [0, 10, 12], [0, 10, -8]])
        np.testing.assert_allclose(angles, [[0, 0], [90, 0], [0, 45], [0, -45]], atol=1e-12)

    def test_rotated_pose_center(self):
        camera = PanoramaCamera((3, 4, 5), 70, 20, 15)
        ray = np.array(camera.center)+camera.basis[:, 2]*10
        np.testing.assert_allclose(camera.pixels([ray], 2000, 1000), [[1000, 500]], atol=1e-10)
        np.testing.assert_allclose(camera.basis.T@camera.basis, np.eye(3), atol=1e-12)

    def test_strip_matches_step5_sampling(self):
        uv = np.array([[1000, 0], [1000, 500], [1000, 999]])
        result = strip_pixels(uv, (2000, 1000), (1600, 2400), 0, 120)
        np.testing.assert_allclose(result[:, 0], 800)
        np.testing.assert_allclose(result[:, 1], [0, 500*2399/999, 2399])

    def test_extrusion_and_height_direction(self):
        edges = prism_edges(box(0, 0, 5, 5), 10)
        self.assertEqual(len(edges), 12)
        self.assertEqual(max(p[:, 2].max() for _,p in edges), 10)
        camera = PanoramaCamera((0, -10, 2.5), 0)
        uv = camera.pixels([[0, 0, 5], [0, 0, 10], [0, 0, 20]], 2000, 1000)
        self.assertTrue(np.all(np.diff(uv[:, 1]) < 0))

    def test_seam_not_connected(self):
        image = np.zeros((100, 200, 3), np.uint8)
        draw_edges(image, [np.array([[199, 50], [0, 50]])], (255, 255, 255))
        self.assertFalse(image[:, 50:150].any())

    def test_camera_origin_rejected(self):
        with self.assertRaises(ValueError):
            PanoramaCamera((0, 0, 0), 0).pixels([[0, 0, 0]], 200, 100)
