"""Continuous cornice/plinth catalogue and salmon house migration. No renders."""
import copy
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from domain.theta import from_json
from domain.architecture import ParcelContext
from modeling.trim_profiles import CORNICES
from modeling.grammar import street_envelope
from modeling.validation import validate_mesh
from modeling.exporters.glb_exporter import export_glb
from pipeline.theta import reconstruct
from shapely.geometry import Polygon


def save(request,directory):
    result=reconstruct(from_json(json.dumps(request)))
    ctx=result.resolved.context
    validation=validate_mesh(result.mesh,Polygon(ctx.parcel),envelope=street_envelope(
        ParcelContext(ctx.parcel,explicit_fronts=ctx.fronts)))
    assert validation['envelope_test']=='passed',validation
    directory.mkdir(parents=True,exist_ok=True)
    export_glb(result.mesh,directory/'building.glb')
    (directory/'request.json').write_text(json.dumps(request,indent=2)+'\n')
    (directory/'validation.json').write_text(json.dumps(validation,indent=2)+'\n')
    (directory/'resolved_trim.json').write_text(json.dumps([asdict(p) for p in result.resolved.trims],indent=2)+'\n')
    return dict(name=directory.name,pieces=len(result.resolved.trims),validation=validation)


def main():
    root=Path(__file__).parent
    catalog=root/'catalogo_remates'
    template=dict(context=dict(parcel=[[0,0],[10,0],[10,10],[0,10]],fronts=[0,1]),
        theta=dict(schema_version='0.3',height_m=3.4,floors=1,side_material='plaster',
            primary_color=[.78,.48,.38],architectural_style='republicano',
            massing=dict(pattern='full',front_setback_m=1.0),
            roof=dict(kind='flat',parapet_m=.35,props=[]),
            facade=dict(mode='explicit',openings=[],projections=[],material_regions=[]),
            trim=dict(cornice=dict(anchor='parapet_top'),plinth=dict(enabled=False)),
            site=dict(fence='none',runs=[],garden=False)))
    # Use an interior component with a concave corner, described by cadastral cuts.
    template['theta'].pop('height_m'); template['theta'].pop('floors')
    template['theta']['massing']=dict(pattern='composition',components=[
        dict(id='body',region=dict(front_edge=0,u=[.10,.9],depth=[.1,.9]),levels_m=[0.,3.4],
             cutouts=[dict(front_edge=0,u=[.55,.9],depth=[.1,.4])])])
    index=[]
    for style in CORNICES:
        r=copy.deepcopy(template); r['theta']['architectural_style']=style
        if style=='moderno':r['theta']['trim']['cornice'].update(height_m=.10,projection_m=.08)
        index.append(save(r,catalog/f'cornisa_{style}'))
    for design in ('smooth','horizontal_joints','stepped','blocks'):
        r=copy.deepcopy(template)
        r['theta']['trim']['cornice']['enabled']=False
        r['theta']['trim']['plinth']=dict(design=design,height_m=.7,relief_m=.035)
        index.append(save(r,catalog/f'zocalo_{design}'))
    for name,trim in (
        ('sin_remates',dict(cornice=dict(enabled=False),plinth=dict(enabled=False))),
        ('zocalo_al_ras',dict(cornice=dict(enabled=False),plinth=dict(height_m=.7,relief_m=0.)))):
        r=copy.deepcopy(template); r['theta']['trim']=trim
        index.append(save(r,catalog/name))
    r=copy.deepcopy(template)
    r['theta']['site']['runs']=[dict(edge=i,start_m=0.,end_m=10.,kind='republicano',height_m=1.2,
        height_mode='low',base_height_m=.4,plinth=dict(design='horizontal_joints',height_m=.35),
        **(dict(gate_u=2.,gate_width=1.1) if i==0 else {})) for i in (0,1)]
    index.append(save(r,catalog/'cerco_esquina'))
    catalog.mkdir(exist_ok=True)
    (catalog/'index.json').write_text(json.dumps(index,indent=2)+'\n')
    lot=root/'lotes/1134299_casa_salmon_republicana'
    r=json.loads((lot/'puertas_vinculadas/request.json').read_text())
    removed=[]
    for f in r['theta']['facades']:
        kept=[]
        for p in f['controls'].get('projections') or []:
            if p['kind'] in ('cornice','denticulated_cornice') and p['source']!='monumental_portal':
                removed.append(dict(mass=f['mass_role'],edge=f['edge'],projection=p))
            else:kept.append(p)
        f['controls']['projections']=kept
    r['theta']['trim']=dict(cornice=dict(profile='republicano',height_m=.30,projection_m=.22,
                                        anchor='parapet_top'),
                            plinth=dict(design='horizontal_joints',height_m=.60,relief_m=.025))
    r['theta']['materials'] += [dict(slot='cornice',template='plaster',color=[.92,.89,.82]),
                                dict(slot='plinth',template='plaster',color=r['theta']['primary_color'])]
    for run in r['theta']['site']['runs']:
        run['plinth']=dict(design='stepped',height_m=.24,relief_m=.018,material='cornice')
    r['evidence']={}
    # Covered lower floors have no parapet. Their cornice is suppressed by topology.
    for c in r['theta']['massing']['components']:
        if c['levels_m'][0]==0:
            c['trim']=copy.deepcopy(r['theta']['trim'])
            c['trim']['cornice']['anchor']='wall_top'
    out=lot/'remates_vinculados'
    report=save(r,out)
    (out/'removed_projections.json').write_text(json.dumps(removed,indent=2)+'\n')
    print(json.dumps(dict(catalogue=len(index),salmon=report),indent=2))


if __name__=='__main__':main()
