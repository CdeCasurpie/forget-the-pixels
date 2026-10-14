"""Twenty reproducible roofs/eaves/junctions, with actual tile meshes."""
import json
from dataclasses import asdict
from generar_frontones import HERE,base_request,facade,opening,save
from domain.theta import from_json
from modeling.theta import resolve_theta


def main(only=None):
    root=HERE/'catalogo_techos';index=[]
    cases=[
        ('01_azotea_tapa',dict(form='flat',covering='none',parapet_m=.65,cap='moulded')),
        ('02_una_agua_panel',dict(form='shed',covering='panel')),
        ('03_una_agua_teja',dict(form='shed',covering='curved_tile')),
        ('04_dos_aguas_teja_plana',dict(form='gable',covering='flat_tile')),
        ('05_cuatro_aguas',dict(form='hip',covering='curved_tile')),
        ('06_pabellon',dict(form='pavilion',covering='curved_tile')),
        ('07_banda_teja',dict(form='band',covering='curved_tile',rotation_deg=90,band_depth_m=1.8)),
        ('08_compuesto_L',dict(form='compound',covering='curved_tile')),
        ('09_canes_rectos',dict(form='shed',covering='panel',eave=dict(kind='exposed',overhang_m=.55))),
        ('10_canes_perfilados',dict(form='hip',covering='flat_tile',eave=dict(kind='profiled',overhang_m=.55))),
        ('11_tornapuntas',dict(form='shed',covering='panel',eave=dict(kind='braces'))),
        ('12_mensulas_curvas',dict(form='shed',covering='panel',eave=dict(kind='curved',spacing_m=2.))),
        ('13_alero_cerrado',dict(form='hip',covering='flat_tile',eave=dict(kind='cornice',soffit=True))),
        ('14_sol_sombra',dict(form='flat',covering='slats',material='wood',eave=dict(kind='exposed',material='metal',fascia_material='metal'))),
        ('15_fronton_hastial',dict(form='gable',covering='flat_tile',eave=dict(overhang_m=0))),
        ('16_fronton_segmental',dict(form='shed',covering='curved_tile',rotation_deg=90,slope_deg=10,eave=dict(overhang_m=0))),
        ('17_fronton_escalonado',dict(form='flat',covering='none',eave=dict(overhang_m=0))),
        ('18_alero_interrumpido',dict(form='shed',covering='panel',rotation_deg=90,slope_deg=10,eave=dict(kind='exposed'))),
        ('19_casona_compuesta',dict(form='compound',covering='curved_tile',eave=dict(kind='profiled'))),
        ('20_moderno_off',dict(form='gable',covering='panel',substrate_material='concrete',eave=dict(kind='clean',overhang_m=0,fascia=False)))
    ]
    for name,design in cases:
        if only and name[:2] not in only:
            report=json.loads((root/name/'manifest.json').read_text())
            report.update(roof_form=design['form'],covering=design['covering']);index.append(report)
            continue
        r=base_request('moderno' if name.startswith('20') else 'republicano');t=r['theta']
        footprint=[[6,6],[14,6],[14,12],[6,12]]
        if name.startswith('06'):footprint=[[7,6],[11,6],[14,9],[14,12],[11,15],[7,15],[4,12],[4,9]]
        if design['form']=='compound':footprint=[[6,6],[14,6],[14,10],[10,10],[10,14],[6,14]]
        t['masses']=[dict(role='house',footprint=footprint,levels_m=[0,4])]
        t['facades']=[facade('house:0',0,[opening('door',2.8,.12,1.4,2.7,door=dict(model='auto'))])]
        if name.startswith('06'):t['facades']=[]
        roof=dict(id='cubierta',mass_ref='house:0',design=design)
        if design['form']=='compound':roof['regions']=[[[6,6],[14,6],[14,10],[6,10]],[[6,6],[10,6],[10,14],[6,14]]]
        if name[:2] in ('11','12','14'):
            t['canopies']=[dict(id='marquesina',mass_ref='house:0',edge=0,u_m=1.5,width_m=4.,depth_m=1.5,height_m=3.2,
                                design=design,posts=name.startswith('14'))]
        else:t['roof_assemblies']=[roof]
        if name[:2] in ('15','16','17','18'):
            family={'15':'triangular','16':'segmental','17':'stepped','18':'triangular'}[name[:2]]
            t['crowns']=[dict(id='fronton',mass_ref='house:0',edge=0,u_m=0 if name.startswith('15') else 2.,width_m=8 if name.startswith('15') else 4.,height_m=1.6,
                              design=dict(family=family,thickness_m=.35,moulding_width_m=.14))]
            roof.update(crown_ref='fronton',junction='gable' if name.startswith('15') else 'behind')
        if name.startswith('19'):
            t['masses']=[dict(role='house',footprint=[[6,8],[14,8],[14,14],[6,14]],levels_m=[0,3.6,7.2]),
                         dict(role='wing',footprint=[[6,4],[10,4],[10,8],[6,8]],levels_m=[0,3.6,6.0]),
                         dict(role='porch',footprint=[[12,4],[14,4],[14,8],[12,8]],levels_m=[0,3.6])]
            t['facades']=[facade('house:0',0,[opening('door',4.4,.12,1.2,2.7,door=dict(model='auto')),
                                            opening('window',4.4,4.2,1.2,2.0)]),
                         facade('wing:0',0,[opening('window',.8,.8,2.2,1.8),opening('window',.8,4.0,2.2,1.65)]),
                         facade('porch:0',0,[opening('window',.4,.8,1.2,1.8)])]
            t['roof_assemblies']=[dict(id='principal',mass_ref='house:0',design=dict(form='hip',eave=dict(kind='profiled',overhang_m=.25))),
                                 dict(id='ala',mass_ref='wing:0',design=dict(form='gable',eave=dict(overhang_m=0)),crown_ref='fronton',junction='gable'),
                                 dict(id='lateral',mass_ref='porch:0',design=dict(form='shed',rotation_deg=90,slope_deg=12,eave=dict(kind='braces',overhang_m=.25)))]
            t['crowns']=[dict(id='fronton',mass_ref='wing:0',edge=0,u_m=0,width_m=4.,height_m=1.,design=dict(family='triangular'))]
            t['canopies']=[dict(id='ingreso',mass_ref='house:0',edge=0,u_m=4.2,width_m=1.6,depth_m=1.3,height_m=3.25,
                               design=dict(form='shed',covering='panel',eave=dict(kind='curved',spacing_m=1.5)))]
        out=root/name;report=save(r,out)
        req=from_json(json.dumps(r));resolved=resolve_theta(req.context,req.theta)
        (out/'resolved_roofs.json').write_text(json.dumps([asdict(x) for x in resolved.roof_assemblies],indent=2)+'\n')
        report['roof_form']=design['form'];report['covering']=design['covering'];index.append(report)
        print(name,report['triangles'],flush=True)
    (root/'index.json').write_text(json.dumps(index,indent=2)+'\n')
    (root/'README.md').write_text('# Techos, aleros y encuentros\n\n'+ '\n'.join(f"- [{e['name']}]({e['name']}/building.glb): {e['roof_form']}, {e['covering']}" for e in index)+'\n')


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--only',nargs='+',help='Existing catalogue: regenerate selected numbered cases')
    main(parser.parse_args().only)
