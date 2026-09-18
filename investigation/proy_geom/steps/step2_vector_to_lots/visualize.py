"""Paso 2: relacionar panoramas GSV con la arista visible de un lote.

Este archivo es deliberadamente un experimento ejecutable, no un módulo de
producción. Trabaja en UTM para que las distancias y los vectores estén en
metros, calcula una línea de vista 2D y genera un mapa de auditoría.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from pyproj import Transformer
from shapely.geometry import LineString, Point, Polygon


LOT_SHP_NAME = "BARRANCO_LM_geogpsperu_SuyoPomalia.shp"
TARGET_CRS = "EPSG:32718"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def defaults() -> tuple[Path, Path, Path]:
    root = repo_root()
    dataset = root / "investigation/proy_geom/steps/step1_acquisition/data/sample_route"
    shapefile = root / "investigation/Lotes/shp_files" / LOT_SHP_NAME
    output = root / "investigation/proy_geom/steps/step2_vector_to_lots/outputs"
    return dataset, shapefile, output


def bearing_from_north(origin: Point, target: Point) -> float:
    """Bearing geográfico, en grados, medido en sentido horario desde norte."""
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
        edges.append((index, start_point, end_point, LineString([start, end]).interpolate(0.5, normalized=True)))
    if not edges:
        raise ValueError("El lote no tiene una arista exterior válida")
    return edges


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


def load_metadata(dataset: Path) -> list[dict]:
    with (dataset / "metadata.json").open(encoding="utf-8") as stream:
        metadata = json.load(stream)
    if isinstance(metadata, dict):
        metadata = metadata.get("panoramas", metadata.get("items", []))
        # El Paso 1 guarda los panoramas indexados por nombre de archivo.
        if isinstance(metadata, dict):
            metadata = list(metadata.values())
    if not metadata:
        raise ValueError(f"No hay panoramas en {dataset / 'metadata.json'}")
    return metadata


def select_lot(gdf: gpd.GeoDataFrame, lot_row: int | None, objectid: int | None):
    if objectid is not None:
        matches = gdf[gdf["objectid"].astype(int) == objectid]
        if matches.empty:
            raise ValueError(f"No existe objectid={objectid} en el shapefile")
        return int(matches.index[0]), matches.iloc[0]
    row = 1515 if lot_row is None else lot_row
    if row < 0 or row >= len(gdf):
        raise ValueError(f"lot-row={row} fuera de rango [0, {len(gdf) - 1}]")
    return int(gdf.index[row]), gdf.iloc[row]


def analyze(
    dataset: Path,
    shapefile: Path,
    output: Path,
    lot_row: int | None,
    objectid: int | None,
    max_camera_distance_m: float,
    selection_json: Path | None = None,
    min_road_clearance_m: float = 1.0,
    min_frontal_cosine: float = 0.5,
) -> None:
    output.mkdir(parents=True, exist_ok=True)
    metadata = load_metadata(dataset)
    gdf = gpd.read_file(shapefile)
    if gdf.crs is None:
        raise ValueError("El shapefile no declara CRS")
    gdf = gdf.to_crs(TARGET_CRS)
    if selection_json is not None:
        with selection_json.open(encoding="utf-8") as stream:
            selection = json.load(stream)
        objectid = int(selection["objectid"])
        lot_row = None
    target_index, target_row = select_lot(gdf, lot_row, objectid)
    target_geometry = target_row.geometry
    if target_geometry.geom_type != "Polygon":
        raise ValueError("El experimento requiere por ahora un lote Polygon")

    transformer = Transformer.from_crs("EPSG:4326", TARGET_CRS, always_xy=True)
    spatial_index = gdf.sindex
    lots_union = gdf.geometry.union_all()
    records = []
    seen_pano_ids = set()
    excluded_by_distance = 0
    for position, pano in enumerate(metadata):
        pano_id = pano.get("pano_id")
        if pano_id in seen_pano_ids:
            continue
        seen_pano_ids.add(pano_id)
        camera_x, camera_y = transformer.transform(float(pano["lon"]), float(pano["lat"]))
        camera = Point(camera_x, camera_y)
        camera_inside_lot = lots_union.covers(camera)
        road_clearance = -camera.distance(lots_union.boundary) if camera_inside_lot else camera.distance(lots_union)
        camera_position_valid = (not camera_inside_lot) and road_clearance >= min_road_clearance_m
        camera_to_lot = camera.distance(target_geometry)
        if camera_to_lot > max_camera_distance_m:
            excluded_by_distance += 1
            continue
        edge_scores = score_edges(
            gdf, target_index, target_geometry, camera, spatial_index, min_frontal_cosine
        )
        geometric_score = sum(edge["score"] for edge in edge_scores)
        camera_score = geometric_score if camera_position_valid else 0
        visible_edges = [edge for edge in edge_scores if edge["visible"]]
        target_candidates = visible_edges or edge_scores
        selected_edge = min(
            target_candidates,
            key=lambda edge: camera.distance(Point(edge["midpoint_x"], edge["midpoint_y"])),
        )
        edge_start = Point(selected_edge["start_x"], selected_edge["start_y"])
        edge_end = Point(selected_edge["end_x"], selected_edge["end_y"])
        target = Point(selected_edge["midpoint_x"], selected_edge["midpoint_y"])
        distance = camera.distance(target)
        target_bearing = bearing_from_north(camera, target)
        heading = float(pano["heading_deg"]) % 360.0
        yaw = signed_angle(target_bearing - heading)
        records.append(
            {
                "sequence": position,
                "pano_id": pano.get("pano_id"),
                "lat": float(pano["lat"]),
                "lon": float(pano["lon"]),
                "heading_deg": heading,
                "camera_x": camera.x,
                "camera_y": camera.y,
                "target_x": target.x,
                "target_y": target.y,
                "edge_start_x": edge_start.x,
                "edge_start_y": edge_start.y,
                "edge_end_x": edge_end.x,
                "edge_end_y": edge_end.y,
                "distance_to_edge_m": distance,
                "camera_to_lot_m": camera_to_lot,
                "camera_inside_cadastral_lot": camera_inside_lot,
                "road_clearance_m": road_clearance,
                "camera_position_valid": camera_position_valid,
                "target_bearing_deg": target_bearing,
                "relative_yaw_deg": yaw,
                "visible": bool(camera_score),
                "camera_score": camera_score,
                "geometric_score_before_position_filter": geometric_score,
                "edge_count": len(edge_scores),
                "edge_scores": edge_scores,
            }
        )

    ranking = sorted(
        records,
        key=lambda record: (
            -record["camera_score"],
            -record["road_clearance_m"],
            record["distance_to_edge_m"],
        ),
    )
    eligible_ranking = [record for record in ranking if record["camera_score"] > 0]
    top_k = min(2, len(eligible_ranking))
    for rank, record in enumerate(ranking, start=1):
        record["camera_rank"] = rank
        record["selected_top2"] = record in eligible_ranking[:top_k]

    report = {
        "crs": TARGET_CRS,
        "shapefile": str(shapefile),
        "dataset": str(dataset),
        "target_lot_row": int(gdf.index.get_loc(target_index)),
        "target_objectid": target_row.get("objectid"),
        "target_geometry_bounds": list(target_geometry.bounds),
        "max_camera_distance_m": max_camera_distance_m,
        "min_road_clearance_m": min_road_clearance_m,
        "min_frontal_cosine": min_frontal_cosine,
        "excluded_by_distance": excluded_by_distance,
        "scoring": "edge midpoint: 1 only if unobstructed, not self-occluded and frontal enough; camera invalid if inside/too close to cadastral lot",
        "top_camera_sequences": [record["sequence"] for record in eligible_ranking[:top_k]],
        "panoramas": records,
    }
    (output / "step2_analysis.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    if not records:
        raise ValueError(
            f"Ninguna panorámica está a menos de {max_camera_distance_m:.1f} m del lote. "
            "Descarga una ruta más cercana o aumenta --max-camera-distance-m."
        )
    draw_map(gdf, target_index, records, output / "step2_vectors_map.png")
    visible_count = sum(record["visible"] for record in records)
    print(f"Lote objetivo: row={report['target_lot_row']}, objectid={report['target_objectid']}")
    print(f"Panoramas analizados: {len(records)}; con al menos una arista visible: {visible_count}")
    selected_text = ", ".join(f"#{record['sequence']} (score={record['camera_score']})" for record in eligible_ranking[:top_k])
    print("Top 2: " + (selected_text or "ninguna cámara válida"))
    print(f"Mapa: {output / 'step2_vectors_map.png'}")
    print(f"Reporte: {output / 'step2_analysis.json'}")


def draw_map(gdf: gpd.GeoDataFrame, target_index, records: list[dict], path: Path) -> None:
    target = gdf.loc[target_index].geometry
    fig, ax = plt.subplots(figsize=(14, 11))
    gdf.boundary.plot(ax=ax, color="#b7c2cc", linewidth=0.25, zorder=1)
    gpd.GeoSeries([target], crs=gdf.crs).plot(ax=ax, color="#ffe082", edgecolor="#1565c0", linewidth=2.2, zorder=2)
    vector_length = 22.0
    for record in records:
        camera = Point(record["camera_x"], record["camera_y"])
        north = point_at_bearing(camera, 0.0, vector_length)
        heading = point_at_bearing(camera, record["heading_deg"], vector_length)
        wanted = point_at_bearing(camera, record["target_bearing_deg"], vector_length)
        alpha = 1.0 if record.get("selected_top2") else 0.28
        width = 2.2 if record.get("selected_top2") else 1.0
        ax.plot([camera.x, north.x], [camera.y, north.y], color="#777777", linewidth=1, alpha=0.55 * alpha, zorder=4)
        ax.plot([camera.x, heading.x], [camera.y, heading.y], color="#d62728", linewidth=1.5 * alpha, alpha=alpha, zorder=5)
        target_color = "#2ca02c" if record["camera_score"] > 0 else "#ff8c00"
        ax.plot([camera.x, wanted.x], [camera.y, wanted.y], color=target_color, linewidth=width, alpha=alpha, zorder=6)
        ax.plot([camera.x, record["target_x"]], [camera.y, record["target_y"]], color=target_color, linestyle=":", linewidth=0.8, alpha=0.7 * alpha, zorder=3)
        ax.scatter(camera.x, camera.y, color="#111111", s=35 if record.get("selected_top2") else 15, zorder=7)
        label = f"{record['sequence']} ({record['camera_score']})" if record.get("selected_top2") else str(record["sequence"])
        ax.text(camera.x + 2, camera.y + 2, label, fontsize=8, fontweight="bold" if record.get("selected_top2") else "normal", alpha=alpha, zorder=8)
        if record["camera_score"] == 0:
            ax.scatter(camera.x, camera.y, marker="x", color="#ff7f0e", s=70, zorder=9)
    ax.set_aspect("equal")
    # El catastro completo sirve como contexto, pero el área de auditoría debe
    # verse a escala de calle para que los tres vectores sean interpretables.
    all_points = [(record["camera_x"], record["camera_y"]) for record in records]
    all_points += [(record["target_x"], record["target_y"]) for record in records]
    min_x = min(point[0] for point in all_points)
    max_x = max(point[0] for point in all_points)
    min_y = min(point[1] for point in all_points)
    max_y = max(point[1] for point in all_points)
    margin = 55.0
    ax.set_xlim(min_x - margin, max_x + margin)
    ax.set_ylim(min_y - margin, max_y + margin)
    ax.set_title("Paso 2 — Top 2 por visibilidad de puntos medios de aristas")
    ax.set_xlabel("UTM Este (m), EPSG:32718")
    ax.set_ylabel("UTM Norte (m), EPSG:32718")
    ax.legend(handles=[
        Line2D([0], [0], color="#777777", label="Norte geográfico"),
        Line2D([0], [0], color="#d62728", label="Heading de la panorámica"),
        Line2D([0], [0], color="#2ca02c", label="Bearing hacia arista cercana"),
        Line2D([0], [0], color="#ff8c00", label="Dirección bloqueada (score 0)"),
        Patch(facecolor="#ffe082", edgecolor="#1565c0", label="Lote objetivo"),
    ], loc="best")
    fig.tight_layout()
    fig.savefig(path, dpi=170)
    plt.close(fig)


def parse_args() -> argparse.Namespace:
    dataset_default, shapefile_default, output_default = defaults()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=dataset_default)
    parser.add_argument("--shapefile", type=Path, default=shapefile_default)
    parser.add_argument("--output", type=Path, default=output_default)
    parser.add_argument("--lot-row", type=int, default=1515, help="Índice de fila del shapefile (no objectid).")
    parser.add_argument("--objectid", type=int, help="Alternativa estable al índice de fila.")
    parser.add_argument("--max-camera-distance-m", type=float, default=100.0, help="Radio máximo cámara-lote en metros.")
    parser.add_argument("--selection-json", type=Path, help="Usa el objectid del lote guardado por select_candidates.py.")
    parser.add_argument("--min-road-clearance-m", type=float, default=1.0)
    parser.add_argument("--min-frontal-cosine", type=float, default=0.5, help="0.5 equivale a máximo 60° respecto a la normal.")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    analyze(
        args.dataset,
        args.shapefile,
        args.output,
        args.lot_row,
        args.objectid,
        args.max_camera_distance_m,
        args.selection_json,
        args.min_road_clearance_m,
        args.min_frontal_cosine,
    )
