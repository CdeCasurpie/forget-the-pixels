"""Frozen bank + phase-3 experiments -> interior plans, summary and checks.

Runs every phase-0 case (three seeds by default) plus the six phase-3 fixtures,
exports colored floor plans and evaluates the fixture expectations.
"""
import argparse
import hashlib
import json
from pathlib import Path
import time

from planning.interiors import plan_interiors
from planning.interiors_export import export_interiors
from domain.architectural_plan import PlanningError


def check_expectations(plan, case):
    """Evaluate the fixture expectations against a finished interior plan.

    Returns a report; every boolean entry must be true for the case to pass.
    """
    expectations=case['expectations'];report={}
    data=plan.to_dict();floors={f['floor']:f for f in data['floors']}
    windows=expectations.get('windows')
    if windows:
        requested=set(windows['floors'])
        report['windows_match']=all(len(floors[f]['windows'])==windows['count'] for f in requested) and \
                               all(not floors[f]['windows'] for f in floors if f not in requested)
        if windows.get('unique_rooms'):
            report['window_rooms_unique']=all(
                len({w['room'] for w in floors[f]['windows']})==len(floors[f]['windows']) for f in requested)
        if 'proportions' in windows:
            values=sorted(w['proportion'] for f in requested for w in floors[f]['windows'])
            report['proportions_match']=values==sorted(windows['proportions']*len([f for f in requested]))
    if 'window_kinds_allowed' in expectations:
        byid={r['id']:r['kind'] for row in floors.values() for r in row['rooms']}
        kinds=[byid[w['room']] for row in floors.values() for w in row['windows']]
        report['window_kinds']=kinds
        report['window_kinds_match']=bool(kinds) and all(k in expectations['window_kinds_allowed'] for k in kinds)
    garage=expectations.get('garage')
    if garage:
        report['garage_present']=any(r['kind']=='garage' for row in floors.values() for r in row['rooms'])
        doors=[c for c in data['connections'] if c['kind']=='door']
        report['garage_not_passage']=not any(d['source'].endswith('/garage') for d in doors)
        if garage.get('vehicle_entry'):
            report['vehicle_entry']=any(c['kind']=='vehicle_entry' for c in data['connections'])
    loggia=expectations.get('loggia')
    if loggia:
        per_floor={floor:sum(1 for c in row['connections'] if c['kind']=='exterior_space') for floor,row in floors.items()}
        report['loggia_connections']=per_floor
        report['loggia_match']=sum(per_floor.values())==1 and per_floor.get(loggia['floor'],0)==1
    return report


def all_expected(checks):
    return all(value for key,value in checks.items() if isinstance(value,bool)) and \
           any(isinstance(value,bool) for value in checks.values())


def run(output, seeds, preview=True, include_bank=True):
    here=Path(__file__).parent
    bank=here.parents[0]/'phase0/cases'
    fixtures=sorted((here/'cases').glob('*.json'))
    output.mkdir(parents=True,exist_ok=False)
    results=[]
    targets=[]
    if include_bank:
        targets.extend((path,'bank') for path in sorted(bank.glob('*/*.json')))
    targets.extend((path,'fixture') for path in fixtures)
    for path,group in targets:
        case=json.loads(path.read_text())
        for seed in seeds:
            request=json.loads(json.dumps(case['request']));request['seed']=seed
            start=time.perf_counter()
            result={'id':case['id'],'group':group,'seed':seed,
                    'fixture_sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
            try:
                plan=plan_interiors(request)
                report=export_interiors(plan,output/f"{case['id']}_seed{seed}",preview)
                result.update(status='passed',floors=[f['floor'] for f in report['floors']],
                              rooms=[f['rooms'] for f in report['floors']],
                              corridor_widths=[f['corridor_width_m'] for f in report['floors']],
                              windows=[f['windows'] for f in report['floors']],
                              selected_alternative=report['selected_alternative'],
                              alternatives=len(report['alternatives']))
                if group=='fixture':
                    checks=check_expectations(plan,case)
                    result['expectations_checked']=checks
                    if not all_expected(checks):result['status']='mismatch'
            except PlanningError as exc:
                result.update(status='conflict',code=exc.code,path=exc.path,message=str(exc))
            result['seconds']=round(time.perf_counter()-start,4);results.append(result)
    report={'scope':'phase3','seeds':seeds,'runs':len(results),
            'passed':sum(r['status']=='passed' for r in results),
            'conflicts':sum(r['status']=='conflict' for r in results),
            'mismatches':sum(r['status']=='mismatch' for r in results),'results':results}
    (output/'results.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='results'},indent=2))
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--seeds',type=int,nargs='+',default=[7,17,81])
    parser.add_argument('--no-preview',action='store_true')
    parser.add_argument('--no-bank',action='store_true')
    args=parser.parse_args();run(args.output,args.seeds,not args.no_preview,not args.no_bank)
