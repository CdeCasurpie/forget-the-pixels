"""Phase 3: constrained schematic room plans, not an interior furnishing system.

Shared vertical cores, visibility-graph circulation and adaptive BSP partitions.
Every graph edge is backed by a real shared boundary or an exterior reservation.
"""
import heapq
import math
from dataclasses import dataclass, asdict

import numpy as np
from shapely.geometry import Polygon, Point, LineString, box, shape
from shapely.ops import unary_union, nearest_points, split

from domain.architectural_plan import PlanningError
from planning.articulation import plan_articulation
from planning.massing import local, world, clean, encode, polygons, fail, EPS
from modeling.randomness import resolve_seed

WALL=.12
EXTERIOR=.18
CORRIDOR=1.20


@dataclass
class InteriorPlan:
    version: str
    request: dict
    massing: dict
    floors: list
    core: dict
    connections: list
    alternatives: list
    checks: dict

    def to_dict(self):
        return asdict(self)


def lines(g):
    if g.is_empty:return []
    if g.geom_type=='LineString':return [g]
    return [p for part in getattr(g,'geoms',()) for p in lines(part)]


def shortest_path(region, start, end, path):
    """Visibility graph in an eroded walkable polygon, including courtyard holes."""
    if start.distance(end)<EPS:return LineString([start.coords[0],end.coords[0]])
    if region.buffer(EPS).covers(LineString([start,end])):return LineString([start,end])
    part=next((p for p in polygons(region) if p.buffer(EPS).covers(start) and p.buffer(EPS).covers(end)),None)
    if part is None:fail('circulation_disconnected',path,'no clear 1.20 m route between anchors')
    nodes=[start.coords[0],end.coords[0]]
    for ring in [part.exterior,*part.interiors]:nodes.extend(list(ring.coords)[:-1])
    graph=[[] for _ in nodes]
    for i,a in enumerate(nodes):
        for j in range(i):
            edge=LineString([a,nodes[j]])
            if part.buffer(EPS).covers(edge):
                graph[i].append((j,edge.length));graph[j].append((i,edge.length))
    queue=[(0.,0)];distance={0:0.};previous={}
    while queue:
        cost,i=heapq.heappop(queue)
        if cost>distance[i]+EPS:continue
        if i==1:break
        for j,length in graph[i]:
            new=cost+length
            if new<distance.get(j,float('inf')):
                distance[j]=new;previous[j]=i;heapq.heappush(queue,(new,j))
    if 1 not in distance:fail('circulation_disconnected',path,'no visibility path')
    route=[1]
    while route[-1]!=0:route.append(previous[route[-1]])
    return LineString([nodes[i] for i in reversed(route)])


def _normal_line(a,b):
    tangent=(np.array(b)-a)/np.linalg.norm(np.array(b)-a)
    return tangent,np.array([-tangent[1],tangent[0]])


def _boundary_slot(line,width):
    center=line.interpolate(.5,normalized=True)
    a,b=list(line.coords)[0],list(line.coords)[-1]
    t,n=_normal_line(a,b)
    segment=LineString([np.array(center.coords[0])-t*width/2,np.array(center.coords[0])+t*width/2])
    return segment,segment.buffer(.24,cap_style=2)


