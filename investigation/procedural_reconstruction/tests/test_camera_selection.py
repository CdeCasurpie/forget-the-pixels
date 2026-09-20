import sys
import unittest
from pathlib import Path

import geopandas as gpd
from shapely.geometry import Point, box

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from vision.cameras import score_edges
from spatial import find_target_lot


class VisibilityTests(unittest.TestCase):
    def test_front_visible_back_self_occluded(self):
        target = box(0, 0, 10, 10)
        lots = gpd.GeoDataFrame(geometry=[target], crs=32718)
        edges = score_edges(lots, 0, target, Point(5, -10), lots.sindex)
        self.assertEqual(sum(e['score'] for e in edges), 1)
        self.assertTrue(next(e for e in edges if e['midpoint_y'] == 10)['self_occluded_by_target_lot'])

    def test_blocker_and_camera_containing_lot(self):
        target = box(0, 0, 10, 10)
        for obstacle, expected in ((box(0, -6, 10, -4), 0), (box(0, -12, 10, -8), 1)):
            lots = gpd.GeoDataFrame(geometry=[target, obstacle], crs=32718)
            edges = score_edges(lots, 0, target, Point(5, -10), lots.sindex)
            self.assertEqual(sum(e['score'] for e in edges), expected)

    def test_wrong_crs_rejected(self):
        lots = gpd.GeoDataFrame(geometry=[box(0, 0, 1, 1)], crs=4326)
        with self.assertRaises(ValueError):
            find_target_lot(lots, 0, 0, 1)
