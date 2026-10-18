"""R0 reference runner: build every catalogue case and render it depth-tested.

Run from the repository root::

    PYTHONPATH=house_grammar/src python3 house_grammar/experiments/r0/run.py \
        --output apps/experimento_paralelizacion/gramatica_adaptable/r0

The output directory must not exist.  For each case the runner writes a
perspective preview, a true orthographic front elevation and a manifest entry
that records the semantics actually emitted, so a missing catalogue piece is a
readable failure instead of a silent visual gap.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import trimesh

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import cases  # noqa: E402  (sibling module)

from domain.theta import from_json  # noqa: E402
from modeling.software_render import render  # noqa: E402
from pipeline.theta import reconstruct  # noqa: E402


def front_direction(parcel):
    """Camera direction for the primary front: outward normal of parcel edge 0."""
    ring = np.asarray(parcel, dtype=float)
    edge = ring[1] - ring[0]
    normal = np.array([edge[1], -edge[0]])
    normal /= np.linalg.norm(normal)
    if np.dot(normal, ring.mean(axis=0) - (ring[0] + ring[1]) / 2) > 0:
        normal = -normal
    return np.array([normal[0], normal[1], 0.0])


def mesh_items(mesh):
    """Split a MeshData into (name, material, mesh) render items, with palette.

    Faces are grouped by material slot, which keeps the catalogue colours the
    grammar assigned instead of flattening every part to one grey.
    """
    palette = {}
    for mat in mesh.materials:
        color = np.asarray(mat['color'], dtype=float)
        if color.max() <= 1.0:
            color = color * 255.0
        palette[mat['name']] = tuple(int(round(c)) for c in color)
    vertices = np.asarray(mesh.vertices)
    faces = np.asarray(mesh.faces)
    if mesh.face_materials is None:
        return [('all', 'plaster', trimesh.Trimesh(vertices, faces, process=False))], palette
    face_materials = np.asarray(mesh.face_materials)
    items = []
    for index in np.unique(face_materials):
        name = mesh.materials[int(index)]['name']
        selection = face_materials == index
        items.append((name, name, trimesh.Trimesh(vertices, faces[selection], process=False)))
    return items, palette


def check(mesh, expected):
    semantics = sorted({part['name'] for part in mesh.parts})
    return dict(
        faces=int(len(mesh.faces)),
        finite=bool(np.isfinite(np.asarray(mesh.vertices)).all()),
        parts=len(mesh.parts),
        semantics=semantics,
        expected=expected,
        found=any(any(token in s for s in semantics) for token in expected),
    )


def contact_sheet(rows, output, columns=4, cell=320):
    """Compose the previews into one sheet; best effort, never fatal."""
    try:
        from PIL import Image, ImageDraw
    except Exception:
        return None
    tiles = []
    for row in rows:
        image = Image.open(row['preview']).convert('RGB')
        image.thumbnail((cell, cell))
        tile = Image.new('RGB', (cell, cell + 18), (255, 255, 255))
        tile.paste(image, ((cell - image.width) // 2, 0))
        ImageDraw.Draw(tile).text((4, cell + 3), row['name'], fill=(20, 20, 20))
        tiles.append(tile)
    if not tiles:
        return None
    rows_count = (len(tiles) + columns - 1) // columns
    sheet = Image.new('RGB', (columns * cell, rows_count * (cell + 18)), (255, 255, 255))
    for index, tile in enumerate(tiles):
        sheet.paste(tile, ((index % columns) * cell, (index // columns) * (cell + 18)))
    sheet.save(output)
    return str(output)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, help='new directory for the run')
    parser.add_argument('--size', type=int, default=760)
    parser.add_argument('--sheet', action='store_true', help='also write contact_sheet.png')
    args = parser.parse_args(argv)

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    manifest = []
    for name, request in cases.all_cases():
        started = time.time()
        result = reconstruct(from_json(json.dumps(request)))
        items, palette = mesh_items(result.mesh)
        parcel = request['context']['parcel']
        case_dir = output / name
        case_dir.mkdir()
        render(items, case_dir / 'preview.png', view=(27, -125), size=args.size, palette=palette)
        render(items, case_dir / 'front.png', direction=front_direction(parcel),
               ortho=True, size=args.size, palette=palette)
        expected = cases.EXPECTED[name.split('_')[0]]
        report = check(result.mesh, expected)
        report.update(name=name, seconds=round(time.time() - started, 2),
                      preview=str(case_dir / 'preview.png'),
                      front=str(case_dir / 'front.png'))
        manifest.append(report)
        flag = 'ok ' if report['found'] else 'MISS'
        print(f"{flag} {name:28s} faces={report['faces']:7d} parts={report['parts']:4d} "
              f"{report['seconds']:5.1f}s")

    (output / 'manifest.json').write_text(
        json.dumps(dict(version='r0-reference', cases=manifest), indent=2, ensure_ascii=False) + '\n')
    if args.sheet:
        contact_sheet(manifest, output / 'contact_sheet.png')
    missing = [row['name'] for row in manifest if not row['found']]
    print(f"\n{len(manifest) - len(missing)}/{len(manifest)} cases emitted their catalogue semantics")
    if missing:
        print('missing:', ', '.join(missing))
    return 1 if missing else 0


if __name__ == '__main__':
    raise SystemExit(main())
