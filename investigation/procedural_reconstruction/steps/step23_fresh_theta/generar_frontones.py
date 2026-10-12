"""Ten crown families, six compositions and a complete original Barranco house.

Run from any directory. Only GLB/JSON/Markdown; no renders or images.
"""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from domain.theta import from_json, canonical
from domain.architecture import ParcelContext
from modeling.grammar import street_envelope
from modeling.validation import validate_mesh
from modeling.exporters.glb_exporter import export_glb
from modeling.crown_catalog import FAMILIES
from pipeline.theta import reconstruct
from shapely.geometry import Polygon

HERE=Path(__file__).parent


def opening(kind,u,v,w,h,**extra):
    return dict(kind=kind,u_m=u,v_m=v,width_m=w,height_m=h,recess_m=.15,
                frame_width_m=.10,frame_depth_m=.12,frame_profile='auto',
                mullion_columns=2,mullion_rows=3,sill=kind=='window',**extra)


def facade(mass,edge,ops):
    return dict(mass_role=mass,edge=edge,controls=dict(mode='explicit',openings=ops,projections=[],material_regions=[]))


def base_request(style='republicano'):
    return dict(context=dict(parcel=[[0,0],[24,0],[24,24],[0,24]],fronts=[0]),theta=dict(
        schema_version='0.3',architectural_style=style,family='republicano',
        massing=dict(pattern='explicit'),masses=[dict(role='house',footprint=[[4,5],[20,5],[20,18],[4,18]],levels_m=[0,4])],
        facade=dict(mode='explicit',openings=[],projections=[],material_regions=[]),facades=[],
        roof=dict(kind='flat',parapet_m=0,props=[]),site=dict(fence='none',garden=False,runs=[]),
        trim=dict(cornice=dict(enabled=False),plinth=dict(enabled=False)),
        primary_color=[.80,.64,.32],materials=[dict(slot='cornice',template='plaster',color=[.94,.92,.83]),
            dict(slot='frame',template='plaster',color=[.94,.92,.83])]),nuisance=dict(seed=23,curtains=False))


def save(r,out):
    req=from_json(json.dumps(r));result=reconstruct(req);ctx=result.resolved.context
    val=validate_mesh(result.mesh,Polygon(ctx.parcel),envelope=street_envelope(ParcelContext(ctx.parcel,explicit_fronts=ctx.fronts)))
    if val['envelope_test']!='passed' or not np.isfinite(result.mesh.vertices).all():raise ValueError(val)
    out.mkdir(parents=True,exist_ok=True)
    export_glb(result.mesh,out/'building.glb')
    (out/'request.json').write_text(json.dumps(r,indent=2)+'\n')
    (out/'resolved_theta.json').write_text(canonical(result.resolved)+'\n')
    (out/'resolved_crowns.json').write_text(json.dumps([asdict(c) for c in result.resolved.crowns],indent=2)+'\n')
    (out/'validation.json').write_text(json.dumps(val,indent=2)+'\n')
    manifest=dict(name=out.name,triangles=len(result.mesh.faces),parts=len(result.mesh.parts),
        crown_families=[c.controls.design.family for c in result.resolved.crowns],envelope=val['envelope_test'],
        mesh_sha256=hashlib.sha256(result.mesh.vertices.tobytes()+result.mesh.faces.tobytes()).hexdigest())
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest


