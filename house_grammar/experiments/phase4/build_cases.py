"""Phase-4 experiment fixtures: constructive vanos, carpintería y encuentros.

Cada caso es un intent-v1 completo más las expectativas que evalúa el runner.
Fixtures sintéticos; nunca se etiquetan como casas reales observadas. Los
antepechos, dinteles y perfiles no se fijan en el contrato: el compilador los
deriva del uso, la proporción y el estilo heredable.
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

    # 1-2. Same requested count on a narrow and a wide front: the count is a
    # contract, the widths adapt to the available facade.
    def fixed_count(req,parcel,organization):
        req['context']['parcel']=parcel
        b=req['building'];b['organization']=organization
        b['facades']=[{'body':'main','front':'F1','floors':[1,2],
                       'windows':{'count':3,'proportions':['horizontal','vertical','small_high'],
                                  'weights':[1.6,1.,.9],'distribution':'balanced'}}]
    add('p4_fixed_count_narrow',
        {'windows':{'floors':[1,2],'count':3,
                    'proportions':['horizontal','vertical','small_high']}},
        lambda r:fixed_count(r,[[0,0],[8,0],[8,20],[0,20]],'compact'))
    add('p4_fixed_count_wide',
        {'windows':{'floors':[1,2],'count':3,
                    'proportions':['horizontal','vertical','small_high']}},
        lambda r:fixed_count(r,[[0,0],[16,0],[16,13],[0,13]],'bar'))

    # 3-4. Floor heights change antepechos and dinteles, never the count.
    def vertical_pair(req):
        b=req['building'];b['organization']='compact'
        b['facades']=[{'body':'main','front':'F1','floors':[1,2],
                       'windows':{'count':2,'proportion':'vertical'}}]
    add('p4_low_ceiling',{'windows':{'floors':[1,2],'count':2},
                          'heights':{'max_window_head_m':2.320001}},lambda r:(r['context'].__setitem__('levels_m',[0,2.7,5.4]),vertical_pair(r)))
    add('p4_tall_floor',{'windows':{'floors':[1,2],'count':2},
                         'heights':{'min_window_height_m':1.0}},
        lambda r:(r['context'].__setitem__('levels_m',[0,3.8,7.6]),
                  r['building'].update({'organization':'compact',
                      'facades':[{'body':'main','front':'F1','floors':[1,2],
                                  'windows':{'count':2,'proportion':'horizontal'}}]})))

    # 5. A raised ground floor: every elevation is floor-relative.
    def raised(req):
        req['context']['levels_m']=[0.5,3.7,6.5]
        b=req['building'];b['organization']='compact'
        b['facades']=[{'body':'main','front':'F1','floors':[1,2],'windows':{'count':2,'proportion':'vertical'}}]
    add('p4_raised_ground',{'windows':{'floors':[1,2],'count':2},'floor_relative':True},raised)

    # 6. Staggered alignment: upper windows shift within the same cell.
    def staggered(req):
        b=req['building'];b['organization']='compact'
        b['facades']=[{'body':'main','front':'F1','floors':[1,2],'alignment':'staggered',
                       'windows':{'count':2,'proportion':'vertical','distribution':'left'}}]
    add('p4_staggered_distribution',{'windows':{'floors':[1,2],'count':2},'staggered':True},staggered)

    # 7. Modern joinery on a republican body: body style is a prior, not a ban.
    def modern_on_republican(req):
        b=req['building'];b['organization']='compact';b['style']='republicano'
        b['facades']=[{'body':'main','front':'F1','floors':[1,2],
                       'windows':{'count':2,'proportion':'vertical','style':'moderno','frame':'metal'}}]
    add('p4_modern_frame_republican',
        {'windows':{'floors':[1,2],'count':2},'completion':{'floors':[3],'min':1},
         'styles':{'present':['moderno','republicano']},'materials':{'present':['metal']},
         'frame_widths':{'moderno':0.045}},modern_on_republican)

    # 8. Mechanism override: guillotine sashes are horizontal tracks in wood.
    def guillotine(req):
        b=req['building'];b['organization']='compact'
        b['facades']=[{'body':'main','front':'F1','floors':[1,2],
                       'windows':{'count':2,'proportion':'horizontal','mechanism':'guillotine','frame':'wood'}}]
    add('p4_guillotine_tracks',
        {'windows':{'floors':[1,2],'count':2},'mechanisms':{'present':['guillotine']},
         'materials':{'present':['wood']}},guillotine)

    # 9. Street door as an object: material independent from the global style.
    def door_materials(req):
        b=req['building'];b['organization']='compact'
        b['site']={'door':{'position':'center','style':'clasico','material':'metal'}}
        b['facades']=[{'body':'main','front':'F1','floors':[1,2],'windows':{'count':2,'proportion':'vertical'}}]
    add('p4_door_materials',
        {'windows':{'floors':[1,2],'count':2},'entrance':{'material':'metal','style':'clasico'},
         'materials':{'present':['metal']}},door_materials)

    # 10. Explicit scopes close only their floors; other exposures complete.
    def completion_upper(req):
        b=req['building'];b['organization']='compact'
        b['facades']=[{'body':'main','front':'F1','floors':[1],'windows':{'count':2,'proportion':'vertical'}}]
    add('p4_completion_upper_floor',
        {'windows':{'floors':[1],'count':2},'no_completion':{'floors':[1]},
         'completion':{'floors':[2,3],'min':1}},completion_upper)

    return result


if __name__=='__main__':
    directory=ROOT/'cases';directory.mkdir(parents=True,exist_ok=True)
    for case in cases():
        (directory/(case['id']+'.json')).write_text(json.dumps(case,indent=2,ensure_ascii=False)+'\n')
    print(f"wrote {len(cases())} phase-4 fixtures to {directory}")
