"""Manual graph walk; only the execute button starts reconstruction."""

import argparse
from functools import lru_cache
import json
from pathlib import Path
import queue
import subprocess
import sys
import threading

STEP = Path(__file__).resolve().parent
sys.path.insert(0, str(STEP/'.dependencies'))
import pygame
import numpy as np
from PIL import Image

from geometry_stage4 import position_enu
from cycle_pipeline import is_cycle, cycle_pairs, run_cycle

ROOT = STEP.parent.parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--radius', type=float, default=180)
    parser.add_argument('--epipolar-px', type=float, default=4)
    parser.add_argument('--min-parallax-deg', type=float, default=2)
    parser.add_argument('--max-ray-gap-m', type=float, default=1)
    parser.add_argument('--smoke-test', action='store_true', help='Render three frames and exit without selecting anything')
    parser.add_argument('--run-selection', type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    thresholds = argparse.Namespace(epipolar_px=args.epipolar_px,
                                    min_parallax_deg=args.min_parallax_deg, max_ray_gap_m=args.max_ray_gap_m)
    if not np.isfinite(args.radius) or args.radius <= 0 or not all(np.isfinite(v) and v >= 0 for v in vars(thresholds).values()):
        parser.error('Invalid radius or thresholds')
    if args.run_selection:
        try:
            run_cycle(args.run_selection, thresholds, lambda text: print(text, flush=True))
        except Exception as error:
            print(f'ERROR: {error}', flush=True)
            sys.exit(1)
        return
    metadata = json.loads((ROOT/'data/poses_barranco/metadata.json').read_text())['panoramas']
    positions = {pid: position_enu(p['lat'], p['lon'], -12.136513, -77.020520)[:2]
                 for pid, p in metadata.items()}
    visible = {pid for pid, pos in positions.items() if np.linalg.norm(pos) <= args.radius}
    pygame.init()
    screen = pygame.display.set_mode((1280, 800)); pygame.display.set_caption('Step 20 - Ciclo Street View')
    font = pygame.font.SysFont('sans', 17)
    clock = pygame.time.Clock()
    map_rect = pygame.Rect(0, 0, 900, 730)
    button = pygame.Rect(925, 620, 330, 48)
    selected_nodes, selected_edges = [], []
    scale, shift = 700/(2*args.radius), np.array([450., 365.])
    status, process, frames = 'Selecciona una cámara para empezar', None, 0
    messages = queue.Queue()

    @lru_cache(maxsize=24)
    def thumbnail(pid):
        try:
            with Image.open(ROOT/'data/fotos_barranco'/f'{pid}.jpg') as im:
                im.thumbnail((350, 180)); im = im.convert('RGB')
                return pygame.image.fromstring(im.tobytes(), im.size, 'RGB')
        except (OSError, ValueError):
            return None

    def text(value, x, y, color=(230, 230, 230)):
        screen.blit(font.render(str(value), True, color), (x, y))

    def read_process(proc):
        for line in proc.stdout:
            if line.strip():
                messages.put(line.strip())

    running = True
    while running:
        busy = process is not None and process.poll() is None
        while not messages.empty():
            status = messages.get()
        if process is not None and process.poll() is not None:
            if process.returncode:
                status = f'ERROR ({process.returncode}): '+status
            process = None
        closed = is_cycle(selected_nodes, metadata)
        selected_edges = list(zip(selected_nodes, selected_nodes[1:]))
        selected_pairs = cycle_pairs(selected_nodes) if closed else selected_edges
        # Reveal all outgoing neighbors of the current node, even beyond initial radius.
        if selected_nodes:
            visible.update(pid for pid in metadata[selected_nodes[-1]]['neighbor_ids'] if pid in positions)
        coords = {pid: (int(shift[0]+positions[pid][0]*scale), int(shift[1]-positions[pid][1]*scale))
                  for pid in sorted(visible)}
        valid = (set(metadata[selected_nodes[-1]]['neighbor_ids'])-set(selected_nodes)) & visible if selected_nodes else visible
        mouse = pygame.mouse.get_pos()
        near = [pid for pid, xy in coords.items() if map_rect.collidepoint(xy) and np.linalg.norm(np.array(xy)-mouse) <= 9]
        hover = min(near, key=lambda p: np.linalg.norm(np.array(coords[p])-mouse)) if near else None
        for event in pygame.event.get():
            if event.type == pygame.QUIT or event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False
            elif event.type == pygame.KEYDOWN and not busy:
                if event.key == pygame.K_BACKSPACE and selected_nodes: selected_nodes.pop()
                if event.key == pygame.K_r: selected_nodes.clear()
            elif event.type == pygame.MOUSEWHEEL and map_rect.collidepoint(mouse):
                factor = 1.15**event.y
                new_scale = min(50, max(.1, scale*factor)); factor = new_scale/scale
                shift = np.array(mouse)+(shift-np.array(mouse))*factor; scale = new_scale
            elif event.type == pygame.MOUSEMOTION and (event.buttons[1] or event.buttons[2]):
                shift += event.rel
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and not busy:
                if button.collidepoint(event.pos) and closed:
                    missing = [pid for pid in selected_nodes if not (ROOT/'data/fotos_barranco'/f'{pid}.jpg').exists()]
                    if missing:
                        status = 'Falta imagen: '+missing[0]
                    else:
                        selection = dict(panorama_ids=selected_nodes.copy(), pairs=selected_pairs,
                                         coordinates={pid: {k: metadata[pid][k] for k in ('lat', 'lon')} for pid in selected_nodes})
                        path = STEP/'selected_cycle.json'; path.write_text(json.dumps(selection, indent=2)+'\n')
                        command = [sys.executable, str(Path(__file__).resolve()), '--run-selection', str(path),
                                   '--epipolar-px', str(args.epipolar_px), '--min-parallax-deg', str(args.min_parallax_deg),
                                   '--max-ray-gap-m', str(args.max_ray_gap_m)]
                        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                                   text=True, bufsize=1)
                        threading.Thread(target=read_process, args=(process,), daemon=True).start()
                        status = 'Iniciando pipeline...'
                elif hover in valid and map_rect.collidepoint(event.pos):
                    selected_nodes.append(hover)
        screen.fill((24, 27, 32)); screen.set_clip(map_rect)
        for a in coords:
            for b in metadata[a]['neighbor_ids']:
                if b in coords:
                    pygame.draw.line(screen, (43, 48, 55), coords[a], coords[b])
        for a, b in selected_pairs:
            pygame.draw.line(screen, (0, 230, 100) if closed else (255, 190, 40), coords[a], coords[b], 3)
        for pid, xy in coords.items():
            color = (255, 190, 40) if pid in selected_nodes else ((80, 210, 255) if pid in valid else (85, 90, 98))
            pygame.draw.circle(screen, color, xy, 5 if pid in valid or pid in selected_nodes else 3)
        for i, pid in enumerate(selected_nodes): text(f'P{i}', *coords[pid])
        screen.set_clip(None)
        text(f'{len(selected_nodes)} cámaras | '+('CICLO CERRADO' if closed else 'Recorrido abierto'), 920, 20)
        text('Azul: vecinos seleccionables', 920, 50)
        text('Amarillo: selección', 920, 75)
        preview = hover or (selected_nodes[-1] if selected_nodes else None)
        if preview:
            text(preview, 920, 110)
            text(metadata[preview].get('date', ''), 920, 135)
            thumb = thumbnail(preview)
            if thumb: screen.blit(thumb, (920, 170))
            else: text('Imagen no disponible', 920, 180)
        for i, line in enumerate(['Click: iniciar / vecino', 'Backspace: Undo', 'R: reset', 'Rueda: zoom',
                                  'Arrastre derecho/central: pan', 'ESC: salir (detiene ejecución)']):
            text(line, 920, 380+26*i)
        pygame.draw.rect(screen, (20, 140, 65) if closed and not busy else (80, 80, 80), button)
        text('EJECUTAR CICLO' if not busy else 'EJECUTANDO...', 955, 635)
        # Wrap messages so missing pano IDs and errors remain readable.
        for i in range(3): text(status[i*130:(i+1)*130], 10, 735+20*i)
        pygame.display.flip(); clock.tick(30); frames += 1
        if args.smoke_test and frames >= 3:
            print(f'UI opened and rendered: {len(visible)} nearby nodes; no selection or reconstruction')
            running = False
    if process is not None and process.poll() is None:
        process.terminate(); process.wait()
    pygame.quit()


if __name__ == '__main__':
    main()
