"""Preparar, inspeccionar y ejecutar una etapa por turno; sin tocar servicios A/B."""
import argparse
import asyncio
from contextlib import contextmanager
import fcntl
import json
from pathlib import Path
import shutil

from .schemas import STAGES
from .case import prepare, write_json
from .workflow import apply_response, materialize, next_stage
from .prompting import build_packet, message_body, save_packet
from .rendering import angular_views
from .client import request, response_text
from domain.theta import canonical
from modeling.exporters.glb_exporter import export_glb


@contextmanager
def case_lock(case):
    with (Path(case)/'.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def load_state(case):
    return json.loads((Path(case)/'state.json').read_text())


def attempt_dir(case, stage):
    parent = Path(case)/'attempts'/stage
    parent.mkdir(parents=True,exist_ok=True)
    number = max([int(p.name) for p in parent.iterdir() if p.is_dir() and p.name.isdigit()],default=0)+1
    path = parent/f'{number:03d}'; path.mkdir()
    return path


def accept(case, state, text, directory, render=True):
    case, directory = Path(case),Path(directory)
    (directory/'response.txt').write_text(text)
    evidence = json.loads((case/'inputs/evidence.json').read_text())
    candidate, resolved = apply_response(state,text,[e['id'] for e in evidence])
    stage = next_stage(state)
    write_json(directory/'request.json',candidate['request'])
    (directory/'resolved_theta.json').write_text(canonical(resolved)+'\n')
    if stage not in ('01_lectura','12_revision'):
        result, validation, topology = materialize(candidate['request'])
        write_json(directory/'validation.json',validation)
        write_json(directory/'topology_summary.json',topology)
        if validation['envelope_test'] != 'passed':
            raise ValueError('La malla no pasa la envolvente.')
        # Las incidencias por conectividad se conservan; las anomalías de malla bloquean.
        serious = [v for v in topology['violations'] if any(v.get(k,0) for k in (
            'boundary_edges','non_manifold_edges','incoherent_edges','duplicate_faces','degenerate_faces'))]
        if serious:
            raise ValueError('Topología con anomalías distintas de conectividad; ver topology_summary.json.')
        export_glb(result.mesh,directory/'building.glb',mode='runtime')
        if render:
            angular_views(result.mesh,evidence,candidate['request']['context']['metric_origin'][:2],
                          case/'inputs',directory/'comparisons')
        candidate['last_artifact'] = str(directory.relative_to(case))
    write_json(directory/'state.json',candidate)
    write_json(directory/'status.json',dict(status='accepted',stage=stage))
    # El checkpoint apunta a una versión concreta e inmutable del intento.
    checkpoint = case/'checkpoints'/stage
    checkpoint.mkdir(parents=True,exist_ok=False)
    write_json(checkpoint/'state.json',candidate)
    write_json(checkpoint/'artifact.json',dict(path=str(directory.relative_to(case))))
    write_json(case/'state.json',candidate)
    return candidate


async def run_one(case, model, max_tokens, render=True, repairs=1, thinking_budget=4096):
    case = Path(case)
    state = load_state(case)
    packet = build_packet(case,state)
    body = message_body(case,packet,model,max_tokens,thinking_budget)
    for attempt in range(repairs+1):
        directory = attempt_dir(case,packet['stage'])
        save_packet(directory,packet)
        write_json(directory/'messages.json',body)
        try:
            data,metrics = await request(body)
            write_json(directory/'api_response.json',data)
            write_json(directory/'metrics.json',metrics)
        except Exception as exc:
            write_json(directory/'status.json',dict(status='transport_failed',error=str(exc)))
            raise
        try:
            text = response_text(data)
            # Solo se repara JSON/contrato/geometría, nunca una respuesta truncada.
        except ValueError as exc:
            write_json(directory/'status.json',dict(status='incomplete_response',error=str(exc)))
            raise
        try:
            return accept(case,state,text,directory,render)
        except (ValueError, TypeError, KeyError) as exc:
            write_json(directory/'status.json',dict(status='rejected',error=str(exc)))
            parsed = None
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                pass
            if attempt == repairs or (isinstance(parsed,dict) and parsed.get('blockers')):
                raise
            body['messages'] += [dict(role='assistant',content=text),dict(role='user',content=(
                'La validación rechazó esta propuesta: '+str(exc)+
                '\nCorrige SOLO la misma etapa; devuelve su objeto JSON completo. '
                'Conserva pisos/contexto y etapas anteriores. Si la corrección corresponde '
                'a otra etapa, usa blockers. No inventes evidencia.'))]
        except Exception as exc:
            write_json(directory/'status.json',dict(status='execution_failed',error=str(exc)))
            raise


def branch(case, output, before, note=''):
    case,output = Path(case),Path(output)
    state = load_state(case)
    if before not in state['accepted']:
        raise ValueError('Solo se bifurca antes de una etapa ya aceptada.')
    preceding = list(STAGES)[:list(STAGES).index(before)]
    checkpoint = preceding[-1] if preceding else '00_base'
    previous = json.loads((case/'checkpoints'/checkpoint/'state.json').read_text())
    output.mkdir(parents=True,exist_ok=False)
    shutil.copytree(case/'inputs',output/'inputs')
    shutil.copyfile(case/'manifest.json',output/'manifest.json')
    for stage in ['00_base',*preceding]:
        shutil.copytree(case/'checkpoints'/stage,output/'checkpoints'/stage)
    for stage in preceding:
        source = case/'attempts'/stage
        if source.exists():
            shutil.copytree(source,output/'attempts'/stage)
    write_json(output/'state.json',previous)
    write_json(output/'branch.json',dict(parent=str(case.resolve()),before=before,review_instruction=note))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command',required=True)
    p = sub.add_parser('prepare'); p.add_argument('--package',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True); p.add_argument('--editor',type=Path)
    p = sub.add_parser('packet'); p.add_argument('--case',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    for name in ['next','run']:
        p = sub.add_parser(name); p.add_argument('--case',type=Path,required=True)
        p.add_argument('--model',default='claude-haiku-4-5'); p.add_argument('--max-tokens',type=int,default=16384)
        p.add_argument('--repairs',type=int,choices=[0,1,2],default=1)
        p.add_argument('--thinking-budget',type=int,default=4096,help='0 desactiva; de otro modo >=1024 y menor que max-tokens.')
        p.add_argument('--no-render',action='store_true',help='Diagnóstico; revisión visual exige renders.')
        if name == 'run':
            p.add_argument('--through',choices=list(STAGES),required=True,help='Última etapa a ejecutar en esta invocación.')
    p = sub.add_parser('apply'); p.add_argument('--case',type=Path,required=True)
    p.add_argument('--response',type=Path,required=True); p.add_argument('--no-render',action='store_true')
    p = sub.add_parser('branch'); p.add_argument('--case',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True); p.add_argument('--before',choices=list(STAGES),required=True)
    p.add_argument('--note',default='',help='Corrección humana que recibirán los turnos de la nueva rama.')
    args = parser.parse_args()
    if args.command == 'prepare':
        state = prepare(args.package,args.output,args.editor)
        save_packet(args.output/'next_packet',build_packet(args.output,state))
        print(f'Caso preparado: {args.output}; pendiente: {next_stage(state)}')
        return
    with case_lock(args.case):
        if args.command == 'packet':
            save_packet(args.output,build_packet(args.case,load_state(args.case)))
        elif args.command == 'branch':
            branch(args.case,args.output,args.before,args.note)
        elif args.command == 'apply':
            state = load_state(args.case); directory = attempt_dir(args.case,next_stage(state))
            save_packet(directory,build_packet(args.case,state))
            try:
                accept(args.case,state,args.response.read_text(),directory,not args.no_render)
            except Exception as exc:
                write_json(directory/'status.json',dict(status='rejected',error=str(exc)))
                raise
        else:
            while (stage := next_stage(load_state(args.case))) is not None:
                if args.command == 'run' and list(STAGES).index(stage)>list(STAGES).index(args.through):
                    break
                state = asyncio.run(run_one(args.case,args.model,args.max_tokens,not args.no_render,args.repairs,args.thinking_budget))
                print(f'{stage}: aceptada; siguiente: {next_stage(state)}')
                if state.get('review'):
                    print('Revisión visual:',state['review']['verdict'])
                if args.command == 'next':
                    break


if __name__ == '__main__':
    main()
