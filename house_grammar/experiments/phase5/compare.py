"""Same building and lot, different fencing/access intentions."""
import copy
import json
from pathlib import Path

from planning.site_access import plan_site
from planning.site_export import export_site


BASE={'version':'intent-v1','seed':17,
      'context':{'parcel':[[0,0],[10,0],[10,18],[0,18]],'fronts':{'F1':0},
                 'levels_m':[0,3.2,6]},
      'building':{'profile':'barranco_residential','organization':'compact'}}
SPACE={'front':'F1','depth':'medium','use':'garden'}


def variants():
    sites={
        'solid_high':dict(front_space=SPACE,fence=dict(front='F1',form='solid',height='high',cap='tile'),door='left'),
        'open_low':dict(front_space=SPACE,fence=dict(front='F1',form='open',height='low'),door='left'),
        'base_and_rail':dict(front_space=SPACE,fence=dict(front='F1',form='base_and_rail',height='low'),door='left'),
        'partial':dict(front_space=SPACE,fence=dict(front='F1',form='partial',height='low'),door='left'),
        'unfenced':dict(front_space=SPACE,fence=False,door='left'),
        'covered_vehicle_portal':dict(front_space=SPACE,fence=dict(front='F1',form='solid',height='high',cap='corrugated'),
                                      door='left',garage='right'),
    }
    for name,site in sites.items():
        request=copy.deepcopy(BASE);request['building']['site']=copy.deepcopy(site)
        yield name,request


def run(output, preview=True):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    table=[]
    for name,request in variants():
        plan=plan_site(request);report=export_site(plan,output/name,preview)
        table.append(dict(id=name,form=plan.fence and plan.fence['form'],
                          gates=[g['kind'] for g in plan.gates],
                          routes=[dict(kind=r['kind'],length_m=round(r['length_m'],3),
                                       transition=r['transition']) for r in plan.routes],
                          site_parts=len(plan.parts),audit=report['audit']))
    (output/'comparisons.json').write_text(json.dumps(table,indent=2,ensure_ascii=False)+'\n')
    print(f'{len(table)} site variants exported to {output}')
    return table


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--no-preview',action='store_true')
    args=parser.parse_args();run(args.output,not args.no_preview)
