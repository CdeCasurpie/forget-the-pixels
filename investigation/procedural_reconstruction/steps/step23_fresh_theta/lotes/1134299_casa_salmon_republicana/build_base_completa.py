"""Complete facade/site program transferred onto the compact cadastral base."""
import json
import sys
from dataclasses import asdict, replace
from pathlib import Path

import geopandas as gpd
import numpy as np
from shapely.geometry import Polygon

ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT/'src'), str(ROOT/'steps/step22_massing_before_after'),
               str(ROOT/'steps/step23_fresh_theta')]
from domain.theta import from_json, decode, canonical, FacadeControls, FacadeOverride
from domain.architecture import ParcelContext
from modeling.base_massing import BaseFloor, with_base
from modeling.theta import resolve_theta
from modeling.grammar import street_envelope
from modeling.validation import validate_mesh
from modeling.exporters.glb_exporter import export_glb
from pipeline.theta import reconstruct
from build_after import render_case
from probar_base_simplificada import RECIPE

LOT = Path(__file__).resolve().parent


def build():
    original = from_json((LOT/'fresh/request.json').read_text())
    old = resolve_theta(original.context, original.theta)
    blank = FacadeControls(mode='explicit', openings=(), projections=())
    request = replace(original, evidence={}, theta=replace(original.theta,
                      facade=blank, facades=(), roofs=()))
    request = with_base(request, tuple(decode(BaseFloor, f) for f in RECIPE['floors']))
    base = resolve_theta(request.context, request.theta)
    overrides = []
    for wall in base.walls:
        if not wall.facade.is_front:
            continue
        a = np.asarray(wall.facade.vertex_a)
        t = (np.asarray(wall.facade.vertex_b)-a)/wall.facade.width_m
        # Match the physical facade plane, not obsolete component/edge indices.
        candidates = [w for w in old.walls if w.facade.is_front and
                      abs(np.dot(np.asarray(w.facade.vertex_a)-a,
                                 wall.facade.normal_xy)) < .01]
        if len(candidates) != 1:
            raise ValueError('Ambiguous facade correspondence')
        source = candidates[0].facade
        du = float(np.dot(np.asarray(source.vertex_a)-a, t))
        low, high = wall.base_z, wall.base_z+wall.height_m
        openings = []
        for op in source.openings:
            if low <= op.v_m and op.v_m+op.height_m <= high:
                openings.append(replace(op, u_m=op.u_m+du, v_m=op.v_m-low))
            elif op.v_m < high and op.v_m+op.height_m > low:
                raise ValueError('Opening crosses new floor boundary')
        projections = []
        for feature in source.projections:
            bottom, top = max(low, feature.v_m), min(high, feature.v_m+feature.height_m)
            if top <= bottom:
                continue
            if feature.kind != 'downpipe' and (bottom != feature.v_m or top != feature.v_m+feature.height_m):
                raise ValueError('Non-continuous ornament crosses new floor boundary')
            projections.append(replace(feature, u_m=feature.u_m+du,
                                       v_m=bottom-low, height_m=top-bottom))
        overrides.append(FacadeOverride(mass_role=wall.mass_role, edge=wall.edge,
            controls=FacadeControls(mode='explicit', openings=tuple(openings),
                                    projections=tuple(projections))))
    request = replace(request, theta=replace(request.theta, facades=tuple(overrides)))
    result = reconstruct(request)
    assert sum(len(w.facade.openings) for w in result.resolved.walls) == sum(
        len(w.facade.openings) for w in old.walls)
    assert result.resolved.boundaries == old.boundaries
    validation = validate_mesh(result.mesh, Polygon(result.resolved.context.parcel),
        envelope=street_envelope(ParcelContext(result.resolved.context.parcel,
                                               explicit_fronts=result.resolved.context.fronts)))
    out = LOT/'base_simplificada_completa'
    out.mkdir(exist_ok=True)
    (out/'base.json').write_text(json.dumps(RECIPE, indent=2)+'\n')
    (out/'request.json').write_text(json.dumps(asdict(request), indent=2)+'\n')
    (out/'resolved_theta.json').write_text(canonical(result.resolved)+'\n')
    export_glb(result.mesh, out/'building.glb')
    lots = gpd.read_file(ROOT/'data/lotes/BARRANCO_LM_geogpsperu.geojson').to_crs(32718)
    geom = lots[lots.objectid == 1134299].iloc[0].geometry
    poses = json.loads((ROOT/'data/poses_barranco/metadata.json').read_text())['panoramas']
    offset = json.loads((ROOT/'data/cadastral_offset.json').read_text())
    count = render_case(result, out, 1134299, geom, poses, offset,
                        after_label='BASE SIMPLIFICADA COMPLETA')
    (out/'manifest.json').write_text(json.dumps(dict(validation=validation, views=count,
        openings=sum(len(w.facade.openings) for w in result.resolved.walls),
        triangles=len(result.mesh.faces)), indent=2)+'\n')
    print(out, validation['envelope_test'], count, 'views')


if __name__ == '__main__':
    build()