def catalogue():
    out=HERE/'catalogo_frontones';index=[]
    for family in FAMILIES:
        r=base_request();height=2.4 if family=='semicircular' else 1.8
        r['theta']['crowns']=[dict(id='coronamiento',mass_ref='house:0',edge=0,u_m=5.6,width_m=4.8,height_m=height,
            design=dict(family=family,thickness_m=.36,moulding_width_m=.14,projection_m=.20,
                        ornament='volutes' if family=='compound_curve' else 'none'))]
        index.append(save(r,out/family))
    configs=[('hotel_arco','republicano',dict(silhouette='curved'),1.4,'none','cartouche'),
             ('mercado_escalonado','republicano',dict(silhouette='mixed',stepped=True),2.,'none','keystone'),
             ('hastial_ojival','republicano',dict(silhouette='pointed'),2.6,'pointed','none'),
             ('hombros_bajo_torre','republicano',dict(concave_shoulders=True),2.4,'oculus','none'),
             ('portada_ornamentada','barroco',dict(silhouette='mixed'),2.2,'none','volutes'),
             ('marco_bajo_alero','republicano',dict(silhouette='curved'),.6,'none','keystone')]
    for name,style,attributes,height,aperture,ornament in configs:
        r=base_request(style);t=r['theta']
        crown=dict(id='coronamiento',mass_ref='house:0',edge=0,u_m=4.7,width_m=6.6,height_m=height,
                   design=dict(**attributes,thickness_m=.42,moulding_width_m=min(.17,height*.24),projection_m=.22,ornament=ornament),
                   aperture=aperture,aperture_width_m=.8,aperture_height_m=1.2,aperture_sill_m=.5)
        ops=[opening('door',7.2,.10,1.6,2.65,shape='arch',arch_rise_m=.55,
                     door=dict(model='auto',construction='panelled',portal='pilasters'))]
        if name=='marco_bajo_alero':
            ops=[opening('window',6.9,.6,2.2,2.4,shape='arch',arch_rise_m=.8)]
            crown.update(anchor='opening_top',opening_index=0,base_m=.08,width_m=2.7)
        else:
            t['entablatures']=[dict(id='entablamento',height_m=.48,projection_m=.22,scope='exposed')]
        t['crowns']=[crown];t['facades']=[facade('house:0',0,ops)]
        if name=='marco_bajo_alero':
            t['facades'][0]['controls']['projections']=[dict(kind='eave',u_m=5.8,v_m=3.8,width_m=4.4,height_m=.16,depth_m=.5,material_slot='wood')]
        if name=='portada_ornamentada':
            t['vertical_members']=[dict(id=f'pilastra_{i}',mass_ref='house:0',edge=0,u_m=u,bottom_m=.1,height_m=3.4,width_m=.45,depth_m=.30,
                design=dict(style='auto',variant='leaf_pilaster',material='frame')) for i,u in enumerate((5.8,10.2))]
        if name=='hombros_bajo_torre':
            # Independent upper mass, supported by the roof, not a stretched crown.
            del t['masses']
            t['massing']=dict(components=[dict(id='house',region=dict(front_edge=0,u=[1/6,5/6],depth_m=[5,18],width_reference='edge'),levels_m=[0,4])])
            t['roof_bodies']=[dict(id='torre',parent='house',region=dict(front_edge=0,u=[.46,.54],depth_m=[5.45,8.5],width_reference='edge'),height_m=3.4,
                facade=dict(mode='explicit',openings=[],projections=[],material_regions=[]))]
        index.append(save(r,out/name))
    (out/'index.json').write_text(json.dumps(index,indent=2)+'\n')
    (out/'README.md').write_text('# Frontones y coronamientos\n\nDiez familias y seis composiciones generales, sin renders.\n\n'+
        '\n'.join(f"- [{i['name']}]({i['name']}/building.glb) — {i['triangles']} triángulos" for i in index)+'\n')
    print('Catalogue:',len(index),'GLB, all envelopes passed',flush=True)


