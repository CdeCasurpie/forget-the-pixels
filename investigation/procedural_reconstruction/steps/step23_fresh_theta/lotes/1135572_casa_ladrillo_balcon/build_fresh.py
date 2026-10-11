"""Reconstruct only the ochre two-storey house, excluding its tall neighbour."""
import json,sys
from pathlib import Path
from dataclasses import asdict
import geopandas as gpd
from shapely.geometry import Polygon
sys.path[:0]=['src','steps/step22_massing_before_after']
from domain.theta import from_json,canonical
from domain.architecture import ParcelContext
from modeling.grammar import street_envelope
from modeling.validation import validate_mesh
from modeling.exporters.glb_exporter import export_glb
from pipeline.theta import reconstruct
from build_after import render_case
from build_lot_before import fingerprint

lot=Path('steps/step23_fresh_theta/lotes/1135572_casa_ladrillo_balcon');r=json.loads((lot/'after/request.json').read_text());r['observations']=[dict(view_id=p.name.removesuffix('_lot.jpg'),image_path=str(p)) for p in sorted(lot.glob('*_lot.jpg'))];r['evidence']={};t=r['theta']
t['family']='quiet_house';t['primary_color']=[.69,.42,.34];t['side_material']='plaster';t['materials']=[dict(slot='frame',template='frame',color=[.75,.58,.47]),dict(slot='stone',template='stone',color=[.64,.43,.34]),dict(slot='wood',template='wood',color=[.39,.24,.18]),dict(slot='metal',template='metal',color=[.21,.19,.17]),dict(slot='glass',template='glass',color=[.14,.20,.20]),dict(slot='brick',template='brick',color=[.59,.32,.27])]
t['massing']['components'][1]['levels_m']=[0.,3.3,5.75]
t['massing']['components'][1]['region']['u']=[0.,1.]
t['roof']={'kind':'flat','parapet_m':.14,'props':[]};t['site']={'fence':'none','garden':False,'runs':[{'edge':3,'start_m':.05,'end_m':1.43,'kind':'reja','height_m':2.05,'gate_u':.09,'gate_width':1.10}],'zones':[{'id':'front_path','kind':'paved','region':{'front_edge':3,'u':[0,.22],'depth_m':[0,4.0],'fit':'parcel','width_reference':'edge'}}]}
t['facade']={'mode':'explicit','openings':[],'projections':[],'material_regions':[]};t['facades']=[]
def op(kind,u,v,w,h,prefab='legacy',**kw):return dict(kind=kind,u_m=u,v_m=v,width_m=w,height_m=h,prefab=prefab,**kw)
def pr(kind,u,v,w,h,d,slot='frame',**kw):return dict(kind=kind,u_m=u,v_m=v,width_m=w,height_m=h,depth_m=d,material_slot=slot,**kw)
def ctl(ops=(),features=(),regions=()):return dict(mode='explicit',openings=list(ops),projections=list(features),material_regions=list(regions))
# Low front pavilion, main black-gridded window set behind a thick terracotta surround.
front=ctl([op('window',.84,.82,1.49,1.75,'slim_window',recess_m=.20,frame_width_m=.085,grille=True,grille_pattern='grid',mullion_columns=3,mullion_rows=3)],
 [pr('moulded_surround',.68,.65,1.81,2.08,.29,'frame',border_width_m=.16),pr('ledge',.54,.58,2.08,.15,.25,'stone'),pr('panel',.13,.18,.24,3.1,.18,'stone'),pr('panel',2.76,.18,.22,3.1,.18,'stone'),pr('cornice',.08,3.20,2.97,.24,.30,'stone'),pr('balcony',.12,3.60,2.88,.40,.24,'stone',label='balusters')])
# Rear body rises above the low pavilion; use one centred balcony with turned
# balusters where it meets the upper-storey door (rather than painting a rail).
rear=ctl([op('door',2.13,3.46,1.03,1.95,'wood_panel',recess_m=.19),
 op('window',.33,3.68,1.10,1.48,'slim_window',recess_m=.19,mullion_columns=2,mullion_rows=3),
 op('door',.33,.07,1.04,2.62,'open',style='vestibule',recess_m=.22)],
 [pr('cornice',.06,5.35,6.63,.27,.22,'stone'),
  pr('frame',.19,3.53,1.38,1.75,.16,'stone',border_width_m=.11)])
# From the side view the only street-visible low wall is an ochre return;
# avoid inventing windows obscured by a tree and the neighbouring apartment.
side=ctl([], [pr('ledge',.07,3.24,3.85,.16,.21,'stone')])
t['facades']=[dict(mass_role='front:0',edge=3,controls=front),dict(mass_role='front:0',edge=0,controls=side),dict(mass_role='rear:0',edge=3,controls=rear)]
r['nuisance']['curtains']=False;r['config']['detail']=3
request=from_json(json.dumps(r));result=reconstruct(request);parcel=Polygon(result.resolved.context.parcel);env=street_envelope(ParcelContext(result.resolved.context.parcel,explicit_fronts=result.resolved.context.fronts));val=validate_mesh(result.mesh,parcel,envelope=env)
out=lot/'fresh';out.mkdir(exist_ok=True);(out/'request.json').write_text(json.dumps(asdict(request),indent=2,ensure_ascii=False)+'\n');(out/'resolved_theta.json').write_text(json.dumps(json.loads(canonical(result.resolved)),indent=2)+'\n');export_glb(result.mesh,out/'building.glb')
lots=gpd.read_file('data/lotes/BARRANCO_LM_geogpsperu.geojson').to_crs(32718);geom=lots[lots.objectid==1135572].iloc[0].geometry
poses=json.load(open('data/poses_barranco/metadata.json'))['panoramas'];offset=json.load(open('data/cadastral_offset.json'))
count=render_case(result,out,1135572,geom,poses,offset,after_label='SOLO CASA OCRE')
(out/'manifest.json').write_text(json.dumps(dict(lot=1135572,comparisons=count,triangles=len(result.mesh.faces),validation=val,mesh_sha256=fingerprint(result.mesh)),indent=2)+'\n')
print('PASS',val['envelope_test'],len(result.mesh.faces),count)
