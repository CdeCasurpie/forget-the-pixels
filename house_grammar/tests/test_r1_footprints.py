"""Audit the R1 evidence: equal area does not imply equal silhouette."""
import importlib.util
import sys
from pathlib import Path

import pytest
from shapely.geometry import Polygon, box


@pytest.fixture
def runner(monkeypatch):
    directory = Path(__file__).resolve().parents[1] / 'experiments' / 'r1'
    monkeypatch.syspath_prepend(str(directory))
    monkeypatch.delitem(sys.modules, 'cases', raising=False)
    spec = importlib.util.spec_from_file_location('r1_audit_runner', directory / 'run.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_equal_area_displacement_is_not_preservation(runner):
    with pytest.raises(ValueError, match='changed massing footprints'):
        runner.footprint_drift({'a': box(0, 0, 4, 4)}, {'a': box(1, 0, 5, 4)})


def test_missing_body_is_not_silently_skipped(runner):
    with pytest.raises(ValueError, match='set of massing bodies'):
        runner.footprint_drift({'a': box(0, 0, 4, 4)}, {})


def test_courtyard_is_part_of_the_footprint(runner):
    courtyard = Polygon(box(0, 0, 4, 4).exterior.coords,
                        [box(1, 1, 2, 2).exterior.coords])
    assert runner.footprint_drift({'a': courtyard}, {'a': courtyard}) == {'a': 0}
    with pytest.raises(ValueError, match='changed massing footprints'):
        runner.footprint_drift({'a': courtyard}, {'a': box(0, 0, 4, 4)})