def _facade_slots(massing, floor, frame, blocked=None):
    """Reserve openings on true facade segments before room partitioning."""
    slots=[];b=massing.request['building']
    for facade in b.get('facades',[]):
        if floor not in facade['floors'] or 'windows' not in facade:continue
        windows=facade['windows'];count=windows['count']
        if count==0:continue
        row=next(r for r in massing.storeys if r['floor']==floor and r['body']==facade['body'])
        candidates=[]
        for s in row['surfaces']:
            if s['front']!=facade['front'] or s['length_m']<=1.:continue
            line=local(LineString(s['line']),frame)
            if blocked is not None:line=line.difference(blocked.buffer(.5,join_style=2))
            inward=-np.array(s['normal']);t=np.array(frame['right']);v=np.array(frame['inward'])
            inward=np.array([inward@t,inward@v])
            for piece in lines(line):
                if piece.length<=.9:continue
                coords=list(piece.coords)
                if coords[0]>coords[-1]:coords.reverse();piece=LineString(coords)
                candidates.append(dict(id=s['id'],line=piece,length_m=piece.length,inward=inward))
        candidates.sort(key=lambda s:s['line'].bounds)
        if not candidates:fail('window_capacity',f'floor{floor}','no facade segment clear of the garage')
        usable=sum(max(0,s['length_m']-.4) for s in candidates)
        if usable<count*.85:fail('window_capacity',f'floor{floor}','not enough facade for requested windows')
        # Allocate counts in proportion to available lengths, stable under rotation.
        allocation=[0]*len(candidates)
        for _ in range(count):
            index=max(range(len(candidates)),key=lambda i:(candidates[i]['length_m']-.4)/(allocation[i]+1))
            allocation[index]+=1
        index=0
        for surface,n in zip(candidates,allocation):
            if not n:continue
            wall=surface['line'];inward=surface['inward']
            for i in range(n):
                distribution=windows.get('distribution','balanced')
                u=(i+.5)/n
                if distribution=='left':u=.05+u*.65
                elif distribution=='right':u=.30+u*.65
                elif distribution=='grouped':u=.2+u*.6
                if facade.get('alignment')=='staggered':
                    # Alternating floors of the SAME front, bounded within its cell.
                    u+=(-1 if floor%2 else 1)*.10/n
                center=wall.interpolate(u,normalized=True)
                proportion=windows.get('proportions',[windows.get('proportion','vertical')]*count)[index]
                weight=windows.get('weights',[1.]*count)[index]
                desired={'horizontal':1.8,'vertical':.9,'square':1.1,'small_high':.6}[proportion]*weight
                span=.6 if distribution=='grouped' else .65 if distribution in ('left','right') else 1.
                width=min(desired,wall.length*span/n-.30)
                if width<.5:fail('window_capacity',surface['id'],'window too narrow')
                coords=list(wall.coords)
                tangent,_=_normal_line(coords[0],coords[-1]);xy=np.array(center.coords[0])
                line=LineString([xy-tangent*width/2,xy+tangent*width/2])
                landing=Polygon([xy-tangent*(width/2+.12),xy+tangent*(width/2+.12),
                                 xy+tangent*(width/2+.12)+inward*1.,xy-tangent*(width/2+.12)+inward*1.])
                slots.append(dict(id=f'window/{facade["body"]}/{facade["front"]}/{floor}/{index}',
                                  line=line,landing=landing,anchor=Point(xy+inward*.65),
                                  proportion=proportion,width_m=width,source='explicit',front=facade['front']))
                index+=1
    return slots


def _entry(massing, envelope, frame, floor, garage=None, protected=()):
    site=massing.request['building'].get('site',{})
    position=site.get('door','left')
    if isinstance(position,dict):position=position.get('position','left')
    if position is False:fail('entry_absent','building.site.door','residential circulation needs an entrance')
    candidates=[]
    for row in massing.storeys:
        if row['floor']!=floor:continue
        for s in row['surfaces']:
            if s['front'] is None or s['length_m']<1.2:continue
            line=local(LineString(s['line']),frame)
            if garage is not None:line=line.difference(garage.buffer(.2))
            for segment in lines(line):
                if segment.length<1.2:continue
                tangent,_=_normal_line(segment.coords[0],segment.coords[-1])
                for at in np.linspace(.65,segment.length-.65,max(4,int(segment.length*4))):
                    center=segment.interpolate(at)
                    door=LineString([np.array(center.coords[0])-tangent*.475,np.array(center.coords[0])+tangent*.475])
                    if any(door.buffer(.2).intersects(p) for p in protected):continue
                    target=nearest_points(envelope,center)[0]
                    x,y=target.coords[0]
                    score=x if position=='left' else -x if position=='right' else abs(x-envelope.centroid.x)
                    candidates.append((y,score,door,target))
    if not candidates:fail('entry_unavailable',f'floor{floor}','no facade segment for independent entrance')
    _,_,segment,target=min(candidates,key=lambda item:item[:2])
    opening,_=_boundary_slot(segment,.95)
    return opening,target


def _usable(poly,min_area=6.):
    return poly.geom_type=='Polygon' and poly.area>=min_area and not poly.buffer(-.8,join_style=2).is_empty


