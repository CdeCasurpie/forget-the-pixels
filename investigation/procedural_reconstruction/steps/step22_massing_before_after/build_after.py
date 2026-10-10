"""Regenerate declarative Step22 AFTER hypotheses; BEFORE is read-only.

Recipes supply scalar regions/levels and facade proportions, never XY building
footprints. This benchmark fitter is intentionally separate from src/.
"""
import argparse
from copy import deepcopy
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
import sys

import cv2
import geopandas as gpd
import numpy as np
from pyproj import Transformer
from shapely.geometry import Polygon
from shapely.ops import unary_union

STEP=Path(__file__).resolve().parent
ROOT=STEP.parents[1]
sys.path.insert(0,str(ROOT/'src'))
from build_lot_before import render_perspective, fingerprint
from domain.theta import *
from domain.models import Opening, FacadeProjection
from domain.architecture import ParcelContext
from modeling.theta import resolve_theta, _context
from modeling.assembly import compose_masses, region_frame, mass_polygon
from modeling.geometry_constraints import outward_normal
from modeling.grammar import street_envelope
from modeling.validation import validate_mesh
from modeling.exporters.glb_exporter import export_glb
from pipeline.theta import reconstruct


def layout_controls(layout, length, mass):
    if length<1.6:return FacadeControls(mode='explicit',openings=())
    count=min(layout.get('count',2),max(1,int(length/layout.get('minimum_pitch',1.5))))
    pitch=(length-.6)/count
    ops=[];features=[]
    height=mass.roof_z-mass.base_z
    for floor,(z0,z1) in enumerate(zip(mass.floor_levels,mass.floor_levels[1:])):
        z0-=mass.base_z;z1-=mass.base_z
        for i in range(count):
            ground=layout.get('ground','door')
            entry_index=min(count-1,layout.get('entrance_index',0))
            is_entry=mass.base_z==0 and floor==0 and (i==entry_index or layout.get('ground_all',ground=='open')) and ground!='window'
            width=min(pitch*layout.get('ratio',.55),pitch-.15)
            if is_entry and 'door_width' in layout:width=min(layout['door_width'],pitch-.15)
            u=.3+pitch*(i+.5)-width/2
            sill=0.05 if is_entry else layout.get('sill',.8)
            h=min(layout.get('window_h',1.65) if not is_entry else layout.get('door_h',z1-z0-.4),z1-z0-sill-.15)
            if h<.3:continue
            prefab=('open' if ground=='open' else 'metal_gate' if ground=='garage' else 'wood_panel') if is_entry else 'slim_window'
            arch=layout.get('arch_all',False) or floor==0 and layout.get('arch_ground',False) and i in layout.get('arch_indices',range(count))
            ops.append(Opening('gate' if is_entry and ground=='garage' else 'door' if is_entry else 'window',
                u,z0+sill,width,h,prefab=prefab,shape='arch' if arch else 'rectangle',
                arch_rise_m=min(.45,h*.3) if arch and not is_entry and layout.get('segmental_windows') else None,grille=arch and not is_entry))
        if (floor>0 or mass.base_z>0) and layout.get('balcony'):
            features.append(FacadeProjection('balcony',.25,max(.16,z0),length-.5,1.,.8,material_slot='plaster'))
        if floor>0 and layout.get('gallery'):
            features.append(FacadeProjection('gallery',.2,z0,length-.4,z1-z0-.2,1.1,material_slot='plaster'))
    if layout.get('cornice'):
        features.append(FacadeProjection('cornice',.08,height-.35,length-.16,.3,.23,material_slot='frame'))
    if layout.get('pilasters'):
        for u in np.linspace(.08,length-.35,count+1):
            features.append(FacadeProjection('pilaster',float(u),.1,.25,height-.45,.13,material_slot='frame'))
    if layout.get('pediment'):
        width=min(3.5,length*.4)
        features.append(FacadeProjection('pediment',(length-width)/2,height-.2,width,1.2,.23,material_slot='frame'))
    if layout.get('fins'):
        features.append(FacadeProjection('vertical_fins',.1,.1,length-.2,height-.3,.18,border_width_m=pitch,material_slot='frame'))
    return FacadeControls(mode='explicit',openings=tuple(ops),projections=tuple(features),material_regions=())


