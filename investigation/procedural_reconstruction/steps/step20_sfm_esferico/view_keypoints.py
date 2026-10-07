"""Inspect cached PR+SIFT detections on original ERPs; no extraction/matching."""
import argparse
import json
from pathlib import Path
import sys

import numpy as np
from PIL import Image

STEP = Path(__file__).resolve().parent
sys.path.insert(0, str(STEP/'.dependencies'))
import pygame


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--smoke-test', action='store_true')
    args = parser.parse_args()
    entries = json.loads((STEP/'output_cycle/features/summary.json').read_text())
    pygame.init()
    screen = pygame.display.set_mode((1280, 800))
    pygame.display.set_caption('PR+SIFT - keypoints sobre ERP original')
    font = pygame.font.SysFont('sans', 19)
    clock = pygame.time.Clock()
    viewport = pygame.Rect(0, 85, 1280, 715)
    colors = [(255, 80, 80), (80, 255, 80), (80, 190, 255),
              (255, 220, 30), (255, 80, 255), (40, 255, 230)]
    index, show, rotation, radius = 0, True, -1, 3

    def load(i):
        entry = entries[i]; pid = entry['pano_id']
        with np.load(STEP/'output_cycle/features'/f"{entry['camera']}_{pid}.npz") as data:
            uv = data['keypoints_uv'].copy()
            groups = data['rectification_index'].copy()
            n = int(data['n'])
        with Image.open(STEP.parent.parent/'data/fotos_barranco'/f'{pid}.jpg') as image:
            image = image.convert('RGB')
            surface = pygame.image.fromstring(image.tobytes(), image.size, 'RGB')
        return surface, uv, groups, n

    def fit(surface):
        scale = min(viewport.width/surface.get_width(), viewport.height/surface.get_height())
        shift = np.array(viewport.center, float)-np.array(surface.get_size())*scale/2
        return scale, shift

    image, uv, groups, n = load(index)
    scale, shift = fit(image)
    running, frames = True, 0
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE: running = False
                elif event.key in (pygame.K_RIGHT, pygame.K_LEFT):
                    index = (index + (1 if event.key == pygame.K_RIGHT else -1)) % len(entries)
                    image, uv, groups, n = load(index); scale, shift = fit(image); rotation = -1
                elif event.key == pygame.K_SPACE: show = not show
                elif event.key == pygame.K_f: scale, shift = fit(image)
                elif event.key == pygame.K_0: rotation = -1
                elif pygame.K_1 <= event.key <= pygame.K_6: rotation = event.key-pygame.K_1
                elif event.key in (pygame.K_EQUALS, pygame.K_PLUS): radius = min(10, radius+1)
                elif event.key == pygame.K_MINUS: radius = max(1, radius-1)
            elif event.type == pygame.MOUSEWHEEL:
                mouse = np.array(pygame.mouse.get_pos())
                new = min(8., max(.05, scale*1.2**event.y))
                shift = mouse+(shift-mouse)*(new/scale); scale = new
            elif event.type == pygame.MOUSEMOTION and any(event.buttons):
                shift += event.rel
        screen.fill((22, 24, 29)); screen.set_clip(viewport)
        # Crop before scaling: zoom does not allocate a giant full-panorama surface.
        w, h = image.get_size()
        x0 = max(0, int((viewport.left-shift[0])/scale))
        y0 = max(0, int((viewport.top-shift[1])/scale))
        x1 = min(w, int(np.ceil((viewport.right-shift[0])/scale)))
        y1 = min(h, int(np.ceil((viewport.bottom-shift[1])/scale)))
        if x1 > x0 and y1 > y0:
            crop = image.subsurface((x0, y0, x1-x0, y1-y0))
            scaled = pygame.transform.smoothscale(crop, (max(1, round((x1-x0)*scale)), max(1, round((y1-y0)*scale))))
            screen.blit(scaled, (round(shift[0]+x0*scale), round(shift[1]+y0*scale)))
        selected = np.ones(len(uv), dtype=bool) if rotation < 0 else groups == rotation
        if show:
            xy = uv*scale+shift
            visible = selected & (xy[:, 0] >= 0) & (xy[:, 0] < 1280) & (xy[:, 1] >= 85) & (xy[:, 1] < 800)
            for point, group in zip(xy[visible], groups[visible]):
                center = tuple(np.rint(point).astype(int))
                pygame.draw.circle(screen, (0, 0, 0), center, radius+1)
                pygame.draw.circle(screen, colors[int(group) % len(colors)], center, radius, 1)
        screen.set_clip(None)
        entry = entries[index]
        lines = [f"{entry['camera']} ({index+1}/{len(entries)}) | {entry['pano_id']} | {len(uv)} keypoints | visibles: {int(selected.sum()) if show else 0}",
                 'Izq/Der: cámara | Rueda: zoom | Arrastrar: mover | Espacio: puntos ON/OFF | F: encajar | +/-: tamaño',
                 '0: todas | 1-6: rotación individual | '+ '  '.join(f'{m+1}: {int((groups==m).sum())}' for m in range(n))]
        for i, line in enumerate(lines): screen.blit(font.render(line, True, (240, 240, 240)), (10, 5+i*26))
        pygame.display.flip(); clock.tick(30); frames += 1
        if args.smoke_test and frames >= 3:
            print(f'Viewer opened: {len(entries)} panoramas; {entry["camera"]}: {len(uv)} cached keypoints')
            running = False
    pygame.quit()


if __name__ == '__main__':
    main()
