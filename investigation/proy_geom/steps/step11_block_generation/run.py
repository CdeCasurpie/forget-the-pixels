"""Build a street-area manifest and procedural meshes from accepted height fits."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import geopandas as gpd
import matplotlib.pyplot as plt

from exporters.glb_exporter import export_glb
from exporters.obj_exporter import export_obj
from procedural_modeling import (
    build_block_specifications,
    generate_mesh,
    load_height_fits,
    select_block_lots,
    validate_mesh,
)


def draw_front_map(lots, report, output: Path) -> None:
    """Audit image: gray parcels, green inferred fronts, blue generated lots."""
    generated = {item["objectid"] for item in report if item["status"] == "generated"}
    fig, axis = plt.subplots(figsize=(11, 11))
    lots.plot(ax=axis, color="#e2e2e2", edgecolor="#858585", linewidth=0.35)
    for _, row in lots.iterrows():
        record = next(item for item in report if item["objectid"] == int(row.objectid))
        coords = list(row.geometry.exterior.coords)
        for edge_index in record.get("street_edge_indices", []):
            a, b = coords[edge_index], coords[edge_index + 1]
            axis.plot([a[0], b[0]], [a[1], b[1]], color="#16a34a", linewidth=2.2)
        if int(row.objectid) in generated:
            gpd.GeoSeries([row.geometry.boundary], crs=lots.crs).plot(
                ax=axis, color="#2563eb", linewidth=1.1
            )
    axis.set_aspect("equal")
    axis.set_title("Step 11: verde = frente vial inferido; azul = malla generada")
    axis.set_axis_off()
    fig.tight_layout()
    fig.savefig(output, dpi=180)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cadastre",
        type=Path,
        default=ROOT.parent / "Lotes/shp_files/BARRANCO_LM_geogpsperu_SuyoPomalia.shp",
    )
    parser.add_argument(
        "--objectid",
        type=int,
        required=True,
        help="Cadastral lot at the centre of the working area",
    )
    parser.add_argument(
        "--height-fit",
        type=Path,
        action="append",
        required=True,
        help="Step 9 height_fit.json; repeat once per measured lot",
    )
    parser.add_argument("--radius-m", type=float, default=45.0)
    parser.add_argument("--setback-m", type=float, default=0.4)
    parser.add_argument("--neighbour-clearance-m", type=float, default=1.25)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--output", type=Path, default=Path(__file__).resolve().parent / "outputs/block"
    )
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    lots = gpd.read_file(args.cadastre).to_crs(32718)
    if "objectid" not in lots:
        raise KeyError("The cadastre needs an 'objectid' column")
    selected = select_block_lots(lots, args.objectid, args.radius_m)
    heights = load_height_fits(args.height_fit)
    specs, report = build_block_specifications(
        selected,
        heights,
        seed=args.seed,
        setback_m=args.setback_m,
        neighbour_clearance_m=args.neighbour_clearance_m,
    )
    validation = []
    for objectid, spec, origin in specs:
        mesh = generate_mesh(spec)
        # The mesh is local; validate against its local cadastral parcel.
        from shapely.geometry import Polygon

        parcel = Polygon(spec.parcel_xy, spec.parcel_holes)
        checks = validate_mesh(mesh, parcel)
        export_obj(mesh, args.output / f"lot_{objectid}.obj")
        export_glb(mesh, args.output / f"lot_{objectid}.glb")
        (args.output / f"lot_{objectid}.json").write_text(
            json.dumps({"schema_version": 2, **asdict(spec)}, indent=2)
        )
        validation.append({"objectid": objectid, **checks})
    manifest = {
        "schema_version": 1,
        "crs": "EPSG:32718",
        "center_objectid": args.objectid,
        "radius_m": args.radius_m,
        "street_front_method": {
            "name": "outward_clearance_to_neighbouring_parcels",
            "neighbour_clearance_m": args.neighbour_clearance_m,
            "minimum_clear_sample_ratio": 2 / 3,
            "warning": "public-space candidate only; validate against a road layer when available",
        },
        "height_policy": "generate only lots with supplied Step 9 height fits; others are skipped",
        "lots": report,
        "validation": validation,
    }
    (args.output / "block_manifest.json").write_text(json.dumps(manifest, indent=2))
    draw_front_map(selected, report, args.output / "fronts.png")
    print(
        f"Selected {len(selected)} lots; generated {len(specs)} meshes; skipped {len(selected)-len(specs)} without a usable height/front."
    )
    print(f"Output: {args.output}")


if __name__ == "__main__":
    main()
