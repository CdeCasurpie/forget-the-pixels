"""Metro monumental_portal demo: PHOTO | BayGroup | motif, fixed cameras."""
from dataclasses import asdict, replace
import json

from build_after import (STEP, ROOT, render_case, write_zone_review, fingerprint,
                         gpd, Polygon, ParcelContext, street_envelope,
                         validate_mesh, export_glb, reconstruct)
from domain.theta import from_json, ArchitecturalMotif, canonical


def main():
    folder=STEP/'lotes/1138323_casona_amarilla_esquina'
    baseline=folder/'after_bay_groups'
    request=from_json((baseline/'request.json').read_text())
    refs=[]
    for ref in request.theta.facades:
        if (ref.mass_role,ref.edge)==('hall:0',6):
            ref=replace(ref,controls=replace(ref.controls,motifs=(
                ArchitecturalMotif('monumental_portal',bay=3,opening_shape='arch'),)))
        refs.append(ref)
    request=replace(request,theta=replace(request.theta,facades=tuple(refs)))
    result=reconstruct(request)
    previous=json.loads((baseline/'resolved_theta.json').read_text())
    current=json.loads(canonical(result.resolved))
    for field in ('context','masses','roofs','boundaries','structures','site_zones'):
        assert previous[field]==current[field],field
    out=folder/'after_monumental_portal';out.mkdir(exist_ok=True)
    validation=validate_mesh(result.mesh,Polygon(result.resolved.context.parcel),
        envelope=street_envelope(ParcelContext(result.resolved.context.parcel,
                                               explicit_fronts=result.resolved.context.fronts)))
    assert validation['envelope_test']=='passed',validation
    (out/'request.json').write_text(json.dumps(asdict(request),indent=2)+'\n')
    (out/'resolved_theta.json').write_text(json.dumps(current,indent=2)+'\n')
    export_glb(result.mesh,out/'building.glb')
    lots=gpd.read_file(ROOT/'data/lotes/BARRANCO_LM_geogpsperu.geojson').to_crs(32718)
    poses=json.loads((ROOT/'data/poses_barranco/metadata.json').read_text())['panoramas']
    offset=json.loads((ROOT/'data/cadastral_offset.json').read_text())
    count=render_case(result,out,1138323,lots[lots.objectid==1138323].iloc[0].geometry,
                      poses,offset,'AFTER MONUMENTAL MOTIF')
    assert json.loads((out/'cameras.json').read_text())==json.loads((baseline/'cameras.json').read_text())
    write_zone_review(out,baseline,'AFTER MONUMENTAL MOTIF')
    manifest={'lot':1138323,'hypothesis':'BayGroup central con monumental_portal opt-in; solo fachada, sin cambios de masa.',
              'comparisons':count,'baseline':'../after_bay_groups',
              'mesh_sha256':fingerprint(result.mesh),'triangles':len(result.mesh.faces),'validation':validation}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print('Metro monumental_portal:',count,'comparativas; envelope passed')


if __name__=='__main__':main()
