"""Generate ten complete theta examples, meshes and a visual contact sheet."""
import json
import sys
from pathlib import Path
import geopandas as gpd
from PIL import Image, ImageDraw
from shapely.geometry import Polygon

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'steps/step22_massing_before_after')]
from domain.theta import from_json
from domain.architecture import ParcelContext
from pipeline.theta import reconstruct
from modeling.fences import STYLES
from modeling.validation import validate_mesh
from modeling.grammar import street_envelope
from modeling.exporters.glb_exporter import export_glb
from build_after import render_case


def main():
    root=Path(__file__).parent
    source=root/'lotes/1134299_casa_salmon_republicana/fresh/request.json'
    out=root/'catalogo_cercos'
    poses=json.loads((ROOT/'data/poses_barranco/metadata.json').read_text())['panoramas']
    offset=json.loads((ROOT/'data/cadastral_offset.json').read_text())
    lots=gpd.read_file(ROOT/'data/lotes/BARRANCO_LM_geogpsperu.geojson').to_crs(32718)
    geom=lots[lots.objectid==1134299].iloc[0].geometry
    rows=[]
    for style in STYLES:
        panels=[]
        for mode,height in [('low',1.1),('high',2.8)]:
            r=json.loads(source.read_text())
            r['evidence']={}
            for run in r['theta']['site']['runs']:
                run.update(kind=style,height_mode=mode,height_m=height,
                           wall_material='plaster',gate_mode='auto',garage_mode='auto',
                           openness=.3,planters=style=='moderno')
            result=reconstruct(from_json(json.dumps(r)))
            p=result.resolved.context
            val=validate_mesh(result.mesh,Polygon(p.parcel),envelope=street_envelope(
                ParcelContext(p.parcel,explicit_fronts=p.fronts)))
            assert val['envelope_test']=='passed',val
            directory=out/f'{style}_{mode}'
            directory.mkdir(parents=True,exist_ok=True)
            (directory/'request.json').write_text(json.dumps(r,indent=2)+'\n')
            (directory/'validation.json').write_text(json.dumps(val,indent=2)+'\n')
            export_glb(result.mesh,directory/'building.glb')
            render_case(result,directory,1134299,geom,poses,offset,after_label=f'{style} {mode}')
            image=Image.open(directory/'render_ip-swgl4tqmTxk1289Ge_Q.jpg').convert('RGB')
            image.thumbnail((800,600))
            panel=Image.new('RGB',(800,630),'white')
            panel.paste(image,(0,30))
            ImageDraw.Draw(panel).text((15,10),f'{style} / {mode} / {height} m',fill='black')
            panels.append(panel)
            print(style,mode,val['envelope_test'])
        row=Image.new('RGB',(1600,630),'white')
        for i,panel in enumerate(panels):row.paste(panel,(800*i,0))
        rows.append(row)
    sheet=Image.new('RGB',(1600,630*len(rows)),'white')
    for i,row in enumerate(rows):sheet.paste(row,(0,630*i))
    sheet.save(out/'catalogo.png')


if __name__=='__main__':main()
