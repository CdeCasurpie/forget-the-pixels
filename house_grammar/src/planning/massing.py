"""Phase 1: street-relative, deterministic massing and geometric support plans.

Qualitative operations modify real polygons, including holes. Each storey has
its own footprint. Pending facade operations stay explicit in the result.
"""
import math

import numpy as np
from shapely import set_precision
from shapely.affinity import affine_transform, translate
from shapely.geometry import Polygon, LineString, box, mapping, shape
from shapely.geometry.polygon import orient
from shapely.ops import unary_union

from domain.architectural_plan import MassingPlan, PlanningError
from domain.building_intent import IntentRequest, validate_intent, operation_order
from modeling.randomness import resolve_seed

IMPLEMENTED = frozenset(('setback','bite','courtyard','attach','advance',
                         'overhang','open_ground','chamfer'))
DEPTH = {'shallow': .08, 'medium': .16, 'deep': .26}
WIDTH = {'narrow': .25, 'medium': .45, 'wide': .65, 'all': 1.}
EPS = 1e-7


def fail(code, path, message):
    raise PlanningError(code, path, message)


def polygons(geometry):
    if geometry.is_empty:
        return []
    if geometry.geom_type == 'Polygon':
        return [geometry]
    return [p for g in getattr(geometry, 'geoms', ()) for p in polygons(g)]


def clean(geometry):
    return unary_union(polygons(geometry))


def encode(geometry):
    return mapping(geometry)


def front_frames(context):
    """x points observer-right, y inward, invariant to input ring winding."""
    points=context['parcel']; ccw=Polygon(points).exterior.is_ccw
    result={}
    for name,edge in sorted(context['fronts'].items()):
        a=np.array(points[edge],float); b=np.array(points[(edge+1)%len(points)],float)
        if not ccw:a,b=b,a
        tangent=(b-a)/np.linalg.norm(b-a)
        inward=np.array([-tangent[1],tangent[0]])
        result[name]={'origin':a.tolist(),'right':tangent.tolist(),
                      'inward':inward.tolist(),'length_m':float(np.linalg.norm(b-a))}
    return result


def local(geometry, frame):
    a=frame['origin'];t=frame['right'];n=frame['inward']
    return set_precision(affine_transform(geometry,[t[0],t[1],n[0],n[1],
                                      -np.dot(a,t),-np.dot(a,n)]),1e-8)


def world(geometry, frame):
    a=frame['origin'];t=frame['right'];n=frame['inward']
    return affine_transform(geometry,[t[0],n[0],t[1],n[1],a[0],a[1]])


def fraction(seed, key, nominal):
    rng=np.random.default_rng(resolve_seed(seed,'intent','massing',key,'dimension'))
    return nominal*float(rng.uniform(.94,1.06))


def viable(poly, path):
    parts=polygons(poly)
    if not parts or not poly.is_valid:
        fail('empty_or_invalid',path,'operation leaves no valid body')
    if len(parts)!=1:
        fail('fragmented_body',path,'operation disconnects a body; declare connected bodies separately')
    if poly.area<4 or poly.buffer(-.40).is_empty:
        fail('unusable_body',path,'remaining body is too small or narrow')


def strip(poly, frame, position, ratio):
    p=local(poly,frame);x0,y0,x1,y1=p.bounds;w=x1-x0;d=y1-y0
    if position=='rear':r=box(x0,y1-d*ratio,x1,y1)
    elif position=='left':r=box(x0,y0,x0+w*ratio,y1)
    elif position=='right':r=box(x1-w*ratio,y0,x1,y1)
    elif position=='center':r=box(x0+w*(1-ratio)/2,y0,x1-w*(1-ratio)/2,y1)
    elif position=='corner':r=box(x0,y0,x0+w*ratio,y0+d*ratio)
    else:r=p
    return clean(world(p.intersection(r),frame))


