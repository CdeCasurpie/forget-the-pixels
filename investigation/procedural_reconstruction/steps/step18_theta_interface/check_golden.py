"""Compare frozen and working-tree legacy meshes in isolated processes.

Never regenerates into golden reference folders. Snapshot is extracted to a
temporary directory. No checkout, index modification or tag update.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import tarfile
import tempfile

ROOT=Path(__file__).resolve().parents[2]
REPO=ROOT.parents[1]
REL=ROOT.relative_to(REPO)


def worker(root):
    sys.path.insert(0,str(root/'src'))
    sys.path.insert(0,str(root/'steps'/'step10_procedural_generation_test'))
    module=runpy.run_path(str(root/'scripts'/'golden_v1'/'generate_golden_v1.py'))
    result={}
    for job in module['pick_jobs'](3,20260923):
        spec=module['build'](module['LOTS'][job['lot_name']],job['family'],job['seed'],job['setback'])
        mesh=module['generate_v4_mesh'](spec,detail=2)
        digest=hashlib.sha256()
        for a in (mesh.vertices,mesh.faces,mesh.corner_uv,mesh.face_materials):
            digest.update(str(a.shape).encode()); digest.update(a.tobytes())
        digest.update(json.dumps(mesh.materials,sort_keys=True).encode())
        digest.update(json.dumps(mesh.components,sort_keys=True).encode())
        result[job['label']]={'vertices':len(mesh.vertices),'triangles':len(mesh.faces),'sha256':digest.hexdigest()}
    print(json.dumps(result))


def check():
    tag=subprocess.check_output(['git','rev-parse','grammar-v1.0^{commit}'],cwd=REPO,text=True).strip()
    archive=subprocess.check_output(['git','archive','grammar-v1.0',str(REL/'src'),str(REL/'scripts'/'golden_v1'),str(REL/'steps'/'step10_procedural_generation_test')],cwd=REPO)
    env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'}
    with tempfile.TemporaryDirectory(prefix='step18-golden-') as temp:
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            tar.extractall(temp,filter='data')
        frozen=json.loads(subprocess.check_output([sys.executable,__file__,'--worker',str(Path(temp)/REL)],env=env,text=True))
        current=json.loads(subprocess.check_output([sys.executable,__file__,'--worker',str(ROOT)],env=env,text=True))
    report={'tag_commit':tag,'frozen':frozen,'current':current,'exact_geometry_uv_material_component_match':frozen==current}
    output=Path(__file__).parent/'outputs'/'golden_check.json'
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    if frozen!=current:
        raise SystemExit('Legacy differs from freeze. Inspect preexisting edits separately; never overwrite reference.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker',type=Path)
    args=parser.parse_args()
    worker(args.worker) if args.worker else check()
