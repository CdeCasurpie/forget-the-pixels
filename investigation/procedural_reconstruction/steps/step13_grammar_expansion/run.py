import sys
import json
import time
from pathlib import Path
from shapely.geometry.polygon import orient
import numpy as np

sys.path.insert(0, str(Path("src").resolve()))
from procedural_modeling.layout import propose_building
from procedural_modeling.grammar import generate_mesh
from exporters.glb_exporter import MaterialLibrary, export_glb
from cases import CASES

def run_phase0():
    out_dir = Path("tests/fixtures/architecture")
    out_dir.mkdir(exist_ok=True, parents=True)
    
    catalog = MaterialLibrary(Path("assets/pbr/catalog.json"))
    baseline_stats = {}
    
    for case in CASES:
        name = case["name"]
        print(f"Generando {name}...")
        
        parcel = orient(case["parcel"], sign=1)
        
        t0 = time.time()
        try:
            spec = propose_building(
                parcel=parcel,
                front_edges=tuple(case["front_edges"]),
                floors=case["floors"],
                style=case["style"],
                seed=42,
                architectural_family=case["family"],
                setback_m=case["setback"]
            )
            mesh = generate_mesh(spec)
            t1 = time.time()
            
            # Export
            glb_path = out_dir / f"{name}_baseline.glb"
            export_glb(mesh, str(glb_path), library=catalog)
            
            baseline_stats[name] = {
                "time_ms": int((t1 - t0) * 1000),
                "vertices": len(mesh.vertices),
                "faces": len(mesh.faces),
                "materials": len(mesh.materials),
                "status": "success"
            }
        except Exception as e:
            baseline_stats[name] = {
                "status": "failed",
                "error": str(e)
            }
            print(f"Error en {name}: {e}")
            
    with open(out_dir / "baseline_stats.json", "w") as f:
        json.dump(baseline_stats, f, indent=2)
        
    print("Baseline completado.")

if __name__ == "__main__":
    run_phase0()