def _organization(poly, org, floor, total, frame, seed, explicit_kinds):
    p=local(poly,frame);x0,y0,x1,y1=p.bounds;w=x1-x0;d=y1-y0
    f=fraction(seed,'organization',1.)
    if org=='bar':p=p.intersection(box(x0,y0,x0+w*.78,y1))
    elif org=='L':p=p.difference(box(x0+w*.48,y0+d*.46,x1+1,y1+1))
    elif org=='U':p=p.difference(box(x0+w*.30,y0-1,x1-w*.30,y0+d*.58))
    elif org=='courtyard' and 'courtyard' not in explicit_kinds:
        p=p.difference(box(x0+w*.32,y0+d*.35,x1-w*.32,y0+d*.65))
    elif org=='stepped' and 'setback' not in explicit_kinds and floor>1:
        p=p.intersection(box(x0,y0+d*.08*(floor-1)*f,x1,y1))
    elif org=='podium' and floor>1:
        p=p.intersection(box(x0+w*.13,y0+d*.12,x1-w*.13,y1-d*.12))
    elif org=='attached' and floor>1:
        p=p.intersection(box(x0,y0,x1,y0+d*.72))
    elif org=='incremental' and floor==total and total>1:
        p=p.intersection(box(x0,y0+d*.12,x0+w*.72,y0+d*.80))
    elif org=='corner':
        if floor==total and total>1:
            p=p.intersection(box(x0,y0,x0+w*.55,y0+d*.55))
        else:p=p.difference(box(x0+w*.68,y0+d*.68,x1+1,y1+1))
    return clean(world(p,frame))


def _cut(poly, op, frame, seed):
    p=local(poly,frame);x0,y0,x1,y1=p.bounds;w=x1-x0;d=y1-y0
    depth=min(4.,d*fraction(seed,op['id']+'/depth',DEPTH[op.get('depth','medium')]))
    width=w*WIDTH[op.get('width','medium')]
    pos=op.get('position','center');kind=op['kind']
    left=x0 if pos in ('left','corner') else x1-width if pos=='right' else (x0+x1-width)/2
    if kind=='setback':
        cutter=box(left,y0-1,left+width,y0+depth) if op.get('width','all')!='all' else box(x0-1,y0-1,x1+1,y0+depth)
    elif kind=='bite':
        cutter=box(left,y0-1,left+width,y0+depth)
    elif kind=='courtyard':
        # Interior courtyard is distinct from a perimeter bite.
        width=min(width,w*.45);height=min(max(depth,1.4),d*.35)
        cx=x0+w*(.35 if pos=='left' else .65 if pos=='right' else .5)
        cy=y0+d*(.68 if pos=='rear' else .5)
        cutter=box(cx-width/2,cy-height/2,cx+width/2,cy+height/2)
        # Prefer a ring wide enough for a 1.20 m room route around the courtyard;
        # fall back to the historical 0.60 m clearance when the body is narrow.
        found=False
        for ring in (1.45,.6):
            safe=p.buffer(-ring,join_style=2)
            if safe.covers(cutter):
                found=True;break
            # Fit the qualitative courtyard inside an existing wing. Preserve
            # its side and minimum size rather than deleting it for a U/L plan.
            candidates=[]
            for scale in (1.,.8,.6,.45,.35):
                ww=max(1.2,width*scale);hh=max(1.2,height*scale)
                for ux in np.linspace(.1,.9,17):
                    if pos=='left' and ux>.5 or pos=='right' and ux<.5:continue
                    for uy in np.linspace(.15,.85,15):
                        xx=x0+w*ux;yy=y0+d*uy
                        q=box(xx-ww/2,yy-hh/2,xx+ww/2,yy+hh/2)
                        if safe.covers(q):candidates.append((-(ww*hh),abs(xx-cx)+abs(yy-cy),xx,yy,q))
                if candidates:break
            if candidates:
                cutter=min(candidates,key=lambda item:item[:4])[-1];found=True;break
        if not found:
            fail('courtyard_clearance',op['id'],'courtyard leaves insufficient surrounding body')
        width=cutter.bounds[2]-cutter.bounds[0];depth=cutter.bounds[3]-cutter.bounds[1]
    else: # chamfer
        size=min(width,depth,w*.3)
        corner=x1 if pos=='right' else x0;sign=-1 if pos=='right' else 1
        cutter=Polygon([(corner,y0),(corner+sign*size,y0),(corner,y0+size)])
    cut=clean(p.intersection(cutter));result=clean(p.difference(cutter))
    if cut.area<EPS:fail('no_effect',op['id'],'requested cut does not intersect body')
    viable(result,op['id'])
    return world(result,frame),world(cut,frame),{'depth_m':depth,'width_m':width}