def _window_cuts(slots):
    """Preferred partition coordinates between neighbouring windows.

    Cutting the body between two windows of the same facade makes each opening
    face its own room; diagonal facades are left to the balanced search.
    """
    cuts_x=[];cuts_y=[];groups={}
    for slot in slots:
        coords=list(slot['line'].coords)
        if abs(coords[0][1]-coords[-1][1])<1e-6:groups.setdefault('h',[]).append(slot)
        elif abs(coords[0][0]-coords[-1][0])<1e-6:groups.setdefault('v',[]).append(slot)
    for key,group in groups.items():
        axis=0 if key=='h' else 1
        ordered=sorted(group,key=lambda s:min(point[axis] for point in s['line'].coords))
        for first,second in zip(ordered,ordered[1:]):
            end=max(point[axis] for point in first['line'].coords)
            start=min(point[axis] for point in second['line'].coords)
            if start-end>.6:(cuts_x if axis==0 else cuts_y).append((end+start)/2)
    return cuts_x,cuts_y


def _partition(region,protected,rng,cuts=((),())):
    leaves=[]
    def divide(p,depth=0):
        if p.area<24 or depth>=7:leaves.append(p);return
        x0,y0,x1,y1=p.bounds
        axes=sorted([0,1],key=lambda axis:-(x1-x0 if axis==0 else y1-y0))
        for axis in axes:
            candidates=[]
            low,high=(x0,x1) if axis==0 else (y0,y1)
            for at in cuts[axis]:
                if low+.3<at<high-.3:candidates.append(at)
            for fraction in (float(rng.uniform(.42,.58)),.5,.4,.6):
                at=low+(high-low)*fraction
                if low+.3<at<high-.3:candidates.append(at)
            for at in candidates:
                cutter=LineString([(at,y0-1),(at,y1+1)]) if axis==0 else LineString([(x0-1,at),(x1+1,at)])
                if any(cutter.intersection(zone).length>EPS for zone in protected):continue
                parts=polygons(split(p,cutter))
                if len(parts)>=2 and all(_usable(part) for part in parts):
                    for part in parts:divide(part,depth+1)
                    return
        leaves.append(p)
    for p in polygons(region):divide(p)
    # Merge slivers into a true adjacent room, never discard area.
    while any(not _usable(p) for p in leaves) and len(leaves)>1:
        i=next(i for i,p in enumerate(leaves) if not _usable(p))
        matches=[(leaves[i].boundary.intersection(p.boundary).length,j) for j,p in enumerate(leaves) if j!=i]
        length,j=max(matches)
        if length<=.05:break
        merged=clean(leaves[i].union(leaves[j]))
        leaves=[p for k,p in enumerate(leaves) if k not in (i,j)]+[merged]
    if any(not _usable(p) for p in leaves):fail('residual_room','partition','unusable leftover cannot be merged')
    return sorted(leaves,key=lambda p:(round(p.centroid.y,6),round(p.centroid.x,6)))


