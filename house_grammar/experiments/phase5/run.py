"""Frozen phase-0 bank plus phase-5 site fixtures and geometric audits."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import time

from domain.architectural_plan import PlanningError
from planning.site_access import plan_site
from planning.site_export import export_site


def check_expectations(plan, case):
    expected=case['expectations'];report={};kinds={p['kind'] for p in plan.parts}
    gate_kinds=sorted(g['kind'] for g in plan.gates)
    route_kinds=sorted(r['kind'] for r in plan.routes)
    transitions=sorted(r['transition'] for r in plan.routes)
    if expected.get('no_fence'):
        report['no_fence']=plan.fence is None
    if 'fence' in expected:
        report['fence_form']=plan.fence is not None and plan.fence['form']==expected['fence']
    if 'height_m' in expected:
        report['fence_height']=plan.fence is not None and abs(plan.fence['height_m']-expected['height_m'])<1e-9
    if 'cap' in expected:
        report['cap']=plan.fence is not None and plan.fence['cap']==expected['cap']
    if 'gates' in expected:report['gates']=gate_kinds==sorted(expected['gates'])
    if 'routes' in expected:report['routes']=route_kinds==sorted(expected['routes'])
    if 'transitions' in expected:report['transitions']=transitions==sorted(expected['transitions'])
    if 'parts' in expected:report['parts']=set(expected['parts'])<=kinds
    if 'canopy' in expected:report['canopy']=('gate_canopy' in kinds)==expected['canopy']
    if 'details' in expected:report['details']=plan.fence is not None and len(plan.fence['details'])==3
    if expected.get('completion'):
        report['completion']=any(d.get('source')=='completion' and d['path']=='site.fence'
                                 for d in plan.decisions)
    return report


def run(output, seeds, preview=True, include_bank=True, comparisons=None):
    here=Path(__file__).parent
    targets=[]
    if include_bank:
        targets.extend((p,'bank') for p in sorted((here.parent/'phase0/cases').glob('*/*.json')))
    targets.extend((p,'fixture') for p in sorted((here/'cases').glob('*.json')))
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    results=[]
    for path,group in targets:
        case=json.loads(path.read_text())
        for seed in seeds:
            request=json.loads(json.dumps(case['request']));request['seed']=seed
            row=dict(id=case['id'],group=group,seed=seed,
                     fixture_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
            start=time.perf_counter()
            try:
                plan=plan_site(request)
                report=export_site(plan,output/f"{case['id']}_seed{seed}",preview)
                audit=report['audit']
                row.update(status='passed',site_parts=report['site_parts'],
                           gates=len(plan.gates),routes=len(plan.routes),
                           watertight=audit['watertight'],group_overlap_m3=audit['group_overlap_m3'])
                if not audit['watertight'] or audit['group_overlap_m3']>1e-8:
                    row['status']='mismatch'
                if group=='fixture':
                    checks=check_expectations(plan,case);row['expectations_checked']=checks
                    if not checks or not all(checks.values()):row['status']='mismatch'
            except PlanningError as exc:
                row.update(status='conflict',code=exc.code,path=exc.path,message=str(exc))
            row['seconds']=round(time.perf_counter()-start,4);results.append(row)
    if comparisons is not None:
        spec=importlib.util.spec_from_file_location('phase5_compare',here/'compare.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        module.run(Path(comparisons),preview)
    report=dict(scope='phase5',seeds=seeds,runs=len(results),
                passed=sum(r['status']=='passed' for r in results),
                conflicts=sum(r['status']=='conflict' for r in results),
                mismatches=sum(r['status']=='mismatch' for r in results),results=results)
    (output/'results.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps({key:value for key,value in report.items() if key!='results'},indent=2))
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--seeds',type=int,nargs='+',default=[7,17,81])
    parser.add_argument('--no-preview',action='store_true')
    parser.add_argument('--no-bank',action='store_true')
    parser.add_argument('--comparisons',type=Path)
    args=parser.parse_args()
    run(args.output,args.seeds,not args.no_preview,not args.no_bank,args.comparisons)
