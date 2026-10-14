"""Declarative oracle benchmark; no image inspection or grammar changes."""
from dataclasses import asdict, replace
import argparse
import json
from build_after import (STEP, ROOT, render_case, write_zone_review, fingerprint,
    gpd, Polygon, ParcelContext, street_envelope, validate_mesh, export_glb, reconstruct)
from domain.theta import from_json, canonical, decode, FacadeControls, FacadeZone


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lot',type=int)
    args=parser.parse_args()
    recipes=json.loads((STEP/'oracle_recipes.json').read_text())
    lots=gpd.read_file(ROOT/'data/lotes/BARRANCO_LM_geogpsperu.geojson').to_crs(32718)
    poses=json.loads((ROOT/'data/poses_barranco/metadata.json').read_text())['panoramas']
    offset=json.loads((ROOT/'data/cadastral_offset.json').read_text())
    for name,recipe in recipes.items():
        if args.lot and int(name.split('_')[0])!=args.lot:continue
        folder=STEP/'lotes'/name; baseline=folder/recipe['baseline']
        request=from_json((folder/recipe['source']/'request.json').read_text())
        refs=list(request.theta.facades)
        components=list(request.theta.massing.components)
        for item in recipe['overrides']:
            index=next(i for i,f in enumerate(refs) if (f.mass_role,f.edge)==(item['mass_role'],item['edge']))
            old=refs[index]
            raw=asdict(old.controls) if item.get('merge') else {}
            if item.get('drop_existing_projections'):raw['projections']=[]
            raw.update(item['controls']); control=decode(FacadeControls,raw)
            if item.get('zone'):
                ci=next(i for i,c in enumerate(components) if c.id==item['mass_role'].split(':')[0])
                components[ci]=replace(components[ci],zones=(FacadeZone('front',control),))
                refs.pop(index)
            else:refs[index]=replace(old,controls=control)
        if recipe.get('primary_color'):
            request=replace(request,theta=replace(request.theta,primary_color=tuple(recipe['primary_color'])))
        request=replace(request,theta=replace(request.theta,facades=tuple(refs),
            massing=replace(request.theta.massing,components=tuple(components))))
        result=reconstruct(request)
        out=folder/'after_oracle';out.mkdir(exist_ok=True)
        validation=validate_mesh(result.mesh,Polygon(result.resolved.context.parcel),
            envelope=street_envelope(ParcelContext(result.resolved.context.parcel,explicit_fronts=result.resolved.context.fronts)))
        assert validation['envelope_test']=='passed',validation
        (out/'request.json').write_text(json.dumps(asdict(request),indent=2))
        (out/'resolved_theta.json').write_text(canonical(result.resolved))
        export_glb(result.mesh,out/'building.glb')
        lot=int(name.split('_')[0])
        count=render_case(result,out,lot,lots[lots.objectid==lot].iloc[0].geometry,poses,offset,'AFTER ORACLE')
        assert json.loads((out/'cameras.json').read_text())==json.loads((baseline/'cameras.json').read_text())
        write_zone_review(out,baseline,'AFTER ORACLE')
        (out/'manifest.json').write_text(json.dumps(dict(recipe=recipe,comparisons=count,
            mesh_sha256=fingerprint(result.mesh),validation=validation),indent=2))
        print(name,count,validation,flush=True)


if __name__=='__main__':main()
