import sys
import numpy as np
from pathlib import Path
from shapely.geometry import Polygon

# Añadir el directorio src al path para que funcionen las importaciones
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from procedural_modeling.layout import propose_building
from procedural_modeling.grammar import generate_mesh
from procedural_modeling.families import apply_family
from exporters.glb_exporter import MaterialLibrary, export_glb

def main():
    root = Path(__file__).resolve().parents[2]
    out_dir = Path(__file__).resolve().parent / "outputs/neighborhood"
    out_dir.mkdir(parents=True, exist_ok=True)
    
    catalog = MaterialLibrary(root / "assets/pbr/catalog.json")
    rng = np.random.default_rng(2024)

    print("Generando 20 casas peruanas procedurales únicas...")
    for i in range(20):
        # Generar lotes de tamaños típicos (angostos, anchos)
        w = rng.uniform(5.0, 10.0)
        d = rng.uniform(12.0, 20.0)
        parcel = Polygon([(0,0), (w,0), (w,d), (0,d)])
        
        style = str(rng.choice(["narrow", "courtyard", "narrow"]))
        floors = int(rng.integers(1, 6)) # 1 a 5 pisos
        family = "auto"
        
        spec = propose_building(
            parcel=parcel,
            front_edges=(0,), # La fachada es el borde inferior (calle)
            floors=floors,
            style=style,
            seed=i,
            architectural_family=family
        )
        mesh_builder = generate_mesh(spec)
        
        file_name = out_dir / f"house_{i:02d}_{spec.metadata.get('architectural_family')}_{floors}pisos.glb"
        export_glb(mesh_builder, file_name, library=catalog)
        print(f"Generada: {file_name.name}")

    print(f"\n¡Barrio completo generado exitosamente en:\n{out_dir}")

if __name__ == "__main__":
    main()