def make_request(before,recipe,folder):
    request=json.loads(json.dumps(before))
    theta=request['theta'];theta['schema_version']='0.3'
    if recipe.get('reuse_before'):
        for facade in theta.get('facades',[]):
            for op in facade['controls'].get('openings',[]):
                op['prefab']=recipe.get('prefab_map',{}).get(op.get('prefab'),op.get('prefab','legacy'))
    else:
        theta.pop('height_m',None);theta.pop('floors',None)
        theta['massing']={'components':recipe['components']}
        theta['facade']={'mode':'explicit','openings':[]}
        theta['facades']=[];theta['roofs']=[]
        theta['roof']={'kind':'flat','parapet_m':.25,'props':[]}
        theta['site']=recipe.get('site',{'fence':'none'})
        theta['side_material']='plaster'
        # A benchmark recipe compiles fractional facade proportions onto each
        # resolved body edge. Architectural polygons remain generator output.
        parsed=from_json(json.dumps(request));ctx=_context(parsed.context)
        masses=compose_masses(ctx,parsed.theta.massing)
        fronts=[outward_normal(Polygon(ctx.parcel),ctx.parcel[i],ctx.parcel[(i+1)%len(ctx.parcel)])[1] for i in ctx.fronts]
        overrides=[]
        for mass in masses:
            if mass.kind=='open':continue
            component=next(c for c in parsed.theta.massing.components if c.id==mass.role)
            _,t,n,_=region_frame(ctx,component.region)
            layouts=recipe.get('layouts',{}).get(mass.role,{})
            for edge,a in enumerate(mass.footprint):
                b=mass.footprint[(edge+1)%len(mass.footprint)]
                _,normal,length=outward_normal(mass_polygon(mass),a,b)
                face=max((('front',-n),('back',n),('left',-t),('right',t)),key=lambda x:np.dot(normal,x[1]))[0]
                layout=layouts.get(face)
                if layout is None and any(np.dot(normal,f)>.85 for f in fronts):layout=layouts.get('street')
                if layout is None:continue
                from modeling.exposure import wall_domains
                if not wall_domains(mass,masses,a,b):continue
                overrides.append(FacadeOverride(mass.id,edge,layout_controls(layout,length,mass)))
        theta['facades']=[asdict(f) for f in overrides]
        # Remove old material overrides that forced all plaster/stone to a
        # previous family palette, but preserve the user's base facade colour.
        theta['materials']=recipe.get('materials',[m for m in theta.get('materials',[]) if m['slot'] not in ('plaster','stone')])
    views=json.loads((folder/'views.json').read_text())
    seg=json.loads((folder/'segmentation.json').read_text())['images']
    valid=[v for v in views['views'] if seg.get(v['camera_id'],{}).get('status')=='present']
    request['observations']=[{'view_id':v['camera_id'],'image_path':str(folder.relative_to(ROOT)/v['file'])} for v in valid]
    request['evidence']={}
    for c in theta['massing'].get('components',[]):
        request['evidence'][f'massing.components[{c["id"]}].levels_m']={'state':'inferred','confidence':.55,'view_ids':[v['camera_id'] for v in valid]}
        request['evidence'][f'massing.components[{c["id"]}].region']={'state':'prior','confidence':.3}
    return from_json(json.dumps(request))


def render_case(result,directory,lot,geom,poses,offset):
    source=STEP/'edificios_a_probar'/str(lot)
    views=json.loads((source/'views.json').read_text())
    seg=json.loads((source/'segmentation.json').read_text())['images']
    ox,oy,_,_=geom.bounds
    target=np.r_[np.array(geom.centroid.coords[0])+[offset['east_m'],offset['north_m']],views['nominal_roof_height_m']/2]
    verts=result.mesh.vertices+np.array([ox+offset['east_m'],oy+offset['north_m'],0.])
    colors=np.array([m['color'] for m in result.mesh.materials])[result.mesh.face_materials]
    project=Transformer.from_crs(4326,32718,always_xy=True)
    records=[]
    for view in views['views']:
        cam=view['camera_id']
        if seg.get(cam,{}).get('status')!='present':continue
        photo=cv2.imread(str(source/view['file']))
        if photo is None:raise ValueError(f'Missing present photo: {cam}')
        h,w=photo.shape[:2];meta=poses[cam];cx,cy=project.transform(meta['lon'],meta['lat'])
        eye=np.array([cx,cy,2.5]);fw=target-eye;fw/=np.linalg.norm(fw)
        right=np.cross(fw,[0.,0.,1.]);right/=np.linalg.norm(right);up=np.cross(right,fw)
        focal=(w/2)/np.tan(np.deg2rad(view['horizontal_fov_deg'])/2)
        render_perspective(verts,result.mesh.faces,colors,eye,fw,right,up,focal,w,h,directory/f'render_{cam}.jpg')
        render=cv2.imread(str(directory/f'render_{cam}.jpg'))
        combined=cv2.copyMakeBorder(np.hstack([photo,render]),40,0,0,0,cv2.BORDER_CONSTANT,value=(24,28,34))
        for label,x in [('FOTO STREET VIEW',30),('AFTER COMPOSITION 0.3',w+30)]:
            cv2.putText(combined,label,(x,28),cv2.FONT_HERSHEY_SIMPLEX,.9,(230,230,230),2)
        cv2.imwrite(str(directory/f'compare_{cam}.jpg'),combined,[cv2.IMWRITE_JPEG_QUALITY,90])
        records.append({'camera_id':cam,'eye':eye.tolist(),'forward':fw.tolist(),'focal_px':float(focal),'width':w,'height':h})
    (directory/'cameras.json').write_text(json.dumps(records,indent=2)+'\n')
    return len(records)


