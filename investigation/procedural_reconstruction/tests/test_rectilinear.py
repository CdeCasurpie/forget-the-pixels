"""Analytic direction fields catch sign, seam, and polar projection errors."""
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from geometry_projection import PinholeCamera, angles_from_direction, extract_rectilinear


class ProjectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        lon, lat = np.meshgrid((np.arange(1440)/1440-.5)*2*np.pi,
                               (.5-np.arange(720)/720)*np.pi)
        cls.sphere = np.stack((np.sin(lon)*np.cos(lat), np.sin(lat),
                               np.cos(lon)*np.cos(lat)), axis=-1).astype(np.float32)

    def test_center_directions_and_poles(self):
        for yaw in (0, 90, -90, 180, 359):
            for pitch in (-90, -30, 0, 60, 90):
                with self.subTest(yaw=yaw, pitch=pitch):
                    camera = PinholeCamera(101, 81, 90, yaw, pitch)
                    view = extract_rectilinear(self.sphere, camera)
                    np.testing.assert_allclose(view[40, 50], camera.camera_to_panorama[:, 2], atol=.005)

    def test_image_is_upright_and_rightward(self):
        view = extract_rectilinear(self.sphere, PinholeCamera(101, 81))
        self.assertGreater(view[0, 50, 1], view[-1, 50, 1])
        self.assertGreater(view[40, -1, 0], view[40, 0, 0])

    def test_seam_continuity(self):
        view = extract_rectilinear(self.sphere, PinholeCamera(101, 81, 90, 180))
        self.assertLess(np.abs(np.diff(view[40], axis=0)).max(), .025)

    def test_direction_conversion(self):
        self.assertEqual(angles_from_direction((1, 0, 0)), (90, 0))
        yaw, pitch = angles_from_direction((0, 1, 1))
        self.assertAlmostEqual(yaw, 0)
        self.assertAlmostEqual(pitch, 45)
        for bad in ((0, 0, 0), (1, 2), (0, float('nan'), 1)):
            with self.assertRaises(ValueError):
                angles_from_direction(bad)

    def test_intrinsics_and_basis(self):
        camera = PinholeCamera(100, 100, 90, 30, 45)
        self.assertAlmostEqual(camera.intrinsics[0, 0], 50)
        self.assertAlmostEqual(camera.vertical_fov_deg, 90)
        np.testing.assert_allclose(camera.camera_to_panorama.T @ camera.camera_to_panorama, np.eye(3), atol=1e-12)

    def test_invalid_camera(self):
        for kwargs in ({'width': 0}, {'height': 1.5}, {'pitch_deg': 91},
                       {'horizontal_fov_deg': 180}, {'yaw_deg': float('nan')}):
            with self.assertRaises(ValueError):
                PinholeCamera(**kwargs)


if __name__ == '__main__':
    unittest.main()
