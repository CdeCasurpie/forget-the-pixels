"""Constructive envelope: metric apertures, hollow walls, slabs and joinery.

The interior plan owns topology. This stage owns floor-relative elevations and
construction. Parts are disjoint-volume vertical prisms; touching interfaces
are intentional. Opening IDs link reservations, cuts, frames and glazing.
"""
from dataclasses import dataclass, asdict
import math

import numpy as np
from shapely import make_valid, remove_repeated_points
from shapely.errors import GEOSException
from shapely.geometry import LineString, MultiPolygon, Point, Polygon, shape
from shapely.ops import unary_union, nearest_points

from planning.interiors import plan_interiors, lines, EXTERIOR, WALL
from planning.massing import clean, encode, polygons, fail

SLAB=.18
LINTEL=.20
RATIOS={'horizontal':(1.15,3.5,1.8),'vertical':(.35,.85,.65),
        'square':(.85,1.15,1.),'small_high':(.8,2.5,1.5)}
PROFILE_WIDTH={'moderno':.045,'madera':.06,'clasico':.06,'republicano':.065,'barroco':.07}


@dataclass
class EnvelopePlan:
    version: str
    request: dict
    interior: dict
    openings: list
    parts: list
    decisions: list
    pending: list
    checks: dict

    def to_dict(self):return asdict(self)


def chart(line, inward=None):
    a=np.asarray(line.coords[0]);b=np.asarray(line.coords[-1])
    t=(b-a)/np.linalg.norm(b-a)
    n=np.asarray(inward) if inward is not None else np.array([-t[1],t[0]])
    return a,t,n


def strip(line, start, end, back, front, inward=None):
    a,t,n=chart(line,inward)
    return Polygon([a+t*start+n*back,a+t*end+n*back,
                    a+t*end+n*front,a+t*start+n*front])


def window_dimensions(width, proportion, room, useful):
    """Solve proportions and useful height jointly, never silently squash a type.

    When the requested band cannot fit at this width, the height is capped at
    the available maximum and the caller records the adaptation as a decision.
    """
    lo,hi,target=RATIOS[proportion]
    sill=1.50 if proportion=='small_high' else {'bathroom':1.2,'service':1.2,
           'kitchen_dining':1.05,'living':.70,'shop':.60}.get(room,.90)
    maximum=useful-LINTEL-sill
    if maximum<.35:fail('useful_height','windows',f'{room} has no room for a window above {sill:.2f} m')
    height=min(width/target,maximum,2.4)
    height=max(height,width/hi,.35)
    height=min(height,width/lo)
    if height<.35-1e-7:fail('opening_height','windows',f'{proportion} width {width:.2f} cannot fit useful height {useful:.2f}')
    adapted=height>maximum+1e-7
    if adapted:height=maximum
    return sill,sill+height,adapted


def _surface(line, surfaces):
    matches=[s for s in surfaces if LineString(s['line']).buffer(1e-6).covers(line)]
    if not matches:fail('opening_out_of_wall','openings','reservation has no exterior host')
    return min(matches,key=lambda s:s['id'])


def _design(request, surface, floor, kind, proportion=None):
    b=request['building'];body=surface.get('body','main')
    body_spec=next((v for v in b.get('bodies',[]) if v['id']==body),{})
    fac=next((f for f in b.get('facades',[]) if f['body']==body and
              f['front']==surface.get('front') and floor in f['floors']),{})
    w=fac.get('windows',{}) if kind=='window' else {}
    door=b.get('site',{}).get('door',{}) if kind=='entrance' else {}
    if not isinstance(door,dict):door={}
    style=door.get('style',w.get('style',fac.get('style',body_spec.get('style',b.get('style','moderno')))))
    if style=='mixed':style='moderno'  # resolved local prior, not a global prohibition
    material=door.get('material',w.get('frame','wood' if style in ('madera','republicano','clasico','barroco') else 'metal'))
    mechanism=w.get('mechanism', 'awning' if proportion=='small_high' else
                    'sliding' if proportion=='horizontal' else 'casement') if kind=='window' else 'hinged'
    if kind=='vehicle_entry':mechanism='sliding';material='metal'
    return dict(style=style,material=material,mechanism=mechanism)


