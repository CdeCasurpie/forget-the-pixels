"""Phase 5: parcel edge, street gates and traversable ground-floor access.

The envelope owns the building entrance. This stage uses that actual opening,
the reserved free ground and the parcel front; it never invents a second door.
"""
from dataclasses import asdict, dataclass
import math

import numpy as np
from shapely.geometry import LineString, Point, Polygon, shape

from planning.envelope import _part, plan_envelope, strip
from planning.massing import encode, fail, local


FENCE_THICKNESS=.16
FENCE_HEIGHT={'low':1.15,'high':2.20}
ACCESS_WIDTH={'pedestrian':.82,'vehicle':2.20}


@dataclass
class SitePlan:
    version: str
    request: dict
    envelope: dict
    fence: dict | None
    gates: list[dict]
    accesses: list[dict]
    routes: list[dict]
    parts: list[dict]
    decisions: list[dict]
    pending: list[dict]
    checks: dict

    def to_dict(self):return asdict(self)


def _line(frame, start, end, depth=0.):
    a=np.asarray(frame['origin']);t=np.asarray(frame['right']);n=np.asarray(frame['inward'])
    return LineString([a+t*start+n*depth,a+t*end+n*depth])


def _intervals(length, openings, form):
    """Fence panel intervals, excluding openings; a partial fence has a gap."""
    solids=[(0.,length)] if form!='partial' else [(0.,length*.38),(length*.62,length)]
    for left,right in sorted(openings):
        solids=[piece for a,b in solids for piece in ((a,min(left,b)),(max(right,a),b))
                if piece[1]-piece[0]>1e-5]
    return solids


def _fence_parts(parts, frame, form, height, cap, panels, gates):
    """A form controls solid/rail topology; style is only a local design label."""
    footprint=lambda a,b,back=0.,front=FENCE_THICKNESS:strip(_line(frame,0,frame['length_m']),a,b,back,front,frame['inward'])
    def emit(name,kind,material,poly,low,high):
        _part(parts,'site/fence/'+name,kind,material,0,poly,low,high)
    if form in ('solid','partial'):
        for i,(a,b) in enumerate(panels):
            emit(f'panel{i}','fence_wall','plaster',footprint(a,b),0.,height)
            if cap:
                material={'plain':'stone','tile':'tile','corrugated':'corrugated'}[cap]
                emit(f'cap{i}','fence_cap',material,footprint(a,b,0.,FENCE_THICKNESS+.02),height,height+.055)
    else:
        base=.235 if form=='open' else min(.75,height*.48)
        for i,(a,b) in enumerate(panels):
            if form=='base_and_rail':
                emit(f'base{i}','fence_base','plaster',footprint(a,b),0.,base)
            # Every span ends in a supported post. Metal avoids post volumes.
            positions=[a+(b-a)*j/max(1,math.ceil((b-a)/1.8))
                       for j in range(max(1,math.ceil((b-a)/1.8))+1)]
            positions=sorted(set(round(x,8) for x in positions))
            for j,x in enumerate(positions):
                left=max(a,x-.075);right=min(b,x+.075)
                if right-left>.02:
                    emit(f'post{i}_{j}','fence_post','plaster',footprint(left,right),
                         base if form=='base_and_rail' else 0.,height)
                    if cap:
                        emit(f'post_cap{i}_{j}','fence_cap',
                             {'plain':'stone','tile':'tile','corrugated':'corrugated'}[cap],
                             footprint(left,right,0.,FENCE_THICKNESS+.02),height,height+.055)
            for j,(left,right) in enumerate(zip(positions,positions[1:])):
                # Gate jambs project 13.5 cm into the adjoining panel span.
                u=left+.155;v=right-.155
                if v-u<.06:continue
                emit(f'rail{i}_{j}','fence_rail','metal',footprint(u,v,.055,.095),height-.13,height-.075)
                if form=='open':
                    emit(f'low_rail{i}_{j}','fence_rail','metal',footprint(u,v,.055,.095),.18,base)
                for k,x in enumerate(np.arange(u+.075,v-.025,.17)):
                    emit(f'bar{i}_{j}_{k}','fence_bar','metal',footprint(x,x+.025,.055,.095),base,height-.13)
    for gate in gates:
        a,b=gate['interval_m'];kind=gate['kind']
        # Partial fences may leave an open span, but every physical gate has jambs.
        for side,x in (('left',a-.075),('right',b+.075)):
            emit(f'{gate["id"]}/{side}_post','gate_post','plaster',
                 footprint(max(0.,x-.06),min(frame['length_m'],x+.06)),0.,height)
        material=gate['material'];doorheight=min(height-.07,2.05 if kind=='pedestrian' else height-.07)
        if material=='metal':
            emit(gate['id']+'/bottom','gate_rail','metal',footprint(a+.012,b-.012,.035,.08),.075,.12)
            emit(gate['id']+'/top','gate_rail','metal',footprint(a+.012,b-.012,.035,.08),doorheight-.07,doorheight-.025)
            for j,x in enumerate(np.arange(a+.06,b-.035,.15)):
                emit(f'{gate["id"]}/bar{j}','gate_bar','metal',footprint(x,x+.025,.035,.08),.12,doorheight-.07)
        else:
            emit(gate['id']+'/leaf','gate_leaf',material,footprint(a+.012,b-.012,.035,.08),.075,doorheight)
            if material=='glass':
                emit(gate['id']+'/frame','gate_frame','metal',footprint(a+.012,a+.05,.025,.035),.075,doorheight)
        if kind=='vehicle' and cap in ('tile','corrugated'):
            # A roof over the portal bridges the gate and bears on its jambs.
            emit(gate['id']+'/canopy','gate_canopy',cap,footprint(a-.075,b+.075,0.,.65),height,height+.085)


