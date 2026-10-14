"""Generate varied window assemblies and salmon-house migration; no renders."""
import json
import sys
from pathlib import Path
from dataclasses import asdict, replace
import numpy as np
from shapely.geometry import Polygon

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from domain.models import Opening
from domain.theta import from_json
from modeling.window_assembly import PROFILES, build_window
from modeling.mesh_builder import MeshBuilder
from modeling.exporters.glb_exporter import export_glb
from modeling.validation import validate_mesh
from modeling.grammar import street_envelope
from domain.architecture import ParcelContext
from pipeline.theta import reconstruct


def main():
    root=Path(__file__).parent
    out=root/'catalogo_ventanas'
    out.mkdir(exist_ok=True)
    parcel=Polygon([(-1,-2),(4,-2),(4,2),(-1,2)])
    presets = {
        'moderno': dict(frame_width_m=.035,frame_depth_m=.035,grid_spacing_m=None,
                        mullion_columns=1,mullion_rows=1,sill=False),
        'clasico': dict(frame_width_m=.09,frame_depth_m=.08,grid_spacing_m=None,
                       mullion_columns=2,mullion_rows=2,sill=True),
        'republicano': dict(frame_width_m=.12,frame_depth_m=.14,grid_spacing_m=.45,sill=True),
        'barroco': dict(frame_width_m=.16,frame_depth_m=.20,grid_spacing_m=.55,sill=True),
        'madera': dict(frame_width_m=.085,frame_depth_m=.09,grid_spacing_m=None,
                      mullion_columns=2,mullion_rows=3,sill=True),
    }
    index=[]
    for style in PROFILES:
        for shape in ('rectangle','arch','circle','ellipse'):
            settings=dict(presets[style])
            if shape in ('circle','ellipse'):
                settings.update(sill=False,grid_spacing_m=None,mullion_columns=1,mullion_rows=1)
            op=Opening('window',.5,.5,1.6,1.6 if shape=='circle' else 2.2,
                shape=shape,frame_profile=style,**settings)
            # Existing filenames now show unprotected glazing; paired files show protection.
            for protected in (False,True):
                variant=replace(op,grille=protected,grille_spacing_m=.20,
                    grille_pattern='diamond' if style=='barroco' else 'vertical')
                name=f'{style}_{shape}'+('_con_reja' if protected else '')
                mb=MeshBuilder(parcel)
                build_window(mb,np.array([0.,0.]),np.array([1.,0.]),np.array([0.,-1.]),variant)
                mesh=mb.finish()
                export_glb(mesh,out/f'{name}.glb')
                (out/f'{name}.json').write_text(json.dumps(asdict(variant),indent=2)+'\n')
                index.append(dict(file=name+'.glb',style=style,shape=shape,grille=protected))
    (out/'index.json').write_text(json.dumps(index,indent=2)+'\n')
    lot=root/'lotes/1134299_casa_salmon_republicana'
    r=json.loads((lot/'base_simplificada_completa/request.json').read_text())
    r['theta']['architectural_style']='republicano'
    removed=[]
    for f in r['theta']['facades']:
        controls=f['controls']
        windows=[o for o in controls['openings'] if o['kind']=='window']
        for op in windows:
            # Foto: marcos blancos republicanos, barras verticales y alfeizar.
            # Piso bajo con mas divisiones; piso alto de 2x3.
            cols,rows=(3,3) if f['mass_role'].startswith('base_0') else (2,3)
            op.update(frame_profile='auto',frame_width_m=.12,frame_depth_m=.14,
                      sill=True,grid_spacing_m=None,mullion_columns=cols,mullion_rows=rows,
                      grille=True,grille_pattern='vertical',grille_spacing_m=.14)
        projections=[]
        for feature in controls['projections']:
            # Remove only standalone surrounds/sills physically associated with a window.
            linked=feature['kind'] in ('moulded_surround','segmental_surround','sill_band') and any(
                abs((feature['u_m']+feature['width_m']/2)-(w['u_m']+w['width_m']/2))<.25 and
                abs(feature['v_m']-w['v_m'])<.3 for w in windows)
            if linked:removed.append(feature)
            else:projections.append(feature)
        controls['projections']=projections
    # Cerco republicano bajo como en la foto: murete + reja con aros,
    # puerta y cochera caladas del mismo estilo.
    for run in r['theta']['site']['runs']:
        run.update(kind='republicano',height_mode='low',height_m=1.2,
                   wall_material='plaster',gate_mode='auto',garage_mode='auto',
                   openness=.3,planters=False)
    r['evidence']={}
    result=reconstruct(from_json(json.dumps(r)))
    p=result.resolved.context
    val=validate_mesh(result.mesh,Polygon(p.parcel),envelope=street_envelope(
        ParcelContext(p.parcel,explicit_fronts=p.fronts)))
    assert val['envelope_test']=='passed',val
    target=lot/'ventanas_vinculadas'
    target.mkdir(exist_ok=True)
    (target/'request.json').write_text(json.dumps(r,indent=2)+'\n')
    (target/'validation.json').write_text(json.dumps(val,indent=2)+'\n')
    (target/'removed_surrounds.json').write_text(json.dumps(removed,indent=2)+'\n')
    export_glb(result.mesh,target/'building.glb')
    print('40 assemblies (20 without grille, 20 with grille); salmon house:',val['envelope_test'],len(removed),'old surrounds/sills replaced')


if __name__=='__main__':main()
