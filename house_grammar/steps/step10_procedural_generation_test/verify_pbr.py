"""Generate actual per-pixel checker diagnostics and textured GLBs."""
from pathlib import Path
import sys
from dataclasses import replace
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"src"))
from shapely.geometry import Polygon
from modeling.layout import propose_building
from modeling.grammar import generate_mesh
from modeling.exporters.glb_exporter import export_glb
from render import render

def main():
    out=Path(__file__).parent/"outputs/pbr_corrected"
    out.mkdir(parents=True,exist_ok=True)
    spec=propose_building(Polygon([(0,0),(8,0),(8,9),(0,9)]),front_edges=(0,1),
                          floors=2,style="corner",setback_m=1.2,boundary="open")
    mesh=generate_mesh(spec)
    render(mesh,out/"checker.png",checker=True,size=1000)
    for name,color in [("white",(.94,.93,.91)),("blue",(.47,.63,.78)),
                       ("terracotta",(.76,.47,.33))]:
        mats=tuple(replace(m,base_color_rgb=color) if m.slot=="plaster" else m
                   for m in spec.appearance.materials)
        variant=replace(spec,appearance=replace(spec.appearance,materials=mats))
        export_glb(generate_mesh(variant),out/f"{name}.glb")
    print(out)

if __name__=="__main__":
    main()
