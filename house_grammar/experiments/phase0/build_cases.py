"""Build synthetic acceptance fixtures. Never labelled as observed real houses."""
import copy
import json
from pathlib import Path

ROOT = Path(__file__).parent
BASE = {'version':'intent-v1','context':{'parcel':[[0,0],[10,0],[10,18],[0,18]],
        'fronts':{'F1':0},'levels_m':[0,3.2,6,8.8]},'building':{},'seed':17}


def cases():
    specs = [
        ('compact_narrow', 'compact', None),
        ('wide_bar', 'bar', None),
        ('corner', 'corner', 'chamfer'),
        ('high_fence', 'compact', None),
        ('open_setback', 'compact', 'setback'),
        ('courtyard', 'courtyard', 'courtyard'),
        ('left_bite', 'compact', 'bite'),
        ('upper_setback', 'stepped', 'setback'),
        ('loggia', 'compact', 'loggia'),
        ('depth_rhythm', 'compact', 'depth_rhythm'),
        ('open_ground', 'podium', 'open_ground'),
        ('mixed_styles', 'incremental', None),
        ('L_rear_wing', 'L', 'attach'),
        ('U_courtyard', 'U', 'courtyard'),
        ('upper_shift', 'attached', 'floor_shift'),
        ('irregular_bite', 'compact', 'bite'),
        ('corrugated_addition', 'incremental', 'attach'),
        ('mixed_use', 'bar', None),
        ('corner_loggia', 'corner', 'loggia'),
        ('complex_combination', 'attached', 'depth_rhythm'),
    ]
    result=[]
    for i,(name,organization,kind) in enumerate(specs,1):
        req=copy.deepcopy(BASE); b=req['building'];b['organization']=organization
        b['profile']='barranco_residential'
        if kind:
            op={'id':'op1','kind':kind,'body':'main','front':'F1','position':'left','depth':'medium'}
            if kind in ('setback','loggia','floor_shift'):op['floors']=[3]
            if kind=='depth_rhythm':op.update(weights=[1,2,1],planes=['base','recessed','projecting'])
            b['operations']=[op]
        if i==1:
            req['context']['parcel']=[[0,0],[5,0],[5,20],[0,20]]
            req['context']['levels_m']=[0,3.2]
        if i==2:
            req['context']['parcel']=[[0,0],[18,0],[18,12],[0,12]]
            req['context']['levels_m']=[0,3.2,6]
        if i in (3,19,20):req['context']['fronts']['F2']=3
        if i==4:b['site']={'front_space':{'front':'F1','depth':'medium','use':'patio'},'fence':{'front':'F1','form':'solid','height':'high','cap':'tile'},'door':'left','garage':'right'}
        if i==5:b['site']={'fence':False,'front_space':{'front':'F1','depth':'shallow','use':'garden'},'garage':False}
        if i==12:
            b['style']='republicano'
            b['profile']='barranco_casona'
            b['facades']=[{'body':'main','front':'F1','floors':[2], 'style':'moderno','windows':{'count':2,'style':'moderno','frame':'metal','proportion':'horizontal'}}]
        if i in (13,17):b['operations'][0]['position']='rear'
        if i==16:req['context']['parcel']=[[0,0],[8,0],[11,9],[7,18],[0,16]]
        if i==17:b.update(profile='barranco_incremental',roof={'cover':'corrugated','objects':['water_tank']},finishes={'sides':'brick','front':'mixed'})
        if i==18:b.update(profile='barranco_mixed_use',site={'door':True,'garage':False})
        if i==19:
            b['operations'][0]['front']='F2'
            b['facades']=[{'body':'main','front':'F2','floors':[1,2],'alignment':'staggered','windows':{'count':2,'proportion':'vertical'}}]
        if i==20:
            b['bodies']=[{'id':'main','floors':[1,2,3]},
                         {'id':'wing','floors':[1],'position':'rear','width':'narrow'}]
            b['operations'] += [
                {'id':'retreat','kind':'setback','body':'main','front':'F1','floors':[3],'depth':'medium'},
                {'id':'loggia','kind':'loggia','body':'main','front':'F2','floors':[2],'after':['op1']},
                {'id':'crown','kind':'crown','body':'main','front':'F1','position':'center','after':['retreat']}]
            b['roof']={'cover':'mixed','shade':True}
        result.append({'id':f'{i:02}_{name}','split':'tuning' if i<=14 else 'evaluation',
                       'source':'synthetic_design_fixture','request':req,
                       'expectations':{'organization':organization,'operations':[x['kind'] for x in b.get('operations',[])],
                                       'evidence_required':False,'geometry_verified':False}})
    return result


if __name__=='__main__':
    for case in cases():
        path=ROOT/'cases'/case['split']/(case['id']+'.json')
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(case,indent=2,ensure_ascii=False)+'\n')
