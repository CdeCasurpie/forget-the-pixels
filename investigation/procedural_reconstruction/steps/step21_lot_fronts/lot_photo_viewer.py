"""Cadastral viewer. Local JPGs only; manual offset saved on explicit button click.

Angular cylindrical views (longitude/latitude, not a tangent cylinder) include
sky up to +85 deg. Overlays are parcel extrusions, not measured buildings.
Flat ground, camera height 2.5 m, same heading/pitch/roll convention as Step 20.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
import json
from pathlib import Path
import sys

import cv2
import geopandas as gpd
import numpy as np
from pyproj import Transformer
from scipy.spatial import cKDTree
from shapely.geometry import Point, LineString, box
from shapely.affinity import translate

STEP = Path(__file__).resolve().parent
ROOT = STEP.parent.parent
OFFSET_PATH = ROOT/'data/cadastral_offset.json'
LOT_LIST_PATH = STEP/'seleccion/lotes.json'


def save_lot(lot_id, description, path=LOT_LIST_PATH):
    data=json.loads(path.read_text()) if path.exists() else {'lots': []}
    record=next((r for r in data['lots'] if r['objectid']==lot_id),None)
    if record is None:
        data['lots'].append({'objectid':lot_id,'description':description})
    else:
        record['description']=description
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n');temp.replace(path)


def load_offset(path=OFFSET_PATH):
    if not path.exists(): return np.zeros(2)
    data=json.loads(path.read_text())
    if data.get('crs') != 'EPSG:32718': raise ValueError('Invalid offset CRS')
    offset=np.array([data['east_m'],data['north_m']],dtype=float)
    if not np.isfinite(offset).all(): raise ValueError('Invalid cadastral offset')
    return offset


def save_offset(offset, path=OFFSET_PATH):
    data=dict(crs='EPSG:32718',east_m=float(offset[0]),north_m=float(offset[1]),
              operation='translated_lot_xy = original_lot_xy + [east_m, north_m]',
              applies_to='cadastral lots only; camera positions unchanged')
    temp=path.with_suffix('.tmp')
    temp.write_text(json.dumps(data,indent=2)+'\n');temp.replace(path)
sys.path.insert(0, str(ROOT/'steps/step20_sfm_esferico'))
sys.path.insert(0, str(ROOT/'steps/step20_sfm_esferico/.dependencies'))
from geometry_stage4 import camera_to_enu
import pygame


@lru_cache(maxsize=6)
def panorama(path):
    image = cv2.imread(path)
    if image is None: raise ValueError(f'No se puede leer {path}')
    return image


def cylindrical_view(pid, meta, center, polygon, target, height, size):
    """World angular view -> camera ERP; identical transform for prism overlay."""
    w,h = size
    camera = np.r_[center, 2.5]
    rotation = camera_to_enu(meta['heading_deg'], meta['pitch_deg'], meta['roll_deg'])
    vertices = np.asarray(polygon.exterior.coords)[:,:2]
    yaw = np.arctan2(target[0]-center[0], target[1]-center[1])
    bearings = np.arctan2(vertices[:,0]-center[0], vertices[:,1]-center[1])
    wrap = lambda x: (x+np.pi)%(2*np.pi)-np.pi
    fov = min(2*np.pi, max(np.deg2rad(40), 2*np.max(np.abs(wrap(bearings-yaw)))+np.deg2rad(16)))
    bottom, top = np.deg2rad(-35), np.deg2rad(85)
    lon,lat = np.meshgrid(yaw+((np.arange(w)+.5)/w-.5)*fov,
                          top-(np.arange(h)+.5)/h*(top-bottom))
    world = np.stack([np.cos(lat)*np.sin(lon),np.cos(lat)*np.cos(lon),np.sin(lat)],axis=-1)
    local = world @ rotation
    image = panorama(str(ROOT/'data/fotos_barranco'/f'{pid}.jpg'))
    ih,iw = image.shape[:2]
    sx = ((np.arctan2(local[...,0],local[...,2])+np.pi)*iw/(2*np.pi)-.5)%iw
    sy = (np.pi/2-np.arctan2(-local[...,1],np.hypot(local[...,0],local[...,2])))*ih/np.pi-.5
    result = cv2.remap(image,sx.astype('float32'),np.clip(sy,0,ih-1).astype('float32'),cv2.INTER_LINEAR,borderMode=cv2.BORDER_WRAP)
    def line(a,b,color):
        pts=np.linspace(a,b,80)-camera
        yy=np.arctan2(pts[:,0],pts[:,1]); pitch=np.arctan2(pts[:,2],np.hypot(pts[:,0],pts[:,1]))
        uv=np.column_stack([(wrap(yy-yaw)/fov+.5)*w,(top-pitch)/(top-bottom)*h])
        for p,q in zip(uv[:-1],uv[1:]):
            if np.linalg.norm(p-q)<max(w,h)/2:
                ok,p0,p1=cv2.clipLine((0,0,w,h),tuple(np.rint(p).astype(int)),tuple(np.rint(q).astype(int)))
                if ok: cv2.line(result,p0,p1,color,1,cv2.LINE_AA)
    for a,b in zip(vertices[:-1],vertices[1:]):
        for z,color in [(0,(0,255,255)),(height,(255,80,255))]: line(np.r_[a,z],np.r_[b,z],color)
        line(np.r_[a,0],np.r_[a,height],(255,180,40))
    return result, float(np.degrees(fov))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--height',type=float,default=15.)
    parser.add_argument('--max-distance',type=float,default=70.)
    parser.add_argument('--smoke-test',action='store_true')
    args=parser.parse_args()
    if args.height<=0 or args.max_distance<=0: parser.error('Height and distance must be positive')
    lots=gpd.read_file(ROOT/'data/lotes/BARRANCO_LM_geogpsperu.geojson').to_crs(32718)
    index=lots.sindex
    polygons=list(lots.geometry)
    outlines=[np.asarray(p.exterior.coords) for p in polygons]
    offset=load_offset(); saved_offset=offset.copy()
    def lot_polygon(i):
        return translate(polygons[i],xoff=offset[0],yoff=offset[1])
    def query_lots(shape, **kwargs):
        return index.query(translate(shape,xoff=-offset[0],yoff=-offset[1]),**kwargs)
    raw=json.loads((ROOT/'data/poses_barranco/metadata.json').read_text())['panoramas']
    metas={p:m for p,m in raw.items() if (ROOT/'data/fotos_barranco'/f'{p}.jpg').is_file()
           and all(m.get(k) is not None for k in ('lat','lon','heading_deg','pitch_deg','roll_deg'))}
    ids=list(metas)
    if not ids: raise ValueError('No local panoramas with complete poses')
    transform=Transformer.from_crs(4326,32718,always_xy=True)
    xy=np.array([transform.transform(metas[p]['lon'],metas[p]['lat']) for p in ids])
    tree=cKDTree(xy)
    @lru_cache(maxsize=5000)
    def candidates(i):
        polygon=lot_polygon(i)
        # Parcel distance, not centroid distance: include cameras beside long lots.
        c=np.array(polygon.centroid.coords[0]); radius=max(np.linalg.norm(np.asarray(polygon.exterior.coords)-c,axis=1))
        return [j for j in tree.query_ball_point(c,radius+args.max_distance)
                if 1.<polygon.distance(Point(xy[j]))<=args.max_distance]
    available={i for i in range(len(lots)) if candidates(i)}
    def find_available(displacement):
        # Independent snapshot: never touches mutable UI offset or candidate caches.
        found=set()
        for i,original in enumerate(polygons):
            polygon=translate(original,xoff=displacement[0],yoff=displacement[1])
            c=np.array(polygon.centroid.coords[0])
            radius=np.max(np.linalg.norm(outlines[i]+displacement-c,axis=1))
            if any(1.<polygon.distance(Point(xy[j]))<=args.max_distance
                   for j in tree.query_ball_point(c,radius+args.max_distance)):
                found.add(i)
        return found
    @lru_cache(maxsize=128)
    def rank(i):
        polygon=lot_polygon(i); vertices=np.array(polygon.exterior.coords)
        targets=(vertices[:-1]+vertices[1:])/2
        if len(targets)>24: targets=targets[np.linspace(0,len(targets)-1,24,dtype=int)]
        scored=[]
        for j in sorted(candidates(i),key=lambda j:polygon.distance(Point(xy[j])))[:40]:
            visible=[]
            for target in targets:
                ray=LineString([xy[j],target]); blocked=False
                for k in query_lots(ray,predicate='intersects'):
                    interior=lot_polygon(k).buffer(-.15)
                    if not interior.is_empty and ray.intersection(interior).length>.25:
                        blocked=True;break
                if not blocked: visible.append(target)
            if visible:
                distance=polygon.distance(Point(xy[j])); score=distance/(.5+.5*len(visible)/len(targets))
                scored.append((score,j,np.mean(visible,axis=0),len(visible)))
        return sorted(scored,key=lambda p:p[0])
    pygame.init(); screen=pygame.display.set_mode((1500,900)); pygame.display.set_caption('Step21 - Catastro + Street View local')
    font=pygame.font.SysFont('sans',17); clock=pygame.time.Clock()
    maprect=pygame.Rect(0,50,760,805)
    save_button=pygame.Rect(570,50,180,30)
    lot_button=pygame.Rect(1280,5,210,30)
    editing=False;description='';edit_id=None
    availability_pool=ThreadPoolExecutor(max_workers=1)
    availability_future=None
    dragging_lots=False
    bounds=lots.total_bounds; origin=(bounds[:2]+bounds[2:])/2
    fullscale=min(720/(bounds[2]-bounds[0]),760/(bounds[3]-bounds[1])); scale=fullscale
    shift=np.array(maprect.center,float); height=args.height
    selected=None; cameras=[]; views=[]; request=0; future=None; error=''; executor=ThreadPoolExecutor(max_workers=1)
    def screenxy(points): return (np.asarray(points)-origin)*[scale,-scale]+shift
    def worldxy(point): return (np.array(point)-shift)/[scale,-scale]+origin
    def render(polygon, chosen, height):
        return [cylindrical_view(ids[j],metas[ids[j]],xy[j],polygon,target,height,(710,355)) for j,target in chosen]
    def choose(i):
        ranked=rank(i)
        return [(j,target) for _,j,target,_ in ranked[:2]]
    def text(s,x,y,color=(230,230,230)): screen.blit(font.render(str(s),True,color),(x,y))
    running=True; frames=0
    try:
        while running:
            mouse=pygame.mouse.get_pos(); hover=None
            if maprect.collidepoint(mouse):
                point=Point(worldxy(mouse))
                hover=next((int(i) for i in query_lots(point,predicate='intersects') if i in available),None)
            changed=False
            for event in pygame.event.get():
                if editing:
                    if event.type==pygame.QUIT: running=False
                    elif event.type==pygame.TEXTINPUT: description+=event.text
                    elif event.type==pygame.KEYDOWN:
                        if event.key==pygame.K_ESCAPE: editing=False;pygame.key.stop_text_input()
                        elif event.key==pygame.K_BACKSPACE: description=description[:-1]
                        elif event.key==pygame.K_RETURN:
                            try:
                                save_lot(edit_id,description);editing=False;pygame.key.stop_text_input();error=''
                            except OSError as exc: error=str(exc)
                    continue
                if event.type==pygame.QUIT or event.type==pygame.KEYDOWN and event.key==pygame.K_ESCAPE: running=False
                elif event.type==pygame.KEYDOWN:
                    if event.key==pygame.K_f: scale=fullscale;shift=np.array(maprect.center,float)
                    elif event.key in (pygame.K_UP,pygame.K_DOWN): height=max(3,height+(3 if event.key==pygame.K_UP else -3));changed=selected is not None
                elif event.type==pygame.MOUSEWHEEL and maprect.collidepoint(mouse):
                    new=np.clip(scale*1.2**event.y,fullscale,50);shift=np.array(mouse)+(shift-mouse)*new/scale;scale=new
                elif event.type==pygame.MOUSEBUTTONDOWN and event.button==2 and maprect.collidepoint(event.pos):
                    dragging_lots=True
                elif event.type==pygame.MOUSEBUTTONUP and event.button==2 and dragging_lots:
                    dragging_lots=False
                    candidates.cache_clear();rank.cache_clear()
                    if availability_future: availability_future[1].cancel()
                    snapshot=offset.copy()
                    availability_future=(snapshot,availability_pool.submit(find_available,snapshot))
                    changed=selected is not None
                elif event.type==pygame.MOUSEMOTION and dragging_lots:
                    delta=np.array(event.rel,dtype=float)/[scale,-scale]
                    offset+=delta
                    cameras=[(j,target+delta) for j,target in cameras]
                    # Map moves immediately; photo reprojection is deferred to release.
                elif event.type==pygame.MOUSEMOTION and event.buttons[2]: shift+=event.rel
                elif event.type==pygame.MOUSEBUTTONDOWN and event.button==1 and save_button.collidepoint(event.pos) and not np.array_equal(offset,saved_offset):
                    try:
                        save_offset(offset);saved_offset=offset.copy();error=''
                    except OSError as exc: error=f'Error al guardar: {exc}'
                elif event.type==pygame.MOUSEBUTTONDOWN and event.button==1 and lot_button.collidepoint(event.pos) and selected is not None:
                    edit_id=int(lots.iloc[selected].objectid);description=''
                    if LOT_LIST_PATH.exists():
                        saved=json.loads(LOT_LIST_PATH.read_text())
                        description=next((r['description'] for r in saved['lots'] if r['objectid']==edit_id),'')
                    editing=True;pygame.key.start_text_input()
                elif event.type==pygame.MOUSEBUTTONDOWN and event.button==1 and maprect.collidepoint(event.pos):
                    near=tree.query_ball_point(worldxy(event.pos),7/scale)
                    if selected is not None and near:
                        j=min(near,key=lambda j:np.linalg.norm(screenxy(xy[j])-event.pos))
                        target=np.array(lot_polygon(selected).centroid.coords[0])
                        cameras=([(cameras[0])] if cameras else [])+[(j,target)]; cameras=cameras[-2:];changed=True
                    elif hover is not None:
                        selected=hover; cameras=choose(selected);changed=True
            if changed:
                request+=1;views=[];error=''
                if future: future[1].cancel()
                future=(request,executor.submit(render,lot_polygon(selected),cameras.copy(),height))
            if future and future[1].done():
                try:
                    loaded=future[1].result()
                    if future[0]==request:
                        views=[(pygame.image.frombuffer(cv2.cvtColor(im,cv2.COLOR_BGR2RGB).tobytes(),(710,355),'RGB'),fov) for im,fov in loaded]
                except Exception as exc: error=str(exc)
                future=None
            if availability_future and availability_future[1].done():
                try:
                    if np.array_equal(availability_future[0],offset): available=availability_future[1].result()
                except Exception as exc: error=str(exc)
                availability_future=None
            screen.fill((25,29,34));screen.set_clip(maprect)
            lo=worldxy(maprect.bottomleft);hi=worldxy(maprect.topright)
            for i in query_lots(box(*lo,*hi)):
                if i not in available: continue
                pts=screenxy(outlines[i]+offset)
                pygame.draw.polygon(screen,(60,130,155) if i==selected else (80,85,95) if i==hover else (42,47,53),pts)
                pygame.draw.lines(screen,(200,220,230) if i in (selected,hover) else (105,110,120),True,pts,1)
            for j,pt in enumerate(screenxy(xy)):
                if maprect.collidepoint(pt): pygame.draw.circle(screen,(135,135,140),pt,3)
            for j,_ in cameras:
                pt=screenxy(xy[j]);pygame.draw.circle(screen,(255,220,0),pt,6);text(ids[j][:8],int(pt[0])+7,int(pt[1]))
            screen.set_clip(None)
            dirty=not np.array_equal(offset,saved_offset)
            text(f'Desfase E {offset[0]:+.2f} m / N {offset[1]:+.2f} m'+(' (sin guardar)' if dirty else ' (guardado)'),10,32)
            if dirty:
                pygame.draw.rect(screen,(30,145,70),save_button)
                text('Guardar desfase',580,55)
            text(f'{len(available)}/{len(lots)} lotes con fotos locales a <= {args.max_distance:g} m | {len(ids)} cámaras',10,10)
            text(f'Hover: {lots.iloc[hover].objectid:.0f}' if hover is not None else 'Click lote: dos vistas | Click cámara: reemplaza segunda vista',10,860)
            text('Rueda: zoom | Rueda pulsada: mover lotes | Derecho: pan | F: encajar | Arriba/abajo: altura | ESC: salir',10,880)
            text(f'Lote: {lots.iloc[selected].objectid:.0f}' if selected is not None else 'Selecciona un lote',780,10)
            text(f'Prisma de referencia: {height:g} m; cámara: 2.5 m; terreno plano',780,35)
            if selected is not None:
                pygame.draw.rect(screen,(30,130,75),lot_button);text('Guardar lote / descripción',1285,10)
            for k,(j,target) in enumerate(cameras):
                y=75+k*395;text(f'{k+1}: {ids[j]} | {metas[ids[j]].get("date", "")}',780,y)
                if k<len(views): screen.blit(views[k][0],(780,y+25));text(f'FOV {views[k][1]:.1f}°',780,y+365)
                else: text('Leyendo y proyectando JPG local...',780,y+60)
            if selected is not None and not cameras: text('Sin vistas no obstruidas según parcelas 2D; elige una cámara.',780,100)
            if error: text(error[:90],780,840,(255,100,100))
            if availability_future: text('Actualizando disponibilidad en segundo plano...',10,815)
            if dragging_lots: text('Moviendo lotes; las fotos se actualizan al soltar.',10,835)
            if editing:
                pygame.draw.rect(screen,(15,20,25),(170,300,1160,230))
                text(f'Lote {edit_id} - descripción (Enter: guardar; Esc: cancelar)',190,320)
                for line in range(5): text(description[line*110:(line+1)*110],190,355+line*25)
            pygame.display.flip();clock.tick(30);frames+=1
            if args.smoke_test and frames>=3:
                # Test one real view in RAM as well as the GUI, without saving.
                i=next(i for i in sorted(available) if rank(i)); chosen=choose(i)
                imgs=render(lot_polygon(i),chosen,height); assert imgs and imgs[0][0].shape==(355,710,3)
                print(f'GUI OK: {len(available)} lots, {len(ids)} cameras; local projection OK for {lots.iloc[i].objectid:g}')
                running=False
    finally:
        availability_pool.shutdown(wait=True,cancel_futures=True)
        executor.shutdown(wait=True,cancel_futures=True);pygame.quit()


if __name__=='__main__': main()
