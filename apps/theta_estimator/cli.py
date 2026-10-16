"""CLI de prueba manual del estimador. No toca B ni el catastro."""
from __future__ import annotations

import argparse
import json
import sys

from apps.theta_estimator.estimator import estimate, render_prompt


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='Prueba manual del estimador con opencode')
    parser.add_argument('--model', default='opencode/muse-spark-1.3-contributor-free')
    parser.add_argument('--agent', default=None)
    parser.add_argument('--timeout', type=int, default=180)
    sub = parser.add_subparsers(dest='command', required=True)
    probe = sub.add_parser('probe', help='Pregunta libre sobre una imagen')
    probe.add_argument('--image', required=True)
    probe.add_argument('--text', default='Describe qué hay en la imagen en dos frases.')
    est = sub.add_parser('estimate', help='Estimación estructurada del formulario')
    est.add_argument('--image', action='append', default=[], dest='images')
    est.add_argument('--lot', default=None)
    est.add_argument('--style-sheet', default=None, help='Lámina de referencia de estilos (se envía primera)')
    dump = sub.add_parser('dump-prompt', help='Muestra el prompt sin llamar a nada')
    dump.add_argument('--lot', default=None)
    dump.add_argument('--images', type=int, default=2)
    args = parser.parse_args(argv)
    if args.command == 'dump-prompt':
        print(render_prompt(args.lot, args.images))
        return 0
    if args.command == 'probe':
        from apps.theta_estimator.estimator import extract_text
        import subprocess
        command = ['opencode', 'run', '--model', args.model, '--format', 'json']
        if args.agent:
            command += ['--agent', args.agent]
        command += ['--file', args.image, args.text]
        try:
            completed = subprocess.run(command, capture_output=True, text=True, timeout=args.timeout)
        except Exception as e:
            print(f'ERROR: falló la llamada: {e}', file=sys.stderr)
            return 1
        if completed.returncode != 0:
            print(f'ERROR: opencode salió con {completed.returncode}: {(completed.stderr or "")[:1000]}', file=sys.stderr)
            return 1
        print(extract_text(completed.stdout or ''))
        return 0
    result = estimate(args.images, lot_id=args.lot, model=args.model, agent=args.agent, timeout_s=args.timeout,
                    style_sheet=args.style_sheet)
    print(json.dumps({k: getattr(result, k) for k in
                      ('floors', 'floor_height_m', 'first_floor_different', 'first_floor_height_m',
                       'style', 'notes', 'model', 'latency_s', 'error')}, indent=2, ensure_ascii=False))
    if result.error:
        print('--- raw ---')
        print((result.raw_text or '')[:2000])
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
