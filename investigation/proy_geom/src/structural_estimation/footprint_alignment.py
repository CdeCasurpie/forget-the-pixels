"""Apply an explicit planar cadastral alignment without mutating source data."""
from shapely.affinity import translate


def aligned_footprint(footprint, east_m: float, north_m: float):
    return translate(footprint, xoff=east_m, yoff=north_m)