def _core_candidates(envelopes,obstacles,levels):
    common=envelopes[0]
    for p in envelopes[1:]:common=common.intersection(p)
    common=clean(common.difference(unary_union(obstacles)))
    if common.is_empty:fail('vertical_core_fit','stairs','floors have no shared usable footprint')
    x0,y0,x1,y1=common.bounds
    rise=max(b-a for a,b in zip(levels,levels[1:]))
    steps=math.ceil(rise/.18)
    length=max(3.4,(math.ceil(steps/2)-1)*.27+1.1)
    candidates=[]
    if len(levels)==2:
        for x in (x0+.12,max(x0+.12,x1-1.82)):
            for y in np.linspace(y0+.88,max(y0+.88,y1-2.62),5):
                bath=box(x,y,x+1.7,y+2.5);landing=box(x,y-.75,x+1.7,y)
                if common.covers(bath.union(landing)):
                    candidates.append(dict(stair=Polygon(),bath=bath,
                        shaft=box(x,y+2.1,x+.4,y+2.5),landing=landing))
        if not candidates:fail('service_core_fit','services','no bathroom/shaft fits single-storey floor')
        return candidates

    def place(stair,bath,landing):
        if common.buffer(EPS).covers(stair.union(bath).union(landing)):
            candidates.append(dict(stair=stair,bath=bath,landing=landing,
                shaft=box(bath.bounds[0],bath.bounds[3]-.4,bath.bounds[0]+.4,bath.bounds[3])))

    # Side by side fits wide wings; stacked variants fit narrow ones (U/L, podium).
    for side in (1,-1):
        xlo=x0+.12 if side==1 else x0+1.94
        xhi=(x1-4.14) if side==1 else (x1-2.32)
        if xhi<xlo:continue
        for x in np.linspace(xlo,xhi,9):
            for y in np.linspace(y0+.87,max(y0+.87,y1-length-.12),7):
                stair=box(x,y,x+2.2,y+length);landing=box(x,y-.75,x+2.2,y)
                bath=box(x+2.32,y,x+4.02,y+2.5) if side==1 else box(x-1.82,y,x-.12,y+2.5)
                place(stair,bath,landing)
    if y1-length-2.74>=y0+.87:
        for x in np.linspace(x0+.12,max(x0+.12,x1-2.32),11):
            for y in np.linspace(y0+.87,y1-length-2.74,6):
                stair=box(x,y,x+2.2,y+length);landing=box(x,y-.75,x+2.2,y)
                place(stair,bath=box(x,y+length+.12,x+2.2,y+length+2.62),landing=landing)
    if y1-length-.12>=y0+3.49:
        for x in np.linspace(x0+.12,max(x0+.12,x1-2.32),11):
            for y in np.linspace(y0+3.49,y1-length-.12,6):
                stair=box(x,y,x+2.2,y+length);landing=box(x,y-.75,x+2.2,y)
                place(stair,bath=box(x,y-3.37,x+2.2,y-.87),landing=landing)
    # Rotated stair (long side along x) for shallow floors: service sits above,
    # below or opposite the flight instead of shoulder to shoulder.
    for foot in (0,1):
        for where in ('above','below','beside'):
            for x in np.linspace(x0+.12,max(x0+.12,x1-length-.12),7):
                for y in np.linspace(y0+.12,max(y0+.12,y1-2.32),7):
                    stair=box(x,y,x+length,y+2.2)
                    landing=box(x-.75,y,x,y+2.2) if foot==0 else box(x+length,y,x+length+.75,y+2.2)
                    if where=='above':bath=box(x,y+2.32,x+1.7,y+4.82)
                    elif where=='below':bath=box(x,y-2.62,x+1.7,y-.12)
                    elif foot==0:bath=box(x+length+.12,y,x+length+1.82,y+2.5)
                    else:bath=box(x-1.82,y,x-.12,y+2.5)
                    place(stair,bath,landing)
    if not candidates:fail('vertical_core_fit','stairs','no continuous 2.20 m stair and service core fits all floors')
    # Spatially distinct options rather than tiny shifts of the same core.
    candidates.sort(key=lambda c:(c['stair'].centroid.distance(common.centroid),c['stair'].bounds))
    selected=[]
    for c in candidates:
        if all(c['stair'].centroid.distance(old['stair'].centroid)>1.5 for old in selected):selected.append(c)
        if len(selected)==8:break
    return selected


