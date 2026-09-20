"""Metric cadastral geometry (EPSG:32718 for Barranco)."""

import math
import geopandas as gpd
from pyproj import Transformer
from shapely.geometry import Point, Polygon, LineString

TARGET_CRS = "EPSG:32718"


def bearing_from_north(origin: Point, target: Point) -> float:
    """Bearing de cuadrícula, en grados, medido en sentido horario desde norte."""
    return math.degrees(math.atan2(target.x - origin.x, target.y - origin.y)) % 360.0


def signed_angle(angle: float) -> float:
    """Normaliza un ángulo a [-180, 180)."""
    return (angle + 180.0) % 360.0 - 180.0


def point_at_bearing(origin: Point, bearing: float, length: float) -> Point:
    radians = math.radians(bearing)
    return Point(
        origin.x + length * math.sin(radians),
        origin.y + length * math.cos(radians),
    )


def edge_midpoints(polygon: Polygon) -> list[tuple[int, Point, Point, Point]]:
    """Devuelve índice, extremos y punto medio de cada arista exterior."""
    ring = polygon.exterior
    coordinates = list(ring.coords)
    edges = []
    for index, (start, end) in enumerate(zip(coordinates, coordinates[1:])):
        start_point = Point(start)
        end_point = Point(end)
        edges.append(
            (
                index,
                start_point,
                end_point,
                LineString([start, end]).interpolate(0.5, normalized=True),
            )
        )
    if not edges:
        raise ValueError("El lote no tiene una arista exterior válida")
    return edges


def find_target_lot(gdf: gpd.GeoDataFrame, lat: float, lon: float, tolerance_m: float):
    if gdf.empty or gdf.crs is None or gdf.crs.to_epsg() != 32718:
        raise ValueError("Se requiere catastro no vacío en EPSG:32718")
    if not math.isfinite(tolerance_m) or tolerance_m < 0:
        raise ValueError("tolerance_m debe ser finito y no negativo")
    transformer = Transformer.from_crs("EPSG:4326", TARGET_CRS, always_xy=True)
    x, y = transformer.transform(lon, lat)
    point = Point(x, y)
    matches = gdf[gdf.geometry.covers(point)]
    if not matches.empty:
        index = matches.index[0]
        return int(index), matches.iloc[0], point, 0.0
    distances = gdf.geometry.distance(point)
    index = distances.idxmin()
    distance = float(distances.loc[index])
    if distance > tolerance_m:
        raise RuntimeError(
            f"La coordenada no cae en un lote; el más cercano está a {distance:.2f} m."
        )
    return int(index), gdf.loc[index], point, distance


from .street_fronts import StreetEdge, street_facing_edges, annotate_street_fronts
