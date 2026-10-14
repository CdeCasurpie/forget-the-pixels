"""Small controllability experiment, not a synthetic training dataset."""
from dataclasses import asdict, replace
import json
from pathlib import Path
import numpy as np
import cv2
from run import run, ROOT
from domain.theta import *

HERE=Path(__file__).resolve().parent


def variants():
    p=ReconstructionContext(((0.,0.),(12.,0.),(12.,20.),(0.,20.)),(0,))
    t=ThetaCandidate(height_m=8.4,floors=3,family='quiet_house',
                     massing=MassingControls(pattern='stepped_back',front_setback_m=3.,upper_setback_m=2.5),
                     facade=FacadeControls(bay_count=3,balconies=False),primary_color=(.75,.75,.68))
    return p,dict(
        base=t,
        height=replace(t,height_m=10.2),
        floors=replace(t,floors=2),
        pattern=replace(t,massing=MassingControls(pattern='single_block',front_setback_m=3.)),
        setback=replace(t,massing=replace(t.massing,upper_setback_m=3.5)),
        bays=replace(t,facade=replace(t.facade,bay_count=4)),
        windows=replace(t,facade=replace(t.facade,window_ratio=.65)),
        balcony=replace(t,facade=replace(t.facade,balconies=True,balcony_depth_m=.9)),
        roof=replace(t,roof=RoofControls(kind='corrugated')),
        parapet=replace(t,roof=RoofControls(kind='flat',parapet_m=.9)),
        fence=replace(t,site=SiteControls(fence='reja')),
        color=replace(t,primary_color=(.35,.55,.72)))


def main():
    for source in sorted((HERE/'examples').glob('*.json')):
        run(source,HERE/'outputs'/source.stem,size=420)
    p,items=variants()
    outputs=HERE/'outputs'/'interventions'
    outputs.mkdir(parents=True,exist_ok=True)
    manifests={}
    tiles=[]
    for label,t in items.items():
        source=outputs/(label+'.json')
        source.write_text(json.dumps(asdict(ReconstructionRequest(p,t,NuisanceParameters(18))),indent=2)+'\n')
        manifest=run(source,outputs/label,size=360)
        manifests[label]=manifest
        tile=cv2.imread(str(outputs/label/'iso.png'))
        cv2.putText(tile,label,(12,340),cv2.FONT_HERSHEY_SIMPLEX,.6,(20,20,20),1,cv2.LINE_AA)
        tiles.append(tile)
    sheet=np.vstack([np.hstack(tiles[i:i+4]) for i in range(0,len(tiles),4)])
    cv2.imwrite(str(outputs/'contact_sheet.png'),sheet)
    report={'purpose':'one-factor interventions; dependent values derive, xi fixed',
            'variants':manifests,'all_mesh_fingerprints_distinct':len({m['mesh_sha256'] for m in manifests.values()})==len(manifests)}
    (outputs/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    assert report['all_mesh_fingerprints_distinct']


if __name__=='__main__':
    main()