def _completion(interior, floor, surfaces, explicit, partitions):
    """One window per eligible perimeter room on an unspecified exposure.

    Named street fronts and boundaries inside the parcel are exposed. Unnamed
    parcel edges are party walls. Explicit counts (including zero) are closed
    scopes. A facade list [] explicitly disables facade completion.
    """
    b=interior['request']['building']
    if b.get('facades')==[]:return []
    parcel=Polygon(interior['request']['context']['parcel'])
    used=[shape(o['cut_geometry']).buffer(.20) for o in explicit]
    result=[]
    for room in floor['rooms']:
        if room['kind'] in ('stairs','circulation','garage','open_ground'):continue
        if any(o.get('room')==room['id'] and o['kind']=='window' for o in explicit):continue
        poly=shape(room['geometry']);options=[]
        for surface in surfaces:
            if not surface['enclosure']:continue
            scopes=[f for f in b.get('facades',[]) if f['body']==surface['body'] and
                    f['front']==surface['front'] and floor['floor'] in f['floors']]
            if any('windows' in f for f in scopes):continue
            edge=LineString(surface['line'])
            if surface['front'] is None and edge.distance(parcel.boundary)<1e-6:continue
            segment=edge.intersection(poly.buffer(EXTERIOR+.015,join_style=2))
            segment=segment.difference(unary_union(used))
            for piece in lines(segment):
                if piece.length<1.05:continue
                width=min(1.5 if room['kind'] in ('living','kitchen_dining','shop') else .85,piece.length-.40)
                center=piece.interpolate(.5,normalized=True)
                _,t,n=chart(edge,-np.asarray(surface['normal']))
                a=np.array(center.coords[0]);line=LineString([a-t*width/2,a+t*width/2])
                inner=strip(line,0,width,EXTERIOR+.01,EXTERIOR+.18,n)
                if not poly.buffer(.01).covers(inner):continue
                if partitions.intersection(inner).area>1e-5:continue
                options.append((-(surface['front'] is not None),-piece.length,surface['id'],line,surface))
        if not options:continue
        _,_,_,line,surface=min(options,key=lambda x:x[:3])
        proportion='small_high' if room['kind'] in ('service','bathroom') else 'horizontal' if line.length>=1.3 else 'vertical'
        result.append((dict(id=room['id']+'/auto_window',geometry=encode(line),width_m=line.length,
                            room=room['id'],proportion=proportion,source='completion'),surface))
        used.append(line.buffer(.40,cap_style=2))
    return result


def _sturdy(poly):
    """Rebuild a construction polygon for extrusion into a closed prism.

    Boolean stages leave sub-micrometre vertices and zero-area rings; GEOS
    dedupe and trimesh extrusion choke on them. Numerically degenerate
    components and holes are dropped and each ring is deduped five orders
    below the 6 cm wall half thickness.
    """
    fixed=[]
    for component in polygons(clean(poly)):
        if component.area<=1e-9:continue
        try:shell=remove_repeated_points(Polygon(component.exterior),tolerance=1e-7)
        except GEOSException:continue
        if shell.is_empty:continue
        holes=[]
        for ring in component.interiors:
            if Polygon(ring).area<=1e-9:continue
            try:hole=remove_repeated_points(Polygon(ring),tolerance=1e-7)
            except GEOSException:continue
            if not hole.is_empty:holes.append(hole.exterior)
        candidate=Polygon(shell.exterior,holes)
        if candidate.is_valid:fixed.append(candidate)
    return MultiPolygon(fixed) if len(fixed)>1 else (fixed[0] if fixed else Polygon())


