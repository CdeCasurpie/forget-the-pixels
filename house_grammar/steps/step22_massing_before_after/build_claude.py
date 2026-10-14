"""Three ornament studies, reproducible from explicit facade-local theta inputs."""
from dataclasses import asdict, replace
import argparse
import json
from build_after import (STEP, ROOT, gpd, Polygon, ParcelContext, render_case,
                         write_zone_review, fingerprint, street_envelope,
                         validate_mesh, export_glb, reconstruct)
from domain.theta import (from_json, canonical, FacadeControls, FacadeOverride,
                          MaterialControl, FacadeTopProfile)
from domain.models import FacadeProjection
from modeling.theta import resolve_theta


STUDIES = {
    '1134299_casa_salmon_republicana': 'neoclassical',
    '1134486_restaurante_terraza': 'composite',
    '1135369_esquina_demolicion': 'neoclassical',
    '1135370_edificio_crema_balcones': 'modern',
    '1135382_casa_blanca_esquina': 'neoclassical',
    '1135384_comercio_ladrillo_blanco': 'modern',
    '1135572_casa_ladrillo_balcon': 'neoclassical',
    '1135847_local_comercial_bajo': 'gallery',
    '1137173_grifo_marquesina': 'modern',
    '1137568_comercio_blanco_dos_plantas': 'composite',
    '1137619_banco_neoclasico': 'neoclassical',
    '1138183_bloque_moderno_balcones': 'modern',
    '1138209_casona_amarilla_galeria': 'gallery',
    '1138261_edificio_azul_cristal': 'modern',
    '1138283_vivienda_verde_tres_pisos': 'composite',
    '1138316_muro_local_bajo': 'modern',
    '1138323_casona_amarilla_esquina': 'composite',
    '1138401_comercio_rojo_rejas': 'gallery',
    '1138477_edificio_blanco_balcones': 'modern',
}


