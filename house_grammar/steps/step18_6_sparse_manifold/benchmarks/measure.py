"""Frozen-input geometry benchmark; run before and after materializer changes."""
from pathlib import Path
import argparse
from collections import Counter
from dataclasses import asdict
import csv
import hashlib
import json
import resource
import struct
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
STEP = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'src'), str(ROOT/'steps/step10_procedural_generation_test')]
from domain.theta import from_json, canonical, ReconstructionRequest, ReconstructionContext
from modeling.theta import resolve_theta, generate_resolved
from modeling.exporters.glb_exporter import export_glb
from modeling.validation import analyze_topology, validate_mesh
from modeling.grammar import street_envelope
from domain.architecture import ParcelContext
from shapely.geometry import Polygon


def prepare():
    from scripts.step3_generate_full_block import choose_theta, select_fronts
    from scripts.step1_select_block import load_lots, select_block_lots, clean_geometry
    from spatial.street_fronts import annotate_street_fronts
    from shapely.geometry.polygon import orient
    target=STEP/'benchmarks'/'inputs'; target.mkdir(parents=True,exist_ok=True)
    for p in sorted((ROOT/'steps/step18_theta_interface/examples').glob('*.json')):
        (target/p.name).write_text(p.read_text())
    centre, selected, seed_index=select_block_lots(load_lots(),seed=123,surrounding_m=20.)
    origin=selected.geometry.union_all().centroid
    selected.geometry=selected.translate(xoff=-origin.x,yoff=-origin.y).apply(clean_geometry)
    selected=annotate_street_fronts(selected)
    seed_point=selected.loc[seed_index].geometry.centroid
    centre_polygon=selected.loc[sorted(centre)].geometry.union_all()
    order=sorted(selected.index,key=lambda i:(i not in centre,selected.loc[i].geometry.centroid.distance(seed_point if i in centre else centre_polygon),str(i)))
    records=[]
    for index in order[:50]:
        row=selected.loc[index]; fronts,source=select_fronts(row)
        poly=orient(row.geometry,sign=1.)
        theta,xi=choose_theta(123,index)
        request=ReconstructionRequest(context=ReconstructionContext(parcel=tuple(poly.exterior.coords),fronts=fronts),theta=theta,nuisance=xi)
        name=f'lot_{index}'
        (target/(name+'.json')).write_text(json.dumps(asdict(request),indent=2)+'\n')
        records.append(dict(name=name,area=poly.area,edges=len(poly.exterior.coords)-1,front_source=source))
    byarea=sorted(records,key=lambda r:r['area'])
    costs=list(csv.DictReader((ROOT/'outputs/cuadras_completas/timings_per_house.csv').open()))
    costs={f"lot_{r['lot_index']}":int(r['faces']) for r in costs if r['status']=='generated'}
    chosen=[byarea[0]['name'],byarea[len(byarea)//2]['name'],byarea[-1]['name'],max(records,key=lambda r:r['edges'])['name'],max(records,key=lambda r:costs.get(r['name'],0))['name']]
    chosen=list(dict.fromkeys(chosen))
    for record in reversed(byarea):
        if len(chosen)==5: break
        if record['name'] not in chosen: chosen.append(record['name'])
    manifest=dict(individual=[p.stem for p in sorted(target.glob('0*.json'))]+chosen,block=[r['name'] for r in records],parcels=records)
    (STEP/'benchmarks/cases.json').write_text(json.dumps(manifest,indent=2)+'\n')


def glb_counts(path):
    with path.open('rb') as f:
        header=f.read(20); n=struct.unpack_from('<I',header,12)[0]; tree=json.loads(f.read(n))
    return dict(glb_bytes=path.stat().st_size,nodes=len(tree['nodes']),meshes=len(tree['meshes']),primitives=sum(len(m['primitives']) for m in tree['meshes']))


def run(phase,block=0,mode='authoring',detail=None,renders=False):
    from dataclasses import replace
    from scripts.glb_incremental import append_glb
    manifest=json.loads((STEP/'benchmarks/cases.json').read_text())
    names=manifest['block'][:block] if block else manifest['individual']
    out=STEP/'outputs'/phase/(f'block{block}' if block else 'individual'); out.mkdir(parents=True,exist_ok=True)
    rows=[]; semantics=[]; started=time.perf_counter()
    for i,name in enumerate(names):
        request=from_json((STEP/'benchmarks/inputs'/f'{name}.json').read_text())
        if detail is not None: request=replace(request,config=replace(request.config,detail=detail))
        start=time.perf_counter()
        try:
            resolved=resolve_theta(request.context,request.theta)
        except ValueError as error:
            if 'Openings cannot fit' not in str(error): raise
            from domain.theta import FacadeControls
            request=replace(request,theta=replace(request.theta,facade=FacadeControls(bay_count=1,window_ratio=.5,window_height_m=1.1,sill_m=.65,balconies=False)))
            try:
                resolved=resolve_theta(request.context,request.theta)
            except ValueError as error:
                if 'Openings cannot fit' not in str(error): raise
                request=replace(request,theta=replace(request.theta,facade=FacadeControls(mode='explicit',openings=())))
                resolved=resolve_theta(request.context,request.theta)
        mesh=generate_resolved(resolved,request.nuisance,request.config); elapsed=time.perf_counter()-start
        row=dict(case=name,vertices=len(mesh.vertices),triangles=len(mesh.faces),components=len(mesh.components),parts=len(mesh.parts),generation_s=elapsed)
        path=out/f'{name}.glb'; start=time.perf_counter()
        kwargs={} if mode=='authoring' else dict(mode=mode)
        export_glb(mesh,path,library=False,**kwargs); row['export_s']=time.perf_counter()-start
        row.update(glb_counts(path)); row['peak_rss_mb']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024
        row['architecture_sha256']=hashlib.sha256(canonical(resolved).encode()).hexdigest()
        row['bounds']=json.dumps([mesh.vertices.min(0).tolist(),mesh.vertices.max(0).tolist()])
        if not block:
            p=request.context
            try:
                valid=validate_mesh(mesh,Polygon(p.parcel),envelope=street_envelope(ParcelContext(p.parcel,explicit_fronts=p.fronts)))
            except ValueError as error:
                valid={'error':str(error)}
            row['validation_error']=valid.get('error','')
            topo=analyze_topology(mesh)
            row['topology_violations']=len(topo['violations'])
            (out/f'{name}.validation.json').write_text(json.dumps(dict(geometry=valid,topology=topo),indent=2))
            counts=Counter(); parts=Counter()
            for part in mesh.parts:
                counts[part['name']]+=part['face_count']; parts[part['name']]+=1
            semantics.extend(dict(case=name,semantic=k,triangles=v,components=parts[k]) for k,v in counts.most_common())
            if renders:
                from render import render
                render_mesh=mesh
                if phase!='baseline':
                    import numpy as np
                    baseline={r['case']:r for r in csv.DictReader((STEP/'reports/baseline.csv').open())}
                    # Freeze the exact pre-change framing, including the light's
                    # shadow-map frame. Unreferenced extrema emit no geometry.
                    render_mesh=replace(mesh,vertices=np.vstack((mesh.vertices,np.asarray(json.loads(baseline[name]['bounds'])))))
                for view,direction in [('iso',(1,-1,1)),('street',(.15,-1,.18))]:
                    destination=out/f'{name}_{view}.png'
                    if not destination.exists() or phase!='baseline':
                        render(render_mesh,destination,direction=direction,size=384,clay=False)
        else:
            p=request.context
            valid=validate_mesh(mesh,Polygon(p.parcel),envelope=street_envelope(ParcelContext(p.parcel,explicit_fronts=p.fronts)))
            topology=analyze_topology(mesh)
            row['topology_violations']=len(topology['violations'])
            if topology['violations']:
                (out/f'{name}.violations.json').write_text(json.dumps(topology['violations'],indent=2))
                raise ValueError(f'{name}: non-manifold source components')
            start=time.perf_counter(); cumulative=out/'block.glb'; temporary=out/'block.tmp.glb'
            append_glb(cumulative if i else None,path,temporary,lot_id=name); temporary.replace(cumulative)
            row['append_s']=time.perf_counter()-start
        rows.append(row)
        (out/'progress.json').write_text(json.dumps(rows,indent=2))
        print(phase,name,row['triangles'],row.get('topology_violations',''),flush=True)
    reports=STEP/'reports'; reports.mkdir(exist_ok=True)
    stem=f'{phase}_block{block}_{mode}' if block else phase
    for suffix,data in [('',rows),('_semantics',semantics)]:
        if data:
            with (reports/f'{stem}{suffix}.csv').open('w',newline='') as f:
                writer=csv.DictWriter(f,fieldnames=list(data[0])); writer.writeheader(); writer.writerows(data)
    summary=dict(seconds=time.perf_counter()-started,triangles=sum(r['triangles'] for r in rows),peak_rss_mb=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)
    if block: summary.update(glb_counts(out/'block.glb'))
    (reports/f'{stem}.json').write_text(json.dumps(summary,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--prepare',action='store_true'); parser.add_argument('--phase',default='baseline'); parser.add_argument('--block',type=int,default=0); parser.add_argument('--mode',default='authoring'); parser.add_argument('--detail',type=int); parser.add_argument('--renders',action='store_true')
    args=parser.parse_args()
    if args.prepare: prepare()
    else: run(args.phase,args.block,args.mode,args.detail,args.renders)
