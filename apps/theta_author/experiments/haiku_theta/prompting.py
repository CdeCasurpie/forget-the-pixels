"""Paquete autocontenido por turno; sin depender de memoria de chat del proveedor."""
import base64
import json
import math
import re
from pathlib import Path

from .schemas import ROOT, response_schema
from .case import digest, write_json
from .workflow import next_stage
from .rendering import projected_wall_chart

HERE = Path(__file__).resolve().parent
GUIDE = ROOT/'house_grammar/docs/guia_theta'


def front_frames(context):
    ring=context['parcel']; frames=[]
    for edge in context['fronts']:
        a,b=ring[edge],ring[(edge+1)%len(ring)]
        dx,dy=b[0]-a[0],b[1]-a[1];length=math.hypot(dx,dy)
        tangent=[dx/length,dy/length]; inward=[-tangent[1],tangent[0]]
        coordinates=[[(p[0]-a[0])*v[0]+(p[1]-a[1])*v[1] for v in (tangent,inward)] for p in ring]
        frames.append(dict(front_edge=edge,origin_xy=a,along_unit=tangent,inward_unit=inward,
            edge_length_m=length,parcel_in_front_frame_m=coordinates,
            max_depth_m=max(p[1] for p in coordinates)))
    return frames

# Secciones completas pertinentes; separar tareas también implica separar referencias.
REFERENCES = {
    '01_lectura': ([1,2], [1,4,8,12]),
    '02_masas': ([1,2,3,7,9], [3]),
    '03_lenguaje': ([1,5,9], [1,2]),
    '04_puertas': ([2,4,5,9], [4,5]),
    '05_ventanas': ([2,4,9], [4]),
    '06_balcones': ([2,5,9], [6]),
    '07_miembros': ([2,5,9], [7]),
    '08_remates': ([2,5,6,9], [8,9,11]),
    '09_cubiertas': ([2,3,5,6,9], [10]),
    '10_sitio': ([2,3,5,9], [12,13]),
    '11_materiales': ([1,4,9], [14]),
    '12_revision': (list(range(1,10)), list(range(1,16))),
}


def sections(text, numbers):
    chunks = re.split(r'(?=^## \d+\.)',text,flags=re.MULTILINE)
    return '\n\n'.join(chunk for chunk in chunks
        if (m:=re.match(r'## (\d+)\.',chunk)) and int(m[1]) in numbers)


# Recortes del paquete: conservan lo que la etapa necesita y descartan la
# justificación repetida de etapas anteriores.
def trim_decisions(decisions):
    return [dict(stage=d['stage'],changes=d['changes'],blockers=d['blockers']) for d in decisions]


def trim_architecture(resolved):
    return dict(schema_version=resolved['schema_version'],masses=resolved['masses'],
                walls=resolved['walls'],roofs=resolved['roofs'],
                site_zones=resolved['site_zones'],completed=resolved['completed'],
                theta=resolved['theta'])


def trim_cameras(evidence):
    return [dict(id=e['id'],projection=e['projection'],attachment=e['attachment']) for e in evidence]


# Contratos necesarios por etapa; el resto infla el paquete sin uso.
CONTRACTS = {
    '01_lectura': ['InventoryItem'],
    '02_masas': ['PlanRegion', 'SupportControls', 'ArchitecturalMass'],
    '03_lenguaje': [],
    '04_puertas': ['Opening', 'DoorControls'],
    '05_ventanas': ['Opening'],
    '06_balcones': ['BalconyControls', 'RailingControls'],
    '07_miembros': ['VerticalMemberControls', 'MemberDesign'],
    '08_remates': ['CrownControls', 'CrownDesign', 'EntablatureControls',
                   'TrimControls', 'FacadeProjection', 'FacadeTopProfile'],
    '09_cubiertas': ['RoofControls', 'RoofOverride', 'RoofAssemblyControls',
                     'CanopyControls', 'RoofDesign', 'EaveDesign'],
    '10_sitio': ['SiteControls', 'EntranceControls', 'PlanRegion'],
    '11_materiales': ['MaterialControl', 'FacadeMaterialRegion'],
    '12_revision': [],
}


def contracts_for(stage):
    fields = json.loads((GUIDE / 'campos.json').read_text())
    names = CONTRACTS.get(stage)
    if names is None:
        return {name: fields[name] for name in fields}
    missing = [n for n in names if n not in fields]
    if missing:
        raise ValueError(f'Contratos ausentes en campos.json: {missing}')
    return {name: fields[name] for name in names}


