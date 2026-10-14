"""Summarize explicit, completed, derived and nuisance fields in five V0 examples."""
from pathlib import Path
import json
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]/'src'))
from domain.theta import from_json
from modeling.theta import resolve_theta


def leaves(value,path=''):
    if isinstance(value,dict):
        for key,item in value.items():
            yield from leaves(item,f'{path}.{key}' if path else key)
    elif isinstance(value,list):
        if not value:
            yield path,[]
        else:
            for index,item in enumerate(value):
                yield from leaves(item,f'{path}[{index}]')
    else:
        yield path,value


def main():
    rows=[]
    for path in sorted((HERE/'examples').glob('*.json')):
        raw=json.loads(path.read_text())
        request=from_json(path.read_text())
        resolved=resolve_theta(request.context,request.theta)
        explicit={name:value for name,value in leaves(raw['theta']) if value is not None}
        rows.append(dict(example=path.name,explicit=explicit,
                         completed=resolved.completion_details,
                         derived=dict(floor_height_m=resolved.theta.height_m/resolved.theta.floors,
                                      mass_refs=[mass.id for mass in resolved.masses],
                                      wall_count=len(resolved.walls),roof_count=len(resolved.roofs),
                                      opening_count=sum(len(w.facade.openings) for w in resolved.walls)),
                         nuisance=dict(seed=request.nuisance.seed,curtains=request.nuisance.curtains)))
    (HERE/'EXAMPLE_RESOLUTION_SUMMARY.json').write_text(json.dumps(rows,indent=2,ensure_ascii=False)+'\n')
    summary=['# Qué describen realmente los 5 ejemplos','',
             'Datos generados por `python steps/step18_theta_interface/audit_examples.py`.','',
             '| Ejemplo | Campos θ explícitos | Completados | Masas | Vanos resueltos | ξ |',
             '|---|---:|---:|---:|---:|---|']
    for row in rows:
        summary.append(f"| {row['example']} | {len(row['explicit'])} | {len(row['completed'])} | {len(row['derived']['mass_refs'])} | {row['derived']['opening_count']} | seed={row['nuisance']['seed']}, cortinas={row['nuisance']['curtains']} |")
    summary.extend(['','El JSON detallado enumera cada campo explícito, su valor completado y la regla de origen.','Las cotas de niveles se derivan de altura y pisos; las exposiciones/vanos repetidos se derivan de masas, familia y bays.','Ningún campo marcado `prior/completed` se convierte en `observed`.'])
    (HERE/'EXAMPLE_RESOLUTION_SUMMARY.md').write_text('\n'.join(summary)+'\n')
    print('\n'.join(summary))


if __name__=='__main__':
    main()