def _part(parts, identity, kind, material, floor, poly, bottom, top, opening=None):
    poly=_sturdy(poly)
    if poly.is_empty or top-bottom<1e-7:return
    if not poly.is_valid:poly=clean(make_valid(poly))
    if poly.is_empty or not poly.is_valid:fail('invalid_part',identity,'invalid construction polygon')
    parts.append(dict(id=identity,kind=kind,material=material,floor=floor,
                      geometry=encode(poly),bottom_m=float(bottom),top_m=float(top),opening=opening))


def _joinery(op, parts):
    """Nested, non-overlapping members. Tracks encode mechanism independently of style."""
    line=shape(op['geometry']);width=line.length;n=op['inward']
    z0,z1=op['bottom_m'],op['top_m'];fw=op['frame_width_m'];depth=op['wall_thickness_m']
    back=min(.06,depth*.25);front=min(depth-.015,back+.065)
    material=op['material'];frame_mat='metal' if material=='glass' else material
    # Interior reveals are clipped against the exterior wall; members must be
    # built from the same clipped reveal, never from the raw wall strip.
    reveal=None if op['surface'] is not None else shape(op['cut_geometry'])
    # Members stop one millimetre short of reveals and of each other: no
    # coplanar faces across material groups, no accidental shared volumes.
    e=.001
    def emit(name,u0,u1,v0,v1,low,high,mat):
        poly=strip(line,u0,u1,v0,v1,n)
        if reveal is not None:
            pieces=polygons(poly.intersection(reveal))
            if not pieces:return
            poly=max(pieces,key=lambda piece:piece.area)
        _part(parts,op['id']+'/'+name,name,mat,op['floor'],poly,low,high,op['id'])
    emit('jamb_left',e,e+fw,back,front,z0,z1-e,frame_mat)
    emit('jamb_right',width-e-fw,width-e,back,front,z0,z1-e,frame_mat)
    emit('head',fw,width-fw,back,front,z1-fw,z1-e,frame_mat)
    window=op['kind']=='window'
    if window:emit('sill',fw,width-fw,back,front,z0,z0+fw,frame_mat)
    low=z0+fw if window else z0+.01;high=z1-fw
    # A small projecting sill is below the glazing, replaces rather than covers masonry.
    if window:emit('sill_cap',e,width-e,-.02,depth-e,z0+.0005,z0+.024,'stone')
    # Frames above the sill cap do not duplicate its volume.
    if window:
        for p in parts:
            if p['opening']==op['id'] and p['kind'] in ('jamb_left','jamb_right','sill'):
                p['bottom_m']=max(p['bottom_m'],z0+.025)
    u0,u1=fw+.004,width-fw-.004;low+=.004;high-=.004
    horizontal=op['mechanism']=='guillotine'
    count=2 if (op['mechanism'] in ('sliding','guillotine') or op['mechanism'] in ('casement','hinged') and width>1.3) else 1
    op['leaves']=count
    rail=.025
    for i in range(count):
        a=u0 if horizontal else u0+(u1-u0)*i/count+.003
        b=u1 if horizontal else u0+(u1-u0)*(i+1)/count-.003
        c=low+(high-low)*i/count+.003 if horizontal else low
        d=low+(high-low)*(i+1)/count-.003 if horizontal else high
        track=back+.008+i*.025 if op['mechanism'] in ('sliding','guillotine') else back+.012
        infill='glass' if window or material=='glass' or op['kind']=='exterior_space' else material
        emit(f'leaf{i}_left',a,a+rail,track,track+.02,c,d,frame_mat)
        emit(f'leaf{i}_right',b-rail,b,track,track+.02,c,d,frame_mat)
        emit(f'leaf{i}_bottom',a+rail,b-rail,track,track+.02,c,c+rail,frame_mat)
        emit(f'leaf{i}_top',a+rail,b-rail,track,track+.02,d-rail,d,frame_mat)
        emit(f'leaf{i}_infill',a+rail+e,b-rail-e,track+.006,track+.014,c+rail+e,d-rail-e,infill)
        if not window:
            emit(f'handle{i}',b-.08,b-.06,track-.025,track-e,c+.9,min(d-.05,c+1.03),'metal')
    op['recess_m']=back
    op['clear_width_m']=width-2*fw
    op['clear_height_m']=z1-z0-fw*(2 if window else 1)


