"""25 adaptive presets, junction examples and salmon terrace. GLB/JSON only."""
import argparse
import copy
import json
import sys
from dataclasses import asdict
from pathlib import Path
import numpy as np
from shapely.geometry import Polygon

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from domain.theta import from_json
from domain.architecture import ParcelContext
from modeling.balcony_catalog import CATALOG
from modeling.grammar import street_envelope
from modeling.validation import validate_mesh
from modeling.exporters.glb_exporter import export_glb
from pipeline.theta import reconstruct

HERE=Path(__file__).parent


def request(style,variant,width):
    p=CATALOG[style][variant]
    return dict(context=dict(parcel=[[0,0],[20,0],[20,20],[0,20]],fronts=[0,1]),
        theta=dict(schema_version='0.3',architectural_style=style,
            massing=dict(pattern='explicit'),
            masses=[dict(role='house',footprint=[[3,3],[15,3],[15,15],[3,15]],levels_m=[0,3,6])],
            facade=dict(mode='explicit',openings=[],projections=[],material_regions=[]),
            roof=dict(kind='flat',parapet_m=0,props=[]),site=dict(fence='none',runs=[],garden=False),
            trim=dict(cornice=dict(enabled=False),plinth=dict(enabled=False)),
            balconies=[dict(id='sample',mass_ref='house:0',edge=0,floor_m=3.,u_m=.5,width_m=width,
                            variant=variant,kind=p.kind,cover=p.kind in ('gallery','box'),brackets=True)]))


def save(r,out):
    result=reconstruct(from_json(json.dumps(r)))
    ctx=result.resolved.context
    val=validate_mesh(result.mesh,Polygon(ctx.parcel),envelope=street_envelope(
        ParcelContext(ctx.parcel,explicit_fronts=ctx.fronts)))
    if val['envelope_test']!='passed':raise ValueError(val)
    out.mkdir(parents=True,exist_ok=True)
    export_glb(result.mesh,out/'building.glb')
    (out/'request.json').write_text(json.dumps(r,indent=2)+'\n')
    (out/'resolved_balconies.json').write_text(json.dumps([asdict(b) for b in result.resolved.balconies],indent=2)+'\n')
    (out/'validation.json').write_text(json.dumps(val,indent=2)+'\n')
    return dict(name=out.name,assemblies=len(result.resolved.balconies),triangles=val['triangles'],envelope=val['envelope_test'])


def terrace(r):
    r=copy.deepcopy(r)
    r['theta']['masses']=[
        dict(role='lower',footprint=[[2,1],[18,1],[18,18],[2,18]],levels_m=[0,3]),
        dict(role='upper',footprint=[[3,3],[15,3],[15,15],[3,15]],levels_m=[3,6])]
    r['theta']['balconies'][0].update(mass_ref='upper:0',floor_m=0,kind='terrace',slab=False,
                                     brackets=False,cover=False,support_mass='lower:0',sides=['front'])
    return r


def catalogue():
    out=HERE/'catalogo_balcones'; index=[]
    for style,family in CATALOG.items():
        for variant in family:
            for size,width in (('compacto',1.2),('mediano',3.2),('corrido',8.)):
                index.append(save(request(style,variant,width),out/f'{style}_{variant}_{size}'))
    reps=dict(republicano='iron_rings',barroco='scroll_iron',clasico='single_baluster',
              madera='turned_timber',moderno='glass_posts')
    for style,variant in reps.items():
        r=terrace(request(style,variant,4.))
        index.append(save(r,out/f'{style}_terraza'))
        r['theta']['balconies'][0]['path']=[[0,.85,0],[4,.85,0],[4,0,0]]
        index.append(save(r,out/f'{style}_esquina'))
        r=request(style,variant,2.)
        r['theta']['balconies'][0].update(kind='juliet',slab=False,brackets=False,depth_m=.06,sides=['front'])
        index.append(save(r,out/f'{style}_falso_balcon'))
        r=request(style,variant,3.)
        r['theta']['facades']=[dict(mass_role='house:0',edge=0,controls=dict(mode='explicit',
            openings=[],projections=[],material_regions=[],stairs=[dict(u_m=2.,base_z_m=0.,target_z_m=3.,run_m=2.2)]))]
        r['theta']['balconies'][0].update(kind='stair',stair_index=0,floor_m=0.,slab=False,brackets=False)
        index.append(save(r,out/f'{style}_escalera_descanso'))
    for style,variant in (('barroco','bowed_iron'),('moderno','glass_posts')):
        r=request(style,variant,3.2);r['theta']['balconies'][0]['curved_front_m']=.30
        index.append(save(r,out/f'{style}_curvo'))
    r=request('moderno','horizontal_rods',3.2)
    r['theta']['balconies'][0]['railing']=dict(pattern='cables')
    index.append(save(r,out/'moderno_cables'))
    r=request('republicano','iron_vertical',3.2)
    r['theta']['balconies'][0]['railing']=dict(material='wood')
    index.append(save(r,out/'republicano_material_manual'))
    r=request('madera','cross_frames',3.2)
    r['theta']['balconies'][0]['enabled']=False
    index.append(save(r,out/'desactivado'))
    r=request('moderno','slim_vertical',3.2)
    r['theta']['balconies'][0].update(brackets=False,fascia=False,railing=dict(enabled=False))
    index.append(save(r,out/'solo_plataforma'))
    r=request('madera','continuous_box',3.2)
    r['theta']['balconies'][0].update(u_m=8.8,corner_return_m=2.5)
    index.append(save(r,out/'madera_cajon_esquina'))
    r=request('republicano','iron_rings',3.2)
    r['theta']['balconies'][0]['planters']=True
    index.append(save(r,out/'republicano_jardineras'))
    (out/'index.json').write_text(json.dumps(index,indent=2)+'\n')
    print(f'Catalogue: {len(index)} GLB/JSON examples, all envelopes passed')


def salmon():
    lot=HERE/'lotes/1134299_casa_salmon_republicana'
    r=json.loads((lot/'profundidad_central/request.json').read_text())
    baseline=reconstruct(from_json(json.dumps(r)))
    # Locate the recessed wall from its two windows, then reference its current
    # canonical edge. No parcel footprint coordinates are copied into theta.
    candidates=[w for w in baseline.resolved.walls if w.mass_role=='base_1:0' and len(w.facade.openings)==2]
    if len(candidates)!=1:raise ValueError('Expected one recessed wall with two windows')
    wall=candidates[0]
    width=wall.facade.width_m-.30
    r['theta']['balconies']=[dict(id='terraza_central',mass_ref=wall.mass_role,edge=wall.edge,
        floor_m=0.,u_m=.15,width_m=width,depth_m=.70,kind='terrace',slab=False,
        variant='iron_rings',support_mass='base_0:0',sides=['front','right'],
        railing=dict(height_m=1.05,spacing_m=.14,post_spacing_m=1.5,material='metal'))]
    # The newly exposed lower roof inherited a solid parapet. Replace that
    # protection with the new railing rather than burying its bars in masonry.
    r['theta']['roofs']=[x for x in r['theta'].get('roofs',[]) if x['mass_ref']!='base_0:0']
    r['theta']['roofs'].append(dict(mass_ref='base_0:0',kind='flat',parapet_m=0.))
    report=save(r,lot/'balcones_vinculados')
    print('Salmon:',json.dumps(report))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--only',choices=('catalogue','salmon'))
    args=parser.parse_args()
    if args.only!='salmon':catalogue()
    if args.only!='catalogue':salmon()
