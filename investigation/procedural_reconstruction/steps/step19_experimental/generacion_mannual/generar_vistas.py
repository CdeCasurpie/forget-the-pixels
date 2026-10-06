"""Vistas adicionales para comparar una generacion con su foto de referencia.

No reemplaza a steps/step18_theta_interface/run.py (que valida y exporta el GLB);
solo anade las camaras que su harness no expone, para poder mirar la fachada
desde el mismo angulo bajo de una foto de Street View.

Uso:
    python generar_vistas.py <theta.json> <salida/> [--size 720]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[1]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "steps" / "step10_procedural_generation_test"))

from domain.theta import from_json          # noqa: E402
from pipeline.theta import reconstruct      # noqa: E402
from render import render                   # noqa: E402

# Camara: la calle esta en -y (el frente del lote es la arista 0).
VISTAS = {
    # Angulo bajo mirando hacia arriba, como la foto de referencia.
    "calle_baja": (0.10, -1.0, -0.32),
    "frontal": (0.0, -1.0, 0.02),
    "iso": (1.0, -1.7, 1.1),
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("theta", type=Path)
    parser.add_argument("salida", type=Path)
    parser.add_argument("--size", type=int, default=720)
    args = parser.parse_args()

    theta, salida = args.theta.resolve(), args.salida.resolve()
    salida.mkdir(parents=True, exist_ok=True)
    result = reconstruct(from_json(theta.read_text()))
    for nombre, direccion in VISTAS.items():
        destino = salida / f"{nombre}.png"
        render(result.mesh, destino, direction=direccion, size=args.size, clay=False)
        print(f"{nombre}.png <- direction={direccion}", flush=True)


if __name__ == "__main__":
    main()
