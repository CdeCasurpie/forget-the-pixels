"""Recorre la cuadra: GSV a la izquierda, nuestro modelo a la derecha.

Mismo punto de vista, mismo angulo: arrastra para mirar (yaw/pitch) y
pulsa W para avanzar a la siguiente panoramica (S retrocede). Sirve para
cazar errores lote por lote entre la casa real y la generada.

Uso:
    python scripts/cuadra_fotos/recorrido/ver_recorrido.py --recorrido scripts/cuadra_fotos/recorrido/recorrido_seed_123

Teclas: W/S o Espacio/Retroceso (siguiente/anterior), R (centrar),
        +/- (zoom), Q o Esc (salir). Arrastrar con el raton = mirar.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import cv2
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.widgets import Button


class Recorrido:
    def __init__(self, root: Path, out_w=960, out_h=600):
        self.root = root
        self.route = json.loads((root / "route.json").read_text())["panos"]
        self.out_w, self.out_h = out_w, out_h
        self.idx, self.yaw, self.pitch, self.fov = 0, 0.0, 0.0, 100.0
        self._drag = None
        self.gsv = self.modelo = None
        self.fig, (self.ax_gsv, self.ax_mod) = plt.subplots(1, 2, figsize=(15, 6.2))
        for ax in (self.ax_gsv, self.ax_mod):
            ax.set_axis_off()
        self.im_gsv = self.ax_gsv.imshow(np.zeros((out_h, out_w, 3), np.uint8))
        self.im_mod = self.ax_mod.imshow(np.zeros((out_h, out_w, 3), np.uint8))
        self.fig.canvas.mpl_connect("key_press_event", self.on_key)
        self.fig.canvas.mpl_connect("button_press_event", self.on_press)
        self.fig.canvas.mpl_connect("button_release_event", self.on_release)
        self.fig.canvas.mpl_connect("motion_notify_event", self.on_motion)
        # Botones por si el teclado no tiene el foco (Wayland/terminal).
        self.fig.subplots_adjust(bottom=0.12)
        ax_prev = self.fig.add_axes([0.30, 0.02, 0.12, 0.06])
        ax_next = self.fig.add_axes([0.58, 0.02, 0.12, 0.06])
        self.btn_prev = Button(ax_prev, "⟨ (S)")
        self.btn_next = Button(ax_next, "(W) ⟩")
        self.btn_prev.on_clicked(lambda _e: self.load(self.idx - 1))
        self.btn_next.on_clicked(lambda _e: self.load(self.idx + 1))
        try:
            self.fig.canvas.manager.window.raise_()
        except Exception:
            pass
        self.load(0)

    def load(self, idx: int):
        self.idx = idx % len(self.route)
        entry = self.route[self.idx]
        gsv = cv2.cvtColor(cv2.imread(str(self.root / entry["gsv"])), cv2.COLOR_BGR2RGB)
        mod = cv2.cvtColor(cv2.imread(str(self.root / entry["modelo"])), cv2.COLOR_BGR2RGB)
        # GSV zoom3 = 4096x2048; el nuestro sale a 2048x1024: igualar alto.
        if gsv.shape[0] != mod.shape[0]:
            gsv = cv2.resize(gsv, (mod.shape[1], mod.shape[0]), interpolation=cv2.INTER_AREA)
        self.gsv, self.modelo = gsv, mod
        self.yaw, self.pitch = 0.0, 0.0
        self.refresh()

    def crop(self, equirect: np.ndarray) -> np.ndarray:
        h, w = equirect.shape[:2]
        f = (self.out_w / 2) / math.tan(math.radians(self.fov / 2))
        xs = (np.arange(self.out_w) - self.out_w / 2) / f
        ys = (np.arange(self.out_h) - self.out_h / 2) / f
        xx, yy = np.meshgrid(xs, -ys)  # arriba = +pitch
        r = np.sqrt(xx**2 + yy**2 + 1)
        yaw = math.radians(self.yaw) + np.arctan2(xx, 1.0)
        pitch = math.radians(self.pitch) + np.arcsin(np.clip(yy / r, -1, 1))
        map_x = (((0.5 + yaw / (2 * math.pi)) % 1.0) * w).astype(np.float32)
        map_y = ((0.5 - pitch / math.pi) * h).astype(np.float32)
        return cv2.remap(equirect, map_x, map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)

    def refresh(self):
        self.im_gsv.set_data(self.crop(self.gsv))
        self.im_mod.set_data(self.crop(self.modelo))
        entry = self.route[self.idx]
        self.ax_gsv.set_title(f"GSV {entry['pano_id']} ({entry.get('date')})", fontsize=10)
        self.ax_mod.set_title("modelo (mismo punto/angulo)", fontsize=10)
        self.fig.suptitle(
            f"[{self.idx + 1}/{len(self.route)}] yaw={self.yaw:.0f} pitch={self.pitch:.0f} "
            f"fov={self.fov:.0f}  |  W/S: pano  R: centrar  +/-: zoom  Q: salir",
            fontsize=11)
        self.fig.canvas.draw_idle()

    def on_key(self, event):
        key = (event.key or "").lower()
        if key in ("w", " "):
            self.load(self.idx + 1)
        elif key in ("s", "backspace"):
            self.load(self.idx - 1)
        elif key == "r":
            self.yaw, self.pitch = 0.0, 0.0
            self.refresh()
        elif key in ("+", "="):
            self.fov = max(30.0, self.fov - 10.0)
            self.refresh()
        elif key in ("-", "_"):
            self.fov = min(150.0, self.fov + 10.0)
            self.refresh()
        elif key in ("q", "escape"):
            plt.close(self.fig)

    def on_press(self, event):
        if event.xdata is not None:
            self._drag = (event.x, event.y, self.yaw, self.pitch)

    def on_release(self, _event):
        self._drag = None

    def on_motion(self, event):
        if self._drag and event.xdata is not None:
            x0, y0, yaw0, pitch0 = self._drag
            self.yaw = yaw0 - (event.x - x0) * 0.12
            self.pitch = max(-85.0, min(85.0, pitch0 + (event.y - y0) * 0.12))
            self.refresh()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recorrido", type=Path, required=True)
    args = parser.parse_args()
    Recorrido(args.recorrido.resolve())
    plt.show()


if __name__ == "__main__":
    main()
