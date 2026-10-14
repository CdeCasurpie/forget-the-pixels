"""Export five local Street View perspective crops for each selected parcel.

The 15 m height is framing guidance only: no cadastral overlay or inferred mass
is drawn. All camera poses and panoramas are read from local data.
"""
import argparse
import json
from pathlib import Path
import sys

import cv2
import geopandas as gpd
import numpy as np
from pyproj import Transformer
from scipy.spatial import cKDTree
from shapely.affinity import translate
from shapely.geometry import Point

STEP = Path(__file__).resolve().parent
ROOT = STEP.parent.parent
sys.path.insert(0, str(ROOT/'steps/step20_sfm_esferico'))
from geometry_stage4 import camera_to_enu


def perspective(panorama, meta, camera_xy, footprint, height, width=1280, image_height=900):
    """Project pinhole rays in ENU into the panorama's oriented equirectangular image."""
    # Use every parcel corner at both ground and nominal roof for full framing.
    vertices = np.asarray(footprint.exterior.coords)[:-1, :2]
    camera = np.r_[camera_xy, 2.5]
    corners = np.vstack([np.column_stack([vertices, np.zeros(len(vertices))]),
                         np.column_stack([vertices, np.full(len(vertices), height)])])
    target = np.r_[footprint.centroid.coords[0], height/2]
    forward = target-camera
    forward /= np.linalg.norm(forward)
    right = np.cross(forward, [0.,0.,1.]); right /= np.linalg.norm(right)
    up = np.cross(right,forward)
    vectors = corners-camera
    z = vectors@forward
    if np.any(z<=0): return None
    horizontal = np.abs(vectors@right/z)
    vertical = np.abs(vectors@up/z)
    # Constrain angular coverage in BOTH image directions with a 10% margin.
    needed = max(horizontal.max(), vertical.max()*width/image_height)*1.1
    hfov = 2*np.arctan(needed)
    if hfov >= np.deg2rad(150): return None
    focal = width/(2*needed)
    x = (np.arange(width,dtype=np.float32)+.5-width/2)/focal
    y = (image_height/2-(np.arange(image_height,dtype=np.float32)+.5))/focal
    xx,yy = np.meshgrid(x,y)
    world = forward+xx[...,None]*right+yy[...,None]*up
    rotation = camera_to_enu(meta['heading_deg'], meta['pitch_deg'], meta['roll_deg'])
    local = world@rotation
    ph,pw = panorama.shape[:2]
    source_x = ((np.arctan2(local[...,0],local[...,2])+np.pi)*pw/(2*np.pi)-.5)%pw
    source_y = (np.pi/2-np.arctan2(-local[...,1],np.hypot(local[...,0],local[...,2])))*ph/np.pi-.5
    crop = cv2.remap(panorama,source_x.astype('float32'),
                     np.clip(source_y,0,ph-1).astype('float32'),
                     cv2.INTER_LINEAR,borderMode=cv2.BORDER_WRAP)
    return crop, float(np.degrees(hfov)), float(np.degrees(2*np.arctan(image_height/(2*focal))))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--height',type=float,default=15.,help='Nominal roof height in metres for framing')
    args=parser.parse_args()
    if args.height<=0: parser.error('--height must be positive')
    selected=json.loads((ROOT/'steps/step21_lot_fronts/seleccion/lotes.json').read_text())['lots']
    offset_data=json.loads((ROOT/'data/cadastral_offset.json').read_text())
    assert offset_data['crs']=='EPSG:32718'
    offset=(offset_data['east_m'],offset_data['north_m'])
    lots=gpd.read_file(ROOT/'data/lotes/BARRANCO_LM_geogpsperu.geojson').to_crs(32718)
    lookup={int(row.objectid):geometry for row,geometry in zip(lots.itertuples(),lots.geometry)}
    raw=json.loads((ROOT/'data/poses_barranco/metadata.json').read_text())['panoramas']
    photos=ROOT/'data/fotos_barranco'
    metas={pid:m for pid,m in raw.items() if (photos/f'{pid}.jpg').is_file()
           and all(m.get(k) is not None for k in ('lat','lon','heading_deg','pitch_deg','roll_deg'))}
    ids=list(metas)
    transformer=Transformer.from_crs(4326,32718,always_xy=True)
    xy=np.asarray([transformer.transform(metas[p]['lon'],metas[p]['lat']) for p in ids])
    tree=cKDTree(xy)
    base=STEP/'edificios_a_probar'
    for item in selected:
        lot_id=int(item['objectid'])
        footprint=translate(lookup[lot_id],xoff=offset[0],yoff=offset[1])
        center=np.asarray(footprint.centroid.coords[0])
        radius=max(np.linalg.norm(np.asarray(footprint.exterior.coords)-center,axis=1))
        # Query nearby cameras, then sort by true distance to the parcel boundary.
        nearby=tree.query_ball_point(center,radius+100)
        nearest=sorted(((footprint.distance(Point(xy[j])),j) for j in nearby),key=lambda v:v[0])
        records=[]
        folder=base/str(lot_id)
        for distance,j in nearest:
            if len(records)>=5: break
            if distance<1.5: continue  # Camera inside/on parcel cannot show the whole building.
            pid=ids[j]
            panorama=cv2.imread(str(photos/f'{pid}.jpg'))
            if panorama is None: continue
            result=perspective(panorama,metas[pid],xy[j],footprint,args.height)
            if result is None: continue
            image,hfov,vfov=result
            folder.mkdir(parents=True,exist_ok=True)
            filename=f'{len(records)+1:02d}_{pid}.jpg'
            if not cv2.imwrite(str(folder/filename),image,[cv2.IMWRITE_JPEG_QUALITY,92]):
                raise OSError(f'Unable to write {folder/filename}')
            records.append({'file':filename,'camera_id':pid,'distance_to_lot_m':round(float(distance),2),
                            'horizontal_fov_deg':round(hfov,2),'vertical_fov_deg':round(vfov,2)})
        if len(records)!=5: raise RuntimeError(f'Lot {lot_id}: only {len(records)} usable local cameras')
        (folder/'views.json').write_text(json.dumps({
            'objectid':lot_id,'description':item.get('description',''),
            'nominal_roof_height_m':args.height,'offset_east_north_m':offset,
            'projection':'rectilinear perspective (pinhole), no overlay',
            'views':records},indent=2,ensure_ascii=False)+'\n')
        print(f'{lot_id}: '+', '.join(r['camera_id'] for r in records),flush=True)
    print(f'Done: {len(selected)} lots, {len(selected)*5} local perspective images in {base}')


if __name__=='__main__': main()