def _floor_layout(massing,floor,envelope,frame,core,seed):
    prefix=f'floor{floor}';rows=[r for r in massing.storeys if r['floor']==floor]
    open_floor=all(r['kind']=='open' for r in rows)
    stair=core['stair'];bath=core['bath'];shaft=core['shaft']
    obstacles=stair.union(bath);garage=None
    site=massing.request['building'].get('site',{})
    if floor==1 and site.get('garage'):
        x0,y0,x1,y1=envelope.bounds
        gx=x0 if site['garage']=='left' else x1-2.9
        garage=box(gx,y0,gx+2.9,y0+5.2)
        if not envelope.buffer(EPS).covers(garage) or garage.intersection(obstacles).area>EPS:
            fail('garage_fit',prefix,'2.90 × 5.20 m garage conflicts with core or footprint')
        obstacles=obstacles.union(garage)
    windows=_facade_slots(massing,floor,frame,blocked=garage)
    spaces=[s for r in rows for s in r.get('spaces',[])]
    protected=[s['landing'] for s in windows]+[local(shape(s['access']['geometry']),frame).buffer(.1) for s in spaces]
    if any(stair.union(bath).intersection(p).area>EPS for p in protected):
        fail('core_blocks_opening',prefix,'vertical core overlaps a window or exterior access')
    if garage is not None and any(garage.intersection(p).area>EPS for p in protected):
        fail('garage_opening',prefix,'garage conflicts with requested opening')
    walkable=clean(envelope.difference(obstacles))
    entry=None;objectives=[core['landing'].centroid]
    if floor==1:
        entry,target=_entry(massing,envelope,frame,floor,garage,protected);objectives.append(Point(target))
    x0,y0,x1,y1=walkable.bounds
    objectives.append(Point((x0+x1)/2,y1-.4))

    def regions(width):
        safe=clean(walkable.buffer(-width/2,join_style=2))
        if safe.is_empty:raise PlanningError('circulation_clearance',prefix,'no circulation strip')
        return safe,clean(safe.difference(unary_union([p.buffer(.1) for p in protected])))

    def route(region,width,extra=()):
        pieces=[];root=nearest_points(region,core['landing'].centroid)[0]
        for objective in list(objectives)+list(extra):
            target=nearest_points(walkable,objective)[0]
            anchor=nearest_points(region,target)[0]
            pieces.append(shortest_path(region,root,anchor,prefix))
            stub=LineString([anchor,target])
            if not walkable.buffer(EPS).covers(stub):stub=shortest_path(walkable,anchor,target,prefix)
            pieces.append(stub)
        return clean(unary_union([p.buffer(width/2,cap_style=1,join_style=2) for p in pieces]
                                +[core['landing']]).intersection(walkable))

    def attempt(width,extra=()):
        collected=[]
        for region in regions(width):
            if region.is_empty:continue
            try:candidate=route(region,width,extra)
            except PlanningError as error:collected.append(error);continue
            if any(candidate.intersection(s['landing']).area>.2 for s in windows):
                collected.append(PlanningError('corridor_blocks_window',prefix,'circulation consumes a requested room window'));continue
            return candidate
        raise collected[-1] if collected else PlanningError('circulation_disconnected',prefix,'no route region')

    circulation=None;corridor_width=CORRIDOR
    for width in (CORRIDOR,1.0):
        try:circulation=attempt(width)
        except PlanningError:continue
        corridor_width=width;break
    if circulation is None:
        fail('circulation_disconnected',prefix,'no clear route at 1.20 m nor 1.00 m')
    # Reach wings or courtyards whose rooms would otherwise stay off the spine.
    residual=clean(envelope.difference(obstacles.union(circulation)))
    extra=[p.representative_point() for p in polygons(residual)
           if _usable(p,min_area=12) and p.distance(circulation)>2.0][:2]
    if extra:
        try:circulation=attempt(corridor_width,extra)
        except PlanningError:pass
    # Absorb thin leftovers into the circulation region; never lose their area.
    for _ in range(2):
        residual=clean(envelope.difference(obstacles.union(circulation)))
        absorbed=False
        for piece in polygons(residual):
            if _usable(piece):continue
            if piece.boundary.intersection(circulation.boundary).length>.05 or piece.distance(circulation)<.05:
                circulation=clean(circulation.union(piece));absorbed=True
        if not absorbed:break
    if any(circulation.intersection(s['landing']).area>.2 for s in windows):
        fail('corridor_blocks_window',prefix,'clearance zones leave no window room')
    residual=clean(envelope.difference(obstacles.union(circulation)))
    rng=np.random.default_rng(resolve_seed(seed,'intent','interiors',prefix,'partition'))
    room_polys=[] if open_floor else _partition(residual,protected,rng,_window_cuts(windows))
    cells=[dict(id=prefix+'/hall',kind='circulation',poly=circulation),
           dict(id=prefix+'/bath',kind='bathroom',poly=clean(bath.difference(shaft)))]
    if not stair.is_empty:cells.append(dict(id=prefix+'/stairs',kind='stairs',poly=stair))
    if open_floor:
        for i,p in enumerate(polygons(residual)):cells.append(dict(id=f'{prefix}/open{i}',kind='open_ground',poly=p))
    else:
        for i,p in enumerate(room_polys):cells.append(dict(id=f'{prefix}/room{i}',kind='unassigned',poly=p))
    if garage is not None:cells.append(dict(id=prefix+'/garage',kind='garage',poly=garage))
    # Build the actual adjacency graph; select a tree favoring direct hall access.
    graph={c['id']:[] for c in cells};byid={c['id']:c for c in cells}
    for i,a in enumerate(cells):
        for b in cells[:i]:
            shared=a['poly'].boundary.intersection(b['poly'].boundary)
            segments=[s for s in lines(shared) if s.length>=1.05]
            if not segments:continue
            segment=max(segments,key=lambda s:s.length)
            graph[a['id']].append((b['id'],segment));graph[b['id']].append((a['id'],segment))
    visited={prefix+'/hall'};queue=[prefix+'/hall'];doors=[]
    while queue:
        source=queue.pop(0)
        for target,line in sorted(graph[source],key=lambda p:p[0]):
            if target in visited:continue
            # Service rooms and garages must never be passageways to bedrooms.
            if byid[source]['kind'] in ('bathroom','garage','stairs'):continue
            door,cut=_boundary_slot(line,.85 if byid[target]['kind']=='bathroom' else .9)
            doors.append(dict(id=f'{prefix}/door{len(doors)}',source=source,target=target,line=door,cut=cut))
            visited.add(target);queue.append(target)
    if set(graph)-visited:fail('room_disconnected',prefix,','.join(sorted(set(graph)-visited)))
    ownership={}
    for slot in windows:
        candidates=[c for c in cells if c['poly'].buffer(EPS).covers(slot['anchor']) and c['kind'] not in ('circulation','stairs','garage')]
        if len(candidates)!=1:fail('window_partition',slot['id'],'window has no unique usable room')
        owner=candidates[0];ownership[slot['id']]=owner['id']
        if owner['kind']=='unassigned':
            if slot['proportion']=='small_high':owner['kind']='service'
            else:owner['kind']='living' if slot['proportion']=='horizontal' else 'bedroom'
    through={d['source'] for d in doors}
    for c in cells:
        if c['kind']=='unassigned':c['kind']='living' if c['id'] in through else 'bedroom'
        if c['kind']=='bedroom' and c['id'] in through:c['kind']='living'
    unassigned=[c for c in cells if c['kind'] in ('bedroom','living')]
    if unassigned:
        kitchen=min(unassigned,key=lambda c:c['poly'].distance(bath))
        if kitchen['id'] not in ownership.values():kitchen['kind']='kitchen_dining'
    if massing.request['building'].get('profile')=='barranco_mixed_use' and floor==1:
        for c in cells:
            if c['kind']=='living':c['kind']='shop'
    exterior_connections=[]
    for space in spaces:
        access=local(shape(space['access']['geometry']),frame)
        candidates=[c for c in cells if c['poly'].intersection(access).area>.03]
        rooms=[c for c in candidates if c['kind'] not in ('stairs','bathroom','garage','circulation')]
        if rooms:candidates=rooms
        if len(candidates)!=1:fail('space_partition',space['id'],'access split between rooms or unavailable')
        exterior_connections.append(dict(source=candidates[0]['id'],target=space['id'],kind='exterior_space',geometry=encode(world(access,frame))))
    if entry is not None:
        exterior_connections.append(dict(source='street',target=prefix+'/hall',kind='entrance',geometry=encode(world(entry,frame))))
    if garage is not None:
        x0,y0,x1,_=garage.bounds
        exterior_connections.append(dict(source='street',target=prefix+'/garage',kind='vehicle_entry',geometry=encode(world(LineString([(x0+.15,y0),(x1-.15,y0)]),frame))))
    room_union=unary_union([c['poly'] for c in cells]+[shaft])
    if room_union.symmetric_difference(envelope).area>1e-5:fail('partition_coverage',prefix,'partition does not cover usable floor')
    walls=clean(unary_union([c['poly'].boundary.buffer(WALL/2,join_style=2) for c in cells]).intersection(envelope))
    # Door cuts connect net room regions; explicit exterior slots remain clear.
    cuts=[d['cut'] for d in doors]+[s['landing'] for s in windows]+[local(shape(s['access']['geometry']),frame) for s in spaces]
    if entry is not None:cuts.append(entry.buffer(.3,cap_style=2))
    walls=clean(walls.difference(unary_union(cuts)))
    room_records=[]
    for c in cells:
        net=clean(c['poly'].difference(walls))
        room_records.append(dict(id=c['id'],kind=c['kind'],geometry=encode(world(c['poly'],frame)),
                                 usable_geometry=encode(world(net,frame)),area_m2=net.area))
    window_records=[dict(id=s['id'],room=ownership[s['id']],geometry=encode(world(s['line'],frame)),
                         clearance=encode(world(s['landing'],frame)),proportion=s['proportion'],width_m=s['width_m'],source=s['source']) for s in windows]
    for d in doors:
        d['geometry']=encode(world(d.pop('line'),frame));d['clearance']=encode(world(d.pop('cut'),frame))
    window_counts={}
    for owner in ownership.values():window_counts[owner]=window_counts.get(owner,0)+1
    shared_windows=sum(count-1 for count in window_counts.values())
    return dict(floor=floor,bottom_m=massing.request['context']['levels_m'][floor-1],
                envelope=encode(world(envelope,frame)),rooms=room_records,doors=doors,windows=window_records,
                connections=exterior_connections,walls=encode(world(walls,frame)),
                service_shaft=encode(world(shaft,frame)),open_ground=open_floor,corridor_width_m=corridor_width,
                score=float(circulation.area/envelope.area+len([c for c in cells if c['id'] in through and c['kind']!='circulation'])*.04+shared_windows*.06),
                checks=dict(connected=True,coverage_error_m2=room_union.symmetric_difference(envelope).area))


