"""BCP and Metro order demos from existing requests and unchanged cameras."""
from dataclasses import asdict, replace
import json

from build_after import (STEP, ROOT, render_case, write_zone_review, fingerprint,
                         gpd, Polygon, ParcelContext, street_envelope,
                         validate_mesh, export_glb, reconstruct)
from domain.theta import from_json, ArchitecturalOrder, canonical


def main():
    lots=gpd.read_file(ROOT/'data/lotes/BARRANCO_LM_geogpsperu.geojson').to_crs(32718)
    poses=json.loads((ROOT/'data/poses_barranco/metadata.json').read_text())['panoramas']
    offset=json.loads((ROOT/'data/cadastral_offset.json').read_text())
    for lot,name,baseline_name,target in (
        (1137619,'1137619_banco_neoclasico','after_bay_groups',('bank:0',5)),
        (1138323,'1138323_casona_amarilla_esquina','after_crown_profile',('hall:0',6)),
    ):
        folder=STEP/'lotes'/name
        baseline=folder/baseline_name
        request=from_json((baseline/'request.json').read_text())
        order=ArchitecturalOrder(pilaster_mode='bay_boundaries',paired_bays=(3,),
            plinth_height_m=.45,belt_courses_m=(),entablature_height_m=.35,cornice_height_m=.28)
        refs=tuple(replace(f,controls=replace(f.controls,order=order)) if (f.mass_role,f.edge)==target
                   else f for f in request.theta.facades)
        assert any(f.controls.order is not None for f in refs)
        request=replace(request,theta=replace(request.theta,facades=refs))
        result=reconstruct(request)
        previous=json.loads((baseline/'resolved_theta.json').read_text())
        current=json.loads(canonical(result.resolved))
        for field in ('context','masses','roofs','boundaries','structures','site_zones'):
            assert previous[field]==current[field],field
        out=folder/'after_architectural_order';out.mkdir(exist_ok=True)
        validation=validate_mesh(result.mesh,Polygon(result.resolved.context.parcel),
            envelope=street_envelope(ParcelContext(result.resolved.context.parcel,
                                                    explicit_fronts=result.resolved.context.fronts)))
        assert validation['envelope_test']=='passed',validation
        (out/'request.json').write_text(json.dumps(asdict(request),indent=2)+'\n')
        (out/'resolved_theta.json').write_text(json.dumps(current,indent=2)+'\n')
        export_glb(result.mesh,out/'building.glb')
        count=render_case(result,out,lot,lots[lots.objectid==lot].iloc[0].geometry,
                          poses,offset,'AFTER ARCHITECTURAL ORDER')
        assert json.loads((out/'cameras.json').read_text())==json.loads((baseline/'cameras.json').read_text())
        write_zone_review(out,baseline,'AFTER ARCHITECTURAL ORDER')
        (out/'manifest.json').write_text(json.dumps(dict(lot=lot,comparisons=count,
            baseline='../'+baseline_name,mesh_sha256=fingerprint(result.mesh),
            triangles=len(result.mesh.faces),validation=validation),indent=2)+'\n')
        print(name,count,'comparisons, envelope passed',flush=True)


if __name__=='__main__':main()