def build_envelope(interior):
    data=interior.to_dict() if hasattr(interior,'to_dict') else interior
    request=data['request'];m=data['massing'];levels=request['context']['levels_m']
    parts=[];openings=[];decisions=[];pending=[];floor_data={f['floor']:f for f in data['floors']}
    for f in data['floors']:
        floor=f['floor'];bottom=levels[floor-1];top=levels[floor]-SLAB
        if top-bottom<2.30:fail('useful_height',f'floor{floor}','less than 2.30 m below slab')
        rows=[r for r in m['storeys'] if r['floor']==floor]
        full=unary_union([shape(r['enclosed_geometry']) for r in rows if r['kind']=='enclosed'])
        env=shape(f['envelope'])
        outer=clean(full.difference(env))
        # Only genuine shared interior boundaries, not the perimeter of the
        # inset envelope (which would add an unintended second exterior wall).
        boundaries=unary_union([shape(r['geometry']).boundary for r in f['rooms']]+[shape(f['service_shaft']).boundary])
        boundaries=boundaries.difference(env.boundary.buffer(1e-6))
        # Overlay re-noding leaves sub-nanometre duplicate vertices; GEOS buffer
        # distorts the offset curve around them, so dedupe two orders of
        # magnitude below the 6 cm wall half thickness.
        boundaries=remove_repeated_points(boundaries,tolerance=1e-9)
        partition=clean(boundaries.buffer(WALL/2,join_style=2,cap_style=2).intersection(env))
        surfaces=[dict(s,body=r['body']) for r in rows for s in r['surfaces'] if s['enclosure']]
        byroom={r['id']:r for r in f['rooms']}
        current=[]

        def opening(record,kind,surface=None):
            line=shape(record['geometry']);w=line.length
            axis=line
            if surface is None:
                n=chart(line)[2];thickness=WALL
                # Local origin is the front face, not the partition centreline.
                line=LineString([np.asarray(p)-n*WALL/2 for p in line.coords])
                surface={}
            else:n=-np.asarray(surface['normal']);thickness=EXTERIOR
            design=_design(request,surface,floor,kind,record.get('proportion'))
            fw=PROFILE_WIDTH[design['style']]
            if kind=='window':
                sill,head,adapted=window_dimensions(w,record['proportion'],byroom[record['room']]['kind'],top-bottom)
                if adapted:decisions.append(dict(id=record['id'],reason='requested proportion adapted to available useful height'))
            else:
                sill=0.;head=min(2.35 if kind=='vehicle_entry' else 2.15,top-bottom-LINTEL)
            # Interior reveals overshoot their partition by one centimetre only;
            # exterior reveals pierce the outer leaf with margin.
            cut=strip(line,0,w,-.01,thickness+(.01 if not surface else .08),n)
            if not surface:
                # Interior reveals may overshoot their partition to pierce the
                # junction, but must never claim volume inside exterior walls.
                cut=cut.difference(outer)
            op=dict(id=record['id'],kind=kind,floor=floor,room=record.get('room',record.get('target')),
                    source=record.get('source','connection'),geometry=encode(line),axis=encode(axis),
                    inward=n.tolist(),cut_geometry=encode(cut),width_m=w,bottom_m=bottom+sill,top_m=bottom+head,
                    sill_m=sill,head_m=head,wall_thickness_m=thickness,frame_width_m=fw,
                    surface=surface.get('id'),body=surface.get('body'),front=surface.get('front'),
                    proportion=record.get('proportion'),**design)
            if kind!='window' and w-2*fw<.70:fail('door_clear_width',op['id'],'insufficient passage after frame')
            if head>=top-bottom-LINTEL-1e-7:decisions.append(dict(id=op['id'],reason='head limited by slab and lintel',head_m=head))
            current.append(op)

        for w in f['windows']:opening(w,'window',_surface(shape(w['geometry']),surfaces))
        for i,c in enumerate(f['connections']):
            if c['kind']=='exterior_space':
                space=next(s for r in rows for s in r.get('spaces',[]) if s['id']==c['target'])
                access=shape(space['access']['geometry'])
                candidates=[(LineString(s['line']).intersection(access.buffer(1e-7)),s) for s in surfaces]
                candidates=[(max(lines(g),key=lambda l:l.length),s) for g,s in candidates if lines(g)]
                line,surface=max(candidates,key=lambda pair:pair[0].length)
                center=line.interpolate(.5,normalized=True);a,t,n=chart(line)
                half=space['access']['width_m']/2
                line=LineString([np.array(center.coords[0])-t*half,np.array(center.coords[0])+t*half])
            else:
                line=shape(c['geometry'])
                # Phase 3 vehicle entrances are drawn on the inset interior boundary.
                surface=min(surfaces,key=lambda s:LineString(s['line']).distance(line)) if surfaces else None
                if surface is None:continue # open ground has no exterior door wall
                edge=LineString(surface['line']);a,t,n=chart(edge)
                center=nearest_points(edge,line.interpolate(.5,normalized=True))[0]
                line=LineString([np.array(center.coords[0])-t*line.length/2,np.array(center.coords[0])+t*line.length/2])
                if not edge.buffer(1e-6).covers(line):fail('entrance_host',c['kind'],'entrance outside host wall')
            opening(dict(id=f'floor{floor}/{c["kind"]}{i}',geometry=encode(line),room=c['source'] if c['kind']=='exterior_space' else c['target']),c['kind'],surface)
        for record,surface in _completion(data,f,surfaces,current,partition):
            opening(record,'window',surface)
            decisions.append(dict(id=record['id'],reason='perimeter room on unspecified exposed wall',source='completion'))
        # Overlap conflicts are volume removed from the SAME masonry: a reveal
        # only claims material within its own wall strip (its axis buffered),
        # never the air of a room nor the leaf of a neighbouring wall.
        def _masonry(op):
            cut=shape(op['cut_geometry'])
            if op['surface'] is None:
                strip=shape(op['axis']).buffer(WALL/2+1e-6,cap_style=2)
                return cut.intersection(partition).intersection(strip)
            return cut.intersection(outer)
        masonry=[dict(id=o['id'],geometry=_masonry(o)) for o in current]
        for door in f['doors']:
            # Cell polygons come from world-encoded boolean history, so shared
            # edges are near-coincident (line/line intersection yields points).
            # Measure the real wall extents by probing coverage of BOTH room
            # boundaries along the original door direction, then keep the door
            # on its own shared wall, away from junctions and other cuts.
            source=shape(byroom[door['source']]['geometry'])
            target=shape(byroom[door['target']]['geometry'])
            original=shape(door['geometry']);width=original.length
            a=np.asarray(original.coords[0]);b=np.asarray(original.coords[-1])
            t=(b-a)/np.linalg.norm(b-a)
            center=np.asarray(original.interpolate(.5,normalized=True).coords[0])
            sb=source.boundary;tb=target.boundary

            def covered(distance,sign):
                point=Point(center+t*(sign*distance))
                return sb.distance(point)<1e-6 and tb.distance(point)<1e-6

            def extent(sign):
                step=.05;low=0.
                while low<8. and covered(low+step,sign):low+=step
                high=low+step
                for _ in range(8):
                    middle=(low+high)/2
                    if covered(middle,sign):low=middle
                    else:high=middle
                return low

            left,right=extent(-1),extent(1)
            for margin in (.07,.06):
                lo=-left+margin+width/2;hi=right-margin-width/2
                if lo<=hi:break
            else:
                fail('door_junction',door['id'],'shared wall shorter than frame and clearances')
            offsets=sorted(set(np.linspace(lo,hi,13).tolist()+[lo,hi]),
                           key=abs)
            line=None;forced=None
            for offset in offsets:
                shifted=LineString([center+t*(offset-width/2),center+t*(offset+width/2)])
                n=chart(shifted)[2]
                cut=strip(shifted,0,width,-WALL/2-.01,WALL/2+.01,n).difference(outer).intersection(partition)
                band=shifted.buffer(WALL/2+1e-6,cap_style=2)
                candidate=cut.intersection(band)
                overlaps=[(entry['id'],candidate.intersection(entry['geometry']).area) for entry in masonry]
                if max((area for _,area in overlaps),default=0.)<=1e-5:
                    line=shifted
                    break
                total=sum(area for _,area in overlaps)
                if forced is None or total<forced[0]:
                    forced=(total,shifted,[name for name,area in overlaps if area>1e-5])
            if line is None:
                if forced is None:fail('door_junction',door['id'],'no collision-free frame on shared wall')
                _,line,_=forced
            if line.hausdorff_distance(original)>.01:
                decisions.append(dict(id=door['id'],reason='shift along same shared wall for frame clearance'))
            opening(dict(door,geometry=encode(line)),'door')
            masonry.append(dict(id=current[-1]['id'],geometry=_masonry(current[-1])))
        # Confirm host and supports before cutting; geometry checks use actual
        # prism intersections rather than a render or a declared boolean flag.
        masonry_by_id={entry['id']:entry['geometry'] for entry in masonry}
        for i,op in enumerate(current):
            cut=shape(op['cut_geometry']);host=partition if op['surface'] is None else outer
            if host.intersection(cut).area<op['width_m']*.04:fail('opening_out_of_wall',op['id'],'no wall through aperture')
            for other in current[:i]:
                if min(op['top_m'],other['top_m'])<=max(op['bottom_m'],other['bottom_m'])+1e-6:continue
                area=masonry_by_id[op['id']].intersection(masonry_by_id[other['id']]).area
                if area<=1e-5:continue
                if op['surface'] is None and other['surface'] is None and \
                   shape(op['axis']).distance(shape(other['axis']))>.02:
                    # Doors facing each other across adjoining thin partitions:
                    # the reveals merge into one opening. Record, never hide.
                    decisions.append(dict(id=op['id'],other=other['id'],
                        reason='reveals merge inside a shared thin wall',overlap_m2=round(area,4)))
                    continue
                fail('opening_overlap',op['id'],other['id'])
            for support in m['supports']:
                if support['kind']!='column':continue
                if min(op['top_m'],support['top_m'])>max(op['bottom_m'],support['bottom_m']) and cut.intersection(shape(support['geometry'])).area>1e-5:
                    fail('column_invades_opening',op['id'],support['id'])
        # Physical internal partitions do not terminate in window/entrance reveals.
        external_cuts=unary_union([shape(o['cut_geometry']) for o in current if o['surface']])
        partition=clean(partition.difference(external_cuts))
        # Walls and partitions yield to columns and plinths: one material per volume.
        supports=[(shape(s['geometry']),s['bottom_m'],
                   s['top_m']-SLAB if s['kind']=='plinth' else s['top_m'])
                  for s in m['supports'] if s['kind']!='cantilever']
        for kind,band in (('wall',outer),('partition',partition)):
            cuts=[o for o in current if (o['surface'] is not None)==(kind=='wall')]
            heights=sorted({bottom,top,*[v for o in cuts for v in (o['bottom_m'],o['top_m'])]})
            for j,(low,high) in enumerate(zip(heights,heights[1:])):
                mid=(low+high)/2
                active=[shape(o['cut_geometry']) for o in cuts if o['bottom_m']<mid<o['top_m']]
                blocked=active+[geometry for geometry,base,cap in supports if base<mid<cap]
                poly=clean(band.difference(unary_union(blocked)))
                _part(parts,f'floor{floor}/{kind}{j}',kind,'plaster',floor,poly,low,high)
        for op in current:_joinery(op,parts)
        openings.extend(current)
        for row in rows:
            for space in row.get('spaces',[]):
                if space['protection']:
                    _part(parts,space['id']+'/parapet','parapet','plaster',floor,shape(space['protection']),bottom,bottom+space['protection_height_m'])
    # At each datum the union of the ceiling below and floor above is ONE slab.
    # Balconies without ceilings are excluded; courtyards remain true holes.
    for i,z in enumerate(levels):
        upper=[shape(r['geometry']) for r in m['storeys'] if r['floor']==i+1]
        lower=[]
        for r in m['storeys']:
            if r['floor']!=i:continue
            p=shape(r['geometry'])
            for space in r.get('spaces',[]):
                if not space['ceiling_thickness_m']:p=p.difference(shape(space['geometry']))
            lower.append(p)
        slab=clean(unary_union(upper+lower))
        if 0<i<len(levels)-1:
            slab=clean(slab.difference(shape(data['core']['stairs'])).difference(shape(data['core']['shaft'])))
        _part(parts,f'level{i}/slab','slab','concrete',max(1,i),slab,z-SLAB,z)
    for s in m['supports']:
        if s['kind']=='cantilever':continue
        # Slabs occupy the final 18 cm below each floor finish.
        high=s['top_m']-SLAB if s['kind']=='plinth' else s['top_m']
        _part(parts,s['id'],s['kind'],'concrete',1,shape(s['geometry']),s['bottom_m'],high)
    for path in ('roof','site.fence','site.access_route','interior.furniture'):
        pending.append(dict(path=path,reason='later architectural phase'))
    plan=EnvelopePlan('envelope-plan-v1',request,data,openings,parts,decisions,pending,{})
    plan.checks=validate_envelope(plan)
    return plan


