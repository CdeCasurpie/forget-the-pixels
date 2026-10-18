"""Frozen bank + phase-4 fixtures -> constructive envelopes, summaries, checks.

Runs every phase-0 case (three seeds by default) plus the phase-4 fixtures,
exports GLB/PNG evidence and evaluates the fixture expectations.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import time

from shapely.geometry import shape

from planning.envelope import plan_envelope
from planning.envelope_export import export_envelope
from domain.architectural_plan import PlanningError


def check_expectations(plan, case):
    """Evaluate fixture expectations against a finished envelope plan.

    Returns a report; every boolean entry must be true for the case to pass.
    """
    expectations=case['expectations'];report={}
    data=plan.to_dict();openings=data['openings']
    windows=[o for o in openings if o['kind']=='window']
    by_floor={}
    for window in windows:by_floor.setdefault(window['floor'],[]).append(window)
    requested=expectations.get('windows')
    if requested:
        floors=requested['floors'];count=requested['count']
        if isinstance(count,dict):
            report['windows_match']=all(len(by_floor.get(f,[]))==count[f] for f in floors)
        else:
            report['windows_match']=all(len(by_floor.get(f,[]))==count for f in floors)
        if requested.get('unique_rooms'):
            report['window_rooms_unique']=all(len({o['room'] for o in by_floor.get(f,[])})==len(by_floor.get(f,[])) for f in floors)
        if 'proportions' in requested:
            expected=sorted(requested['proportions'])
            report['proportions_match']=all(
                sorted(o['proportion'] for o in by_floor.get(f,[]))==expected for f in floors)
    closed=expectations.get('no_completion')
    if closed:
        report['closed_floors']=all(not any(o['source']=='completion' for o in by_floor.get(f,[])) for f in closed['floors'])
    completed=expectations.get('completion')
    if completed:
        report['completion_present']=all(
            sum(o['source']=='completion' for o in by_floor.get(f,[]))>=completed.get('min',1) for f in completed['floors'])
    mechanisms=expectations.get('mechanisms')
    if mechanisms:
        values={o['mechanism'] for o in windows}
        if 'allowed' in mechanisms:report['mechanisms_allowed']=values<=set(mechanisms['allowed'])
        if 'present' in mechanisms:report['mechanisms_present']=set(mechanisms['present'])<=values
    styles=expectations.get('styles')
    if styles and 'present' in styles:
        report['styles_present']=set(styles['present'])<={o['style'] for o in openings}
    materials=expectations.get('materials')
    if materials and 'present' in materials:
        report['materials_present']=set(materials['present'])<={o['material'] for o in openings}
    widths=expectations.get('frame_widths')
    if widths:
        report['frame_widths']=all(
            all(abs(o['frame_width_m']-value)<1e-9 for o in windows if o['style']==style)
            for style,value in widths.items())
    entrance=expectations.get('entrance')
    if entrance:
        found=[o for o in openings if o['kind']=='entrance']
        report['entrance_design']=bool(found) and found[0]['material']==entrance['material'] and found[0]['style']==entrance['style']
    heights=expectations.get('heights')
    if heights:
        if 'max_window_head_m' in heights:
            report['max_window_head']=all(o['head_m']<=heights['max_window_head_m']+1e-9 for o in windows)
        if 'min_window_height_m' in heights:
            report['min_window_height']=all(o['head_m']-o['sill_m']>=heights['min_window_height_m']-1e-9 for o in windows)
    if expectations.get('floor_relative'):
        levels=data['request']['context']['levels_m']
        report['floor_relative']=all(o['bottom_m']>=levels[o['floor']-1]-1e-9 for o in openings)
    if expectations.get('staggered'):
        floors=sorted(by_floor)
        shifted=False
        for low,high in zip(floors,floors[1:]):
            first=[shape(o['geometry']).centroid for o in by_floor[low]]
            second=[shape(o['geometry']).centroid for o in by_floor[high]]
            if first and second and max(min(a.distance(b) for b in second) for a in first)>.05:
                shifted=True
        report['staggered']=shifted
    return report


def all_expected(checks):
    return all(value for value in checks.values() if isinstance(value,bool)) and \
           any(isinstance(value,bool) for value in checks.values())


def run(output, seeds, preview=True, include_bank=True, comparisons=None):
    here=Path(__file__).parent
    bank=here.parents[0]/'phase0/cases'
    fixtures=sorted((here/'cases').glob('*.json'))
    output.mkdir(parents=True,exist_ok=False)
    results=[];targets=[]
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
                plan=plan_envelope(request, interiors=True)
                report=export_envelope(plan,output/f"{case['id']}_seed{seed}",preview)
                result.update(status='passed',parts=report['parts'],openings=report['openings'],
                              windows=report['windows'],doors=report['doors'],
                              completed_windows=report['completed_windows'],
                              mechanisms=report['mechanisms'],styles=report['styles'],
                              watertight=report['audit']['watertight'],
                              group_overlap_m3=report['audit']['group_overlap_m3'],
                              minimum_lintel_m=plan.checks['minimum_lintel_m'])
                if group=='fixture':
                    checks=check_expectations(plan,case)
                    result['expectations_checked']=checks
                    if not all_expected(checks):result['status']='mismatch'
            except PlanningError as exc:
                result.update(status='conflict',code=exc.code,path=exc.path,message=str(exc))
            result['seconds']=round(time.perf_counter()-start,4);results.append(result)
    if comparisons is not None:
        spec=importlib.util.spec_from_file_location('phase4_compare',Path(__file__).parent/'compare.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        module.run(comparisons)
    report={'scope':'phase4','seeds':seeds,'runs':len(results),
            'passed':sum(r['status']=='passed' for r in results),
            'conflicts':sum(r['status']=='conflict' for r in results),
            'mismatches':sum(r['status']=='mismatch' for r in results),'results':results}
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
    args=parser.parse_args();run(args.output,args.seeds,not args.no_preview,not args.no_bank,args.comparisons)
