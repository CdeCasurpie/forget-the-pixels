"""Paso 3: fachada rectilínea con pitch=0."""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "src"))
from geometry_projection.experiment import main

if __name__ == "__main__":
    main(step=3, output_default=HERE / "outputs")
