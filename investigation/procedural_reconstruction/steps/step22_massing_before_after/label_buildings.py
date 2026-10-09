"""Interactive graph-segment painter for local perspective crops (no downloads).

Left-drag adds touched regions; right-drag removes them. Wheel resizes brush.
Space/Next saves and
advances. An empty selection deletes that derived JPG and records absence.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sys

import cv2
import geopandas as gpd
import numpy as np
from pyproj import Transformer
from skimage.segmentation import felzenszwalb
from shapely.affinity import translate

STEP=Path(__file__).resolve().parent
ROOT=STEP.parent.parent
sys.path.insert(0,str(ROOT/'steps/step20_sfm_esferico/.dependencies'))
import pygame

DATA=STEP/'edificios_a_probar'


def segments(image):
    """Segment at displayed resolution, preserving exact pixel ownership."""
    rgb=cv2.cvtColor(image,cv2.COLOR_BGR2RGB)
    labels=felzenszwalb(rgb,scale=160,sigma=.8,min_size=65).astype(np.int32)
    return labels, int(labels.max()+1)


def touched_labels(labels, x, y, radius):
    """All graph regions intersecting a circular brush, including at its edges."""
    h,w=labels.shape
    left,right=max(0,x-radius),min(w,x+radius+1)
    top,bottom=max(0,y-radius),min(h,y+radius+1)
    if left>=right or top>=bottom:return np.empty(0,dtype=np.int32)
    yy,xx=np.ogrid[top:bottom,left:right]
    return np.unique(labels[top:bottom,left:right][(xx-x)**2+(yy-y)**2<=radius**2])


def polygons_from_mask(mask, original_size):
    """Return simplified exterior rings and their holes in original JPG pixels."""
    ow,oh=original_size
    full=cv2.resize(mask.astype('uint8'),(ow,oh),interpolation=cv2.INTER_NEAREST)
    contours,hierarchy=cv2.findContours(full,cv2.RETR_CCOMP,cv2.CHAIN_APPROX_SIMPLE)
    if hierarchy is None:return []
    rings=[]
    for i,contour in enumerate(contours):
        if cv2.contourArea(contour)<12: continue
        approx=cv2.approxPolyDP(contour,epsilon=2.0,closed=True)[:,0,:].tolist()
        if len(approx)<3:continue
        rings.append((i,approx,int(hierarchy[0,i,3])))
    outer={i:{'exterior':p,'holes':[]} for i,p,parent in rings if parent==-1}
    for i,p,parent in rings:
        if parent in outer:outer[parent]['holes'].append(p)
    return list(outer.values())


def box_lines(polygon, camera_xy, nominal_height, hfov, image_size):
    """Reproduce the crop's pinhole orientation for a visual-only lot prism."""
    w,h=image_size
    vertices=np.asarray(polygon.exterior.coords)[:-1,:2]
    eye=np.r_[camera_xy,2.5]
    target=np.r_[polygon.centroid.coords[0],nominal_height/2]
    forward=target-eye;forward/=np.linalg.norm(forward)
    right=np.cross(forward,[0.,0.,1.]);right/=np.linalg.norm(right)
    up=np.cross(right,forward)
    f=w/(2*np.tan(np.deg2rad(hfov)/2))
    def point(xy,z):
        ray=np.r_[xy,z]-eye
        depth=ray@forward
        if depth<=0:return None
        return (int(w/2+f*(ray@right)/depth),int(h/2-f*(ray@up)/depth))
    result=[]
    for a,b in zip(vertices,np.roll(vertices,-1,axis=0)):
        for za,zb in ((0,0),(nominal_height,nominal_height),(0,nominal_height)):
            p,q=point(a,za),point(b if za==zb else a,zb)
            if p and q:result.append((p,q))
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--smoke-test',action='store_true',help='Load first photo and exit without writes')
    args=parser.parse_args()
    folders=sorted(p for p in DATA.iterdir() if p.is_dir() and (p/'views.json').exists())
    if not folders:raise ValueError(f'No lot folders under {DATA}')
    jobs=[(folder,view) for folder in folders
          for view in json.loads((folder/'views.json').read_text())['views']]
    lots=gpd.read_file(ROOT/'data/lotes/BARRANCO_LM_geogpsperu.geojson').to_crs(32718)
    geometries={int(k):g for k,g in zip(lots.objectid,lots.geometry)}
    poses=json.loads((ROOT/'data/poses_barranco/metadata.json').read_text())['panoramas']
    offset=json.loads((ROOT/'data/cadastral_offset.json').read_text())
    if offset['crs']!='EPSG:32718':raise ValueError('Unexpected offset CRS')
    project=Transformer.from_crs(4326,32718,always_xy=True)
    pygame.init()
    screen=pygame.display.set_mode((1460,930),pygame.RESIZABLE)
    pygame.display.set_caption('Step22 | Etiquetar edificios')
    font=pygame.font.SysFont('sans',20)
    small=pygame.font.SysFont('sans',16)
    pool=ThreadPoolExecutor(max_workers=1)
    index=0;pending=None;state=None;error='';show_box=True;running=True
    brush_radius=24;last_paint=None

    def load(n):
        folder,view=jobs[n]
        source=folder/view['file']
        if not source.exists():return {'missing':True}
        original=cv2.imread(str(source))
        if original is None:raise ValueError(f'Cannot read {source}')
        ow,oh=original.shape[1],original.shape[0]
        max_w,max_h=1200,820
        factor=min(max_w/ow,max_h/oh,1.)
        dw,dh=round(ow*factor),round(oh*factor)
        image=cv2.resize(original,(dw,dh),interpolation=cv2.INTER_AREA)
        labels,count=segments(image)
        old=folder/'segmentation.json'
        entries=json.loads(old.read_text()).get('images',{}) if old.exists() else {}
        saved=entries.get(view['camera_id'],{})
        selected=np.zeros(count,dtype=bool)
        # Restore using saved polygons, even if graph segments changed between runs.
        if saved.get('status')=='present':
            mask_path=folder/saved.get('mask_file','') if saved.get('mask_file') else None
            full_mask=cv2.imread(str(mask_path),cv2.IMREAD_GRAYSCALE) if mask_path else None
            if full_mask is not None and full_mask.shape==(oh,ow):
                old_mask=cv2.resize(full_mask,(dw,dh),interpolation=cv2.INTER_NEAREST)>127
            else:
                old_mask=np.zeros((dh,dw),dtype=np.uint8)
                for poly in saved.get('polygons',[]):
                    exterior=np.rint(np.array(poly['exterior'])*[dw/ow,dh/oh]).astype(np.int32)
                    cv2.fillPoly(old_mask,[exterior],1)
                    for hole in poly.get('holes',[]):
                        cv2.fillPoly(old_mask,[np.rint(np.array(hole)*[dw/ow,dh/oh]).astype(np.int32)],0)
            counts=np.bincount(labels.ravel(),weights=old_mask.ravel(),minlength=count)
            sizes=np.bincount(labels.ravel(),minlength=count)
            selected=counts>sizes*.5
        lot_id=int(folder.name)
        polygon=translate(geometries[lot_id],xoff=offset['east_m'],yoff=offset['north_m'])
        meta=poses[view['camera_id']]
        camera_xy=project.transform(meta['lon'],meta['lat'])
        nominal=json.loads((folder/'views.json').read_text())['nominal_roof_height_m']
        lines=box_lines(polygon,camera_xy,nominal,view['horizontal_fov_deg'],(dw,dh))
        return {'image':cv2.cvtColor(image,cv2.COLOR_BGR2RGB),'labels':labels,
                'selected':selected,'original_size':(ow,oh),'lines':lines,
                'camera_xy':camera_xy,'count':count}

    def request(n):
        nonlocal index,pending,state,error,last_paint
        index=n;state=None;error=''
        last_paint=None
        pending=pool.submit(load,n)

    def save():
        nonlocal error
        folder,view=jobs[index]
        if not state or state.get('missing'):return
        mask=state['selected'][state['labels']]
        polygons=polygons_from_mask(mask,state['original_size'])
        present=bool(np.any(mask))
        ow,oh=state['original_size']
        mask_file=f'{view["camera_id"]}_mask.png'
        mask_path=folder/mask_file
        full_mask=cv2.resize(mask.astype('uint8')*255,(ow,oh),interpolation=cv2.INTER_NEAREST)
        if present:
            if not cv2.imwrite(str(mask_path),full_mask):
                raise OSError(f'Cannot write {mask_path}')
        else:
            mask_path.unlink(missing_ok=True)
        path=folder/'segmentation.json'
        data=json.loads(path.read_text()) if path.exists() else {'objectid':int(folder.name),'images':{}}
        data['images'][view['camera_id']]={
            'file':view['file'],'status':'present' if present else 'absent',
            'image_size_px':list(state['original_size']),
            'mask_file':mask_file if present else None,
            'polygons':polygons,
            'note':'Binary PNG (white=building, black=background); simplified polygons in original pixels. No cadastral overlay.'}
        temp=path.with_suffix('.tmp')
        temp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
        temp.replace(path)
        if not present:(folder/view['file']).unlink(missing_ok=True)
        error='Guardado: '+('máscara del edificio' if present else 'ausente; JPG eliminado')

    def draw_text(msg,pos,color=(230,230,230),f=None):
        screen.blit((f or font).render(str(msg),True,color),pos)

    request(0)
    try:
        while running:
            for event in pygame.event.get():
                if event.type==pygame.QUIT:running=False
                elif event.type==pygame.MOUSEWHEEL:
                    brush_radius=int(np.clip(brush_radius+event.y*4,4,120))
                elif event.type==pygame.MOUSEBUTTONUP and event.button in (1,3):
                    last_paint=None
                elif event.type==pygame.KEYDOWN:
                    if event.key==pygame.K_ESCAPE:running=False
                    elif event.key==pygame.K_b:show_box=not show_box
                    elif event.key==pygame.K_s and state and not state.get('missing'):save()
                    elif event.key in (pygame.K_SPACE,pygame.K_RIGHT) and pending is None:
                        if state and not state.get('missing'):save()
                        if index+1<len(jobs):request(index+1)
                    elif event.key==pygame.K_LEFT and pending is None and index>0:
                        if state and not state.get('missing'):save()
                        request(index-1)
                if event.type in (pygame.MOUSEMOTION,pygame.MOUSEBUTTONDOWN) and state and not state.get('missing'):
                    buttons=pygame.mouse.get_pressed(3)
                    button=event.button if event.type==pygame.MOUSEBUTTONDOWN else (1 if buttons[0] else 3 if buttons[2] else 0)
                    if button not in (1,3):
                        last_paint=None
                        continue
                    x,y=event.pos[0]-20,event.pos[1]-75
                    if last_paint and last_paint[2]==button:
                        px,py,_=last_paint
                        steps=max(1,int(np.hypot(x-px,y-py)/(max(2,brush_radius/2))))
                    else: px,py,steps=x,y,1
                    for t in range(1,steps+1):
                        cx=round(px+(x-px)*t/steps)
                        cy=round(py+(y-py)*t/steps)
                        touched=touched_labels(state['labels'],cx,cy,brush_radius)
                        if len(touched) and np.any(state['selected'][touched]!=(button==1)):
                            state['selected'][touched]=button==1
                            state['overlay_dirty']=True
                    last_paint=(x,y,button)
            if pending and pending.done():
                try:
                    state=pending.result()
                    if not state.get('missing'):
                        im=state['image'];h,w=im.shape[:2]
                        state['surface']=pygame.image.frombuffer(im.tobytes(),(w,h),'RGB')
                        state['overlay_dirty']=True
                        if args.smoke_test:
                            assert state['labels'].shape==(h,w)
                            print(f'OK: {len(jobs)} images; first lot {jobs[index][0].name}; {state["count"]} graph segments; guide {len(state["lines"])} lines')
                            running=False
                except Exception as exc:error=str(exc);state={'missing':True}
                pending=None
            screen.fill((24,28,34))
            folder,view=jobs[index]
            draw_text(f'Lote {folder.name}  |  Foto {index+1}/{len(jobs)}  |  Cámara {view["camera_id"]}',(20,12))
            draw_text('Izquierdo: añadir (arrastrar)   Derecho: quitar   Espacio/→: guardar y seguir   ←: anterior   S: guardar   B: caja   Esc: salir',
                      (20,42),f=small)
            if pending:draw_text('Segmentando imagen en segundo plano...', (30,120))
            elif state and state.get('missing'):draw_text('JPG ausente: esta vista fue descartada.',(30,120))
            elif state:
                labels=state['labels'];chosen=state['selected']
                if state.pop('overlay_dirty',False):
                    colored=np.zeros((*labels.shape,4),dtype=np.uint8)
                    colored[chosen[labels]]=[20,245,90,105]
                    state['overlay']=pygame.image.frombuffer(colored.tobytes(),(labels.shape[1],labels.shape[0]),'RGBA')
                screen.blit(state['surface'],(20,75))
                if show_box:
                    for a,b in state['lines']:
                        pygame.draw.line(screen,(255,200,40),(a[0]+20,a[1]+75),(b[0]+20,b[1]+75),2)
                screen.blit(state['overlay'],(20,75))
                mx,my=pygame.mouse.get_pos()
                bx,by=mx-20,my-75
                dh,dw=labels.shape
                if 0<=bx<dw and 0<=by<dh:
                    prospective=touched_labels(labels,bx,by,brush_radius)
                    key=tuple(prospective.tolist())
                    if state.get('preview_key')!=key:
                        preview=np.zeros((*labels.shape,4),dtype=np.uint8)
                        preview[np.isin(labels,prospective)]=[55,160,255,102]  # 40% opacity
                        state['preview']=pygame.image.frombuffer(preview.tobytes(),(dw,dh),'RGBA')
                        state['preview_key']=key
                    screen.blit(state['preview'],(20,75))
                    pygame.draw.circle(screen,(255,255,255),(mx,my),brush_radius,2)
                    pygame.draw.circle(screen,(20,35,45),(mx,my),brush_radius-2,1)
                draw_text(f'Regiones: {int(chosen.sum())}/{len(chosen)}', (1230,100),f=small)
                draw_text(f'Pincel: {brush_radius}px', (1230,75),f=small)
                draw_text('Amarillo: guía catastral', (1230,135),f=small)
                draw_text('Verde: etiqueta guardable', (1230,165),f=small)
                draw_text('Azul: próximo trazo (40%)', (1230,190),f=small)
                draw_text('VACÍO + avanzar:',(1230,220),(255,180,100),small)
                draw_text('borra este JPG', (1230,245),(255,180,100),small)
                draw_text('y marca ausente.', (1230,270),(255,180,100),small)
            if error:draw_text(error[:120],(20,900),(255,190,95),small)
            pygame.display.flip()
            pygame.time.Clock().tick(30)
    finally:
        pool.shutdown(wait=True,cancel_futures=True)
        pygame.quit()


if __name__=='__main__':main()
