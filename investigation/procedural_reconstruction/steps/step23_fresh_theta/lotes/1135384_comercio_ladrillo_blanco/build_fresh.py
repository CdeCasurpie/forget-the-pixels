"""Generate the brick-front lot only from its two lot-box photographs."""
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

lot=Path('steps/step23_fresh_theta/lotes/1135384_comercio_ladrillo_blanco')
r=json.loads((lot/'after/request.json').read_text());r['observations']=[{'view_id':p.name.removesuffix('_lot.jpg'),'image_path':str(p)} for p in sorted(lot.glob('*_lot.jpg'))];r['evidence']={}
t=r['theta'];t['family']='quiet_house';t['primary_color']=[.88,.89,.86];t['side_material']='plaster'
t['materials']=[{'slot':'brick','template':'brick','color':[.60,.29,.25]},{'slot':'stone','template':'stone','color':[.57,.56,.53]},{'slot':'frame','template':'frame','color':[.74,.72,.67]},{'slot':'metal','template':'metal','color':[.21,.23,.22]},{'slot':'wood','template':'wood','color':[.32,.18,.13]},{'slot':'glass','template':'glass','color':[.17,.19,.19]}]
t['roof']={'kind':'flat','parapet_m':.22,'props':[]};t['site']={'fence':'none','garden':False,'runs':[],'zones':[]}
t['facade']={'mode':'explicit','openings':[],'projections':[],'material_regions':[]}
def op(kind,u,v,w,h,prefab,**kw):return dict(kind=kind,u_m=u,v_m=v,width_m=w,height_m=h,prefab=prefab,**kw)
def pr(kind,u,v,w,h,d,slot='stone',**kw):return dict(kind=kind,u_m=u,v_m=v,width_m=w,height_m=h,depth_m=d,material_slot=slot,**kw)
def controls(ops,proj,regions):return dict(mode='explicit',openings=ops,projections=proj,material_regions=regions)
# Brick street plane: solid left bay, arched pedestrian door, timber vehicle gate.
garage=controls(
 [op('door',3.06,.05,1.05,2.70,'legacy',shape='arch',arch_rise_m=.44,recess_m=.17),op('gate',4.54,.04,2.53,2.68,'wood_panel',recess_m=.17)],
 [pr('panel',.02,.10,.31,2.78,.21,'stone'),pr('panel',2.69,.06,.28,2.84,.18,'stone'),pr('panel',4.19,.04,.22,2.88,.18,'stone'),pr('panel',7.16,.06,.25,2.84,.18,'stone'),
  pr('ledge',.04,2.91,7.51,.17,.28,'stone'),pr('sill_band',.04,3.00,7.51,.08,.19,'stone'),
  pr('segmental_surround',2.94,.02,1.29,2.86,.17,'stone',border_width_m=.11,arch_rise_m=.44),
  pr('frame',4.42,.02,2.78,2.76,.19,'stone',border_width_m=.12)],
 [{'u_m':0,'v_m':0,'width_m':7.6172553,'height_m':3.1,'material_slot':'brick'}])
# Upper white facade behind the street brick plane: flush horizontal windows,
# red-brown access door, roof terrace rail and a real projecting sill/coping.
house=controls(
 [op('window',.48,4.07,2.05,1.07,'slim_window',mullion_columns=3,mullion_rows=1,recess_m=.18),
  op('door',3.50,3.19,.80,2.28,'wood_panel',recess_m=.22),
  op('window',5.46,4.07,2.04,1.07,'slim_window',mullion_columns=3,mullion_rows=1,recess_m=.18)],
 [pr('ledge',.33,3.90,2.35,.13,.16,'frame'),pr('ledge',5.30,3.90,2.37,.13,.16,'frame'),
  pr('balcony',.16,3.12,8.18,1.02,.62,'plaster',label='bars'),
  pr('eave',.04,6.43,8.48,.25,.32,'frame')],[])
t['facades']=[{'mass_role':'garage:0','edge':1,'controls':controls([],[],[{'u_m':0,'v_m':0,'width_m':.9848,'height_m':3.1,'material_slot':'brick'}])},{'mass_role':'garage:0','edge':2,'controls':garage},{'mass_role':'house:0','edge':1,'controls':house}]
r['nuisance']['curtains']=False;r['config']['detail']=3
req=from_json(json.dumps(r));result=reconstruct(req)
parcel=Polygon(result.resolved.context.parcel);env=street_envelope(ParcelContext(result.resolved.context.parcel,explicit_fronts=result.resolved.context.fronts));val=validate_mesh(result.mesh,parcel,envelope=env)
out=lot/'fresh';out.mkdir(exist_ok=True);(out/'request.json').write_text(json.dumps(asdict(req),indent=2,ensure_ascii=False)+'\n');(out/'resolved_theta.json').write_text(json.dumps(json.loads(canonical(result.resolved)),indent=2)+'\n');export_glb(result.mesh,out/'building.glb')
lots=gpd.read_file('data/lotes/BARRANCO_LM_geogpsperu.geojson').to_crs(32718);geom=lots[lots.objectid==1135384].iloc[0].geometry
poses=json.load(open('data/poses_barranco/metadata.json'))['panoramas'];offset=json.load(open('data/cadastral_offset.json'))
count=render_case(result,out,1135384,geom,poses,offset,after_label='SOLO LOTE LADRILLO BLANCO')
(out/'manifest.json').write_text(json.dumps(dict(lot=1135384,comparisons=count,triangles=len(result.mesh.faces),validation=val,mesh_sha256=fingerprint(result.mesh)),indent=2)+'\n')
print('PASS',val['envelope_test'],len(result.mesh.faces),count)
