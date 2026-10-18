"""Phase-4 comparisons: same envelope, different carpentry and door materials.

Six variants of one synthetic three-storey house: three frame styles and three
street-door materials. Each variant is a full envelope export; the JSON table
records the resolved designs so differences are auditable, not asserted.
"""
import copy
import json
from pathlib import Path

from planning.envelope import plan_envelope
from planning.envelope_export import export_envelope


def variants():
    base=dict(version='intent-v1',seed=17,
              context=dict(parcel=[[0,0],[10,0],[10,18],[0,18]],fronts={'F1':0},levels_m=[0,3.2,6]),
              building=dict(profile='barranco_residential',organization='compact'))
    for name,style,frame in (('joinery_republican_wood','republicano','wood'),
                             ('joinery_modern_metal','moderno','metal'),
                             ('joinery_classic_pvc','clasico','pvc')):
        request=copy.deepcopy(base)
        request['building']['facades']=[dict(body='main',front='F1',floors=[1,2],
            windows=dict(count=2,proportion='vertical',style=style,frame=frame))]
        yield name,request
    for name,material in (('doors_wood','wood'),('doors_metal','metal'),('doors_glass','glass')):
        request=copy.deepcopy(base)
        request['building']['site']={'door':{'position':'left','material':material}}
        request['building']['facades']=[dict(body='main',front='F1',floors=[1,2],
            windows=dict(count=2,proportion='vertical'))]
        yield name,request


def design_table(plan):
    table=[]
    for opening in plan.openings:
        table.append(dict(id=opening['id'],kind=opening['kind'],floor=opening['floor'],
                          style=opening['style'],material=opening['material'],
                          mechanism=opening['mechanism'],frame_width_m=opening['frame_width_m'],
                          leaves=opening.get('leaves'),width_m=round(opening['width_m'],3),
                          clear_width_m=round(opening['clear_width_m'],3),
                          sill_m=round(opening['sill_m'],3),head_m=round(opening['head_m'],3)))
    return table


def run(output):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    report=[]
    for name,request in variants():
        plan=plan_envelope(request, interiors=True)
        export_envelope(plan,output/name)
        report.append(dict(id=name,checks=plan.checks,openings=design_table(plan)))
    (output/'comparisons.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
    print(f'{len(report)} envelope variants exported to {output}')
    return report


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args().output)
