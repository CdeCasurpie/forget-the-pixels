"""Same site, seven spatial articulations; separate from the frozen phase-0 bank."""
import argparse
import copy
import json
from pathlib import Path

from planning.articulation import plan_articulation
from planning.massing_export import export_plan


def cases():
    base=dict(version='intent-v1',seed=17,context=dict(
        parcel=[[0,0],[10,0],[10,18],[0,18]],fronts={'F1':0},levels_m=[0,3.2,6,8.8]),
        building=dict(site={'front_space':{'front':'F1','depth':'medium'}}))
    variants=[('compact',None,{}),('center_recess','recess',{}),
              ('right_loggia','loggia',{'position':'right'}),
              ('alternating','floor_shift',{'floors':[2,3]}),
              ('projecting_rhythm','depth_rhythm',{'weights':[1,2,1],'planes':['base','projecting','recessed']}),
              ('portico','portico',{'floors':[1],'width':'wide'}),
              ('vestibule','vestibule',{'floors':[1],'width':'narrow'}),
              ('balcony','balcony',{'position':'right'})]
    for name,kind,extra in variants:
        d=copy.deepcopy(base)
        if kind:d['building']['operations']=[dict(id='articulation',kind=kind,body='main',front='F1',**dict(floors=[2])|extra)]
        yield name,d


def run(output):
    output.mkdir(parents=True,exist_ok=False)
    results=[]
    for name,request in cases():
        p=plan_articulation(request);summary=export_plan(p,output/name)
        if not all(summary[k] for k in ('all_components_watertight','all_components_positive_volume','all_components_winding_consistent')):
            raise ValueError(f'{name}: invalid exported mesh')
        results.append(dict(id=name,**summary))
    (output/'results.json').write_text(json.dumps(results,indent=2)+'\n')
    print(f'{len(results)} comparison variants exported to {output}')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args().output)