def build_packet(case, state):
    case = Path(case)
    stage = next_stage(state)
    if stage is None:
        raise ValueError('No hay etapa pendiente.')
    inputs = case / 'inputs'
    evidence = json.loads((inputs / 'evidence.json').read_text())
    for e in evidence:
        if digest(inputs / e['attachment']) != e['sha256']:
            raise ValueError('Cambió una imagen congelada.')
    schema = response_schema(stage)
    contracts = contracts_for(stage)
    origin = state['request']['context']['metric_origin'][:2]
    context = dict(stage=stage, constraints=state['constraints'],
        human_parameters=json.loads((inputs / 'human.json').read_text()),
        manifest=json.loads((case / 'manifest.json').read_text()),
        front_frames=front_frames(state['request']['context']),
        parametric_scaffold=dict(id='principal',region=dict(front_edge=state['request']['context']['fronts'][0],
            u=[0,1],depth=[0,1],fit='parcel'),levels_m=state['floor_levels_m']),
        current_request=state['request'], floor_levels_m=state['floor_levels_m'],
        inventory=state['inventory'], accepted_decisions=trim_decisions(state['decisions']),
        resolved_architecture=trim_architecture(state['resolved_architecture']),
        resolved_walls=state['walls'], opening_ledger=state['opening_ledger'],
        cameras=trim_cameras(evidence), wall_projection_px=projected_wall_chart(state['walls'],evidence,origin),
        response_schema=schema, field_reference=contracts)
    if (case/'branch.json').exists():
        context['revision_instruction'] = json.loads((case/'branch.json').read_text())
    files = [HERE/'prompts/common.md',HERE/'prompts'/f'{stage}.md',GUIDE/'README.md',GUIDE/'CATALOGOS.md']
    text = '\n\n'.join(f'# FUENTE: {p.name}\n{p.read_text()}' for p in files[:2])
    for path, numbers in zip(files[2:],REFERENCES[stage]):
        text += f'\n\n# REFERENCIA COMPLETA DE SECCIONES PERTINENTES: {path.name}\n'+sections(path.read_text(),numbers)
    example_path = GUIDE/'ejemplos/casa_balcon_republicano.json'
    if stage not in ('01_lectura','12_revision'):
        text += '\n\n# EJEMPLO DE SINTAXIS (otra casa, no copiar apariencia)\n'+example_path.read_text()
    text += '\n\n# PAQUETE ACTUAL Y CONTRATO DE ESTA ETAPA\n'+json.dumps(context,ensure_ascii=False,indent=2)
    attachments = []
    for i,e in enumerate(evidence,1):
        attachments += [dict(path=f'inputs/{e["attachment"]}',role='FOTO LIMPIA',view_id=e['id']),
                        dict(path=f'inputs/target_{i:02d}.jpg',role='IDENTIFICACIÓN AUXILIAR',view_id=e['id'])]
    attachments.append(dict(path='inputs/plan.png',role='PLANO MÉTRICO',view_id=None))
    if state['last_artifact']:
        folder = case/state['last_artifact']
        for i,e in enumerate(evidence,1):
            image = folder/'comparisons'/f'{i:02d}_comparison.jpg'
            if image.exists():
                attachments.append(dict(path=str(image.relative_to(case)), role='COMPARACIÓN ACEPTADA',view_id=e['id']))
        for name in ['validation.json','topology_summary.json']:
            p = folder/name
            if p.exists():
                text += '\n\n# DIAGNÓSTICO '+name+'\n'+p.read_text()
    if stage == '12_revision' and not any(a['role']=='COMPARACIÓN ACEPTADA' for a in attachments):
        raise ValueError('La revisión visual requiere comparaciones generadas.')
    for a in attachments:
        a['sha256'] = digest(case/a['path'])
    hashes = {str(p.relative_to(ROOT)):digest(p) for p in [*files, example_path, GUIDE/'campos.json']}
    hashes.update({str(p.relative_to(ROOT)):digest(p) for p in HERE.glob('*.py')})
    hashes.update({str(p.relative_to(ROOT)):digest(p) for p in (ROOT/'house_grammar/src').rglob('*.py')})
    return dict(stage=stage,system='Eres autor arquitectónico incremental. Sigue el contrato de la etapa y las restricciones humanas.',
                prompt=text, attachments=attachments, response_schema=schema, source_hashes=hashes,
                reference_sections=dict(guide=REFERENCES[stage][0],catalogs=REFERENCES[stage][1]))


def message_body(case, packet, model='claude-haiku-4-5', max_tokens=16384, thinking_budget=4096):
    if thinking_budget and not 1024 <= thinking_budget < max_tokens:
        raise ValueError('thinking_budget debe ser 0 o estar entre 1024 y max_tokens-1.')
    content = [dict(type='text',text=packet['prompt'])]
    for a in packet['attachments']:
        path = Path(case)/a['path']
        if digest(path) != a['sha256']:
            raise ValueError('Adjunto cambió después de preparar el prompt.')
        content.append(dict(type='text',text=f"{a['role']} · view_id={a['view_id']} · {a['path']}"))
        content.append(dict(type='image',source=dict(type='base64',
            media_type='image/png' if path.suffix=='.png' else 'image/jpeg',
            data=base64.b64encode(path.read_bytes()).decode('ascii'))))
    thinking=dict(type='enabled',budget_tokens=thinking_budget) if thinking_budget else dict(type='disabled')
    return dict(model=model,max_tokens=max_tokens,thinking=thinking,system=packet['system'],
                messages=[dict(role='user',content=content)])


def save_packet(directory, packet):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    write_json(directory/'packet.json',packet)
    write_json(directory/'response_schema.json',packet['response_schema'])
    (directory/'prompt.txt').write_text(packet['prompt'])