def _columns(poly, frame, z0, z1, prefix):
    """Conceptual supports on a bounded grid, not an engineering design."""
    p=local(poly,frame);x0,y0,x1,y1=p.bounds
    safe=p.buffer(-.16,join_style=2)
    if safe.is_empty:fail('support_clearance',prefix,'no room for a 0.30 m support')
    xs=np.linspace(x0+.17,x1-.17,max(2,math.ceil((x1-x0)/3.5)+1))
    ys=np.linspace(y0+.17,y1-.17,max(2,math.ceil((y1-y0)/3.5)+1))
    footprints=[]
    for x in xs:
        for y in ys:
            q=box(x-.15,y-.15,x+.15,y+.15)
            if p.buffer(EPS).covers(q):footprints.append(q)
    for part in polygons(p):
        if not any(part.covers(q) for q in footprints):
            point=part.buffer(-.22).representative_point()
            q=box(point.x-.15,point.y-.15,point.x+.15,point.y+.15)
            if not part.buffer(EPS).covers(q):fail('support_clearance',prefix,'cannot place support in uncovered region')
            footprints.append(q)
    return [dict(id=f'{prefix}/column{i}',kind='column',geometry=encode(world(q,frame)),
                 bottom_m=z0,top_m=z1) for i,q in enumerate(footprints)]


def _surfaces(record, storeys, frames, frame):
    """Stable wall charts for subsequent facade planning; internal joins omitted."""
    poly=orient(shape(record['geometry']))
    neighbors=unary_union([shape(s['geometry']) for s in storeys
                          if s['floor']==record['floor'] and s['id']!=record['id'] and s['kind']=='enclosed'])
    result=[]
    for ring_index,ring in enumerate([poly.exterior,*poly.interiors]):
        coords=list(ring.coords)[:-1]
        # Canonical start in the primary street frame, not arbitrary Shapely order.
        def key(p):
            a=frame['origin'];t=frame['right'];n=frame['inward']
            delta=np.asarray(p)-a
            return (round(float(delta@t),6),round(float(delta@n),6))
        start=min(range(len(coords)),key=lambda i:key(coords[i]))
        coords=coords[start:]+coords[:start]
        for edge,a in enumerate(coords):
            b=coords[(edge+1)%len(coords)]
            line=LineString([a,b]);visible=line.difference(neighbors)
            pieces=[visible] if visible.geom_type=='LineString' else list(getattr(visible,'geoms',()))
            t=(np.asarray(b)-a)/line.length;n=np.array([t[1],-t[0]])
            front=None
            if ring_index==0:
                matches=[name for name,f in frames.items() if np.dot(n,-np.asarray(f['inward']))>.98]
                if matches:front=min(matches)
            for part_index,piece in enumerate(sorted(pieces,key=lambda p:p.wkt)):
                if piece.geom_type!='LineString' or piece.length<1e-6:continue
                result.append(dict(id=f'{record["id"]}/ring{ring_index}/edge{edge}/part{part_index}',
                                   kind='courtyard' if ring_index else 'exterior',front=front,
                                   line=list(piece.coords),normal=n.tolist(),length_m=piece.length,
                                   bottom_m=record['bottom_m'],top_m=record['top_m'],
                                   enclosure=record['kind']=='enclosed'))
    return result


