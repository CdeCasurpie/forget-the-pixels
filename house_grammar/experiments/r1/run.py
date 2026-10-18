"""R1 reference runner: new masses dressed with real catalogue pieces.

Run from the repository root::

    PYTHONPATH=house_grammar/src python3 house_grammar/experiments/r1/run.py \
        --output apps/experimento_paralelizacion/gramatica_adaptable/r1

The output directory must not exist.  For each case the runner plans the
massing, interiors and constructive envelope, derives the neutral surface chart,
places a frontón and a balcón through the catalogue resolvers, materializes them
with the catalogue assemblers and renders the masses plus the pieces.  The
manifest records the semantics actually emitted and proves the massing
footprints were untouched, so a missing piece is a readable failure.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import trimesh
from shapely.geometry import Polygon, shape
from shapely.ops import unary_union

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import cases  # noqa: E402  (sibling module)

from modeling.software_render import render  # noqa: E402
from planning.catalogue import materialize  # noqa: E402
from planning.chart import permitted_envelope, surface_chart  # noqa: E402
from planning.envelope import plan_envelope  # noqa: E402
from planning.envelope_export import MATERIAL_COLORS, solids  # noqa: E402


def mesh_items(mesh, palette):
    """Split a MeshData into (name, material, mesh) render items."""
    for material in mesh.materials:
        color = np.asarray(material['color'], dtype=float)
        if color.max() <= 1.0:
            color = color * 255.0
        palette.setdefault(material['name'], tuple(int(round(c)) for c in color))
    vertices = np.asarray(mesh.vertices)
    faces = np.asarray(mesh.faces)
    if mesh.face_materials is None:
        return [('all', 'plaster', trimesh.Trimesh(vertices, faces, process=False))]
    face_materials = np.asarray(mesh.face_materials)
    items = []
    for index in np.unique(face_materials):
        name = mesh.materials[int(index)]['name']
        selection = face_materials == index
        items.append((name, name, trimesh.Trimesh(vertices, faces[selection], process=False)))
    return items


def front_direction(frame):
    inward = np.asarray(frame['inward'], dtype=float)
    direction = np.array([-inward[0], -inward[1], 0.0])
    return direction / np.linalg.norm(direction)


def massing_footprints(plan):
    """Storey id -> area, the silhouette the pieces must not move."""
    data = plan.to_dict()
    return {storey['id']: float(shape(storey['geometry']).area)
            for storey in data['interior']['massing']['storeys']}


def chart_footprints(chart):
    return {body.id: float(Polygon(body.footprint).area) for body in chart.bodies}


def contact_sheet(rows, output, columns=2, cell=420):
    try:
        from PIL import Image, ImageDraw
    except Exception:
        return None
    tiles = []
    for row in rows:
        image = Image.open(row['front']).convert('RGB')
        image.thumbnail((cell, cell))
        tile = Image.new('RGB', (cell, cell + 18), (255, 255, 255))
        tile.paste(image, ((cell - image.width) // 2, 0))
        ImageDraw.Draw(tile).text((4, cell + 3), row['name'], fill=(20, 20, 20))
        tiles.append(tile)
    if not tiles:
        return None
    count = (len(tiles) + columns - 1) // columns
    sheet = Image.new('RGB', (columns * cell, count * (cell + 18)), (255, 255, 255))
    for index, tile in enumerate(tiles):
        sheet.paste(tile, ((index % columns) * cell, (index // columns) * (cell + 18)))
    sheet.save(output)
    return str(output)


def run_case(name, request, style, case_dir, size):
    started = time.time()
    case_dir.mkdir()
    plan = plan_envelope(request)
    chart = surface_chart(plan)
    crowns, balconies = cases.placements(chart, style)
    envelope = permitted_envelope(plan)
    parcel = Polygon(request['context']['parcel'])
    catalog, resolved_crowns, resolved_balconies = materialize(
        chart, crowns=crowns, balconies=balconies, style=style,
        envelope=envelope, parcel=parcel)

    palette = dict(MATERIAL_COLORS)
    items = list(solids(plan)[0])
    items += mesh_items(catalog, palette)

    fronts = plan.to_dict()['interior']['massing']['fronts']
    primary = min(fronts, key=lambda key: (-fronts[key]['length_m'], key))
    render(items, case_dir / 'preview.png', view=(27, -125), size=size, palette=palette)
    render(items, case_dir / 'front.png', direction=front_direction(fronts[primary]), ortho=True,
           size=size, palette=palette)

    semantics = sorted({part['name'] for part in catalog.parts})
    found = all(any(token in semantic for semantic in semantics) for token in cases.EXPECTED)
    before = massing_footprints(plan)
    after = chart_footprints(chart)
    drift = {key: round(abs(after[key] - value), 9) for key, value in before.items() if key in after}
    return dict(
        name=name, style=style, seconds=round(time.time() - started, 2),
        found=bool(found), semantics=semantics,
        crowns=[dict(id=crown.controls.id, base_z=round(crown.base_z, 3),
                     reason=crown.classification_reason) for crown in resolved_crowns],
        balconies=[dict(id=balcony.controls.id, floor_z=round(balcony.floor_z, 3),
                        upper=balcony.upper, ornate=balcony.ornate)
                   for balcony in resolved_balconies],
        catalogue_faces=int(len(catalog.faces)), envelope_parts=len(plan.parts),
        massing_footprints=len(before), silhouette_drift_m2=drift,
        preview=str(case_dir / 'preview.png'), front=str(case_dir / 'front.png'))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, help='new directory for the run')
    parser.add_argument('--size', type=int, default=760)
    parser.add_argument('--sheet', action='store_true', help='also write contact_sheet.png')
    args = parser.parse_args(argv)

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    manifest = []
    for name, request, style in cases.CASES:
        report = run_case(name, request, style, output / name, args.size)
        manifest.append(report)
        flag = 'ok ' if report['found'] else 'MISS'
        print(f"{flag} {name:30s} faces={report['catalogue_faces']:6d} "
              f"crowns={len(report['crowns'])} balconies={len(report['balconies'])} "
              f"{report['seconds']:5.1f}s")

    (output / 'manifest.json').write_text(
        json.dumps(dict(version='r1-reference', cases=manifest), indent=2, ensure_ascii=False) + '\n')
    if args.sheet:
        contact_sheet(manifest, output / 'contact_sheet.png')
    missing = [row['name'] for row in manifest if not row['found']]
    print(f"\n{len(manifest) - len(missing)}/{len(manifest)} cases emitted crown and balcony pieces")
    if missing:
        print('missing:', ', '.join(missing))
    return 1 if missing else 0


if __name__ == '__main__':
    raise SystemExit(main())
