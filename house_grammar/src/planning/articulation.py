"""Qualitative facade depth and usable outdoor-space reservations.

All metric dimensions are compiler priors. Access pockets reserve connections
for phase 3; they are not a claim that an interior circulation graph exists.
"""
import numpy as np
from shapely.geometry import box, shape, LineString
from shapely.affinity import translate
from shapely.ops import unary_union
from planning.massing import local, world, clean, encode, viable, fail, WIDTH, EPS

IMPLEMENTED=frozenset(('recess','depth_rhythm','floor_shift','loggia',
                       'portico','vestibule','balcony'))
DEPTH={'shallow':.8,'medium':1.4,'deep':2.0}


def plan_articulation(request):
    from planning.massing import plan_massing
    plan=plan_massing(request,articulation=True)
    # Space boundaries, not the outer envelope, are the next facade datum.
    from planning.massing import _surfaces
    primary=min(plan.fronts,key=lambda key:(-plan.fronts[key]['length_m'],key))
    cores=[]
    for row in plan.storeys:
        voids=unary_union([shape(s['geometry']) for s in row.get('spaces',[])])
        core=clean(shape(row['geometry']).difference(voids))
        viable(core,row['id']+'/enclosure')
        row['enclosed_geometry']=encode(core)
        cores.append(dict(row,geometry=encode(core)))
    for row,core in zip(plan.storeys,cores):
        row['surfaces']=_surfaces(core,cores,plan.fronts,plan.fronts[primary])
        for surface in row['surfaces']:
            surface['access_reservations']=[s['id'] for s in row.get('spaces',[])
                if shape(s['access']['geometry']).distance(LineString(surface['line']))<EPS]
    occupied=unary_union([shape(r['enclosed_geometry']) for r in plan.storeys if r['floor']==1 and r['kind']=='enclosed']+
                        [shape(s['geometry']) for s in plan.supports if s['kind']=='column' and s['bottom_m']<=plan.request['context']['levels_m'][0]+EPS])
    parcel=shape({'type':'Polygon','coordinates':[plan.request['context']['parcel']]})
    free=clean(parcel.difference(occupied));coverage=unary_union([shape(r['geometry']) for r in plan.storeys])
    plan.site.update(occupied=encode(occupied),free=encode(free),covered_free=encode(free.intersection(coverage)))
    plan.checks.update(occupied_ground_m2=occupied.area,free_ground_m2=free.area,
                       covered_free_m2=free.intersection(coverage).area,
                       area_balance_error_m2=abs(occupied.area+free.area-parcel.area))
    return plan


def solid_sections(row):
    """Disjoint horizontal sections: usable voids, access pockets and parapets."""
    bottom=row['bottom_m'];top=row['top_m'];spaces=row.get('spaces',[])
    if row['kind']=='open':return [(shape(row['geometry']),top-.18,top)]
    heights={bottom,top}
    for s in spaces:
        heights.update((bottom+2.1,bottom+s['protection_height_m']))
        if s['ceiling_thickness_m']:heights.add(top-s['ceiling_thickness_m'])
    heights=sorted(h for h in heights if bottom<=h<=top)
    # levels_m are finished floor elevations. Slabs extend below, not above.
    # Continue the slab under the enclosure as well: a slab only under the
    # outdoor void would touch a ground-floor return along an edge, not a face.
    result=[(shape(row['geometry']),bottom-.18,bottom)] if spaces else []
    for low,high in zip(heights,heights[1:]):
        if high-low<EPS:continue
        mid=(low+high)/2;poly=shape(row['geometry'])
        for s in spaces:
            if mid>bottom and mid<top-s['ceiling_thickness_m']:
                poly=poly.difference(shape(s['geometry']))
                if mid<bottom+2.1:poly=poly.difference(shape(s['access']['geometry']))
                if s['protection'] and mid<bottom+s['protection_height_m']:
                    poly=poly.union(shape(s['protection']))
        result.append((clean(poly),low,high))
    return result


