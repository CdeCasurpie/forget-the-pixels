"""Frozen phase-0 bank -> phase-1 plans, diagnostic GLBs and aggregate report."""
import argparse
import hashlib
import json
from pathlib import Path
import time

from planning.massing import plan_massing
from planning.massing_export import export_plan
from domain.architectural_plan import PlanningError


def run(output, seeds, preview=True):
    bank=Path(__file__).parents[1]/'phase0/cases'
    output.mkdir(parents=True,exist_ok=False)
    results=[]
    for path in sorted(bank.glob('*/*.json')):
        case=json.loads(path.read_text())
        for seed in seeds:
            req=case['request'];req['seed']=seed;start=time.perf_counter()
            result={'id':case['id'],'split':case['split'],'seed':seed,
                    'fixture_sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
            try:
                plan=plan_massing(req)
                summary=export_plan(plan,output/f'{case["id"]}_seed{seed}',preview)
                result.update(status='passed',**summary)
            except PlanningError as exc:
                result.update(status='conflict',code=exc.code,path=exc.path,message=str(exc))
            result['seconds']=round(time.perf_counter()-start,4);results.append(result)
    report={'scope':'phase1_massing','seeds':seeds,'runs':len(results),
            'passed':sum(r['status']=='passed' for r in results),
            'conflicts':sum(r['status']=='conflict' for r in results),'results':results}
    (output/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='results'},indent=2))
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--seeds',type=int,nargs='+',default=[17])
    parser.add_argument('--no-preview',action='store_true')
    args=parser.parse_args();run(args.output,args.seeds,not args.no_preview)
