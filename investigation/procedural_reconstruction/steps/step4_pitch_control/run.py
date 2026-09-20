"""Paso 4: elevación paramétrica manteniendo el yaw de cada fachada."""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "src"))
from vision.projection.experiment import main

if __name__ == "__main__":
    main(step=4, output_default=HERE / "outputs")
