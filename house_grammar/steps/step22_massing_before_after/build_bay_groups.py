"""Two declarative BayGroup demos; existing AFTER artifacts are read-only."""
import argparse
from dataclasses import asdict, replace
import json

from build_after import (STEP, ROOT, render_case, write_zone_review, fingerprint,
                         gpd, Polygon, ParcelContext, street_envelope,
                         validate_mesh, export_glb, reconstruct)
from domain.theta import from_json, decode, FacadeControls, FacadeOverride, canonical


def make_demo_request(baseline, recipe):
    control=decode(FacadeControls,recipe['controls'])
    target=(recipe['mass_role'],recipe['edge'])
    overrides=tuple(f for f in baseline.theta.facades if (f.mass_role,f.edge)!=target)
    return replace(baseline,theta=replace(baseline.theta,
        facades=overrides+(FacadeOverride(*target,control),)))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lot',type=int,action='append')
    args=parser.parse_args()
    recipes=json.loads((STEP/'bay_group_recipes.json').read_text())
    lots=gpd.read_file(ROOT/'data/lotes/BARRANCO_LM_geogpsperu.geojson').to_crs(32718)
    poses=json.loads((ROOT/'data/poses_barranco/metadata.json').read_text())['panoramas']
    offset=json.loads((ROOT/'data/cadastral_offset.json').read_text())
    for name,recipe in recipes.items():
        lot=int(name.split('_')[0])
        if args.lot and lot not in args.lot:continue
        folder=STEP/'lotes'/name;baseline=folder/'after'
        request=make_demo_request(from_json((baseline/'request.json').read_text()),recipe)
        result=reconstruct(request)
        old=json.loads((baseline/'resolved_theta.json').read_text())
        current=json.loads(canonical(result.resolved))
        for field in ('context','masses','roofs','boundaries','structures','site_zones'):
            assert current[field]==old[field],field
        out=folder/'after_bay_groups';out.mkdir(exist_ok=True)
        validation=validate_mesh(result.mesh,Polygon(result.resolved.context.parcel),
            envelope=street_envelope(ParcelContext(result.resolved.context.parcel,explicit_fronts=result.resolved.context.fronts)))
        assert validation['envelope_test']=='passed',validation
        (out/'request.json').write_text(json.dumps(asdict(request),indent=2)+'\n')
        (out/'resolved_theta.json').write_text(json.dumps(current,indent=2)+'\n')
        export_glb(result.mesh,out/'building.glb')
        count=render_case(result,out,lot,lots[lots.objectid==lot].iloc[0].geometry,poses,offset,'AFTER BAYGROUP')
        assert json.loads((out/'cameras.json').read_text())==json.loads((baseline/'cameras.json').read_text())
        write_zone_review(out,baseline,'AFTER BAYGROUP')
        manifest={'lot':lot,'hypothesis':recipe['note'],'comparisons':count,
                  'baseline':'../after','baseline_mesh_sha256':json.loads((baseline/'manifest.json').read_text())['mesh_sha256'],
                  'mesh_sha256':fingerprint(result.mesh),'triangles':len(result.mesh.faces),'validation':validation}
        (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
        print(name,count,'views, envelope passed',flush=True)


if __name__=='__main__':main()
