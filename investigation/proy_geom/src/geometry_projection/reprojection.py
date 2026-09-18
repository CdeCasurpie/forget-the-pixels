"""Pure metric-prism reprojection used by alignment, height fitting, and QA."""
from __future__ import annotations

import numpy as np
from pyproj import Geod, Transformer

from geometry_projection.spherical import PanoramaCamera, prism_edges


def project_prism_to_panorama(footprint, height_m: float, *, crs: str, latitude: float, longitude: float,
                               heading_deg: float, image_width: int, image_height: int,
                               camera_height_m: float = 2.5):
    """Project all sampled prism edges into an equirectangular panorama.

    The footprint is in a metric CRS. The result is a list of Nx2 pixel curves;
    rendering remains the responsibility of an experiment or visualization.
    """
    to_geographic = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
    geod = Geod(ellps="WGS84")
    camera = PanoramaCamera((0.0, 0.0, camera_height_m), heading_deg)
    curves = []
    for _, points in prism_edges(footprint, height_m):
        lon, lat = to_geographic.transform(points[:, 0], points[:, 1])
        azimuth, _, distance = geod.inv(
            np.full(len(lon), longitude), np.full(len(lat), latitude), lon, lat,
        )
        azimuth = np.radians(azimuth)
        enu = np.column_stack((distance * np.sin(azimuth), distance * np.cos(azimuth), points[:, 2]))
        curves.append(camera.pixels(enu, image_width, image_height))
    return curves
