"""Camera ranking and approximate 2D cadastral visibility."""
import math
import geopandas as gpd
from pyproj import Transformer
from shapely.geometry import Point, Polygon, LineString
from spatial import TARGET_CRS, edge_midpoints, bearing_from_north, signed_angle

def intersection_distance(line: LineString, polygon, camera: Point) -> float | None:
    intersection = line.intersection(polygon)
    if intersection.is_empty:
        return None
    # La distancia sobre la línea coincide con la distancia métrica desde la
    # cámara porque la línea es recta y está construida desde la cámara.
    if intersection.geom_type in {"Point", "MultiPoint"}:
        points = list(intersection.geoms) if intersection.geom_type == "MultiPoint" else [intersection]
        return min(camera.distance(point) for point in points)
    return camera.distance(intersection)


def find_blockers(gdf: gpd.GeoDataFrame, target_index, camera: Point, target: Point, spatial_index=None) -> list[int]:
    """Busca lotes que cortan la línea antes de alcanzar el lote objetivo."""
    sightline = LineString([camera, target])
    target_distance = camera.distance(target)
    blockers: list[int] = []
    # Se tolera 1 m al final para no marcar como oclusor al lote objetivo ni a
    # un lote vecino que comparte exactamente la arista de llegada.
    # El índice espacial evita probar la línea contra los miles de lotes de
    # Barranco cuando solo unos pocos están dentro de su caja envolvente.
    candidate_positions = spatial_index.query(sightline, predicate="intersects") if spatial_index is not None else range(len(gdf))
    for position in candidate_positions:
        index = gdf.iloc[int(position)].name
        row = gdf.iloc[int(position)]
        if index == target_index:
            continue
        # Street View puede caer dentro de un lote por un pequeño desfase GPS.
        # Ese polígono contenedor no debe bloquear los rayos de su propia
        # cámara; los demás polígonos sí siguen siendo oclusores.
        if row.geometry.covers(camera):
            continue
        distance = intersection_distance(sightline, row.geometry, camera)
        if distance is not None and distance < target_distance - 1.0:
            blockers.append(int(index))
    return blockers


def score_edges(
    gdf: gpd.GeoDataFrame,
    target_index,
    polygon: Polygon,
    camera: Point,
    spatial_index=None,
    min_frontal_cosine: float = 0.5,
) -> list[dict]:
    """Puntúa cada arista por la visibilidad de su punto medio.

    La puntuación es binaria por diseño: 1 si el segmento está libre y 0 si
    otro lote lo bloquea. Así, la suma por cámara es interpretable como el
    número de aristas observables desde ella.
    """
    results = []
    for edge_index, start, end, midpoint in edge_midpoints(polygon):
        sightline = LineString([camera, midpoint])
        # No se puede ignorar el lote objetivo: una arista posterior queda
        # auto-oculta cuando el rayo entra al interior del propio polígono
        # antes de alcanzar su punto medio.
        self_intersection = sightline.intersection(polygon)
        self_occluded = (not self_intersection.is_empty) and self_intersection.length > 0.05
        blockers = find_blockers(gdf, target_index, camera, midpoint, spatial_index)
        edge_dx, edge_dy = end.x - start.x, end.y - start.y
        view_dx, view_dy = camera.x - midpoint.x, camera.y - midpoint.y
        denominator = math.hypot(edge_dx, edge_dy) * math.hypot(view_dx, view_dy)
        frontal_cosine = abs(edge_dx * view_dy - edge_dy * view_dx) / denominator if denominator else 0.0
        frontal_enough = frontal_cosine >= min_frontal_cosine
        visible = not self_occluded and not blockers and frontal_enough
        results.append({
            "edge_index": edge_index,
            "start_x": start.x,
            "start_y": start.y,
            "end_x": end.x,
            "end_y": end.y,
            "midpoint_x": midpoint.x,
            "midpoint_y": midpoint.y,
            "visible": visible,
            "self_occluded_by_target_lot": self_occluded,
            "frontal_cosine": frontal_cosine,
            "passes_frontal_threshold": frontal_enough,
            "score": 1 if visible else 0,
            "blocking_lot_rows": blockers,
        })
    return results


def select_cameras(
    gdf: gpd.GeoDataFrame,
    target_index: int,
    target_geometry,
    metadata: list[dict],
    max_distance_m: float,
    top_k: int,
) -> list[dict]:
    """Rank visible cameras by metric distance to lot; preserve input metadata."""
    if type(top_k) is not int or top_k <= 0:
        raise ValueError("top_k debe ser entero positivo")
    if not math.isfinite(max_distance_m) or max_distance_m <= 0:
        raise ValueError("max_distance_m debe ser positivo y finito")
    if gdf.crs is None or gdf.crs.to_epsg() != 32718:
        raise ValueError("Se requiere catastro en EPSG:32718")
    if target_geometry.geom_type != "Polygon" or not target_geometry.is_valid:
        raise ValueError("El lote objetivo debe ser un Polygon válido")
    transformer = Transformer.from_crs("EPSG:4326", TARGET_CRS, always_xy=True)
    spatial_index = gdf.sindex
    selected_candidates = []
    seen = set()
    for entry in metadata:
        pano_id = str(entry["pano_id"])
        if pano_id in seen:
            continue
        seen.add(pano_id)
        x, y = transformer.transform(float(entry["lon"]), float(entry["lat"]))
        camera = Point(x, y)
        distance = camera.distance(target_geometry)
        if distance > max_distance_m:
            continue
        edges = score_edges(
            gdf,
            target_index,
            target_geometry,
            camera,
            spatial_index,
            min_frontal_cosine=0.5,
        )
        visible_edges = [edge for edge in edges if edge["visible"]]
        if not visible_edges:
            continue
        edge = min(
            visible_edges,
            key=lambda item: camera.distance(Point(item["midpoint_x"], item["midpoint_y"])),
        )
        target = Point(edge["midpoint_x"], edge["midpoint_y"])
        bearing = bearing_from_north(camera, target)
        heading = float(entry["heading_deg"]) % 360.0
        selected_candidates.append({
            **entry,
            "camera_x": camera.x,
            "camera_y": camera.y,
            "camera_to_lot_m": distance,
            "target_edge_index": edge["edge_index"],
            "target_x": target.x,
            "target_y": target.y,
            "target_bearing_deg": bearing,
            "relative_yaw_deg": signed_angle(bearing - heading),
            "visibility_score": sum(item["score"] for item in edges),
        })
    selected_candidates.sort(key=lambda item: item["camera_to_lot_m"])
    return selected_candidates[:top_k]