def plan_interiors(request):
    massing=plan_articulation(request)
    primary=min(massing.fronts,key=lambda key:(-massing.fronts[key]['length_m'],key));frame=massing.fronts[primary]
    levels=massing.request['context']['levels_m'];seed=massing.request.get('seed',0)
    floor_numbers=sorted({r['floor'] for r in massing.storeys})
    if floor_numbers!=list(range(1,max(floor_numbers)+1)):fail('floor_gap','floors','continuous floors required')
    envelopes=[]
    for floor in floor_numbers:
        full=unary_union([shape(r['enclosed_geometry']) for r in massing.storeys if r['floor']==floor])
        envelope=clean(local(full,frame).buffer(-EXTERIOR,join_style=2))
        if envelope.geom_type!='Polygon':fail('disconnected_floor',f'floor{floor}','enclosed bodies must share a usable connection')
        envelopes.append(envelope)
    obstacles=[local(shape(s['geometry']),frame).buffer(.1) for s in massing.supports if s['kind']=='column']
    candidates=_core_candidates(envelopes,obstacles,levels)
    alternatives=[];solutions=[]
    for index,core in enumerate(candidates):
        try:
            floors=[_floor_layout(massing,f,e,frame,core,seed+index) for f,e in zip(floor_numbers,envelopes)]
            score=sum(f['score'] for f in floors)
            alternatives.append(dict(id=index,status='valid',score=score))
            solutions.append((score,index,core,floors))
        except PlanningError as error:
            alternatives.append(dict(id=index,status='conflict',code=error.code,path=error.path,message=str(error)))
    if not solutions:
        fail('no_feasible_layout','interiors','; '.join(f"{a['id']}:{a['code']}" for a in alternatives))
    score,index,core,floors=min(solutions,key=lambda item:item[:2])
    connections=[dict(source=d['source'],target=d['target'],kind='door',id=d['id']) for f in floors for d in f['doors']]
    connections.extend(c for f in floors for c in f['connections'])
    flights=[]
    for a,b in zip(floor_numbers,floor_numbers[1:]):
        rise=levels[b-1]-levels[a-1];risers=math.ceil(rise/.18)
        flights.append(dict(source=f'floor{a}/stairs',target=f'floor{b}/stairs',bottom_m=levels[a-1],top_m=levels[b-1],
                            risers=risers,riser_m=rise/risers,tread_m=.27,flight_width_m=.95,landing_m=1.1))
        connections.append(dict(source=f'floor{a}/stairs',target=f'floor{b}/stairs',kind='stair'))
    return InteriorPlan('interior-plan-v1',massing.request,massing.to_dict(),floors,
                        dict(stairs=encode(world(core['stair'],frame)),shaft=encode(world(core['shaft'],frame)),
                             services=encode(world(core['bath'],frame)),flights=flights,selected_alternative=index),
                        connections,alternatives,dict(connected=True,continuous_core=True,engineering_verified=False,
                                                      score=score,exterior_preserved=True))
