"""Resolve accesses without inventing doors or silently clipping their runs."""
from dataclasses import dataclass, asdict
import math
import numpy as np
from shapely.geometry import Polygon, box
from shapely.ops import unary_union
from modeling.assembly import mass_polygon
from domain.entrances import EntranceControls


@dataclass(frozen=True)
class ResolvedEntrance:
    controls: EntranceControls
    origin: tuple[float,float]
    tangent: tuple[float,float]
    normal: tuple[float,float]
    width_m: float
    top_z_m: float
    step_count: int
    riser_m: float
    length_m: float
    slope_deg: float


def resolve_entrances(theta,walls,masses,envelope,materials):
    result=[];ids=set();occupied=[]
    for c in theta.entrances:
        if not c.id or c.id in ids:raise ValueError('Duplicate/empty entrance id')
        ids.add(c.id)
        if c.kind not in ('steps','ramp','passage'):raise ValueError('Unknown entrance kind')
        values=[v for v in asdict(c).values() if isinstance(v,(float,int))]
        if not all(math.isfinite(v) for v in values):raise ValueError('Nonfinite entrance dimensions')
        if not (.05<=c.slab_m<=.4 and .24<=c.tread_m<=.45 and .10<=c.max_riser_m<=.20
                and .3<=c.landing_m<=5 and .3<=c.run_m<=20 and 0<=c.nosing_m<=.05
                and .06<=c.side_width_m<=.4 and 0<=c.cheek_height_m<=3 and c.width_m>=0):
            raise ValueError('Invalid entrance dimensions')
        if c.material not in materials or c.side_material not in materials:raise ValueError('Unknown entrance material')
        candidates=[w for w in walls if w.mass_role==c.mass_ref and w.edge==c.edge]
        if len(candidates)!=1:raise ValueError('Entrance needs unambiguous wall anchor')
        w=candidates[0];f=w.facade
        if not 0<=c.opening_index<len(f.openings):raise ValueError('Entrance opening missing')
        op=f.openings[c.opening_index]
        if op.kind not in ('door','gate'):raise ValueError('Entrance requires door or gate')
        width=c.width_m or op.width_m
        if not op.width_m<=width<=12:raise ValueError('Entrance width must cover doorway')
        top=w.base_z+op.v_m;rise=top-c.ground_z_m
        if rise<0 or rise>3:raise ValueError('Invalid entrance level difference')
        count=max(1,math.ceil(rise/c.max_riser_m)) if rise and c.kind=='steps' else 0
        length=c.landing_m+max(0,count-1)*c.tread_m if c.kind=='steps' else c.run_m
        slope=0.
        if c.kind=='ramp':
            if not 0<c.transition_m<c.run_m/2:raise ValueError('Invalid ramp transitions')
            slope=math.degrees(math.atan2(rise,c.run_m-c.transition_m))
            if slope>15:raise ValueError('Ramp slope exceeds 15 degrees')
        if c.kind=='passage' and rise>1e-6:raise ValueError('Passage must join equal levels')
        t=(np.asarray(f.vertex_b)-f.vertex_a)/f.width_m;n=np.asarray(f.normal_xy)
        u=op.u_m+(op.width_m-width)/2
        if u<0 or u+width>f.width_m:raise ValueError('Entrance exceeds facade width')
        if w.visible_domains and not unary_union([box(*r) for r in w.visible_domains]).buffer(1e-6).covers(box(op.u_m,op.v_m,op.u_m+op.width_m,op.v_m+op.height_m)):
            raise ValueError('Entrance doorway is hidden')
        a=np.asarray(f.vertex_a)+t*u+n*w.plane_offset_m
        extra=c.side_width_m if c.cheek_height_m else 0.
        outer_length=length+(c.nosing_m if c.kind=='steps' and count else 0.)
        footprint=Polygon([a+t*x+n*d for x,d in ((-extra,0),(width+extra,0),(width+extra,outer_length),(-extra,outer_length))])
        if not envelope.buffer(1e-6).covers(footprint):raise ValueError('Entrance outside envelope')
        for m in masses:
            if m.base_z<top+c.cheek_height_m+.01 and m.roof_z>c.ground_z_m and footprint.intersection(mass_polygon(m)).area>1e-6:
                raise ValueError('Entrance intersects building mass')
        if any(footprint.intersection(p).area>1e-6 for p in occupied):raise ValueError('Overlapping entrances')
        occupied.append(footprint)
        result.append(ResolvedEntrance(c,tuple(a),tuple(t),tuple(n),width,top,count,rise/count if count else 0.,length,slope))
    return tuple(result)


def build_entrance(mb,r):
    c=r.controls;a=np.asarray(r.origin);t=np.asarray(r.tangent);n=np.asarray(r.normal)
    top=r.top_z_m;low=c.ground_z_m;length=r.length_m
    if c.kind=='steps':
        profile=[(0,top),(c.landing_m,top)]
        for i in range(1,r.step_count):
            d=c.landing_m+(i-1)*c.tread_m;z=top-i*r.riser_m
            profile.extend(((d,z),(d+c.tread_m,z)))
    elif c.kind=='ramp':
        k=(top-low)/(length-c.transition_m);h=c.transition_m*k/2
        profile=[(0,top),(c.transition_m,top-h),(length-c.transition_m,low+h),(length,low)]
    else:profile=[(0,top),(length,top)]
    # Extrude a stepped side section across the width, rather than stacked cubes.
    shape=Polygon([(0,low-c.slab_m),*profile,(length,low-c.slab_m)])
    with mb.assembly('entrance/'+c.id):
        mb.panel(a,n,-t,[shape],-r.width_m,0,lambda *args:c.material,'entrance_'+c.kind)
        if c.kind=='steps' and r.step_count and c.nosing_m:
            for i in range(r.step_count):
                d=c.landing_m+i*c.tread_m;z=top-i*r.riser_m
                mb.box(a,t,n,0,r.width_m,z-min(.025,r.riser_m/3),z,d-c.nosing_m,d+c.nosing_m,c.material,'entrance_nosing')
        if c.cheek_height_m:
            side=Polygon([*profile,*[(d,z+c.cheek_height_m) for d,z in reversed(profile)]])
            for start in (-c.side_width_m,r.width_m):
                mb.panel(a,n,-t,[side],-start-c.side_width_m,-start,lambda *args:c.side_material,'entrance_side')
