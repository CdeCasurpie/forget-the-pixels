"""BCP bank only: render mass first, then its observed classical facade."""
import argparse,json,sys
from pathlib import Path
from dataclasses import asdict
import geopandas as gpd
from shapely.geometry import Polygon
sys.path[:0]=['src','steps/step22_massing_before_after']
from domain.theta import from_json,canonical
from domain.architecture import ParcelContext
from modeling.theta import resolve_theta
from modeling.grammar import street_envelope
from modeling.validation import validate_mesh
from modeling.exporters.glb_exporter import export_glb
from pipeline.theta import reconstruct
from build_after import render_case
from build_lot_before import fingerprint

lot=Path('steps/step23_fresh_theta/lotes/1137619_banco_neoclasico')

def build(details):
 r=json.loads((lot/'after/request.json').read_text());r['observations']=[dict(view_id=p.name.removesuffix('_lot.jpg'),image_path=str(p)) for p in sorted(lot.glob('*_lot.jpg'))];r['evidence']={};t=r['theta']
 c=t['massing']['components'][0];c['region']['front_edge']=7;c['levels_m']=[0.,5.25]
 t['family']='republicano';t['primary_color']=[.39,.41,.39];t['side_material']='plaster';t['roof']={'kind':'flat','parapet_m':.06,'props':[]};t['site']={'fence':'none','garden':False,'runs':[],'zones':[]}
 t['materials']=[dict(slot='frame',template='frame',color=[.70,.72,.68]),dict(slot='stone',template='stone',color=[.35,.37,.35]),dict(slot='accent',template='plaster',color=[.29,.31,.30]),dict(slot='metal',template='metal',color=[.51,.53,.52]),dict(slot='glass',template='glass',color=[.11,.17,.19]),dict(slot='sign',template='plaster',color=[.40,.43,.42])]
 t['facade']={'mode':'explicit','openings':[],'projections':[],'material_regions':[]};t['facades']=[]
 if details:
  def op(kind,u,v,w,h,prefab='legacy',**kw):return dict(kind=kind,u_m=round(u,3),v_m=v,width_m=round(w,3),height_m=h,prefab=prefab,**kw)
  def pr(kind,u,v,w,h,d,slot='frame',**kw):return dict(kind=kind,u_m=round(u,3),v_m=v,width_m=round(w,3),height_m=h,depth_m=d,material_slot=slot,**kw)
  base=from_json(json.dumps(r));mass=resolve_theta(base.context,base.theta)
  for wall in mass.walls:
   if not wall.facade.is_front or wall.facade.width_m<2.5:continue
   L=wall.facade.width_m;e=wall.edge
   # Canonical long street wall e7; corner return e6, transverse wall e5.
   # Two visible views are partially occluded by trees; avoid repeating phantom doors.
   openings=[];features=[]
   if L>16:
    openings=[op('gate',.68,.04,2.7,3.15,'metal_gate',recess_m=.19),op('window',L*.51,1.18,1.60,2.2,'slim_window',recess_m=.18,grille=True,grille_pattern='diamond',mullion_columns=2,mullion_rows=3),op('window',L*.77,1.18,1.60,2.2,'slim_window',recess_m=.18,grille=True,grille_pattern='diamond',mullion_columns=2,mullion_rows=3)]
    features=[pr('frame',.49,.05,3.08,3.3,.17,'stone',border_width_m=.11)]
   elif L>10:
    openings=[op('window',L*.22,1.16,1.52,2.22,'slim_window',recess_m=.18,grille=True,grille_pattern='diamond',mullion_columns=2,mullion_rows=3),op('window',L*.64,1.16,1.52,2.22,'slim_window',recess_m=.18,grille=True,grille_pattern='diamond',mullion_columns=2,mullion_rows=3)]
   else:
    # Corner bank portal: white sculpted surround, glass infill and blue fascia.
    openings=[op('door',(L-1.65)/2,.05,1.65,3.22,'storefront',recess_m=.21,mullion_columns=2,mullion_rows=2)]
    features=[pr('moulded_surround',(L-2.18)/2,.04,2.18,3.52,.27,'frame',border_width_m=.24),pr('pediment',(L-2.5)/2,3.68,2.5,.39,.20,'frame'),pr('sign_box',(L-2.0)/2,4.66,2.0,.35,.10,'sign',label='BCP')]
   if L>10:
    for item in openings:
     if item['kind']=='window':features.append(pr('moulded_surround',item['u_m']-.14,item['v_m']-.14,item['width_m']+.28,item['height_m']+.28,.15,'stone',border_width_m=.13))
    for pos in [L*.13,L*.36,L*.60,L*.86]:features.append(pr('pilaster',pos,.24,.22,4.28,.14,'stone'))
    features.append(pr('sign_box',L*.38,4.63,min(2.5,L*.25),.36,.10,'sign',label='BCP'))
   features.extend([pr('panel',.04,.0,L-.08,.85,.09,'stone'),pr('classical_cornice',.04,4.41,L-.08,.54,.37,'frame'),pr('ledge',.02,5.01,L-.04,.14,.22,'stone')])
   t['facades'].append(dict(mass_role=wall.mass_role,edge=e,controls=dict(mode='explicit',openings=openings,projections=features,material_regions=[])))
 r['nuisance']['curtains']=False;r['config']['detail']=3
 req=from_json(json.dumps(r));res=reconstruct(req);parcel=Polygon(res.resolved.context.parcel);env=street_envelope(ParcelContext(res.resolved.context.parcel,explicit_fronts=res.resolved.context.fronts));val=validate_mesh(res.mesh,parcel,envelope=env)
 out=lot/('fresh' if details else 'massing_preview');out.mkdir(exist_ok=True)
 (out/'request.json').write_text(json.dumps(asdict(req),indent=2,ensure_ascii=False)+'\n');(out/'resolved_theta.json').write_text(json.dumps(json.loads(canonical(res.resolved)),indent=2)+'\n');export_glb(res.mesh,out/'building.glb')
 lots=gpd.read_file('data/lotes/BARRANCO_LM_geogpsperu.geojson').to_crs(32718);geom=lots[lots.objectid==1137619].iloc[0].geometry
 poses=json.load(open('data/poses_barranco/metadata.json'))['panoramas'];offset=json.load(open('data/cadastral_offset.json'))
 n=render_case(res,out,1137619,geom,poses,offset,after_label='SOLO BCP '+('DETAIL' if details else 'MASSING'))
 (out/'manifest.json').write_text(json.dumps(dict(lot=1137619,phase='details' if details else 'massing',comparisons=n,triangles=len(res.mesh.faces),validation=val,mesh_sha256=fingerprint(res.mesh)),indent=2)+'\n')
 print(out,'VALID',val['envelope_test'],len(res.mesh.faces),n)
 for m in res.resolved.masses:print(m.id,round(Polygon(m.footprint).area,2),m.roof_z)
 for w in res.resolved.walls:print('wall',w.edge,round(w.facade.width_m,2),w.facade.is_front,len(w.facade.openings))

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--massing-only',action='store_true');args=ap.parse_args();build(not args.massing_only)
