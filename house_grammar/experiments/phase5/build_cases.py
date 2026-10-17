"""Synthetic phase-5 site and access scenarios (never claimed as observed houses)."""
import copy
import json
from pathlib import Path


ROOT=Path(__file__).parent
BASE={'version':'intent-v1','seed':17,
      'context':{'parcel':[[0,0],[10,0],[10,18],[0,18]],'fronts':{'F1':0},
                 'levels_m':[0,3.2,6]},
      'building':{'profile':'barranco_residential','organization':'compact'}}


def cases():
    result=[]
    def add(name,site,expectations,levels=None,organization=None):
        request=copy.deepcopy(BASE);request['building']['site']=site
        if levels:request['context']['levels_m']=levels
        if organization:request['building']['organization']=organization
        result.append(dict(id=name,source='synthetic_design_fixture',request=request,
                           expectations=dict(expectations,evidence_required=False)))

    front=lambda depth,use:dict(front='F1',depth=depth,use=use)
    fence=lambda form,height='low',cap='plain':dict(front='F1',form=form,height=height,cap=cap)
    add('p5_high_fence_hidden',dict(front_space=front('medium','patio'),
        fence=fence('solid','high','tile'),door='left',garage='right'),
        dict(fence='solid',height_m=2.20,cap='tile',gates=['pedestrian','vehicle'],
             routes=['pedestrian','vehicle'],canopy=True,details=True))
    add('p5_low_open_rail',dict(front_space=front('medium','garden'),
        fence=fence('open'),door='left'),
        dict(fence='open',height_m=1.15,gates=['pedestrian'],routes=['pedestrian'],
             parts=['fence_post','fence_rail','fence_bar'],details=True))
    add('p5_base_and_rail',dict(front_space=front('medium','garden'),
        fence=fence('base_and_rail','low','tile'),door='left'),
        dict(fence='base_and_rail',parts=['fence_base','fence_rail','fence_cap'],details=True))
    add('p5_open_setback',dict(front_space=front('shallow','garden'),fence=False,garage=False),
        dict(no_fence=True,gates=[],routes=['pedestrian'],transitions=['level']))
    add('p5_partial_fence',dict(front_space=front('medium','garden'),
        fence=fence('partial','low','corrugated'),door='left'),
        dict(fence='partial',gates=['pedestrian'],parts=['fence_wall','fence_cap']))
    add('p5_garage_without_fence_gate',dict(front_space=front('medium','driveway'),
        fence=False,garage='right'),
        dict(no_fence=True,gates=[],routes=['pedestrian','vehicle']))
    add('p5_street_edge',dict(fence=False),
        dict(no_fence=True,gates=[],transitions=['direct']),organization='bar')
    add('p5_covered_portal',dict(front_space=front('medium','driveway'),
        fence=fence('solid','high','corrugated'),door='left',garage='right'),
        dict(fence='solid',cap='corrugated',gates=['pedestrian','vehicle'],canopy=True))
    add('p5_raised_steps',dict(front_space=front('shallow','garden'),fence=False),
        dict(no_fence=True,transitions=['steps'],parts=['step']),levels=[.5,3.7,6.5])
    add('p5_raised_ramp',dict(front_space=front('deep','garden'),fence=False),
        dict(no_fence=True,transitions=['ramp'],parts=['ramp']),levels=[.2,3.4,6.2])
    add('p5_auto_low_fence',dict(front_space=front('medium','garden'),door='left'),
        dict(fence='open',gates=['pedestrian'],completion=True))
    return result


def build():
    directory=ROOT/'cases';directory.mkdir(exist_ok=True)
    for case in cases():
        (directory/(case['id']+'.json')).write_text(json.dumps(case,indent=2,ensure_ascii=False)+'\n')
    print(f'{len(cases())} phase-5 fixtures in {directory}')


if __name__=='__main__':build()
