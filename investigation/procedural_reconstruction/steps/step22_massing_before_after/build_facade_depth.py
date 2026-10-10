"""Two depth-only comparisons from oracle recipes; fixed cameras/seeds."""
from dataclasses import asdict, replace
import json
from build_after import (STEP, ROOT, render_case, write_zone_review, fingerprint,
    gpd, Polygon, ParcelContext, street_envelope, validate_mesh, export_glb, reconstruct)
from domain.theta import from_json, canonical


def main():
    lots=gpd.read_file(ROOT/'data/lotes/BARRANCO_LM_geogpsperu.geojson').to_crs(32718)
    poses=json.loads((ROOT/'data/poses_barranco/metadata.json').read_text())['panoramas']
    offset=json.loads((ROOT/'data/cadastral_offset.json').read_text())
    for name,depth in [('1134299_casa_salmon_republicana',-.65),('1135370_edificio_crema_balcones',-.95)]:
        folder=STEP/'lotes'/name; baseline=folder/'after_oracle'
        request=from_json((baseline/'request.json').read_text())
        def split(c):
            if c.id!='main':return c
            zones=[]
            for z in c.zones:
                for floor,(lo,hi) in enumerate(zip(c.levels_m,c.levels_m[1:])):
                    controls=replace(z.controls,opening_programs=tuple(p for p in z.controls.opening_programs
                        if p.floor is None or p.floor==floor),order=z.controls.order if floor else None)
                    zones.append(replace(z,z_m=(lo,hi),controls=controls,offset_m=depth if floor==0 else 0.))
            return replace(c,zones=tuple(zones))
        components=tuple(split(c) for c in request.theta.massing.components)
        assert any(z.offset_m for c in components for z in c.zones)
        request=replace(request,theta=replace(request.theta,massing=replace(request.theta.massing,components=components)))
        result=reconstruct(request)
        out=folder/'after_facade_depth';out.mkdir(exist_ok=True)
        validation=validate_mesh(result.mesh,Polygon(result.resolved.context.parcel),
            envelope=street_envelope(ParcelContext(result.resolved.context.parcel,explicit_fronts=result.resolved.context.fronts)))
        assert validation['envelope_test']=='passed'
        (out/'request.json').write_text(json.dumps(asdict(request),indent=2))
        (out/'resolved_theta.json').write_text(canonical(result.resolved))
        export_glb(result.mesh,out/'building.glb')
        lot=int(name.split('_')[0])
        count=render_case(result,out,lot,lots[lots.objectid==lot].iloc[0].geometry,poses,offset,'AFTER FACADE DEPTH')
        assert json.loads((out/'cameras.json').read_text())==json.loads((baseline/'cameras.json').read_text())
        write_zone_review(out,baseline,'AFTER FACADE DEPTH')
        (out/'manifest.json').write_text(json.dumps(dict(comparisons=count,mesh_sha256=fingerprint(result.mesh),validation=validation),indent=2))
        print(name,count,'views; envelope passed')


if __name__=='__main__':main()
