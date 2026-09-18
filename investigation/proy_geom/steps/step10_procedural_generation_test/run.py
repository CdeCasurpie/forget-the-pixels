"""Generate reference-inspired houses and real cadastral examples, offline."""

import argparse
from dataclasses import asdict, replace
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
import numpy as np
from shapely.geometry import Polygon, Point
from shapely.affinity import translate
from shapely.geometry.polygon import orient
from procedural_modeling.layout import propose_building
from procedural_modeling.grammar import generate_mesh
from procedural_modeling.validation import validate_mesh
from procedural_modeling.io import read_specification
from exporters.obj_exporter import export_obj
from exporters.glb_exporter import export_glb
from render import render


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parent / "outputs/new_proposal",
    )
    parser.add_argument("--no-render", action="store_true")
    parser.add_argument("--cadastre", action="store_true")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--spec",
        type=Path,
        help="Generate an edited specification instead of the demo set",
    )
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    examples = [
        (
            "01_narrow",
            Polygon([(0, 0), (5, 0), (5, 10), (0, 10)]),
            dict(
                front_edges=(0,),
                style="narrow",
                floors=2,
                setback_m=0.3,
                boundary="open",
            ),
        ),
        (
            "02_courtyard",
            Polygon([(0, 0), (10, 0), (10, 13), (0, 13)]),
            dict(
                front_edges=(0,),
                style="courtyard",
                floors=2,
                setback_m=2.3,
                boundary="wall",
            ),
        ),
        (
            "03_corner",
            Polygon([(0, 0), (10, 0), (10, 16), (0, 16)]),
            dict(
                front_edges=(0, 1),
                style="corner",
                floors=3,
                setback_m=1.5,
                boundary="fence",
            ),
        ),
        (
            "04_concave",
            Polygon([(0, 0), (10, 0), (10, 5), (5, 5), (5, 12), (0, 12)]),
            dict(
                front_edges=(0,),
                style="corner",
                floors=3,
                setback_m=1.2,
                boundary="open",
            ),
        ),
    ]
    if args.cadastre and not args.spec:
        import geopandas as gpd
        from pyproj import Transformer

        gdf = gpd.read_file(
            ROOT.parent / "Lotes/shp_files/BARRANCO_LM_geogpsperu_SuyoPomalia.shp"
        ).to_crs(32718)
        manifest = json.loads(
            (
                ROOT
                / "steps/step5_cylindrical_facade/outputs/lot_-12.135895_-77.019184/projection_metadata.json"
            ).read_text()
        )
        tf = Transformer.from_crs(4326, 32718, always_xy=True)
        cameras = [
            Point(*tf.transform(c["lon"], c["lat"])) for c in manifest["cameras"]
        ]
        for oid in [1134711, 1134712, 1135743]:
            original = orient(gdf[gdf.objectid == oid].geometry.iloc[0], sign=1)
            coords = list(original.exterior.coords)
            candidates = []
            for i, (a, b) in enumerate(zip(coords[:-1], coords[1:])):
                t = np.array(b) - a
                length = np.linalg.norm(t)
                t /= length
                n = np.array([t[1], -t[0]])
                mid = (np.array(a) + b) / 2
                for c in cameras:
                    ray = np.array([c.x, c.y]) - mid
                    if length > 2 and np.dot(ray, n) > 0:
                        candidates.append((np.linalg.norm(ray), i))
            edge = min(candidates)[1] if candidates else 0
            origin = original.centroid
            local = translate(original, -origin.x, -origin.y)
            examples.append(
                (
                    f"lot_{oid}",
                    local,
                    dict(
                        front_edges=(edge,),
                        style="corner" if oid == 1135743 else "courtyard",
                        floors=3 if oid == 1135743 else 2,
                        setback_m=0.9,
                        boundary="open",
                        objectid=oid,
                    ),
                )
            )
    if args.spec:
        loaded = read_specification(args.spec)
        examples = [
            (
                args.spec.stem,
                Polygon(loaded.parcel_xy or loaded.footprint_xy, loaded.parcel_holes),
                None,
            )
        ]
    report = []
    for name, parcel, options in examples:
        print("Generating", name, flush=True)
        spec = (
            loaded if args.spec else propose_building(parcel, seed=args.seed, **options)
        )
        if not args.spec and name.startswith("lot_"):
            original = gdf[gdf.objectid == int(name[4:])].geometry.iloc[0]
            spec = replace(
                spec,
                metadata={
                    **spec.metadata,
                    "local_origin_utm": [original.centroid.x, original.centroid.y],
                    "front_source": "nearest outward-facing edge to saved cameras; hypothesis",
                },
            )
        mesh = generate_mesh(spec)
        checks = validate_mesh(mesh, orient(parcel, sign=1))
        export_obj(mesh, args.output / f"{name}.obj")
        export_glb(mesh, args.output / f"{name}.glb")
        (args.output / f"{name}.json").write_text(
            json.dumps({"schema_version": 2, **asdict(spec)}, indent=2, allow_nan=False)
        )
        if not args.no_render:
            first_front = next((f for f in spec.facade_edges if f.is_front), None)
            direction = (1, -1.7, 1.1)
            if first_front is not None:
                t = np.array(first_front.vertex_b) - first_front.vertex_a
                t /= np.linalg.norm(t)
                n = np.array([t[1], -t[0]])
                direction = (*((n * 1.7) + (t * 0.8)), 1.0)
            render(mesh, args.output / f"{name}_clay.png", direction=direction)
            render(
                mesh, args.output / f"{name}_color.png", clay=False, direction=direction
            )
        report.append({"name": name, **checks})
        print(name, checks["triangles"], "triangles; parcel containment OK", flush=True)
    (args.output / "validation.json").write_text(json.dumps(report, indent=2))
    if not args.no_render:
        import cv2

        thumbnails = []
        for name, _, _ in examples:
            pair = []
            for mode in ("clay", "color"):
                preview = cv2.imread(str(args.output / f"{name}_{mode}.png"))
                preview = cv2.resize(preview, (600, 600), interpolation=cv2.INTER_AREA)
                caption = np.full((36, 600, 3), 240, np.uint8)
                cv2.putText(
                    caption,
                    f"{name} / {mode}",
                    (12, 25),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (35, 35, 35),
                    1,
                    cv2.LINE_AA,
                )
                pair.append(np.vstack([caption, preview]))
            thumbnails.append(np.hstack(pair))
        cv2.imwrite(str(args.output / "comparison.png"), np.vstack(thumbnails))
    print("Output:", args.output)


if __name__ == "__main__":
    main()
