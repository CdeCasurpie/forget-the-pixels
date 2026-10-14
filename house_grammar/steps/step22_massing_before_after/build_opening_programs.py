"""Generate comparisons without visual inspection."""
from dataclasses import asdict, replace
import json
from build_after import (STEP, ROOT, render_case, write_zone_review, fingerprint,
    gpd, Polygon, ParcelContext, street_envelope, validate_mesh, export_glb, reconstruct)
from domain.theta import from_json, canonical, OpeningProgram, BayGroup, FacadeControls


def main():
    lots=gpd.read_file(ROOT/'data/lotes/BARRANCO_LM_geogpsperu.geojson').to_crs(32718)
    poses=json.loads((ROOT/'data/poses_barranco/metadata.json').read_text())['panoramas']
    offset=json.loads((ROOT/'data/cadastral_offset.json').read_text())
    for name,base in [('1137619_banco_neoclasico','after_architectural_order'),
                      ('1138183_bloque_moderno_balcones','after')]:
        folder=STEP/'lotes'/name; baseline=folder/base
        request=from_json((baseline/'request.json').read_text())
        refs=[]
        for f in request.theta.facades:
            c=f.controls
            if name.startswith('1138183') and (f.mass_role,f.edge)==('south:0',1):
                c=FacadeControls(bay_count=4,window_ratio=.65,window_height_m=1.9,sill_m=.8,balconies=False)
            if c.bay_groups:
                c=replace(c,opening_programs=(OpeningProgram(0,height_m=3.5,width_ratio=.68),
                    OpeningProgram(1,kind='door',height_m=3.8,sill_m=.04),
                    OpeningProgram(2,height_m=3.5,width_ratio=.68)))
            elif name.startswith('1138183') and c.mode=='repeat' and c.bay_count and c.bay_count>=4:
                count=c.bay_count
                c=replace(c,bay_count=None,bay_axes_m=None,
                    bay_groups=(BayGroup((0.,.5),count//2),BayGroup((.5,1.),count-count//2)),
                    opening_programs=(OpeningProgram(0,0,kind='gate',prefab='roller',height_m=2.2,sill_m=.04,width_ratio=.65),
                        OpeningProgram(1,0,kind='window',shape='rectangle',height_m=1.4,sill_m=.8,width_ratio=.7),
                        OpeningProgram(0,1,kind='window',height_m=1.2,sill_m=.9,width_ratio=.7)))
            refs.append(replace(f,controls=c))
        assert any(f.controls.opening_programs for f in refs)
        request=replace(request,theta=replace(request.theta,facades=tuple(refs)))
        result=reconstruct(request)
        out=folder/'after_opening_programs';out.mkdir(exist_ok=True)
        previous=json.loads((baseline/'resolved_theta.json').read_text())
        current=json.loads(canonical(result.resolved))
        for field in ('masses','roofs','context'):assert previous[field]==current[field]
        validation=validate_mesh(result.mesh,Polygon(result.resolved.context.parcel),
            envelope=street_envelope(ParcelContext(result.resolved.context.parcel,explicit_fronts=result.resolved.context.fronts)))
        assert validation['envelope_test']=='passed'
        (out/'request.json').write_text(json.dumps(asdict(request),indent=2))
        (out/'resolved_theta.json').write_text(json.dumps(current,indent=2))
        export_glb(result.mesh,out/'building.glb')
        lot=int(name.split('_')[0])
        count=render_case(result,out,lot,lots[lots.objectid==lot].iloc[0].geometry,poses,offset,'AFTER OPENING PROGRAM')
        assert json.loads((out/'cameras.json').read_text())==json.loads((baseline/'cameras.json').read_text())
        write_zone_review(out,baseline,'AFTER OPENING PROGRAM')
        (out/'manifest.json').write_text(json.dumps(dict(comparisons=count,mesh_sha256=fingerprint(result.mesh),validation=validation),indent=2))
        print(name,count,'comparisons; envelope passed',flush=True)


if __name__=='__main__':main()
