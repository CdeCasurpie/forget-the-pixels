"""Generate one candidate: JSON -> resolved architecture -> GLB + diagnostic views."""
from __future__ import annotations
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
sys.path.insert(0,str(ROOT/'steps'/'step10_procedural_generation_test'))
from domain.theta import from_json, canonical
from pipeline.theta import reconstruct
from modeling.exporters.glb_exporter import export_glb
from modeling.validation import validate_mesh
from modeling.grammar import street_envelope
from domain.architecture import ParcelContext
from shapely.geometry import Polygon
from render import render


def fingerprint(mesh):
    digest=hashlib.sha256()
    for array in (mesh.vertices,mesh.faces,mesh.corner_uv,mesh.face_materials):
        digest.update(str(array.shape).encode())
        digest.update(array.tobytes())
    digest.update(json.dumps(mesh.materials,sort_keys=True).encode())
    return digest.hexdigest()


def run(source, output, size=512, no_render=False):
    source,output=Path(source).resolve(),Path(output).resolve()
    request=from_json(source.read_text())
    result=reconstruct(request)
    p=result.resolved.context
    validation=validate_mesh(result.mesh,Polygon(p.parcel),envelope=street_envelope(ParcelContext(p.parcel,explicit_fronts=p.fronts)))
    output.mkdir(parents=True,exist_ok=True)
    # Requested source is preserved byte-for-byte; normalized form is separate.
    (output/'input_theta.json').write_text(source.read_text())
    (output/'canonical_request.json').write_text(canonical(request)+'\n')
    (output/'resolved_theta.json').write_text(json.dumps(json.loads(canonical(result.resolved)),indent=2)+'\n')
    export_glb(result.mesh,output/'building.glb')
    if not no_render:
        render(result.mesh,output/'iso.png',direction=(1,-1,1),size=size,clay=False)
        render(result.mesh,output/'street.png',direction=(.15,-1,.18),size=size,clay=False)
    manifest={
        'theta_schema_version':request.theta.schema_version,
        'nuisance_seed':request.nuisance.seed,
        'grammar_reference':request.config.grammar_reference,
        'implementation':request.config.implementation,
        'source_example':str(source),
        'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'mesh_sha256':fingerprint(result.mesh),
        'vertices':len(result.mesh.vertices),'triangles':len(result.mesh.faces),
        'renders':'diagnostic orthographic mesh views; not PBR/photo evaluation',
        'completed':result.resolved.completed,
        'validation':validation,
        'files':['input_theta.json','canonical_request.json','resolved_theta.json','building.glb'] + ([] if no_render else ['iso.png','street.png'])}
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(f"{source.name}: {manifest['triangles']} triangles -> {output}",flush=True)
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--theta',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--size',type=int,default=512)
    parser.add_argument('--no-render',action='store_true')
    args=parser.parse_args()
    run(args.theta,args.output,args.size,args.no_render)