def _details(parts, frame, gate, height, style):
    """Devices sit on an inward face beside the gate, never in its clearance."""
    a,b=gate['interval_m'];length=frame['length_m']
    center=b+.12 if b+.35<length else a-.12
    def plate(name,material,width,low,high):
        p=strip(_line(frame,0,length),center-width/2,center+width/2,
                FENCE_THICKNESS,FENCE_THICKNESS+.02,frame['inward'])
        _part(parts,'site/detail/'+name,name,material,0,p,low,high)
    plate('meter','metal',.17,.28,.58)
    plate('bell','metal',.075,min(height-.22,1.00),min(height-.13,1.10))
    plate('number','stone',.18,min(height-.12,1.72),min(height-.035,1.83))
    return [dict(id='site/detail/'+name,anchor_id='site/fence/'+gate['id']+('/right_post' if center>b else '/left_post'),style=style)
            for name in ('meter','bell','number')]


def _route(parts, access_id, kind, start, end, free, occupied, level):
    width=ACCESS_WIDTH[kind]
    axis=LineString([start,end]);distance=axis.length
    if distance<.015:
        if level>.02:fail('access_run',access_id,'raised building at the street edge has no space for a transition')
        return dict(id=access_id+'/route',kind=kind,axis=encode(axis),geometry=encode(Polygon()),
                    width_m=width,length_m=distance,rise_m=level,transition='direct')
    footprint=axis.buffer(width/2,cap_style=2,join_style=2)
    if not free.buffer(1e-5).covers(footprint):
        fail('access_outside_free',access_id,'passage does not fit in the free ground')
    if footprint.intersection(occupied).area>1e-4:
        fail('access_blocked',access_id,'ground mass or column blocks the route')
    _part(parts,access_id+'/pavement','pavement','concrete',0,footprint,-.08,0.)
    transition='level'
    if level>.02:
        if distance>=level*12+1.:
            transition='ramp'
            _part(parts,access_id+'/ramp','ramp','concrete',0,footprint,0.,level)
            parts[-1]['mesh_kind']='ramp';parts[-1]['rise_m']=level
            parts[-1]['axis']=encode(axis)
        else:
            count=max(1,math.ceil(level/.17));run=count*.32
            if distance<run+.25:fail('access_run',access_id,'insufficient parcel run for steps or a compliant ramp')
            transition='steps'
            for i in range(count):
                a=distance-run+i*.32;b=a+.32
                poly=strip(axis,a,b,-width/2,width/2,np.array([-(end[1]-start[1]),end[0]-start[0]])/distance)
                _part(parts,access_id+f'/step{i}','step','concrete',0,poly,0.,level*(i+1)/count)
    return dict(id=access_id+'/route',kind=kind,axis=encode(axis),geometry=encode(footprint),
                width_m=width,length_m=distance,rise_m=level,transition=transition)


