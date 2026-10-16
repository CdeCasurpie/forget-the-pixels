"""Build mass-only checkpoint, then detailed Tintoretto white restaurant theta."""
import json,sys,argparse
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

lot=Path('steps/step23_fresh_theta/lotes/1137568_comercio_blanco_dos_plantas')

def build(detailed):
 r=json.loads((lot/'after/request.json').read_text());r['observations']=[dict(view_id=p.name.removesuffix('_lot.jpg'),image_path=str(p)) for p in sorted(lot.glob('*_lot.jpg'))];r['evidence']={};t=r['theta']
 # Long plot extends behind a 7.3 m frontage. Only the first ~9 m are visibly built.
 ground,roof=t['massing']['components'];ground['region']['depth_m']=[0,9.0];ground['levels_m']=[0,3.3]
 roof['region']['u']=[0,1];roof['region']['depth_m']=[0,8.5];roof['levels_m']=[3.3,6.0];roof['support']['kind']='columns';roof['support']['column_width_m']=.16;roof['support']['spacing_m']=4.0;roof['roof']={'kind':'flat','parapet_m':0}
 t['roof_assemblies']=[dict(id='terrace_cover',mass_ref=roof['id']+':0',design=dict(
     form='flat',covering='corrugated',material='roof',rotation_deg=5.279328393121386,
     eave=dict(kind='clean',overhang_m=0.,fascia=False)))]
 t['family']='quiet_house';t['primary_color']=[.88,.89,.86];t['side_material']='plaster';t['roof']={'kind':'flat','parapet_m':.36,'props':[]};t['materials']=[dict(slot='frame',template='frame',color=[.16,.18,.17]),dict(slot='metal',template='metal',color=[.18,.19,.18]),dict(slot='wood',template='wood',color=[.39,.25,.20]),dict(slot='roof',template='roof',color=[.16,.17,.17]),dict(slot='sign',template='plaster',color=[.92,.93,.91]),dict(slot='stone',template='stone',color=[.77,.79,.76]),dict(slot='glass',template='glass',color=[.13,.16,.15])]
 t['facade']={'mode':'explicit','openings':[],'projections':[],'material_regions':[]};t['facades']=[];t['site']={'fence':'none','garden':False,'runs':[],'zones':[]}
 if detailed:
  def op(kind,u,v,w,h,prefab='legacy',**kw):return dict(kind=kind,u_m=u,v_m=v,width_m=w,height_m=h,prefab=prefab,**kw)
  def pr(kind,u,v,w,h,d,slot='frame',**kw):return dict(kind=kind,u_m=u,v_m=v,width_m=w,height_m=h,depth_m=d,material_slot=slot,**kw)
  # One rectangular glazed shop on the left; arched, recessed entry on the right.
  # Thick corner pilasters / sign-backing and a deeper lintel are real relief.
  facade={'mode':'explicit','openings':[
    op('window',.59,.31,2.52,2.05,'storefront',recess_m=.19,mullion_columns=3,mullion_rows=2)],
    'projections':[
     pr('sign_box',.34,2.49,3.18,.40,.10,'sign',label='TINTORETTO'),
     pr('panel',.04,.04,.23,3.15,.22,'stone'),pr('panel',3.56,.04,.24,3.15,.21,'stone'),
     pr('ledge',.02,3.10,3.78,.17,.27,'stone')],
    'material_regions':[dict(u_m=0,v_m=0,width_m=3.80,height_m=.27,material_slot='stone')]}
  ground['zones']=[dict(face='front',u=[.53,1.0],z_m=[0,3.3],offset_m=-1.15,role='recessed_entry',section=dict(back_wall=True,column_axes_u=[.08,.92],column_width_m=.20,slab_m=.20),controls={'mode':'explicit','openings':[op('door',.83,.04,1.70,2.83,'open',shape='arch',arch_rise_m=.82,style='vestibule',recess_m=.32)],'projections':[pr('segmental_surround',.67,.02,2.02,2.96,.17,'stone',border_width_m=.12,arch_rise_m=.82)],'material_regions':[]})]
  t['facades']=[dict(mass_role='shop:0',edge=0,controls=facade)]
 r['nuisance']['curtains']=False;r['config']['detail']=3
 request=from_json(json.dumps(r));result=reconstruct(request);parcel=Polygon(result.resolved.context.parcel);env=street_envelope(ParcelContext(result.resolved.context.parcel,explicit_fronts=result.resolved.context.fronts));val=validate_mesh(result.mesh,parcel,envelope=env)
 out=lot/('fresh' if detailed else 'massing_preview');out.mkdir(exist_ok=True)
 (out/'request.json').write_text(json.dumps(asdict(request),indent=2,ensure_ascii=False)+'\n');(out/'resolved_theta.json').write_text(json.dumps(json.loads(canonical(result.resolved)),indent=2)+'\n');export_glb(result.mesh,out/'building.glb')
 lots=gpd.read_file('data/lotes/BARRANCO_LM_geogpsperu.geojson').to_crs(32718);geom=lots[lots.objectid==1137568].iloc[0].geometry
 poses=json.load(open('data/poses_barranco/metadata.json'))['panoramas'];offset=json.load(open('data/cadastral_offset.json'))
 n=render_case(result,out,1137568,geom,poses,offset,after_label='TINTORRETTO '+('DETAIL' if detailed else 'MASSING'))
 (out/'manifest.json').write_text(json.dumps(dict(lot=1137568,phase='detail' if detailed else 'massing',comparisons=n,triangles=len(result.mesh.faces),validation=val,mesh_sha256=fingerprint(result.mesh)),indent=2)+'\n')
 print(out, 'VALID',val['envelope_test'],'triangles',len(result.mesh.faces),'views',n)

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--massing-only',action='store_true');args=ap.parse_args();build(not args.massing_only)