def showcase():
    r=base_request();t=r['theta'];t['primary_color']=[.86,.69,.42]
    t['masses']=[dict(role='principal',footprint=[[3,8],[21,8],[21,19],[3,19]],levels_m=[0,3.6,7.2]),
                 dict(role='izquierda',footprint=[[3,3],[8,3],[8,8],[3,8]],levels_m=[0,3.6,7.2]),
                 dict(role='derecha',footprint=[[17,4],[21,4],[21,8],[17,8]],levels_m=[0,3.6,6.8])]
    glazed=dict(model='auto',leaves=2,construction='glazed',leaf_material='wood',frame_material='frame')
    mainops=[opening('window',5.8,.70,1.5,2.1,grille=True),opening('door',8.6,.12,1.6,2.7,door=glazed),
             opening('window',11.3,.7,1.5,2.1,grille=True),opening('window',5.8,4.25,1.5,2.2),
             opening('door',8.6,3.63,1.6,2.85,door=glazed),opening('window',11.3,4.25,1.5,2.2)]
    leftops=[opening('door',.65,.12,1.45,2.5,shape='arch',arch_rise_m=.5,
                door=dict(model='auto',leaves=1,construction='panelled',portal='pilasters',leaf_material='wood')),
             opening('window',3.,.8,1.25,1.95,grille=True),opening('window',.7,4.3,1.45,2.1),opening('window',3.,4.3,1.35,2.1)]
    rightops=[opening('window',.65,.8,2.5,1.9,grille=True),opening('window',.85,4.25,2.15,1.85)]
    t['facades']=[facade('principal:0',0,mainops),facade('izquierda:0',0,leftops),facade('derecha:0',0,rightops),
        facade('izquierda:0',1,[opening('window',1.,.8,1.6,2.),opening('window',1.,4.35,1.6,2.)]),
        facade('derecha:0',3,[opening('window',1.,.8,1.5,1.9),opening('window',1.,4.2,1.5,1.9)])]
    t['trim']=dict(cornice=dict(enabled=False),plinth=dict(design='horizontal_joints',height_m=.55,relief_m=.025,material='stone'))
    t['entablatures']=[dict(id='coronacion',height_m=.48,projection_m=.23,scope='exposed',ornament='dentils'),
                       dict(id='cinturon',anchor='absolute',top_m=3.6,height_m=.24,projection_m=.12,scope='exposed')]
    t['crowns']=[dict(id='fronton_central',mass_ref='principal:0',edge=0,u_m=5.1,width_m=8.5,height_m=2.,
        design=dict(silhouette='mixed',stepped=True,thickness_m=.42,moulding_width_m=.18,projection_m=.25,ornament='keystone'),
        aperture='oculus',aperture_width_m=.70,aperture_height_m=.70,aperture_sill_m=.65),
        dict(id='fronton_ala',mass_ref='izquierda:0',edge=0,u_m=.30,width_m=4.4,height_m=1.1,
             design=dict(family='triangular',thickness_m=.34,moulding_width_m=.14,projection_m=.20,ornament='cartouche')),
        dict(id='sobrepuerta',mass_ref='izquierda:0',edge=0,u_m=0,width_m=2.25,height_m=.48,
             anchor='opening_top',opening_index=0,base_m=.23,
             design=dict(family='segmental',thickness_m=.20,moulding_width_m=.09,projection_m=.12,ornament='keystone'))]
    t['balconies']=[dict(id='galeria_blanca',mass_ref='principal:0',edge=0,floor_m=3.6,u_m=5.7,width_m=7.2,depth_m=1.3,
        kind='gallery',variant='turned_gallery',cover=True,enclosure_height_m=3.15,brackets=False,
        slab_material='wood',railing=dict(pattern='cross',material='wood',height_m=1.0,post_spacing_m=2.5),
        column_member=dict(style='madera',variant='saddle_post',material='wood',base=False))]
    t['vertical_members']=[dict(id=f'poste_porche_{i}',mass_ref='principal:0',edge=0,u_m=u,bottom_m=0,height_m=3.42,
        width_m=.18,depth_m=.18,placement='freestanding',offset_m=1.3,
        design=dict(style='auto',variant='smooth_moulded',section='chamfered',material='wood',base=False))
        for i,u in enumerate((5.7,8.1,10.5,12.9))]
    t['vertical_members'] += [dict(id=f'pilastra_derecha_{i}',mass_ref='derecha:0',edge=0,u_m=u,bottom_m=.55,
        height_m=5.77,width_m=.30,depth_m=.14,design=dict(style='auto',variant='recessed_panel',material='frame'))
        for i,u in enumerate((.25,3.75))]
    t['site']=dict(fence='none',garden=False,runs=[dict(edge=0,start_m=1.,end_m=23.,kind='republicano',height_m=1.65,
        height_mode='high',gate_u=11.7,gate_width=1.4,garage_u=18.3,garage_width=3.0,base_height_m=.4,
        wall_material='plaster',plinth=dict(design='stepped',height_m=.3,material='stone'))],zones=[
        dict(id='jardin_izquierdo',kind='garden',region=dict(front_edge=0,u=[.14,.35],depth_m=[.6,2.4],width_reference='edge')),
        dict(id='patio',kind='patio',region=dict(front_edge=0,u=[.36,.68],depth_m=[.5,7.8],width_reference='edge')),
        dict(id='jardin_derecho',kind='garden',region=dict(front_edge=0,u=[.72,.88],depth_m=[.6,3.4],width_reference='edge'))])
    t['materials']=[dict(slot=slot,template=template,color=color) for slot,template,color in (
        ('frame','plaster',[.95,.92,.83]),('cornice','plaster',[.96,.93,.84]),('wood','wood',[.87,.90,.83]),
        ('metal','metal',[.12,.25,.23]),('stone','stone',[.37,.40,.39]),('plinth','stone',[.37,.40,.39]),
        ('glass','glass',[.31,.44,.43]),('roof','roof',[.40,.26,.22]))]
    out=HERE/'casa_demostracion_barranco'
    report=save(r,out)
    (out/'README.md').write_text('# Casa de los Arcos — composición original\n\n'+
        'Casona republicana inventada para demostrar la gramática; no corresponde a un predio real.\n\n'+
        '- Tres cuerpos, dos pisos y jardín delantero.\n- Galería blanca con cruces, zapatas y apoyos inferiores.\n'+
        '- Frontón central mixto con óculo real; frontón triangular y sobrepuerta segmental.\n'+
        '- Entablamentos continuos, dentículos y zócalos de piedra.\n'+
        '- Ventanas molduradas, rejas y puertas de madera.\n- Cerco republicano con acceso peatonal y portón.\n\n'+
        'Abrir `building.glb`. `request.json` permite editar todos los controles. Validación geométrica en `validation.json`.\n')
    print('Showcase:',json.dumps(report),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--only',choices=('catalogue','house'));args=parser.parse_args()
    if args.only!='house':catalogue()
    if args.only!='catalogue':showcase()