def plan_massing(request, *, articulation=False):
    request=validate_intent(request.data if isinstance(request,IntentRequest) else request)
    data=request.data;c=data['context'];b=data['building'];seed=data.get('seed',0)
    if articulation:
        from planning.articulation import IMPLEMENTED as depth_kinds, apply_operation
    else:
        depth_kinds=frozenset()
    implemented=IMPLEMENTED | depth_kinds
    parcel=Polygon(c['parcel']);frames=front_frames(c)
    primary=min(frames,key=lambda key:(-frames[key]['length_m'],key));frame=frames[primary]
    levels=c['levels_m'];total=len(levels)-1
    decisions=[];pending=[];records=[];site_reservations=[]
    available=parcel
    site=b.get('site',{});space=site.get('front_space')
    if space is None and site.get('fence'):
        space={'front':site['fence']['front'],'depth':'shallow','use':'patio'}
        decisions.append(dict(path='site.front_space',reason='space behind requested fence',source='completion'))
    if space and space is not False:
        sf=frames[space['front']];p=local(parcel,sf);x0,y0,x1,y1=p.bounds
        depth=min(4.,(y1-y0)*fraction(seed,'site/depth',DEPTH[space.get('depth','medium')]))
        reserve=clean(world(p.intersection(box(x0-1,y0-1,x1+1,y0+depth)),sf))
        available=clean(parcel.difference(reserve));viable(available,'site.front_space')
        site_reservations.append(dict(id='front_space',use=space.get('use','patio'),geometry=encode(reserve)))
        decisions.append(dict(path='site.front_space.depth',value_m=depth,source='qualitative'))
    # Reserve a modest rear service yard only for omitted site intent.
    if 'front_space' not in site and not space:
        reserve=strip(available,frame,'rear',fraction(seed,'rear_service',.10))
        available=clean(available.difference(reserve));viable(available,'rear_service')
        site_reservations.append(dict(id='rear_service',use='unclassified',geometry=encode(reserve)))
        decisions.append(dict(path='site.rear_service',source='completion',reason='service yard prior, not legal area requirement'))
    bodies=sorted(b.get('bodies',[{'id':'main'}]),key=lambda x:x['id'])
    base_body=next((x for x in bodies if x['id']=='main'),bodies[0])
    masks={};remaining=available
    for body in bodies:
        if body is base_body:continue
        mask=strip(remaining,frame,body.get('position','rear'),WIDTH[body.get('width','narrow')])
        viable(mask,'bodies/'+body['id']);masks[body['id']]=mask
        remaining=clean(remaining.difference(mask));viable(remaining,'bodies/'+base_body['id'])
    masks[base_body['id']]=remaining
    if 'position' in base_body or 'width' in base_body:
        masks[base_body['id']]=strip(remaining,frame,base_body.get('position','center'),
                                   WIDTH[base_body.get('width','wide')])
        viable(masks[base_body['id']],'bodies/'+base_body['id'])
    ops={o['id']:o for o in b.get('operations',[])}
    rows={};attachment_reserves={}
    org=b.get('organization','compact')
    for body in bodies:
        floors=body.get('floors',list(range(1,total+1)))
        kinds={o['kind'] for o in ops.values() if o['body']==body['id']}
        mask=masks[body['id']]
        for floor in floors:
            poly=_organization(mask,org if body is base_body else 'compact',floor,total,frame,seed,kinds)
            # An explicit advance/overhang needs real room to extend into.
            for op in sorted(ops.values(),key=lambda o:o['id']):
                if op['body']!=body['id']:continue
                if op['kind'] in ('advance','overhang'):
                    p=local(poly,frames[op['front']]);x0,y0,x1,y1=p.bounds
                    gap=min(1.0 if op['kind']=='overhang' else 2.,(y1-y0)*DEPTH[op.get('depth','medium')])
                    poly=clean(world(p.intersection(box(x0-1,y0+gap,x1+1,y1+1)),frames[op['front']]))
                if op['kind']=='attach' and floor in op.get('floors',floors):
                    reserve=strip(poly,frames.get(op.get('front'),frame),op.get('position','rear'),.20)
                    attachment_reserves[(op['id'],floor)]=reserve
                    poly=clean(poly.difference(reserve))
            viable(poly,f'{body["id"]}/floor{floor}')
            rows[(body['id'],floor)]={'poly':poly,'kind':'enclosed'}
    for opid in operation_order(request):
        op=ops[opid];kind=op['kind'];body=op['body'];oframe=frames.get(op.get('front'),frame)
        if kind not in implemented:
            pending.append(dict(id=opid,kind=kind,path='building.operations',reason='phase_2_or_later'))
            records.append(dict(id=opid,kind=kind,status='pending'))
            continue
        if any(ops[ref]['kind'] not in implemented for ref in op.get('after',[])):
            fail('pending_dependency',opid,'mass operation depends on a future-stage operation')
        floors=op.get('floors',sorted(f for bid,f in rows if bid==body))
        if kind=='open_ground' and 'floors' not in op:floors=[min(floors)]
        record=dict(id=opid,kind=kind,status='applied',floors=[])
        for floor in floors:
            row=rows[(body,floor)];before=row['poly'];params={}
            if kind in depth_kinds:
                after,params=apply_operation(row,op,oframe,parcel,floor,levels,seed,c.get('ground_z_m',min(0.,levels[0])))
            elif kind in ('setback','bite','courtyard','chamfer'):
                after,cut,params=_cut(before,op,oframe,seed)
            elif kind=='attach':
                reserve=attachment_reserves[(opid,floor)]
                added=strip(reserve,oframe,'left',WIDTH[op.get('width','medium')])
                after=clean(before.union(added));viable(after,opid)
                if before.boundary.intersection(added.boundary).length<.2:
                    fail('disconnected_attachment',opid,'addition must share a wall with its body')
            elif kind in ('advance','overhang'):
                p=local(before,oframe);x0,y0,x1,y1=p.bounds
                gap=min(1.0 if kind=='overhang' else 2.,(local(masks[body],oframe).bounds[3]-local(masks[body],oframe).bounds[1])*DEPTH[op.get('depth','medium')])
                if kind=='overhang' and floor==1:fail('ground_overhang',opid,'overhang requires an upper storey')
                extent=(x1-x0)*WIDTH[op.get('width','all')]
                pos=op.get('position','center')
                left=x0 if pos in ('left','corner') else x1-extent if pos=='right' else (x0+x1-extent)/2
                extension=world(box(left,y0-gap,left+extent,y0),oframe)
                after=clean(before.union(extension.intersection(masks[body])))
                params={'extension_m':gap}
                viable(after,opid)
                if after.area-before.area<EPS:fail('no_effect',opid,'no available space for projection')
            else:
                after=before;row['kind']='open'
            row['poly']=after
            record['floors'].append(dict(floor=floor,before_m2=before.area,after_m2=after.area,
                                         removed=encode(before.difference(after)),added=encode(after.difference(before)),**params))
        records.append(record)
    storeys=[];supports=[];ground=c.get('ground_z_m',min(0.,levels[0]))
    for (body,floor),row in sorted(rows.items()):
        poly=row['poly'];viable(poly,f'{body}/floor{floor}')
        record=dict(id=f'{body}/floor{floor}',body=body,floor=floor,kind=row['kind'],
                    bottom_m=levels[floor-1],top_m=levels[floor],geometry=encode(poly))
        storeys.append(record)
        if row.get('spaces'):record['spaces']=row['spaces']
        if floor==1 and levels[0]>ground+EPS and row['kind']=='enclosed':
            supports.append(dict(id=record['id']+'/base',kind='plinth',geometry=encode(poly),bottom_m=ground,top_m=levels[0]))
        if row['kind']=='open':
            if levels[floor]-levels[floor-1]<=.5:fail('storey_height',record['id'],'open storey needs usable headroom')
            supports+=_columns(poly,frame,min(ground,levels[0]) if floor==1 else levels[floor-1],levels[floor]-.18,record['id'])
        if floor>1:
            below=unary_union([r['poly'] for (bid,f),r in rows.items() if f==floor-1])
            missing=clean(poly.difference(below))
            if missing.area>EPS:
                # Small projections can be conceptually cantilevered; larger
                # unsupported bodies are diagnosed, never silently cropped.
                if below.is_empty:
                    fail('unsupported_storey',record['id'],'no lower body; declare an open supporting body')
                if below.buffer(1.2+EPS,join_style=2).covers(poly) and missing.area<=poly.area*.30:
                    supports.append(dict(id=record['id']+'/cantilever',kind='cantilever',geometry=encode(missing),
                                         bottom_m=levels[floor-1],top_m=levels[floor-1]+.18,
                                         reason='within 1.2 m conceptual reach and 30% area; not engineering verification'))
                else:
                    columns=_columns(missing,frame,levels[0],levels[floor-1],record['id']+'/support')
                    for column in columns:
                        footprint=shape(column['geometry'])
                        # A column stops on the highest lower enclosed body,
                        # rather than being drawn through it to ground level.
                        for (bid,f),lower in rows.items():
                            if f>=floor or lower['kind']!='enclosed':continue
                            overlap=footprint.intersection(lower['poly']).area
                            if overlap>EPS and not lower['poly'].buffer(EPS).covers(footprint):
                                fail('support_collision',record['id'],'support straddles a lower wall')
                            if overlap>EPS:column['bottom_m']=max(column['bottom_m'],levels[f])
                    supports+=columns
    for record in storeys:
        record['surfaces']=_surfaces(record,storeys,frames,frame)
    # Audit same-floor intersections and parcel containment independently.
    for i,s in enumerate(storeys):
        p=shape(s['geometry'])
        if p.difference(parcel).area>EPS:fail('outside_parcel',s['id'],'structural footprint leaves parcel')
        for other in storeys[:i]:
            if s['floor']==other['floor'] and p.intersection(shape(other['geometry'])).area>EPS:
                fail('body_overlap',s['id'],other['id'])
    for i,s in enumerate(supports):
        if s['kind']=='cantilever':continue
        p=shape(s['geometry'])
        if p.difference(parcel).area>EPS:fail('support_outside',s['id'],'support leaves parcel')
        for other in storeys:
            bottom=other['bottom_m'] if other['kind']=='enclosed' else other['top_m']-.18
            if min(s['top_m'],other['top_m'])>max(s['bottom_m'],bottom)+EPS and p.intersection(shape(other['geometry'])).area>EPS:
                fail('support_collision',s['id'],other['id'])
        for other in supports[:i]:
            if other['kind']=='cantilever':continue
            if min(s['top_m'],other['top_m'])>max(s['bottom_m'],other['bottom_m'])+EPS and p.intersection(shape(other['geometry'])).area>EPS:
                fail('support_overlap',s['id'],other['id'])
    ground_closed=unary_union([shape(s['geometry']) for s in storeys if s['floor']==1 and s['kind']=='enclosed'])
    ground_posts=unary_union([shape(s['geometry']) for s in supports if s['kind']=='column' and s['bottom_m']<=levels[0]+EPS])
    occupied=ground_closed.union(ground_posts)
    free=clean(parcel.difference(occupied))
    coverage=unary_union([shape(s['geometry']) for s in storeys])
    uncovered=clean(parcel.difference(coverage))
    covered_free=clean(free.intersection(coverage))
    for key in ('site','facades','roof','finishes'):
        if key in b:pending.append(dict(path='building.'+key,reason='only site free-space reservation is materialized' if key=='site' else 'future_stage'))
    checks={'parcel_containment':True,'same_floor_overlap':False,'support_collisions':False,'valid_footprints':True,
            'conceptual_support':True,'engineering_verified':False,
            'parcel_area_m2':parcel.area,'occupied_ground_m2':occupied.area,
            'free_ground_m2':free.area,'covered_free_m2':covered_free.area,
            'uncovered_m2':uncovered.area,
            'area_balance_error_m2':abs(occupied.area+free.area-parcel.area)}
    return MassingPlan('articulation-plan-v1' if articulation else 'massing-plan-v1',data,frames,storeys,supports,
                      dict(reservations=site_reservations,occupied=encode(occupied),free=encode(free),
                           covered_free=encode(covered_free),uncovered=encode(uncovered)),
                      records,decisions,pending,checks)