def apply_operation(row, op, frame, parcel, floor, levels, seed, ground_z=0.):
    if row['kind']!='enclosed':
        fail('open_body_articulation',op['id'],'requires an enclosed body')
    p=local(row['poly'],frame);x0,y0,x1,y1=p.bounds
    kind=op['kind'];depth=DEPTH[op.get('depth','medium')]
    width=(x1-x0)*WIDTH[op.get('width','medium')]
    position=op.get('position','center')
    if position not in ('left','center','right','all','corner'):
        fail('space_position',op['id'],'use an oriented front and left/center/right/all')
    left=x0 if position in ('left','corner') else x1-width if position=='right' else (x0+x1-width)/2
    if position=='all':left=x0;width=x1-x0
    if kind=='recess':
        result=clean(p.difference(box(left,y0-1,left+width,y0+depth)))
    elif kind=='depth_rhythm':
        # The outermost plane stays inside the parcel; base lies halfway in.
        # Thus 'projecting' is genuinely forward relative to base, never clipped.
        edges=x0+(x1-x0)*np.r_[0,np.cumsum(op['weights'])]/sum(op['weights'])
        result=p
        for a,b,plane in zip(edges,edges[1:],op['planes']):
            offset={'projecting':0.,'base':depth/2,'recessed':depth}[plane]
            if offset:result=clean(result.difference(box(a,y0-1,b,y0+offset)))
    elif kind=='floor_shift':
        shift=min(depth/3,(x1-x0)*.08)
        core=p.intersection(box(x0+shift,y0-1,x1-shift,y1+1))
        sign=-1 if position=='left' else 1 if position=='right' else (-1 if floor%2 else 1)
        result=translate(core,xoff=sign*shift)
        if not p.buffer(EPS).covers(result):
            fail('shift_outside_body',op['id'],'shift cannot fit this irregular footprint')
    else:
        if levels[floor]-levels[floor-1]<2.6:
            fail('space_headroom',op['id'],'requires at least 2.6 m storey height')
        width=min(width,(x1-x0)-.4)
        left=max(x0+.2,min(left,x1-.2-width))
        if width<1.4:fail('space_width',op['id'],'usable space requires at least 1.4 m width')
        if kind=='balcony':
            if floor==1:fail('ground_balcony',op['id'],'balcony requires upper storey')
            depth=min(depth,1.0)  # conceptual cantilever limit
            zone=box(left,y0-depth,left+width,y0)
            result=clean(p.union(zone))
            back=y0
        else:
            zone=box(left,y0,left+width,y0+depth)
            if not p.buffer(EPS).covers(zone):
                fail('space_fit',op['id'],'space crosses a void or irregular edge')
            back=y0+depth;result=p
        access_width=.9;center=left+width/2
        access=box(center-access_width/2,back,center+access_width/2,back+.45)
        if not p.buffer(EPS).covers(access):
            fail('space_access',op['id'],'no enclosed landing behind space')
        zone_world=world(zone,frame);access_world=world(access,frame)
        for existing in row.get('spaces',[]):
            if zone_world.union(access_world).intersection(shape(existing['geometry']).union(shape(existing['access']['geometry']))).area>EPS:
                fail('space_overlap',op['id'],'outdoor spaces or access reservations overlap')
        if not parcel.buffer(EPS).covers(world(result,frame)):
            fail('space_outside_parcel',op['id'],'provide a front setback for a projecting balcony')
        protected=levels[floor-1]-ground_z>.6
        # Continuous solid parapet on exposed edges; door side remains open.
        boundary=zone.boundary.difference(box(left-.1,back-.01,left+width+.1,back+.1))
        guard=clean(boundary.buffer(.06,cap_style=2,join_style=2).intersection(zone)) if protected else None
        if guard is not None and kind in ('portico','vestibule') and floor==1:
            guard=clean(guard.difference(box(center-.5,y0-.1,center+.5,y0+.1)))
        row.setdefault('spaces',[]).append(dict(
            id=f'{op["id"]}/floor{floor}',kind=kind,front=op['front'],
            geometry=encode(zone_world),bottom_m=levels[floor-1],top_m=levels[floor],
            floor_thickness_m=.18,ceiling_thickness_m=.18 if kind!='balcony' else 0.,
            access=dict(geometry=encode(access_world),width_m=access_width,height_m=2.1,
                        status='reserved_for_phase3',connects_to=op['body']),
            protection=encode(world(guard,frame)) if guard is not None else None,
            protection_height_m=1.05 if protected else 0.,depth_m=depth))
    result=clean(result);viable(result,op['id'])
    if kind in ('recess','depth_rhythm','floor_shift') and result.symmetric_difference(p).area<EPS:
        fail('no_effect',op['id'],'depth operation leaves geometry unchanged')
    return world(result,frame),dict(depth_m=depth,datum='outer_envelope')
