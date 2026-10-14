"""Small reproducible catalogue of dimensioned access assemblies; no renders."""
import json
from dataclasses import asdict
from generar_frontones import HERE, base_request, opening, facade, save
from domain.theta import from_json
from modeling.theta import resolve_theta


def main():
    cases=[('umbral_y_descanso','steps',0.,dict(landing_m=.6)),
           ('dos_gradas','steps',.32,dict(landing_m=.9)),
           ('gradas_con_mejillas','steps',.64,dict(landing_m=1.1,cheek_height_m=.35)),
           ('escalinata_ancha','steps',.90,dict(width_m=3.,landing_m=1.2,tread_m=.32)),
           ('rampa_cochera','ramp',.36,dict(run_m=3.6,transition_m=.5,cheek_height_m=.12)),
           ('rampa_corta','ramp',.18,dict(run_m=2.4,transition_m=.4)),
           ('paso_zaguan','passage',0.,dict(run_m=3.,cheek_height_m=2.7)),
           ('camino_acceso','passage',0.,dict(run_m=4.,width_m=2.))]
    root=HERE/'catalogo_entradas';index=[]
    for name,kind,rise,params in cases:
        r=base_request();width=3. if name=='rampa_cochera' else 1.5
        op=opening('door',7.,rise,width,2.7,door=dict(model='auto',construction='panelled'))
        r['theta']['facades']=[facade('house:0',0,[op])]
        r['theta']['entrances']=[dict(id=name,mass_ref='house:0',edge=0,opening_index=0,kind=kind,**params)]
        out=root/name;entry=save(r,out)
        req=from_json(json.dumps(r));resolved=resolve_theta(req.context,req.theta)
        dimensions=asdict(resolved.entrances[0])
        (out/'medidas.json').write_text(json.dumps(dimensions,indent=2)+'\n')
        entry.update({k:dimensions[k] for k in ('width_m','length_m','step_count','riser_m','slope_deg')})
        index.append(entry)
    for name,switchback,run in [('escalera_recta',False,4.48),('escalera_retorno',True,2.24)]:
        r=base_request();controls=facade('house:0',0,[])['controls']
        stair=dict(u_m=6.,base_z_m=0.,target_z_m=2.88,flight_width_m=1.15,
                   run_m=run,step_count=16,switchback=switchback)
        controls['stairs']=[stair]
        r['theta']['facades']=[dict(mass_role='house:0',edge=0,controls=controls)]
        out=root/name;entry=save(r,out)
        dimensions=dict(**stair,tread_m=.28,riser_m=.18)
        (out/'medidas.json').write_text(json.dumps(dimensions,indent=2)+'\n')
        entry.update(width_m=1.15,length_m=run,step_count=16,riser_m=.18,slope_deg=32.735)
        index.append(entry)
    (root/'index.json').write_text(json.dumps(index,indent=2)+'\n')
    (root/'README.md').write_text('# Entradas y pasos\n\n'+
        '| Caso | Ancho | Desarrollo | Contrahuellas | Contrahuella | Pendiente máxima |\n'+
        '|---|---:|---:|---:|---:|---:|\n'+''.join(
            f"| [{e['name']}]({e['name']}/building.glb) | {e['width_m']:.2f} m | {e['length_m']:.2f} m | {e['step_count']} | {e['riser_m']:.3f} m | {e['slope_deg']:.2f}° |\n" for e in index)+
        '\nEl paso de zaguán es un corredor exterior abierto, con piso y laterales; no perfora la masa existente. Umbrales y hojas pertenecen a la puerta. Las dos escaleras altas muestran el generador existente (ancho de tramo 1.15 m), con su baranda sencilla.\n')
    print(f'{len(index)} accesos generados en {root}')


if __name__=='__main__':main()
