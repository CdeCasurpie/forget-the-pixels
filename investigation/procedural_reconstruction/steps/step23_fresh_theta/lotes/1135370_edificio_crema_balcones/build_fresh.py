"""Regenerate the cream building alone from this lot's three photographs."""
import json, sys
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

lot=Path('steps/step23_fresh_theta/lotes/1135370_edificio_crema_balcones')
r=json.loads((lot/'after/request.json').read_text());r['observations']=[dict(view_id=p.name.removesuffix('_lot.jpg'),image_path=str(p)) for p in sorted(lot.glob('*_lot.jpg'))];r['evidence']={}
t=r['theta'];t['family']='quiet_house';t['primary_color']=[.66,.65,.56];t['side_material']='plaster';t['materials']=[{'slot':'frame','template':'frame','color':[.57,.58,.53]},{'slot':'metal','template':'metal','color':[.29,.31,.29]},{'slot':'wood','template':'wood','color':[.27,.25,.20]},{'slot':'stone','template':'stone','color':[.51,.52,.48]},{'slot':'brick','template':'plaster','color':[.62,.62,.54]},{'slot':'glass','template':'glass','color':[.21,.25,.24]}]
t['roof']={'kind':'flat','parapet_m':.14,'props':[]};t['site']={'fence':'none','garden':False,'runs':[{'edge':3,'start_m':.1,'end_m':10.05,'kind':'reja','height_m':1.18,'gate_u':2.3,'gate_width':1.05}], 'zones':[{'id':'forecourt','kind':'paved','region':{'front_edge':3,'u':[0,1],'depth_m':[0,1.3],'fit':'parcel','width_reference':'edge'}}]}
t['facade']={'mode':'explicit','openings':[],'projections':[],'material_regions':[]}
# Place the taller garage bay at the right in all three photographic views.
for component in t['massing']['components']:
 component['region']['u']=[0,.75] if component['id']=='main' else [.75,1.]
t['facades']=[]
def op(kind,u,v,w,h,prefab='slim_window',**other):return dict(kind=kind,u_m=u,v_m=v,width_m=w,height_m=h,prefab=prefab,**other)
def pr(kind,u,v,w,h,d,material='frame',**other):return dict(kind=kind,u_m=u,v_m=v,width_m=w,height_m=h,depth_m=d,material_slot=material,**other)
def ctl(ops,features):return dict(mode='explicit',openings=ops,projections=features,material_regions=[])
# Reflected rhythm: small balcony at the left, doorway near the right, garage at the far right.
main_ops=[op('door',4.76,.04,1.02,2.78,'open',style='vestibule'),op('window',.56,.83,1.13,1.48,grille=True,mullion_columns=3,mullion_rows=2),op('window',2.36,4.26,1.35,1.48,mullion_columns=3,mullion_rows=2),op('window',.56,3.92,1.13,1.87,'slim_window',mullion_columns=3,mullion_rows=2)]
main_features=[pr('balcony',.32,3.81,1.62,1.02,.42,'plaster',label='bars'),pr('ledge',.06,6.82,7.54,.12,.19,'stone'),pr('sill_band',2.24,4.13,1.59,.09,.12)]
# Narrower right-hand volume: garage at street level, broad square window above.
tower_ops=[op('gate',.35,.05,1.85,2.82,'metal_gate',shape='arch',arch_rise_m=.55),op('window',.42,4.05,1.72,1.62,'slim_window',mullion_columns=3,mullion_rows=2)]
tower_features=[pr('ledge',.05,7.38,2.45,.12,.18,'stone'),pr('ledge',.36,3.83,1.85,.12,.14,'stone')]
t['facades']=[dict(mass_role='main:0',edge=3,controls=ctl(main_ops,main_features)),dict(mass_role='tower:0',edge=3,controls=ctl(tower_ops,tower_features))]
r['nuisance']['curtains']=False;r['config']['detail']=3
request=from_json(json.dumps(r));result=reconstruct(request);parcel=Polygon(result.resolved.context.parcel);env=street_envelope(ParcelContext(result.resolved.context.parcel,explicit_fronts=result.resolved.context.fronts));val=validate_mesh(result.mesh,parcel,envelope=env)
out=lot/'fresh';out.mkdir(exist_ok=True)
(out/'request.json').write_text(json.dumps(asdict(request),indent=2,ensure_ascii=False)+'\n');(out/'resolved_theta.json').write_text(json.dumps(json.loads(canonical(result.resolved)),indent=2)+'\n');export_glb(result.mesh,out/'building.glb')
lots=gpd.read_file('data/lotes/BARRANCO_LM_geogpsperu.geojson').to_crs(32718);geom=lots[lots.objectid==1135370].iloc[0].geometry
poses=json.load(open('data/poses_barranco/metadata.json'))['panoramas'];offset=json.load(open('data/cadastral_offset.json'))
count=render_case(result,out,1135370,geom,poses,offset,after_label='EDIFICIO CREMA FRESH')
(out/'manifest.json').write_text(json.dumps(dict(lot=1135370,comparisons=count,triangles=len(result.mesh.faces),validation=val,mesh_sha256=fingerprint(result.mesh)),indent=2)+'\n')
print('PASS',val['envelope_test'],'faces',len(result.mesh.faces),'views',count)
