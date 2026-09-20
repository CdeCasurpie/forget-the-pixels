"""Export six editable building programs with identical lot/seed for comparison."""
from pathlib import Path
from dataclasses import asdict
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"src"))
import cv2
import numpy as np
from shapely.geometry import Polygon
from procedural_modeling.families import FAMILIES
from procedural_modeling.layout import propose_building
from procedural_modeling.grammar import generate_mesh
from procedural_modeling.validation import validate_mesh
from exporters.glb_exporter import export_glb
from texturing.library import MaterialLibrary
from render import render

def main():
    root=Path(__file__).resolve().parents[2]
    out=Path(__file__).parent/"outputs/families_v4"
    out.mkdir(parents=True,exist_ok=True)
    library=MaterialLibrary(root/"assets/pbr/catalog.json")
    panels=[]; reports=[]
    for family in FAMILIES:
        lot=Polygon([(0,0),(9,0),(9,11),(0,11)])
        spec=propose_building(lot,architectural_family=family,seed=23,
                              floors=3 if family in ("mixed_use","balcony_apartments") else 2,
                              front_edges=(0,),setback_m=1.4,
                              boundary="wall" if family=="brick_courtyard" else "open")
        mesh=generate_mesh(spec)
        reports.append({"family":family,**validate_mesh(mesh,lot)})
        export_glb(mesh,out/f"{family}.glb",library=library)
        (out/f"{family}.json").write_text(json.dumps({"schema_version":3,**asdict(spec)},indent=2))
        render(mesh,out/f"{family}.png",direction=(.4,-1.8,.65),size=640,clay=False)
        panel=cv2.imread(str(out/f"{family}.png"))
        cv2.putText(panel,family,(15,30),cv2.FONT_HERSHEY_SIMPLEX,.7,(30,30,30),1,cv2.LINE_AA)
        panels.append(panel)
        print(family,flush=True)
    cv2.imwrite(str(out/"comparison.png"),np.vstack([np.hstack(panels[:3]),np.hstack(panels[3:])]))
    (out/"validation.json").write_text(json.dumps(reports,indent=2))

if __name__=="__main__":
    main()
