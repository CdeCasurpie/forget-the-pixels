"""Build the reproducible multiview input for one cadastral lot."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from vision.acquisition import build_reconstruction_input, write_reconstruction_input


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shapefile", type=Path, default=ROOT.parent / "Lotes/shp_files/BARRANCO_LM_geogpsperu_SuyoPomalia.shp")
    parser.add_argument("--manifest", type=Path, default=ROOT / "steps/step5_cylindrical_facade/outputs/lot_-12.135895_-77.019184/projection_metadata.json")
    parser.add_argument("--objectid", type=int, default=1134979)
    parser.add_argument("--views", type=int, default=None)
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parent / "outputs/lot_1134979.json")
    args = parser.parse_args()
    package = build_reconstruction_input(args.shapefile, args.manifest, args.objectid, views=args.views)
    write_reconstruction_input(package, args.output)
    print(f"Lote: OBJECTID={package.lot.objectid}; vértices={len(package.lot.footprint_xy) - 1}")
    print(f"Vistas multivista: {len(package.views)}")
    print(f"Input: {args.output}")


if __name__ == "__main__":
    main()