def validate_envelope(plan):
    """Audit cuts, solid volumes, lintels and passage widths independently."""
    minimum=float('inf');error=0.
    for op in plan.openings:
        levels=plan.request['context']['levels_m'];ceiling=levels[op['floor']]-SLAB
        minimum=min(minimum,ceiling-op['top_m'])
        cut=shape(op['cut_geometry'])
        for part in plan.parts:
            if part['kind'] not in ('wall','partition','slab','column','plinth'):continue
            dz=min(part['top_m'],op['top_m'])-max(part['bottom_m'],op['bottom_m'])
            if dz>1e-7:error+=shape(part['geometry']).intersection(cut).area*dz
    if error>1e-5:fail('solid_blocks_opening','envelope',f'{error:.6f} m3 in apertures')
    if minimum<LINTEL-1e-6:fail('lintel_insufficient','envelope','insufficient lintel depth')
    return dict(aperture_intrusion_m3=error,minimum_lintel_m=None if not plan.openings else minimum,
                openings=len(plan.openings),explicit_windows=sum(o['kind']=='window' and o['source']=='explicit' for o in plan.openings),
                completed_windows=sum(o['kind']=='window' and o['source']=='completion' for o in plan.openings),
                floor_relative_elevations=True,engineering_verified=False)


def plan_envelope(request, *, interiors=False):
    """Exterior-only by default; full room/BSP layout is explicitly opt-in.

    Historical phase-4/5 evaluations can still request ``interiors=True``.
    The exterior route reserves only a stair footprint and facade openings.
    """
    if interiors:
        return build_envelope(plan_interiors(request))
    from planning.exterior_envelope import plan_exterior_envelope
    return plan_exterior_envelope(request)
