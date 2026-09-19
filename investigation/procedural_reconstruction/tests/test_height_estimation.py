import unittest
import numpy as np
from height_estimation import split_strip, fit_height
from structural_estimation import regularize_height_to_floors
from geometry_projection.spherical import PanoramaCamera


class HeightTests(unittest.TestCase):
    def test_known_color_boundary_with_dark_ground_floor(self):
        image = np.zeros((240, 9, 3), np.uint8)
        image[:55] = [125, 165, 210]
        image[55:220] = [190, 180, 150]
        image[220:] = [10, 10, 10]
        cut, score = split_strip(image)
        self.assertEqual(cut, 55)
        self.assertGreater(score, .2)

    def test_uniform_strip_not_confident(self):
        _, score = split_strip(np.full((100, 9, 3), 130, np.uint8))
        self.assertLess(score, .01)

    def test_recover_height_from_independent_projection(self):
        observations = []
        camera = PanoramaCamera((0, 0, 2.5), 0)
        for distance in [10., 20., 40., 70.]:
            row = camera.pixels([[0, distance, 35.]], 4096, 2048)[0, 1]
            observations.append({'distance_m': distance, 'image_height': 2048, 'cut_y': row})
        result = fit_height(observations)
        self.assertAlmostEqual(result['height_m'], 35., places=5)
        self.assertLess(result['rmse_normalized_px'], 1e-5)

    def test_insufficient_views(self):
        with self.assertRaises(ValueError):
            fit_height([])

    def test_regularize_to_architectural_floor_grid(self):
        result = regularize_height_to_floors(33.62)
        self.assertEqual(result['floor_count'], 12)
        self.assertAlmostEqual(result['floor_height_m'], 2.8)
        self.assertAlmostEqual(result['regularized_height_m'], 33.6)
