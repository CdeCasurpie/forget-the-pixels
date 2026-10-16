"""Rebuild both connected parts of the yellow house from photographs; mass-first checkpoint."""
import argparse,json,sys
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

lot=Path('steps/step23_fresh_theta/lotes/1138209_casona_amarilla_galeria')
def region(u,depth):return dict(front_edge=4,u=u,depth=[0,1],depth_m=depth,fit='parcel',width_reference='edge')
def component(id,u,depth,levels,roof):return dict(id=id,region=region(u,depth),levels_m=levels,kind='enclosed',cutouts=[],support=dict(kind='bearing',spacing_m=4.,column_width_m=.24,inset_m=.4,max_cantilever_m=0.),facade=None,faces=[],roof=roof,slab_m=.18)
def op(kind,u,v,w,h,prefab='slim_window',**kw):return dict(kind=kind,u_m=u,v_m=v,width_m=w,height_m=h,prefab=prefab,**kw)
def pr(kind,u,v,w,h,d,slot='frame',**kw):return dict(kind=kind,u_m=u,v_m=v,width_m=w,height_m=h,depth_m=d,material_slot=slot,**kw)
def controls(ops,proj=[],regions=[]):return dict(mode='explicit',openings=ops,projections=proj,material_regions=regions)

def build(details):
 r=json.loads((lot/'after/request.json').read_text());r['observations']=[dict(view_id=p.name.removesuffix('_lot.jpg'),image_path=str(p)) for p in sorted(lot.glob('*_lot.jpg'))];r['evidence']={};t=r['theta']
 # Explicit catalog coverings on the front blocks; rear blocks stay flat.
 t['massing']['components']=[
 component('street_front',[0,.44],[0,3.8],[0,3.35,6.9],dict(kind='flat',parapet_m=0)),
 component('street_rear',[0,.44],[3.8,15.5],[0,3.35,6.9],None),
 component('garden_front',[.44,1],[2.35,7.0],[0,3.15,6.35],dict(kind='flat',parapet_m=0)),
 component('garden_rear',[.44,1],[7.0,15.5],[0,3.15,6.35],None)]
 t['roof_assemblies']=[dict(id=name+'_roof',mass_ref=name+':0',design=dict(
     form='shed',covering='curved_tile',slope_deg=slope,rotation_deg=-84.52396504632391,
     eave=dict(kind='clean',overhang_m=0.,fascia=False)))
     for name,slope in [('street_front',35.),('garden_front',20.)]]
 t['family']='galeria_madera';t['primary_color']=[.85,.82,.67];t['side_material']='plaster';t['roof']={'kind':'flat','parapet_m':0,'props':[]};t['facade']=controls([]);t['facades']=[]
 t['materials']=[dict(slot='frame',template='frame',color=[.93,.94,.88]),dict(slot='stone',template='stone',color=[.52,.53,.51]),dict(slot='wood',template='wood',color=[.92,.91,.83]),dict(slot='metal',template='metal',color=[.90,.91,.86]),dict(slot='glass',template='glass',color=[.37,.46,.43]),dict(slot='roof_tile',template='roof_tile',color=[.38,.28,.25]),dict(slot='roof',template='roof',color=[.36,.28,.24]),dict(slot='pavement',template='pavement',color=[.68,.66,.56]),dict(slot='brick',template='brick',color=[.72,.71,.66])]
 t['site']={'fence':'none','garden':False,'runs':[],'zones':[]}
 if details:
  # Street block seen from the two north cameras: door left, two tall grid
  # windows, one triple diamond window above plus a narrow side window.
  house=controls([
    op('door',.60,.13,1.15,2.85,'open',style='vestibule',recess_m=.25),
    op('window',2.15,.60,1.30,2.25,recess_m=.16,mullion_columns=3,mullion_rows=4),
    op('window',3.85,.60,1.30,2.25,recess_m=.16,mullion_columns=3,mullion_rows=4),
    op('window',1.85,3.86,2.20,2.10,recess_m=.15,mullion_columns=3,mullion_rows=3,grille=True,grille_pattern='diamond'),
    op('window',5.45,3.95,.70,1.90,recess_m=.15,mullion_columns=1,mullion_rows=3)],
    [pr('panel',.04,.02,7.30,.28,.09,'stone'),
     pr('frame',.46,.03,1.44,3.05,.20,'frame',border_width_m=.13),
     pr('moulded_surround',2.04,.49,1.52,2.47,.13,'frame',border_width_m=.11),
     pr('moulded_surround',3.74,.49,1.52,2.47,.13,'frame',border_width_m=.11),
     pr('moulded_surround',1.74,3.75,2.42,2.32,.14,'frame',border_width_m=.10),
     pr('sill_band',2.02,.43,3.24,.17,.20,'frame'),
     pr('sill_band',1.71,3.58,2.68,.18,.20,'frame'),
     pr('denticulated_cornice',.08,6.30,7.20,.42,.30,'frame')])
  # Gallery block set behind the garden: glass doors/windows behind two open verandas.
  gallery=controls([
   op('window',1.00,.55,1.50,2.10,recess_m=.14,mullion_columns=2,mullion_rows=4),
   op('door',4.20,.08,1.15,2.60,'storefront',recess_m=.12,mullion_columns=2,mullion_rows=3),
   op('window',6.90,.55,1.50,2.10,recess_m=.14,mullion_columns=2,mullion_rows=4),
   op('window',1.00,3.60,1.50,2.15,recess_m=.14,mullion_columns=2,mullion_rows=3),
   op('door',4.20,3.18,1.15,2.62,'storefront',recess_m=.14,mullion_columns=2,mullion_rows=3),
   op('window',6.90,3.60,1.50,2.15,recess_m=.14,mullion_columns=2,mullion_rows=3)],
   [pr('gallery',.60,3.00,8.60,3.10,1.05,'wood',label='classical'),
    pr('gallery',.60,.10,8.60,2.70,.95,'wood',label='classical'),
    pr('eave',.55,6.05,8.70,.23,.48,'wood')])
  draft=from_json(json.dumps(r));resolved=reconstruct(draft).resolved
  for wall in resolved.walls:
   if wall.facade.is_front and wall.mass_role=='street_front:0' and wall.facade.width_m>=7.2:
    t['facades'].append(dict(mass_role=wall.mass_role,edge=wall.edge,controls=house))
   if wall.facade.is_front and wall.mass_role=='garden_front:0' and wall.facade.width_m>=9.2:
    t['facades'].append(dict(mass_role=wall.mass_role,edge=wall.edge,controls=gallery))
  t['site']['runs']=[dict(edge=4,start_m=7.83,end_m=17.40,kind='republicano',height_m=1.65,gate_u=8.00,gate_width=1.15)]
  t['site']['zones']=[dict(id='front_garden',kind='garden',region=region([.44,1],[0,2.35]))]
 r['nuisance']['curtains']=False;r['config']['detail']=3
 req=from_json(json.dumps(r));res=reconstruct(req);parcel=Polygon(res.resolved.context.parcel);env=street_envelope(ParcelContext(res.resolved.context.parcel,explicit_fronts=res.resolved.context.fronts));val=validate_mesh(res.mesh,parcel,envelope=env)
 out=lot/('fresh' if details else 'massing_preview');out.mkdir(exist_ok=True)
 (out/'request.json').write_text(json.dumps(asdict(req),indent=2,ensure_ascii=False)+'\n');(out/'resolved_theta.json').write_text(json.dumps(json.loads(canonical(res.resolved)),indent=2)+'\n');export_glb(res.mesh,out/'building.glb')
 lots=gpd.read_file('data/lotes/BARRANCO_LM_geogpsperu.geojson').to_crs(32718);geom=lots[lots.objectid==1138209].iloc[0].geometry
 poses=json.load(open('data/poses_barranco/metadata.json'))['panoramas'];offset=json.load(open('data/cadastral_offset.json'))
 n=render_case(res,out,1138209,geom,poses,offset,after_label='CASONA '+('DETALLE' if details else 'MASA'))
 (out/'manifest.json').write_text(json.dumps(dict(lot=1138209,phase='detail' if details else 'massing',comparisons=n,triangles=len(res.mesh.faces),validation=val,mesh_sha256=fingerprint(res.mesh)),indent=2)+'\n')
 print(out,val['envelope_test'],len(res.mesh.faces),'views',n)
 for w in res.resolved.walls:
  if w.facade.is_front:print(w.mass_role,w.edge,round(w.facade.width_m,2),len(w.facade.openings),len(w.facade.projections))

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--massing-only',action='store_true');build(not p.parse_args().massing_only)