def write_zone_review(directory, baseline):
    """All fixed-camera views: photo | original AFTER | zoned AFTER."""
    rows=[]
    for camera in json.loads((directory/'cameras.json').read_text()):
        key=camera['camera_id']
        photo=cv2.imread(str(directory/f'compare_{key}.jpg'))[40:,:camera['width']]
        old=cv2.imread(str(baseline/f'render_{key}.jpg'))
        new=cv2.imread(str(directory/f'render_{key}.jpg'))
        panels=[]
        for label,image in [('STREET VIEW',photo),('AFTER 0.3 BASE',old),('AFTER FACADE ZONES',new)]:
            if image is None:
                raise ValueError(f'Missing baseline render for zone review: {key}')
            resized=cv2.resize(image,(640,round(640*camera['height']/camera['width'])))
            panel=cv2.copyMakeBorder(resized,32,0,0,0,cv2.BORDER_CONSTANT,value=(24,28,34))
            cv2.putText(panel,label,(12,23),cv2.FONT_HERSHEY_SIMPLEX,.6,(240,240,240),1)
            panels.append(panel)
        rows.append(np.hstack(panels))
    cv2.imwrite(str(directory/'review_all_views.jpg'),np.vstack(rows),[cv2.IMWRITE_JPEG_QUALITY,90])


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--lot',type=int,action='append')
    ap.add_argument('--no-render',action='store_true')
    ap.add_argument('--facade-zones',action='store_true',
                    help='Apply the two FacadeZone demos and write after_facade_zones/')
    args=ap.parse_args()
    recipes=json.loads((STEP/'after_recipes.json').read_text())
    if args.facade_zones:
        demonstrations=json.loads((STEP/'facade_zone_recipes.json').read_text())
        recipes={name:deepcopy(recipes[name]) for name in demonstrations}
        for name,recipe in recipes.items():
            demo=demonstrations[name]
            recipe['note']=demo['note']
            for component in recipe['components']:
                component['zones']=demo['components'].get(component['id'],[])
    lots=None
    if not args.no_render:
        lots=gpd.read_file(ROOT/'data/lotes/BARRANCO_LM_geogpsperu.geojson').to_crs(32718)
        poses=json.loads((ROOT/'data/poses_barranco/metadata.json').read_text())['panoramas']
        offset=json.loads((ROOT/'data/cadastral_offset.json').read_text())
    failures=[]
    for name,recipe in recipes.items():
        lot=int(name.split('_')[0])
        if args.lot and lot not in args.lot:continue
        d=STEP/'lotes'/name;out=d/('after_facade_zones' if args.facade_zones else 'after');out.mkdir(exist_ok=True)
        try:
            before=json.loads((d/'before/request.json').read_text())
            request=make_request(before,recipe,STEP/'edificios_a_probar'/str(lot))
            result=reconstruct(request)
            parcel=Polygon(result.resolved.context.parcel)
            env=street_envelope(ParcelContext(result.resolved.context.parcel,explicit_fronts=result.resolved.context.fronts))
            validation=validate_mesh(result.mesh,parcel,envelope=env)
            (out/'request.json').write_text(json.dumps(asdict(request),indent=2,ensure_ascii=False)+'\n')
            (out/'resolved_theta.json').write_text(json.dumps(json.loads(canonical(result.resolved)),indent=2)+'\n')
            export_glb(result.mesh,out/'building.glb')
            masses=result.resolved.masses
            occupied=unary_union([mass_polygon(m) for m in masses if m.base_z<.01 and m.kind=='enclosed'])
            manifest={'lot':lot,'hypothesis':recipe['note'],'before_request_sha256':hashlib.sha256((d/'before/request.json').read_bytes()).hexdigest(),
                'mass_count':len(masses),'ground_occupancy_ratio':occupied.area/parcel.area,
                'height_before_m':before['theta'].get('height_m'),'height_after_m':result.resolved.theta.height_m,
                'triangles':len(result.mesh.faces),'validation':validation,'mesh_sha256':fingerprint(result.mesh)}
            if not args.no_render:
                manifest['comparisons']=render_case(result,out,lot,lots[lots.objectid==lot].iloc[0].geometry,poses,offset)
                if args.facade_zones:
                    write_zone_review(out,d/'after')
            (out/'manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n')
            print(name,'OK',len(masses),'bodies',round(occupied.area/parcel.area,3),'occupied',flush=True)
        except Exception as exc:
            import traceback
            traceback.print_exc();failures.append((name,str(exc)))
    if failures:raise SystemExit(str(failures))


if __name__=='__main__':main()
