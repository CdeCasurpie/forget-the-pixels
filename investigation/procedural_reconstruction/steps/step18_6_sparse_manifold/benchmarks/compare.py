"""Reproducible numeric and visual comparison of the ten frozen buildings."""
from pathlib import Path
import csv
import json
import numpy as np
from PIL import Image, ImageDraw

STEP=Path(__file__).resolve().parents[1]


def compare(before='baseline',after='final_street'):
    reports=STEP/'reports'
    old={r['case']:r for r in csv.DictReader((reports/f'{before}.csv').open())}
    new={r['case']:r for r in csv.DictReader((reports/f'{after}.csv').open())}
    out=STEP/'renders_before_after';out.mkdir(exist_ok=True)
    results=[]
    for section,names in [('manual',list(old)[:5]),('cadastral',list(old)[5:])]:
        sheet=Image.new('RGB',(4*384,5*422),'white')
        drawer=ImageDraw.Draw(sheet)
        for row,name in enumerate(names):
            metrics={}
            for view in ('iso','street'):
                a=np.asarray(Image.open(STEP/'outputs'/before/'individual'/f'{name}_{view}.png').convert('RGB'))
                b=np.asarray(Image.open(STEP/'outputs'/after/'individual'/f'{name}_{view}.png').convert('RGB'))
                ma=np.max(np.abs(a.astype(int)-237),axis=2)>12
                mb=np.max(np.abs(b.astype(int)-237),axis=2)>12
                union=np.count_nonzero(ma|mb)
                metrics[f'{view}_mask_iou']=round(np.count_nonzero(ma&mb)/union,6) if union else 1.
                metrics[f'{view}_rgb_mae']=round(float(np.mean(np.abs(a.astype(float)-b))),4)
                col=0 if view=='iso' else 2
                for offset,image in enumerate((a,b)):
                    sheet.paste(Image.fromarray(image),(384*(col+offset),row*422+30))
            original,newrow=old[name],new[name]
            oldtri,newtri=int(original['triangles']),int(newrow['triangles'])
            result=dict(case=name,old_triangles=oldtri,new_triangles=newtri,
                reduction_pct=round(100*(1-newtri/oldtri),2),
                old_vertices=int(original['vertices']),new_vertices=int(newrow['vertices']),
                old_components=int(original['components']),new_components=int(newrow['components']),
                old_glb_bytes=int(original['glb_bytes']),new_glb_bytes=int(newrow['glb_bytes']),
                old_generation_s=float(original['generation_s']),new_generation_s=float(newrow['generation_s']),
                old_export_s=float(original['export_s']),new_export_s=float(newrow['export_s']),
                architecture_equal=original['architecture_sha256']==newrow['architecture_sha256'],
                old_topology_violations=int(original['topology_violations']),new_topology_violations=int(newrow['topology_violations']),
                **metrics)
            results.append(result)
            drawer.text((8,row*422+8),f'{name}  ISO before / after  STREET before / after',fill='black')
        sheet.save(out/f'{section}_before_after.png')
    with (reports/'COMPARISON.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(results[0]));writer.writeheader();writer.writerows(results)
    (reports/'COMPARISON.json').write_text(json.dumps(results,indent=2)+'\n')
    return results


if __name__=='__main__':
    for row in compare(): print(row['case'],row['reduction_pct'],row['iso_mask_iou'],row['architecture_equal'])
