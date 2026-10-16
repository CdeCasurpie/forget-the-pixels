"""Explicit, offline migration of component roofs; never used by the resolver.

Usage: python migrar_techos.py request.json --output migrated.json
Existing catalog replacements win. Geometry/orientation still needs visual review.
"""
import argparse
import copy
import json
import math
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'src'))
from domain.theta import from_json
from modeling.assembly import region_frame
from modeling.theta import resolve_theta, _context


def migrate(data):
    data=copy.deepcopy(data)
    theta=data['theta']
    req=from_json(json.dumps(data))
    assemblies=theta.setdefault('roof_assemblies',[])
    managed={a['mass_ref'] for a in assemblies if a.get('enabled',True)}
    ids={a['id'] for a in assemblies}
    items=[*zip(theta.get('massing',{}).get('components',[]),req.theta.massing.components),
           *zip(theta.get('roof_bodies',[]),req.theta.roof_bodies)]
    for raw,item in items:
        old=raw.get('roof') or {}
        kind=old.get('kind')
        if kind in (None,'flat'):continue
        if kind not in ('tile_shed','gable','corrugated'):
            raise ValueError('Unknown legacy roof '+str(kind))
        ref=item.id+':0'
        if ref not in managed:
            _,t,n,_=region_frame(_context(req.context),item.region)
            axis=t if kind=='gable' else n
            name=item.id+'_roof'
            if name in ids:raise ValueError('Migration roof id conflict: '+name)
            ids.add(name)
            assemblies.append(dict(id=name,mass_ref=ref,design=dict(
                form={'tile_shed':'shed','gable':'gable','corrugated':'flat'}[kind],
                covering='corrugated' if kind=='corrugated' else 'curved_tile',
                material='roof' if kind=='corrugated' else 'roof_tile',
                slope_deg=old.get('slope_deg') or 12.,
                rotation_deg=math.degrees(math.atan2(axis[1],axis[0])),
                detail='full',eave=dict(kind='clean',overhang_m=0.,fascia=False))))
            managed.add(ref)
        raw['roof']={**old,'kind':'flat','slope_deg':None}
    # Global roofs and ambiguous role overrides need an authored mass selection.
    # Resolution fails explicitly rather than guessing that selection or tolerance.
    req=from_json(json.dumps(data))
    resolve_theta(req.context,req.theta)
    return data


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('request',type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    result=migrate(json.loads(args.request.read_text()))
    args.output.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
