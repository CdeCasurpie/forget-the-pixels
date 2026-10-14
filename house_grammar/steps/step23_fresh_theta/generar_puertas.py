"""20 style/shape/size assemblies and the complete house. GLB/JSON only."""
import json
import sys
from dataclasses import asdict
from pathlib import Path
import numpy as np
from shapely.geometry import Polygon

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from domain.models import Opening, DoorControls
from domain.theta import from_json
from domain.architecture import ParcelContext
from modeling.door_assembly import DEFAULTS, build_door
from modeling.mesh_builder import MeshBuilder
from modeling.exporters.glb_exporter import export_glb
from modeling.validation import validate_mesh
from modeling.grammar import street_envelope
from pipeline.theta import reconstruct


def main():
    root=Path(__file__).parent
    catalog=root/'catalogo_puertas'
    catalog.mkdir(exist_ok=True)
    index=[]
    for style in DEFAULTS:
        for shape in ('rectangle','arch'):
            for large in (False,True):
                name=f'{style}_{shape}_'+('porton' if large else 'puerta')
                portal='columns' if large and style in ('clasico','barroco') else 'pilasters' if style=='republicano' else 'none'
                op=Opening('gate' if large else 'door',1.,.1,3.2 if large else 1.1,3.4 if large else 2.7,
                    shape=shape,frame_width_m=.10 if style!='moderno' else .045,
                    frame_depth_m=.14 if style!='moderno' else .04,
                    door=DoorControls(model=style,portal=portal,cornice=portal!='none',
                        transom_height_m=.55 if shape=='arch' else 0.,
                        transom_grille=style in ('republicano','barroco'),
                        construction='glazed' if style=='moderno' and large else 'auto'))
                parcel=Polygon([(-2,-4),(8,-4),(8,4),(-2,4)])
                mb=MeshBuilder(parcel)
                build_door(mb,np.zeros(2),np.array([1.,0.]),np.array([0.,-1.]),op)
                mesh=mb.finish()
                validation=validate_mesh(mesh,parcel,envelope=parcel)
                assert validation['envelope_test']=='passed'
                export_glb(mesh,catalog/f'{name}.glb')
                (catalog/f'{name}.json').write_text(json.dumps(asdict(op),indent=2)+'\n')
                index.append(dict(name=name,validation=validation))
    (catalog/'index.json').write_text(json.dumps(index,indent=2)+'\n')
    lot=root/'lotes/1134299_casa_salmon_republicana'
    r=json.loads((lot/'ventanas_vinculadas/request.json').read_text())
    removed=[]
    for f in r['theta']['facades']:
        controls=f['controls']
        for op in controls['openings']:
            if op['kind'] not in ('door','gate'):continue
            principal=op['kind']=='door'
            op['door']=asdict(DoorControls(model='auto',leaves=1 if principal else 2,
                construction='grille' if principal else 'panelled',leaf_material='metal',
                frame_material='frame',portal='none',cornice=False,threshold=True,
                grille_pattern='rings' if principal else 'vertical'))
            op['grille']=False
            op['frame_profile']=None
            op['frame_width_m']=.10
            op['frame_depth_m']=.13
            if principal:
                # Replace the detached rectangular portal; keep the observed horizontal hood.
                kept=[]
                for feature in controls['projections']:
                    center=feature['u_m']+feature['width_m']/2
                    near=abs(center-(op['u_m']+op['width_m']/2))<op['width_m']/2+.6
                    if feature['kind'] in ('frame','pilaster') and near:
                        removed.append(feature)
                    else:kept.append(feature)
                controls['projections']=kept
    r['evidence']={}
    result=reconstruct(from_json(json.dumps(r)))
    ctx=result.resolved.context
    val=validate_mesh(result.mesh,Polygon(ctx.parcel),envelope=street_envelope(
        ParcelContext(ctx.parcel,explicit_fronts=ctx.fronts)))
    assert val['envelope_test']=='passed',val
    out=lot/'puertas_vinculadas'
    out.mkdir(exist_ok=True)
    (out/'request.json').write_text(json.dumps(r,indent=2)+'\n')
    (out/'validation.json').write_text(json.dumps(val,indent=2)+'\n')
    (out/'removed_portal.json').write_text(json.dumps(removed,indent=2)+'\n')
    export_glb(result.mesh,out/'building.glb')
    print('20 catalogue assemblies and complete salmon house:',val['envelope_test'])


if __name__=='__main__':main()
