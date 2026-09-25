"""Select the seed block and its neighbouring complete blocks."""

from __future__ import annotations

import argparse
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import shapely


ROOT = Path(__file__).resolve().parents[1]
LOTS_PATH = ROOT / "Lotes/shp_files/BARRANCO_LM_geogpsperu.geojson"


def clean_geometry(geometry):
    geometry = shapely.set_precision(geometry, grid_size=1e-4)
    return geometry if geometry.is_valid else geometry.buffer(0)


def load_lots(path: Path = LOTS_PATH) -> gpd.GeoDataFrame:
    lots = gpd.read_file(path).to_crs(epsg=32718)
    lots.geometry = lots.geometry.apply(clean_geometry)
    return lots


def expand_connected(lots: gpd.GeoDataFrame, indices, gap_m: float = 1.0) -> set:
    """Include the complete connected component around the given lot indices."""
    selected = set(indices)
    while True:
        neighbourhood = lots.loc[list(selected)].geometry.buffer(gap_m).union_all()
        found = set(lots[lots.geometry.intersects(neighbourhood)].index)
        if found <= selected:
            return selected
        selected.update(found)


def select_block_lots(
    lots: gpd.GeoDataFrame,
    *,
    seed: int = 123,
    surrounding_m: float = 20.0,
    gap_m: float = 1.0,
) -> tuple[set, gpd.GeoDataFrame, object]:
    """Return centre IDs, full selection and seed ID; central lots stay identifiable."""
    if lots.empty:
        raise ValueError("No cadastral lots found")
    seed_index = lots.sample(1, random_state=seed).index[0]
    centre = expand_connected(lots, [seed_index], gap_m)
    nearby = lots.loc[list(centre)].geometry.union_all().buffer(surrounding_m)
    surrounding = lots[lots.geometry.intersects(nearby)].index
    all_indices = expand_connected(lots, surrounding, gap_m)
    return centre, lots.loc[sorted(all_indices)].copy(), seed_index


def plot_selection(selected: gpd.GeoDataFrame, centre: set, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(10, 10))
    selected.plot(ax=ax, edgecolor="black", facecolor="lightgray")
    selected.loc[sorted(centre)].plot(ax=ax, edgecolor="red", facecolor="salmon", alpha=0.5)
    ax.set_title(f"Seleccion de Cuadra y Alrededores ({len(selected)} lotes)")
    fig.savefig(output, dpi=130, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=123)
    parser.add_argument("--surrounding-m", type=float, default=20.0)
    parser.add_argument("--output", type=Path, default=ROOT / "outputs/cuadras_completas/lot_selection.png")
    args = parser.parse_args()
    centre, selected, seed_index = select_block_lots(
        load_lots(), seed=args.seed, surrounding_m=args.surrounding_m
    )
    plot_selection(selected, centre, args.output)
    print(f"Seed {seed_index}: {len(centre)} lotes centrales, {len(selected)} en total. {args.output}")


if __name__ == "__main__":
    main()
