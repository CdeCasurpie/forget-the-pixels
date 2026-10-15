"""Render foto vs malla con la proyección angular real (angular-enu-v1).

Uso:
  python3 -m apps.theta_author.experiments.manual_opus.render_comparisons \
    --request data/barranco/theta_experiments/<LOTE>_manual_v1/request.json \
    --package data/barranco/theta_author/runs/<RUN_ID>/package.json \
    --output data/barranco/theta_experiments/<LOTE>_manual_v1/runXX/comparisons
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'house_grammar' / 'src'))
sys.path.insert(0, str(ROOT))

from domain.theta import from_json
from pipeline.theta import reconstruct
from apps.theta_author.experiments.haiku_theta.rendering import angular_views


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request', type=Path, required=True)
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    request = from_json(args.request.read_text())
    result = reconstruct(request)
    package = json.loads(args.package.read_text())
    paths = angular_views(result.mesh, package['evidence'],
                          request.context.metric_origin[:2],
                          str(args.package.parent), str(args.output))
    print('\n'.join(paths))


if __name__ == '__main__':
    main()
