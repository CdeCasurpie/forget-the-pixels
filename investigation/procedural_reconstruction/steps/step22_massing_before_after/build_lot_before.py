"""Before grammar for one selected lot, rendered from the same Street View angles.

Parcel shape: original cadastral polygon (EPSG:32718, translated to local m).
Fronts: street_edge_indices from steps/step21_lot_fronts/lot_fronts.json mapped
to parcel-ring order by matching unordered endpoints.
Mesh placement for renders: local mesh + original min + cadastral_offset, so the
render shares the exact eye/forward/focal of the local perspective crops
(pixel-aligned architecture comparison). Geometry itself derives from the
original cadastral shape, not hand-drawn masses.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import cv2
import geopandas as gpd
import numpy as np
from pyproj import Transformer
from shapely.affinity import translate

STEP = Path(__file__).resolve().parent
ROOT = STEP.parent.parent
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'steps/step18_theta_interface'))
sys.path.insert(0, str(ROOT / 'steps/step10_procedural_generation_test'))
from domain.theta import from_json, canonical
from pipeline.theta import reconstruct
from modeling.exporters.glb_exporter import export_glb
from modeling.validation import validate_mesh
from modeling.grammar import street_envelope
from domain.architecture import ParcelContext
from shapely.geometry import Polygon


def fingerprint(mesh):
    digest = hashlib.sha256()
    for array in (mesh.vertices, mesh.faces, mesh.corner_uv, mesh.face_materials):
        digest.update(str(array.shape).encode())
        digest.update(array.tobytes())
    digest.update(json.dumps(mesh.materials, sort_keys=True).encode())
    return digest.hexdigest()


def ring_fronts(ring, street_edges):
    fronts = []
    for ed in street_edges:
        s, e = tuple(ed['start_xy']), tuple(ed['end_xy'])
        hit = None
        for i in range(len(ring)):
            a, b = ring[i], ring[(i + 1) % len(ring)]
            if ((abs(a[0]-s[0])<1e-6 and abs(a[1]-s[1])<1e-6 and abs(b[0]-e[0])<1e-6 and abs(b[1]-e[1])<1e-6)
                    or (abs(a[0]-e[0])<1e-6 and abs(a[1]-e[1])<1e-6 and abs(b[0]-s[0])<1e-6 and abs(b[1]-s[1])<1e-6)):
                hit = i
                break
        if hit is None:
            raise ValueError(f'Street edge {ed["edge_index"]} does not match parcel ring')
        fronts.append(hit)
    return sorted(fronts)


def render_perspective(vertices, faces, face_colors, eye, forward, right, up, focal, w, h, path):
    v = vertices - eye
    z = v @ forward
    xr = v @ right
    yu = v @ up
    front = z > 0.1
    px = np.full(len(vertices), np.nan)
    py = np.full(len(vertices), np.nan)
    px[front] = w/2 + focal*xr[front]/z[front]
    py[front] = h/2 - focal*yu[front]/z[front]
    p = np.stack([px, py, z], axis=1)
    depth = np.full((h, w), np.inf)
    ids = np.full((h, w), -1, int)
    tri = vertices[faces]
    normals = np.cross(tri[:, 1]-tri[:, 0], tri[:, 2]-tri[:, 0])
    normals /= np.linalg.norm(normals, axis=1)[:, None]
    for fi, f in enumerate(faces):
        a, b, c = p[f]
        if np.isnan(a[:2]).any() or np.isnan(b[:2]).any() or np.isnan(c[:2]).any():
            continue
        x0 = max(0, int(np.floor(min(a[0], b[0], c[0]))))
        x1 = min(w-1, int(np.ceil(max(a[0], b[0], c[0]))))
        y0 = max(0, int(np.floor(min(a[1], b[1], c[1]))))
        y1 = min(h-1, int(np.ceil(max(a[1], b[1], c[1]))))
        denom = (b[1]-c[1])*(a[0]-c[0]) + (c[0]-b[0])*(a[1]-c[1])
        if abs(denom) < 1e-8 or x1 < x0 or y1 < y0:
            continue
        yy, xx = np.mgrid[y0:y1+1, x0:x1+1]
        u = ((b[1]-c[1])*(xx-c[0]) + (c[0]-b[0])*(yy-c[1]))/denom
        v = ((c[1]-a[1])*(xx-c[0]) + (a[0]-c[0])*(yy-c[1]))/denom
        ww = 1-u-v
        zz = u*a[2]+v*b[2]+ww*c[2]
        tgt = depth[y0:y1+1, x0:x1+1]
        m = (u>=-1e-7) & (v>=-1e-7) & (ww>=-1e-7) & (zz>0.1) & (zz<tgt)
        tgt[m] = zz[m]
        ids[y0:y1+1, x0:x1+1][m] = fi
    light = np.array([-1.0, -1.4, 2.5])
    light /= np.linalg.norm(light)
    diffuse = np.maximum(0, normals @ light)
    rgb = np.full((h, w, 3), 0.93)
    yy, xx = np.where(ids >= 0)
    idx = ids[yy, xx]
    rgb[yy, xx] = face_colors[idx] * (0.5+0.5*diffuse[idx])[:, None]
    img = np.uint8(np.clip(rgb, 0, 1)**(1/1.5)*255)
    cv2.imwrite(str(path), cv2.cvtColor(img, cv2.COLOR_RGB2BGR))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--lot', type=int, required=True)
    ap.add_argument('--name', required=True, help='short slug, e.g. local_comercial_bajo')
    ap.add_argument('--height', type=float, default=7.0)
    ap.add_argument('--floors', type=int, default=2)
    ap.add_argument('--family', default='mixed_use')
    ap.add_argument('--bay-count', type=int, default=1)
    ap.add_argument('--color', default='0.82,0.78,0.68',
                    help='primary_color as r,g,b in 0..1')
    ap.add_argument('--seed', type=int, default=11)
    ap.add_argument('--theta-file', type=Path, help='JSON with theta overrides for this lot')
    ap.add_argument('--include-absent', action='store_true', help='Render absent viewpoints without photo comparison')
    args = ap.parse_args()

    lots = gpd.read_file(ROOT/'data/lotes/BARRANCO_LM_geogpsperu.geojson').to_crs(32718)
    geom = lots[lots.objectid==args.lot].iloc[0].geometry
    ring = list(geom.exterior.coords)[:-1]
    lf = json.loads((ROOT/'steps/step21_lot_fronts/lot_fronts.json').read_text())[f'{args.lot}.0']
    street = [e for e in lf['edges'] if e['edge_index'] in lf['street_edge_indices']]
    fronts = ring_fronts(ring, street)
    ox, oy = min(p[0] for p in ring), min(p[1] for p in ring)
    local = [[round(x-ox,3), round(y-oy,3)] for x, y in ring]

    request = {'context': {'parcel': local, 'fronts': fronts},
               'theta': {'height_m': args.height, 'floors': args.floors, 'family': args.family,
                         'facade': {'bay_count': args.bay_count},
                         'primary_color': [float(c) for c in args.color.split(',')]},
               'nuisance': {'seed': args.seed}}
    if args.theta_file:
        request['theta'].update(json.loads(args.theta_file.read_text()))
    out = STEP/'lotes'/f'{args.lot}_{args.name}'/'before'
    out.mkdir(parents=True, exist_ok=True)
    (out/'request.json').write_text(json.dumps(request, indent=2)+'\n')
    result = reconstruct(from_json(json.dumps(request)))
    p = result.resolved.context
    validation = validate_mesh(result.mesh, Polygon(p.parcel),
                               envelope=street_envelope(ParcelContext(p.parcel, explicit_fronts=p.fronts)))
    (out/'input_theta.json').write_text(json.dumps(request, indent=2)+'\n')
    (out/'canonical_request.json').write_text(canonical(from_json(json.dumps(request)))+'\n')
    (out/'resolved_theta.json').write_text(json.dumps(json.loads(canonical(result.resolved)), indent=2)+'\n')
    export_glb(result.mesh, out/'building.glb')
    (out/'manifest.json').write_text(json.dumps({
        'lot': args.lot, 'parcel_source': 'original cadastral polygon, translated to local metres',
        'fronts_ring_order': fronts, 'street_edge_indices': lf['street_edge_indices'],
        'triangles': len(result.mesh.faces), 'validation': validation,
        'mesh_sha256': fingerprint(result.mesh)}, indent=2)+'\n')
    print(f'mesh: {len(result.mesh.faces)} triangles -> {out}')

    # Same-angle perspective renders for every present view.
    offset = json.loads((ROOT/'data/cadastral_offset.json').read_text())
    assert offset['crs'] == 'EPSG:32718'
    folder = STEP/'edificios_a_probar'/str(args.lot)
    views = json.loads((folder/'views.json').read_text())
    nominal = views['nominal_roof_height_m']
    poses = json.loads((ROOT/'data/poses_barranco/metadata.json').read_text())['panoramas']
    project = Transformer.from_crs(4326, 32718, always_xy=True)
    seg = json.loads((folder/'segmentation.json').read_text())['images']
    shifted = translate(geom, xoff=offset['east_m'], yoff=offset['north_m'])
    target = np.r_[shifted.centroid.coords[0], nominal/2]
    world_verts = result.mesh.vertices + np.array([ox+offset['east_m'], oy+offset['north_m'], 0.])
    face_colors = np.array([m['color'] for m in result.mesh.materials])[result.mesh.face_materials]
    W, H = 1280, 900
    for v in views['views']:
        if seg.get(v['camera_id'], {}).get('status') != 'present' and not args.include_absent:
            continue
        meta = poses[v['camera_id']]
        cx, cy = project.transform(meta['lon'], meta['lat'])
        eye = np.r_[cx, cy, 2.5]
        fw = target-eye; fw /= np.linalg.norm(fw)
        right = np.cross(fw, [0.,0.,1.]); right /= np.linalg.norm(right)
        up = np.cross(right, fw)
        focal = (W/2)/np.tan(np.deg2rad(v['horizontal_fov_deg'])/2)
        render_perspective(world_verts, result.mesh.faces, face_colors,
                           eye, fw, right, up, focal, W, H, out/f'render_{v["camera_id"]}.jpg')
        print(f'render_{v["camera_id"]}.jpg fov={v["horizontal_fov_deg"]}', flush=True)
        photo = cv2.imread(str(folder/v['file']))
        rend = cv2.imread(str(out/f'render_{v["camera_id"]}.jpg'))
        if photo is None:
            continue
        combo = cv2.hconcat([photo, rend])
        bar = cv2.copyMakeBorder(combo, 40, 0, 0, 0, cv2.BORDER_CONSTANT, value=(24,28,34))
        cv2.putText(bar, 'FOTO STREET VIEW', (30,28), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (230,230,230), 2)
        cv2.putText(bar, 'BEFORE GRAMATICA ACTUAL', (W+30,28), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (230,230,230), 2)
        cv2.imwrite(str(out/f'compare_{v["camera_id"]}.jpg'), bar, [cv2.IMWRITE_JPEG_QUALITY, 90])


if __name__ == '__main__':
    main()
