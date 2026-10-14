"""Local upper-volume capability demos, not measured reconstructions."""
from dataclasses import asdict, replace
import json
from build_after import (STEP, ROOT, render_case, write_zone_review, fingerprint,
    gpd, Polygon, ParcelContext, street_envelope, validate_mesh, export_glb, reconstruct)
from domain.theta import from_json, canonical, RoofBody, RoofControls, PlanRegion


def main():
    lots=gpd.read_file(ROOT/'data/lotes/BARRANCO_LM_geogpsperu.geojson').to_crs(32718)
    poses=json.loads((ROOT/'data/poses_barranco/metadata.json').read_text())['panoramas']
    offset=json.loads((ROOT/'data/cadastral_offset.json').read_text())
    for name,parent,region in [
        ('1138209_casona_amarilla_galeria','main',PlanRegion(front_edge=4,u=(.15,.35),depth=(.3,.5))),
        ('1138323_casona_amarilla_esquina','hall',PlanRegion(front_edge=6,width_reference='edge',u=(.4,.6),depth_m=(1.,4.)))]:
        folder=STEP/'lotes'/name;baseline=folder/'after_oracle'
        request=from_json((baseline/'request.json').read_text())
        request=replace(request,theta=replace(request.theta,roof_bodies=(RoofBody('upper_gable',parent,region,
            roof=RoofControls(kind='gable',slope_deg=25.)),)))
        result=reconstruct(request)
        out=folder/'after_roof_bodies';out.mkdir(exist_ok=True)
        validation=validate_mesh(result.mesh,Polygon(result.resolved.context.parcel),
            envelope=street_envelope(ParcelContext(result.resolved.context.parcel,explicit_fronts=result.resolved.context.fronts)))
        assert validation['envelope_test']=='passed'
        (out/'request.json').write_text(json.dumps(asdict(request),indent=2))
        (out/'resolved_theta.json').write_text(canonical(result.resolved))
        export_glb(result.mesh,out/'building.glb')
        lot=int(name.split('_')[0])
        count=render_case(result,out,lot,lots[lots.objectid==lot].iloc[0].geometry,poses,offset,'AFTER ROOF BODY')
        assert json.loads((out/'cameras.json').read_text())==json.loads((baseline/'cameras.json').read_text())
        write_zone_review(out,baseline,'AFTER ROOF BODY')
        (out/'manifest.json').write_text(json.dumps(dict(comparisons=count,mesh_sha256=fingerprint(result.mesh),validation=validation),indent=2))
        print(name,count,'views, envelope passed')


if __name__=='__main__':main()
