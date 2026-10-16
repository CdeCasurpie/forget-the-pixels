"""Prepare cadastral overlays locally; never calls a model."""
import hashlib
import json
from pathlib import Path
import sys

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parents[1]))
from packages.barranco_imaging.angular import project_points


def main():
    manifest_path = ROOT/'inputs/manifest.json'
    manifest = json.loads(manifest_path.read_text())
    evidence = json.loads((ROOT/'inputs/evidence.json').read_text())
    data = json.loads((ROOT/'inputs/context_and_levels.json').read_text())
    levels = data['levels_m']
    originals = manifest.get('clean_images', manifest['images'])
    output = ROOT/'inputs/projected_images'
    output.mkdir(exist_ok=True)
    images = []
    for index, (name, e) in enumerate(zip(originals, evidence), 1):
        source = ROOT/name
        if hashlib.sha256(source.read_bytes()).hexdigest() != manifest['sha256'][name]:
            raise ValueError(f'Original image changed: {name}')
        image = cv2.imread(str(source))
        spec = e['projection']
        if spec['version'] != 'angular-enu-v1':
            raise ValueError('Unknown projection')
        h, w = image.shape[:2]
        if (w, h) != (spec['width'], spec['height']):
            raise ValueError('Photo/camera dimensions disagree')
        context = data['context']
        vertices = np.asarray(context['parcel']) + np.asarray(context['metric_origin'][:2]) - np.asarray(spec['camera_xy'])
        vertices = np.vstack([vertices, vertices[0]])

        def line(a, b, color):
            points = project_points(np.linspace(a, b, 80), spec)
            for p, q in zip(points[:-1], points[1:]):
                if np.linalg.norm(p-q) >= max(w, h)/2:
                    continue
                ok, p0, p1 = cv2.clipLine((0, 0, w, h), tuple(np.rint(p).astype(int)), tuple(np.rint(q).astype(int)))
                if ok:
                    cv2.line(image, p0, p1, color, 2, cv2.LINE_AA)

        for a in vertices[:-1]:
            line([*a, levels[0]], [*a, levels[-1]], (255, 180, 40))
        for j, z in enumerate(levels):
            color = (0, 255, 255) if j == 0 else ((255, 80, 255) if j == len(levels)-1 else (0, 255, 0))
            for a, b in zip(vertices[:-1], vertices[1:]):
                line([*a, z], [*b, z], color)
            uv = project_points([[*a, z] for a in vertices[:-1]], spec)
            visible = [p for p in uv if 0 <= p[0] < w-160 and 100 < p[1] < h-15]
            if visible:
                p = min(visible, key=lambda p: p[0])
                at = (int(p[0])+5, int(p[1])-5)
                label = f'N{j}: {z:g} m'
                cv2.putText(image, label, at, cv2.FONT_HERSHEY_SIMPLEX, .45, (0,0,0), 3)
                cv2.putText(image, label, at, cv2.FONT_HERSHEY_SIMPLEX, .45, color, 1)
        # Add legend outside the photograph; image projection itself is unchanged.
        image = cv2.copyMakeBorder(image, 90, 0, 0, 0, cv2.BORDER_CONSTANT, value=(25,25,25))
        lines = [f'LOTE {data["lot_id"]} | FOTO {index:03} | {len(levels)-1} pisos | altura {levels[-1]:g} m',
                 'Alturas por piso (m): '+', '.join(f'{b-a:g}' for a,b in zip(levels[:-1],levels[1:])),
                 'Amarillo: suelo | Verde: niveles | Magenta: techo | Azul: aristas',
                 'REFERENCIA CATASTRAL + ALTURAS HUMANAS; no es la silueta observada']
        for i, text in enumerate(lines):
            cv2.putText(image, text, (10,19+21*i), cv2.FONT_HERSHEY_SIMPLEX, .46, (255,255,255), 1, cv2.LINE_AA)
        relative = f'inputs/projected_images/{index:03}.jpg'
        if not cv2.imwrite(str(ROOT/relative), image):
            raise RuntimeError('Could not save projection')
        images.append(relative)
        manifest['sha256'][relative] = hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()
    manifest.update(clean_images=originals, images=images, primary_image=images[0],
                    projection_levels_m=levels, image_role='cadastral_prism_with_human_floor_levels',
                    primary_selection='First B evidence, with cadastral prism and manual levels',
                    overlay_note='90px legend above unchanged photo; angular camera metadata refers to photo excluding legend')
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')


if __name__ == '__main__':
    main()
