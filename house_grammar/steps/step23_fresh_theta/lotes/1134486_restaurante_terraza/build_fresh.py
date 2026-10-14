import json,sys,copy
from pathlib import Path
from dataclasses import asdict
import numpy as np, geopandas as gpd, cv2
from shapely.geometry import Polygon
sys.path[:0]=['src','steps/step22_massing_before_after']
from domain.theta import from_json,canonical
from pipeline.theta import reconstruct
from modeling.theta import resolve_theta
from modeling.grammar import street_envelope
from domain.architecture import ParcelContext
from modeling.validation import validate_mesh
from modeling.exporters.glb_exporter import export_glb
from build_after import render_case
from build_lot_before import fingerprint
P=Path('steps/step23_fresh_theta/lotes/1134486_restaurante_terraza'); base=json.loads((P/'after/request.json').read_text()); r=copy.deepcopy(base)
r['observations']=[dict(view_id=p.name.removesuffix('_lot.jpg'),image_path=str(p)) for p in sorted(P.glob('*_lot.jpg'))]
r['evidence']={}; t=r['theta']; t['family']='mixed_use';t['primary_color']=[.89,.90,.87];t['materials']=[dict(slot='frame',template='frame',color=[.14,.48,.44]),dict(slot='accent',template='plaster',color=[.81,.83,.80]),dict(slot='sign',template='plaster',color=[.89,.90,.87]),dict(slot='wood',template='wood',color=[.55,.34,.19]),dict(slot='metal',template='metal',color=[.35,.37,.32]),dict(slot='stone',template='concrete',color=[.69,.69,.64])]
cs=[c for c in t['massing']['components'] if c['id'] in ('restaurant','upper')]
t['massing']['components']=cs
for c in cs:
 c['region']['u']=[0,.68]
# white lower is recessed; white upper reaches out to sidewalk, with exposed support columns
cs[0]['region']['depth_m']=[2.2,11.0]
cs[1]['region']['depth_m']=[.6,11.0]
t['roof']={'kind':'flat','parapet_m':.18,'props':[]};t['site']={'fence':'none','garden':False,'runs':[],'zones':[{'id':'dining','kind':'terrace','region':{'front_edge':0,'u':[0,.68],'depth_m':[0,2.2],'fit':'parcel','width_reference':'edge'}}]}
t['facade']={'mode':'explicit','openings':[],'projections':[],'material_regions':[]}
t['facades']=[]

def op(kind,u,v,w,h,prefab='slim_window',**kw):return dict(kind=kind,u_m=round(u,3),v_m=v,width_m=round(w,3),height_m=h,prefab=prefab,**kw)
def pr(kind,u,v,w,h,d,mat='frame',**kw):return dict(kind=kind,u_m=round(u,3),v_m=v,width_m=round(w,3),height_m=h,depth_m=d,material_slot=mat,**kw)
def ctl(ops=(),projs=(),regions=(),**kw):return dict(mode='explicit',openings=list(ops),projections=list(projs),material_regions=list(regions),**kw)
def reg(u,v,w,h,slot):return dict(u_m=u,v_m=v,width_m=w,height_m=h,material_slot=slot)
# Discover canonical wall indices and lengths from scalar regions; do not inherit old openings.
b=from_json(json.dumps(r)); ir=resolve_theta(b.context,b.theta)
for m in ir.masses:print('mass',m.id,'z',m.base_z,m.roof_z,'area',round(Polygon(m.footprint).area,2))
for w in ir.walls:print('wall',w.mass_role,w.edge,round(w.facade.width_m,2),'front',w.facade.is_front,'xy',w.facade.vertex_a,w.facade.vertex_b,'visible',w.visible_domains)
for w in ir.walls:
 mid=w.mass_role;edge=w.edge;L=w.facade.width_m;h=w.height_m
 if not w.facade.is_front and not (w.mass_role in ('upper:0','restaurant:0') and w.edge==3):continue
 c=None
 if mid=='upper:0' and edge==0:  # white first-floor frontage, 3 teal gridded windows
  xs=[.75,L*.40,L*.72]
  ops=[op('window',u,.75,1.15,1.52,mullion_columns=4,mullion_rows=3) for u in xs]
  projs=[pr('cornice',.04,h-.18,L-.08,.14,.12,'plaster'),pr('sign_box',2.1,2.78,3.4,.20,.035,'sign',label='TERMINAL'),pr('sign_box',2.1,2.53,3.4,.20,.035,'sign',label='PESQUERO')]
  c=ctl(ops,projs)
 elif mid=='restaurant:0' and edge==0: # white recessed ground: dark dining apertures
  ops=[op('window',L*.17,.35,1.8,2.22,'storefront',mullion_columns=3,mullion_rows=2),op('door',L*.63,.05,1.5,2.55,'open',style='vestibule')]
  c=ctl(ops,[pr('canopy',.05,2.88,L-.10,.14,.58,'stone')])
 elif mid=='upper:0' and edge==3: # west-facing white wall, three narrow vertical panes in oblique photos
  c=ctl([op('window',u,.65,.48,1.75,'slim_window',mullion_columns=1,mullion_rows=4) for u in (2.0,4.4,6.8)])
 elif mid=='restaurant:0' and edge==3: # west-facing wooden garage and access
  c=ctl([op('gate',2.2,.06,3.1,2.62,'wood_panel'),op('door',6.1,.06,1.0,2.55,'wood_panel')])
 if c:t['facades'].append(dict(mass_role=mid,edge=edge,controls=c))
r['nuisance']['curtains']=False;r['config']['detail']=3
parsed=from_json(json.dumps(r)); result=reconstruct(parsed)
poly=Polygon(result.resolved.context.parcel);env=street_envelope(ParcelContext(result.resolved.context.parcel,explicit_fronts=result.resolved.context.fronts));val=validate_mesh(result.mesh,poly,envelope=env)
out=P/'fresh';out.mkdir(exist_ok=True)
(out/'request.json').write_text(json.dumps(asdict(parsed),indent=2,ensure_ascii=False)+'\n');(out/'resolved_theta.json').write_text(json.dumps(json.loads(canonical(result.resolved)),indent=2)+'\n');export_glb(result.mesh,out/'building.glb')
lots=gpd.read_file('data/lotes/BARRANCO_LM_geogpsperu.geojson').to_crs(32718);geom=lots[lots.objectid==1134486].iloc[0].geometry
poses=json.load(open('data/poses_barranco/metadata.json'))['panoramas'];offset=json.load(open('data/cadastral_offset.json'))
n=render_case(result,out,1134486,geom,poses,offset,after_label='SOLO RESTAURANTE BLANCO')
(out/'manifest.json').write_text(json.dumps(dict(lot=1134486,validation=val,triangles=len(result.mesh.faces),comparisons=n,mesh_sha256=fingerprint(result.mesh)),indent=2)+'\n')
print('VALID',val['envelope_test'],'tris',len(result.mesh.faces),'views',n)
