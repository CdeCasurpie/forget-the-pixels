"""Compile roof-anchored bodies into the existing compositional pipeline.

Real volumes reuse exposure, roof subtraction and opening materialization.
No facade-only silhouette is used as a substitute for a roof behind it.
"""
from dataclasses import replace
import math
from domain.theta import MassComponent


def expand_roof_bodies(theta):
    if not theta.roof_bodies:return theta
    if theta.schema_version!='0.3' or not theta.massing.components:
        raise ValueError('RoofBody requires schema 0.3 and components')
    components=list(theta.massing.components)
    originals={c.id:c for c in components}
    ids=set(originals)
    for body in theta.roof_bodies:
        if body.parent not in originals or body.id in ids:
            raise ValueError('RoofBody needs an existing parent and a unique id')
        if not math.isfinite(body.height_m) or not 2.2<=body.height_m<=6.:
            raise ValueError('RoofBody height_m must be 2.2..6 m')
        base=originals[body.parent].levels_m[-1]
        components.append(MassComponent(body.id,body.region,(base,base+body.height_m),
                                        roof=body.roof,facade=body.facade))
        ids.add(body.id)
    return replace(theta,roof_bodies=(),height_m=None,floors=None,
                   massing=replace(theta.massing,components=tuple(components)))
