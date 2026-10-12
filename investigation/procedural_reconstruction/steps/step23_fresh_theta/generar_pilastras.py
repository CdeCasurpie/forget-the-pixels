"""Small, representative catalogue: 25 variants, five family views, five anchors.

Exports GLB and reusable JSON only. Does not enumerate parameter combinations.
"""
import json
import sys
from dataclasses import asdict
from pathlib import Path
import numpy as np
import trimesh
from shapely.geometry import box, Polygon

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from domain.vertical_members import MemberDesign
from domain.theta import from_json
from modeling.mesh_builder import MeshBuilder
from modeling.vertical_member_catalog import CATALOG
from modeling.vertical_member_assembly import build_member
from modeling.exporters.glb_exporter import export_glb
from modeling.validation import validate_mesh
from pipeline.theta import reconstruct
from domain.architecture import ParcelContext
from modeling.grammar import street_envelope

OUT=Path(__file__).parent/'catalogo_pilastras'


def controls(style,variant,preset,index=0):
    round_section=preset.section in ('circle','ellipse','octagon')
    width=.55;depth=.55 if round_section else .28
    placement='freestanding' if round_section or style=='moderno' else 'attached'
    if preset.section=='ellipse':depth=.35
    return dict(id=f'{style}_{variant}',mass_ref='house:0',edge=0,u_m=1.4+index*2,
                bottom_m=0.,height_m=3.2,width_m=width,depth_m=depth,placement=placement,
                offset_m=.9 if placement=='freestanding' else 0.,
                design=asdict(MemberDesign(style=style,variant=variant,material='wood' if style=='madera' else 'plaster')))


def request(style,members):
    return dict(context=dict(parcel=[[0,0],[20,0],[20,16],[0,16]],fronts=[0]),theta=dict(
        schema_version='0.3',architectural_style=style,massing=dict(pattern='explicit'),
        masses=[dict(role='house',footprint=[[3,3],[17,3],[17,12],[3,12]],levels_m=[0,3.2,6.4])],
        facade=dict(mode='explicit',openings=[],projections=[],material_regions=[]),
        roof=dict(kind='flat',parapet_m=0,props=[]),site=dict(fence='none',runs=[],garden=False),
        trim=dict(cornice=dict(enabled=False),plinth=dict(enabled=False)),vertical_members=members))


def validate_parts(mesh):
    checks=[]
    for part in mesh.parts:
        if not part['name'].startswith('member_'):continue
        faces=mesh.faces[part['face_start']:part['face_start']+part['face_count']]
        used,local=np.unique(faces,return_inverse=True)
        solid=trimesh.Trimesh(mesh.vertices[used],local.reshape(-1,3),process=False)
        if not solid.is_watertight or not solid.is_winding_consistent or solid.volume<=0:
            raise ValueError(f'Invalid solid {part}')
        checks.append(part['component_id'])
    return len(checks)


def save(name,mesh,r,resolved,description):
    out=OUT/name;out.mkdir(parents=True,exist_ok=True)
    count=validate_parts(mesh)
    ctx=r['context']
    envelope=street_envelope(ParcelContext(tuple(map(tuple,ctx['parcel'])),explicit_fronts=tuple(ctx['fronts'])))
    validation=validate_mesh(mesh,Polygon(ctx['parcel']),envelope=envelope)
    if validation['envelope_test']!='passed':raise ValueError(validation)
    validation['closed_member_parts']=count
    export_glb(mesh,out/'building.glb')
    (out/'request.json').write_text(json.dumps(r,indent=2)+'\n')
    (out/'resolved_members.json').write_text(json.dumps([asdict(m) for m in resolved],indent=2)+'\n')
    (out/'validation.json').write_text(json.dumps(validation,indent=2)+'\n')
    return dict(name=name,description=description,glb=f'{name}/building.glb',triangles=len(mesh.faces),closed_parts=count)


def isolated(result,backing=False):
    mb=MeshBuilder(box(-5,-5,30,25))
    for member in result.resolved.vertical_members:
        c=member.controls
        with mb.assembly('vertical_member/'+c.id):
            build_member(mb,member.center,member.tangent,member.normal,member.bottom,
                         c.width_m,c.depth_m,c.height_m,c.design,c.placement)
        if backing and c.placement=='attached':
            x,y=member.center
            mb.solid(box(x-.48,y+.14,x+.48,y+.35),0,c.height_m,'concrete','display_backing')
    return mb.finish()


def main():
    OUT.mkdir(parents=True,exist_ok=True);index=[]
    for style,family in CATALOG.items():
        members=[]
        for i,(variant,preset) in enumerate(family.items()):
            c=controls(style,variant,preset,i);members.append(c)
            r=request(style,[c]);result=reconstruct(from_json(json.dumps(r)))
            index.append(save(f'{style}_{variant}',isolated(result),r,result.resolved.vertical_members,
                              'Pieza aislada; request.json reconstruye también su edificio de anclaje.'))
        r=request(style,members);result=reconstruct(from_json(json.dumps(r)))
        index.append(save(f'00_conjunto_{style}',isolated(result,True),r,result.resolved.vertical_members,
                          'Cinco variantes, de izquierda a derecha en el orden del catálogo.'))
    examples=[('adosada','republicano','recessed_panel','attached'),
              ('semicolumna','clasico','ionic','embedded'),
              ('exenta','barroco','salomonic','freestanding'),
              ('esquina','republicano','rusticated','corner'),
              ('segundo_nivel','madera','joinery_pilaster','attached')]
    for name,style,variant,placement in examples:
        c=controls(style,variant,CATALOG[style][variant]);c.update(placement=placement,offset_m=.9 if placement=='freestanding' else 0.)
        if placement=='corner':c.update(u_m=0.,embed_ratio=.5)
        if name=='segundo_nivel':c['bottom_m']=3.2
        r=request(style,[c]);result=reconstruct(from_json(json.dumps(r)))
        index.append(save(f'01_anclaje_{name}',result.mesh,r,result.resolved.vertical_members,
                          'Edificio completo para comprobar colocación e integración.'))
    (OUT/'index.json').write_text(json.dumps(index,indent=2)+'\n')
    lines=['# Catálogo de pilastras y columnas','',
           '35 GLB: 25 variantes únicas, cinco conjuntos y cinco ejemplos de anclaje.',
           'Empieza por los archivos `00_conjunto_*/building.glb`. No hay combinaciones exhaustivas.','',
           'Los GLB individuales muestran solo la pieza. Sus requests incluyen un edificio de anclaje.',
           'En cada conjunto el orden de izquierda a derecha coincide con la tabla siguiente.','',
           '| Estilo | Variantes de izquierda a derecha |','|---|---|']
    lines += [f'| {style} | '+', '.join(family)+' |' for style,family in CATALOG.items()]
    lines += ['','## Archivos','']+[f"- [{e['name']}]({e['glb']}) — {e['description']}" for e in index]
    (OUT/'README.md').write_text('\n'.join(lines)+'\n')
    print(f'{len(index)} GLB; all member solids closed, consistently oriented and positive.')


if __name__=='__main__':main()
