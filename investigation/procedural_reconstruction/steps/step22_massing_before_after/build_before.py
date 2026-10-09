"""Reconstruct Step 22's non-explicit baseline cases with existing src."""
import json
from pathlib import Path
import sys

STEP = Path(__file__).resolve().parent
ROOT = STEP.parent.parent
sys.path.insert(0, str(ROOT/'steps/step18_theta_interface'))
from run import run


def main():
    result=[]
    for path in sorted((STEP/'before').glob('*.json')):
        source=json.loads(path.read_text())
        assert source['theta'].get('masses') is None
        assert source['theta']['massing']['pattern'] != 'explicit'
        output=STEP/'before_output'/path.stem
        manifest=run(path,output,size=640)
        resolved=json.loads((output/'resolved_theta.json').read_text())
        result.append({'case':path.stem,'pattern':resolved['theta']['massing']['pattern'],
                       'family':resolved['theta']['family'],
                       'masses':[{'role':m['role'],'base_z':m['base_z'],
                                  'roof_z':m['roof_z'],'footprint':m['footprint']} for m in resolved['masses']],
                       'triangles':manifest['triangles'],
                       'envelope_test':manifest['validation']['envelope_test'],
                       'max_outside_triangle_area_m2':manifest['validation']['max_outside_triangle_area_m2']})
    if len(result)!=7: raise ValueError('Expected exactly seven baseline cases')
    (STEP/'before_output/summary.json').write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__': main()