def build_site(envelope):
    data=envelope.to_dict() if hasattr(envelope,'to_dict') else envelope
    request=data['request'];site=request['building'].get('site',{})
    mass=data['interior']['massing'];frames=mass['fronts'];parcel=Polygon(request['context']['parcel'])
    free=shape(mass['site']['free']);occupied=shape(mass['site']['occupied'])
    level=request['context']['levels_m'][0];parts=[];gates=[];routes=[];accesses=[];decisions=[]
    fencespec=site.get('fence');fence=None
    if fencespec is None and site.get('front_space') not in (None,False):
        # A modest open boundary is a prior, not a hidden contractual requirement.
        fencespec=dict(front=site['front_space']['front'],form='open',height='low')
        decisions.append(dict(path='site.fence',reason='low open boundary for requested front garden',source='completion'))
    targets=[o for o in data['openings'] if o['floor']==1 and o['kind'] in ('entrance','vehicle_entry')]
    if not any(o['kind']=='entrance' for o in targets):
        # Open ground has a Phase-3 street-to-hall crossing but no exterior wall.
        crossing=next((c for c in data['interior']['floors'][0]['connections'] if c['kind']=='entrance'),None)
        if crossing is None:fail('entrance_host','site','no building entrance or open-ground threshold')
        targets.append(dict(id='site/open_arcade',kind='entrance',axis=crossing['geometry'],
                            front=None,inward=None,clear_width_m=shape(crossing['geometry']).length))
        decisions.append(dict(path='site.open_arcade',reason='no door leaf without an exterior wall'))
    if fencespec:
        front=fencespec['front'];frame=frames[front];length=frame['length_m']
        form=fencespec['form'];height=FENCE_HEIGHT[fencespec.get('height','low')]
        cap=fencespec.get('cap','plain');style=fencespec.get('style',request['building'].get('style','moderno'))
        intervals=[]
        for target in targets:
            kind='vehicle' if target['kind']=='vehicle_entry' else 'pedestrian'
            local_center=local(shape(target['axis']).centroid,frame).x
            if target.get('front') not in (front,None):
                fail('fence_front_mismatch',target['id'],'requested fence and building entrance are on different fronts')
            width=2.72 if kind=='vehicle' else 1.02
            center=max(width/2+.13,min(length-width/2-.13,local_center))
            if abs(center-local_center)>.40:
                fail('gate_alignment',target['id'],'front too narrow to align a safe gate with the building entrance')
            interval=(center-width/2,center+width/2)
            if any(min(interval[1],b)-max(interval[0],a)>.05 for a,b in intervals):
                fail('gate_overlap',target['id'],'pedestrian and vehicle gates collide')
            intervals.append(interval)
            door=site.get('door',{}) if kind=='pedestrian' else {}
            material=door.get('material','metal') if isinstance(door,dict) else 'metal'
            gate_style=door.get('style',style) if isinstance(door,dict) else style
            gate=dict(id='site/'+kind+'_gate',kind=kind,front=front,interval_m=interval,
                      width_m=width,material=material,style=gate_style,
                      geometry=encode(_line(frame,*interval)))
            gates.append(gate)
        panels=_intervals(length,intervals,form)
        _fence_parts(parts,frame,form,height,cap,panels,gates)
        fence=dict(front=front,form=form,height_m=height,cap=cap,style=style,
                   geometry=encode(_line(frame,0,length)),panels_m=panels,
                   details=_details(parts,frame,next(g for g in gates if g['kind']=='pedestrian'),height,style))
        if any(shape(p['geometry']).intersection(occupied).area>1e-4 for p in parts if p['kind'].startswith('fence')):
            fail('fence_blocked','site.fence','building mass reaches the fence')
    for target in targets:
        kind='vehicle' if target['kind']=='vehicle_entry' else 'pedestrian'
        access_id='site/'+kind+'_access'
        axis=shape(target['axis']);point=axis.centroid
        if fence:
            gate=next(g for g in gates if g['kind']==kind);frame=frames[fence['front']]
            # Paving reaches the inward face of the gate leaf, without a gap.
            start=_line(frame,sum(gate['interval_m'])/2,sum(gate['interval_m'])/2,.08).centroid
            from_id=gate['id']
        else:
            fr=frames.get(target.get('front'))
            if fr is None:
                fr=min(frames.values(),key=lambda f:LineString([f['origin'],
                    (np.asarray(f['origin'])+np.asarray(f['right'])*f['length_m']).tolist()]).distance(point))
            projected=local(point,fr);u=max(0.,min(fr['length_m'],projected.x))
            start=_line(fr,u,u).centroid;from_id='street/'+str(target.get('front') or 'open')
        # A building already on the parcel line needs no paving outside it.
        # Otherwise the paving terminates at the actual opening, not 1 cm shy.
        end=start if not fence and start.distance(point)<.03 else point
        route=_route(parts,access_id,kind,start.coords[0],end.coords[0],free,occupied,level)
        routes.append(route)
        accesses.append(dict(id=access_id,kind=kind,from_id=from_id,to_id=target['id'],
                             route_id=route['id'],clear_width_m=min(target['clear_width_m'],
                                                        next((g['width_m'] for g in gates if g['kind']==kind),float('inf')))))
    if not fence and site.get('fence') is False:
        decisions.append(dict(path='site.fence',reason='explicit absence respected'))
    pending=[p for p in data['pending'] if p['path'] not in ('site.fence','site.access_route')]
    plan=SitePlan('site-plan-v1',request,data,fence,gates,accesses,routes,parts,decisions,pending,{})
    plan.checks=validate_site(plan)
    return plan


def validate_site(plan):
    parcel=Polygon(plan.request['context']['parcel']);parts=plan.parts
    for part in parts:
        if not parcel.buffer(1e-6).covers(shape(part['geometry'])):
            fail('site_outside_parcel',part['id'],'site piece leaves the parcel')
    if len({a['kind'] for a in plan.accesses})!=len(plan.accesses):
        fail('duplicate_access','site','more than one street access for a kind')
    for access in plan.accesses:
        route=next(r for r in plan.routes if r['id']==access['route_id'])
        if access['clear_width_m']<(.75 if access['kind']=='pedestrian' else 2.10):
            fail('access_clear_width',access['id'],'insufficient clear passage')
        if route['transition']=='ramp' and route['rise_m']/route['length_m']>1/12+1e-9:
            fail('ramp_slope',route['id'],'ramp steeper than 1:12')
    return dict(parcel_containment=True,accesses_connected=True,
                fence_absent=plan.fence is None,ground_routes=len(plan.routes),
                engineering_verified=False)


def plan_site(request):
    return build_site(plan_envelope(request))
