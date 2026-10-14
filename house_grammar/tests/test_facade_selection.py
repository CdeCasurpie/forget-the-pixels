import sys
import unittest
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from vision.segmentation.selection import select_vertical


class SelectionTests(unittest.TestCase):
    def test_actual_pixels_not_bbox(self):
        masks = np.zeros((3, 10, 10), bool)
        masks[0, 2:8, 4:7] = True
        masks[1, 2:8, 1] = True
        masks[1, 2:8, 8] = True  # box crosses center, mask does not
        masks[2, 0:2, 5] = True
        selected, evidence = select_vertical(masks, 5)
        self.assertEqual(selected, [0, 2])
        self.assertEqual(evidence[0]['intersection_rows'], 6)

    def test_empty_and_invalid(self):
        self.assertEqual(select_vertical(np.zeros((0, 10, 10), bool), 5)[0], [])
        with self.assertRaises(ValueError):
            select_vertical(np.zeros((1, 10, 10), bool), 10)

    def test_band(self):
        masks = np.zeros((1, 10, 10), bool)
        masks[0, :, 4] = True
        self.assertEqual(select_vertical(masks, 5)[0], [])
        self.assertEqual(select_vertical(masks, 5, 1)[0], [0])
