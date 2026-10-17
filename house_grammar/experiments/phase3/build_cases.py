"""Phase-3 experiment fixtures: interiors driven by windows, garage and loggia.

Each case is a full intent-v1 request plus the interior expectations the runner
evaluates. Fixtures are synthetic; never labelled as observed real houses.
"""
import copy
import json
from pathlib import Path

ROOT = Path(__file__).parent
BASE = {'version':'intent-v1','context':{'parcel':[[0,0],[10,0],[10,18],[0,18]],
        'fronts':{'F1':0},'levels_m':[0,3.2,6,8.8]},'building':{},'seed':17}


def cases():
    result=[]

    def add(cid, expectations, mutate):
        req=copy.deepcopy(BASE);req['building']['profile']='barranco_residential'
        mutate(req)
        result.append({'id':cid,'source':'synthetic_design_fixture','request':req,
                       'expectations':dict(expectations,evidence_required=False,geometry_verified=False)})

    # 1. Two large windows: both must own usable rooms, on a unique room each.
    def two_large(req):
        b=req['building'];b['organization']='compact'
        b['facades']=[{'body':'main','front':'F1','floors':[1,2],
                       'windows':{'count':2,'proportions':['horizontal','horizontal'],
                                  'weights':[1.5,1.5],'distribution':'balanced'}}]
    add('p3_two_large_windows',
        {'windows':{'floors':[1,2],'count':2,'unique_rooms':True}},two_large)

    # 2. Three unequal windows: distinct proportions survive to room assignment.
    def three_unequal(req):
        b=req['building'];b['organization']='bar'
        req['context']['parcel']=[[0,0],[16,0],[16,13],[0,13]]
        b['facades']=[{'body':'main','front':'F1','floors':[1,2],
                       'windows':{'count':3,'proportions':['horizontal','vertical','small_high'],
                                  'weights':[1.6,1.0,.9],'distribution':'balanced'}}]
    add('p3_three_unequal_windows',
        {'windows':{'floors':[1,2],'count':3,
                    'proportions':['horizontal','vertical','small_high']},
         'window_kinds_allowed':['living','bedroom','kitchen_dining','service','bathroom']},three_unequal)

    # 3. One small high window must land on a service-like room, never a bedroom.
    def small_high(req):
        b=req['building'];b['organization']='compact'
        req['context']['parcel']=[[0,0],[5,0],[5,20],[0,20]]
        req['context']['levels_m']=[0,3.2]
        b['facades']=[{'body':'main','front':'F1','floors':[1],
                       'windows':{'count':1,'proportions':['small_high'],'weights':[1.]}}]
    add('p3_small_high_window',
        {'windows':{'floors':[1],'count':1,'unique_rooms':True},
         'window_kinds_allowed':['service','bathroom']},small_high)

    # 4. Garage with its own street access; never used as a passageway.
    def garage(req):
        b=req['building'];b['organization']='compact'
        b['site']={'door':'left','garage':'right'}
        b['facades']=[{'body':'main','front':'F1','floors':[1,2],
                       'windows':{'count':2,'proportion':'vertical'}}]
    add('p3_garage_independent',
        {'windows':{'floors':[1,2],'count':2,'unique_rooms':True},
         'garage':{'present':True,'not_passage':True,'vehicle_entry':True}},garage)

    # 5. A different upper floor: windows requested only on the recessed level.
    def upper_different(req):
        b=req['building'];b['organization']='stepped'
        b['operations']=[{'id':'op1','kind':'setback','body':'main','front':'F1',
                          'position':'left','depth':'medium','floors':[3]}]
        b['facades']=[{'body':'main','front':'F1','floors':[3],
                       'windows':{'count':2,'proportions':['horizontal','vertical']}}]
    add('p3_upper_floor_different',
        {'windows':{'floors':[3],'count':2,'unique_rooms':True}},upper_different)

    # 6. Loggia connected to exactly one room on its floor.
    def loggia(req):
        b=req['building'];b['organization']='compact'
        b['operations']=[{'id':'op1','kind':'loggia','body':'main','front':'F1',
                          'position':'center','depth':'medium','floors':[2]}]
        b['facades']=[{'body':'main','front':'F1','floors':[1,3],
                       'windows':{'count':2,'proportion':'square'}}]
    add('p3_connected_loggia',
        {'windows':{'floors':[1,3],'count':2,'unique_rooms':True},
         'loggia':{'floor':2}},loggia)

    return result


if __name__=='__main__':
    directory=ROOT/'cases';directory.mkdir(parents=True,exist_ok=True)
    for case in cases():
        (directory/(case['id']+'.json')).write_text(json.dumps(case,indent=2,ensure_ascii=False)+'\n')
    print(f"wrote {len(cases())} phase-3 fixtures to {directory}")