def ornament_request(request, style, lot_name=''):
    resolved = resolve_theta(request.context, request.theta)
    overrides=[]
    for wall in resolved.walls:
        f=wall.facade; length=f.width_m; height=wall.height_m
        if not f.has_program or not f.openings:
            continue
        features=[];ops=[]
        def add(kind,u,z,w,h,d=.20,material='frame',label='',border=.18,rise=None):
            features.append(FacadeProjection(kind,u,z,w,h,d,material,
                                            border_width_m=border,label=label,arch_rise_m=rise))
        profile = None
        if f.top_profile:
            p=f.top_profile
            profile=FacadeTopProfile(tuple((u/length,z-p.base_z_m) for u,z in p.points_m),
                                      p.depth_m,.22,.16,p.trim_material_slot)
        portal = next((o for o in f.openings if o.kind=='door'),None)
        monumental = style=='composite' and '1138323' in lot_name and portal and (length>25 or len(f.openings)==1)
        if monumental:
            cx=(portal.u_m+portal.width_m/2)/length
            half=min(.43,max(3.0,(portal.width_m/2+.22)/.52)/length)
            # A shouldered, curved crest on the actual wall, not a roof box.
            shape=((-1,0),(-1,.25),(-.82,.25),(-.82,.60),(-.60,.60),
                   (-.60,.95),(-.40,1.28),(-.2,1.50),(0,1.58),
                   (.2,1.50),(.40,1.28),(.60,.95),(.60,.60),(.82,.60),
                   (.82,.25),(1,.25),(1,0))
            profile=FacadeTopProfile(((0.,0.),)+tuple((cx+x*half,z) for x,z in shape)+((1.,0.),),
                                      .38,.22,.18,'frame')
        for op in f.openings:
            op=replace(op,recess_m=.22 if style not in ('gallery','modern') else .16,curtain=0.)
            if style=='modern':
                op=replace(op,mullion_columns=2 if op.width_m<2.2 else 3,mullion_rows=2 if op.height_m<1.8 else 3)
            elif style=='gallery':
                op=replace(op,mullion_columns=3 if op.width_m>1.8 else 2,mullion_rows=5)
                if op.prefab=='open':op=replace(op,style='vestibule')
            elif style=='neoclassical':
                op=replace(op,grille=op.kind=='window',grille_pattern='diamond')
            elif op.kind=='door':
                op=replace(op,prefab='open',grille=True,style='vestibule')
                if monumental and op.u_m==portal.u_m:
                    op=replace(op,height_m=height+.65-op.v_m,arch_rise_m=.9)
            ops.append(op)
            b=.12 if style=='modern' else (.16 if style=='gallery' else .22)
            if op.u_m>b and op.u_m+op.width_m+b<length:
                add('segmental_surround' if op.shape=='arch' else 'moulded_surround',
                    op.u_m-b,max(0.,op.v_m-b),op.width_m+2*b,
                    op.height_m+b+min(b,op.v_m),.20 if style=='gallery' else .28,border=b,
                    rise=(op.arch_rise_m if op.arch_rise_m is not None else min(op.width_m/2,op.height_m/2)) if op.shape=='arch' else None)
            if op.kind=='window' and op.v_m>.65:
                add('frame',op.u_m,op.v_m-.45,op.width_m,.30,.09,border=.055)
            if style=='gallery' and op.v_m>3.5:
                add('classical_cornice',max(.04,op.u_m-.2),op.v_m+op.height_m+.20,
                    min(op.width_m+.4,length-op.u_m-.1),.20,.24)
        for feature in f.projections:
            if feature.kind in ('pilaster',):
                features.append(replace(feature,kind='composite_pilaster' if style=='composite' else 'classical_pilaster',
                                        u_m=min(feature.u_m,length-max(.38,feature.width_m)-.04),
                                        width_m=max(.38,feature.width_m),depth_m=.28))
            elif feature.kind not in ('cornice','denticulated_cornice','pediment','frame','panel','shutter','awning','downpipe'):
                features.append(replace(feature,label='classical') if feature.kind=='gallery' else feature)
        if style=='gallery':
            add('classical_cornice',.05,height-.32,length-.10,.30,.30)
            add('ledge',.05,3.48,length-.10,.16,.22)
            # Upper windows have shallow balconies with turned silhouettes.
            if not any(p.kind=='gallery' for p in features):
                for op in ops:
                    if op.v_m>3.5 and op.width_m>1.8:
                        add('balcony',op.u_m-.15,op.v_m-.05,op.width_m+.30,1.05,.55,label='turned')
        elif style=='modern':
            for lo,hi in [(.04,length-.04)]:
                if hi-lo>.3:
                    add('cornice',lo,height-.30,hi-lo,.28,.22)
                    add('ledge',lo,height-.52,hi-lo,.12,.16)
        else:
            intervals=[(.04,length-.04)]
            if monumental:
                intervals=[(.04,max(.05,portal.u_m-.55)),
                           (min(length-.05,portal.u_m+portal.width_m+.55),length-.04)]
                sign_w=min(2.,portal.width_m*.84)
                add('oval_sign',portal.u_m+(portal.width_m-sign_w)/2,height-.90,
                    sign_w,1.20,.34,label='METRO')
            for lo,hi in intervals:
                if hi-lo>.3:
                    add('classical_cornice',lo,height-.54,hi-lo,.52,.46)
                    add('ledge',lo,height-.86,hi-lo,.16,.22)
            if style=='neoclassical' and '1137619' in lot_name:
                for frac in ((.25,.75) if length>12 else (.5,)):
                    sw=min(2.,length*.45)
                    add('sign_box',length*frac-sw/2,height-.38,sw,.65,.54,label='BCP')
            # The dark plinth is segmented at entrances so it never seals a door.
            cursor=.02
            for op in sorted((o for o in ops if o.v_m<.3),key=lambda o:o.u_m):
                if op.u_m>cursor:
                    add('panel',cursor,0.,op.u_m-cursor,.42,.08,'accent')
                cursor=op.u_m+op.width_m
            if cursor<length-.02:
                add('panel',cursor,0.,length-.02-cursor,.42,.08,'accent')
        controls=FacadeControls(mode='explicit',openings=tuple(ops),projections=tuple(features),
                                material_regions=(),top_profile=profile)
        overrides.append(FacadeOverride(wall.mass_role,wall.edge,controls))
    colors={'frame':(.94,.93,.87),'stone':(.86,.85,.78),
            'accent':(.22,.26,.27),'sign':(.10,.15,.17),
            'roof':(.33,.29,.28),'roof_tile':(.34,.26,.24)}
    if style=='neoclassical':
        colors.update(frame=(.69,.72,.69),stone=(.52,.56,.53),sign=(.37,.42,.40))
    if style=='gallery':colors.update(wood=(.92,.91,.84),accent=(.60,.61,.56))
    materials={m.slot:m for m in request.theta.materials}
    for slot,color in colors.items():
        materials[slot]=MaterialControl(slot,'plaster' if slot in ('frame','stone','wood') else slot,color)
    theta=replace(request.theta,facades=tuple(overrides),materials=tuple(materials.values()))
    return replace(request,theta=theta,nuisance=replace(request.nuisance,curtains=False),evidence={})


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lot',type=int)
    args=parser.parse_args()
    lots=gpd.read_file(ROOT/'data/lotes/BARRANCO_LM_geogpsperu.geojson').to_crs(32718)
    poses=json.loads((ROOT/'data/poses_barranco/metadata.json').read_text())['panoramas']
    offset=json.loads((ROOT/'data/cadastral_offset.json').read_text())
    for name,style in STUDIES.items():
        lot=int(name.split('_')[0])
        if args.lot and args.lot!=lot:continue
        folder=STEP/'lotes'/name
        baseline=folder/'after_oracle' if (folder/'after_oracle'/'request.json').exists() else folder/'after'
        baseline_tag='after_oracle' if baseline.name=='after_oracle' else 'after'
        base_label='AFTER ORACLE' if baseline_tag=='after_oracle' else 'AFTER 0.3 BASE'
        out=folder/'after_claude'
        request=ornament_request(from_json((baseline/'request.json').read_text()),style,name)
        result=reconstruct(request)
        validation=validate_mesh(result.mesh,Polygon(result.resolved.context.parcel),
            envelope=street_envelope(ParcelContext(result.resolved.context.parcel,explicit_fronts=result.resolved.context.fronts)))
        assert validation['envelope_test']=='passed',validation
        out.mkdir(exist_ok=True)
        (out/'request.json').write_text(json.dumps(asdict(request),indent=2))
        (out/'resolved_theta.json').write_text(canonical(result.resolved))
        export_glb(result.mesh,out/'building.glb')
        count=render_case(result,out,lot,lots[lots.objectid==lot].iloc[0].geometry,poses,offset,'AFTER CLAUDE')
        assert json.loads((out/'cameras.json').read_text())==json.loads((baseline/'cameras.json').read_text())
        write_zone_review(out,baseline,'AFTER CLAUDE',baseline_label=base_label)
        (out/'manifest.json').write_text(json.dumps(dict(style=style,baseline=baseline_tag,
            comparisons=count,mesh_sha256=fingerprint(result.mesh),validation=validation),indent=2))
        print(name,count,validation['triangles'],validation['envelope_test'],flush=True)


if __name__=='__main__':main()
