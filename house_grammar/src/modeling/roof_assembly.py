"""Detailed covers, measured timber eaves and shared-edge roof finishes."""
import math
import numpy as np
from shapely.geometry import Polygon, LineString, box
from shapely.ops import unary_union
from modeling.mesh_builder import polygons
from modeling.roof_planes import geometry,height


def roof_edges(faces):
    """Split boundaries into shared and exposed segments, including T junctions."""
    result=[]
    for i,f in enumerate(faces):
        poly=geometry(f);remaining=poly.boundary
        for j,g in enumerate(faces):
            if j==i:continue
            shared=poly.boundary.intersection(geometry(g).boundary)
            if shared.is_empty:continue
            remaining=remaining.difference(shared)
            if j<i:continue
            for line in lines(shared):
                mid=line.interpolate(.5,normalized=True);x,y=mid.coords[0]
                if abs(height(f.plane,x,y)-height(g.plane,x,y))>1e-5:kind='abutment'
                elif np.linalg.norm(np.asarray(f.plane)-g.plane)<1e-6:continue
                else:
                    v=np.asarray(geometry(g).representative_point().coords[0])-[x,y]
                    kind='ridge' if np.dot(np.asarray(f.plane[:2])-g.plane[:2],v)>0 else 'valley'
                result.append((line,kind,f.plane,g.plane))
        for line in lines(remaining):result.append((line,'edge',f.plane,None))
    return result


def lines(shape):
    if shape is None or shape.is_empty:return
    if shape.geom_type in ('LineString','LinearRing'):
        if shape.length>1e-7:yield shape
    elif hasattr(shape,'geoms'):
        for s in shape.geoms:yield from lines(s)


def timber(mb,a,b,width,depth,material,semantic):
    """Rectangular beam in a stable vertical frame, not a round railing tube."""
    a=np.asarray(a,float);b=np.asarray(b,float);axis=b-a
    axis/=np.linalg.norm(axis)
    side=np.cross(axis,[0,0,1.])
    if np.linalg.norm(side)<1e-7:side=np.array([1.,0,0])
    side/=np.linalg.norm(side);up=np.cross(side,axis)
    vertices=np.array([p+side*x*width/2+up*y*depth/2 for p in (a,b) for x,y in ((-1,-1),(1,-1),(1,1),(-1,1))])
    ff=np.array([(0,2,1),(0,3,2),(4,5,6),(4,6,7),(0,1,5),(0,5,4),(1,2,6),(1,6,5),(2,3,7),(2,7,6),(3,0,4),(3,4,7)])
    v=vertices[ff]
    if np.einsum('ij,ij->i',v[:,0],np.cross(v[:,1],v[:,2])).sum()<0:ff=ff[:,::-1]
    mb.member_mesh(vertices,ff,material,semantic)


def tile_mesh(mb,points,plane,material,semantic,clip_shape=None):
    """Small closed profiled tile; station rows preserve curved cross section."""
    verts=np.asarray(points,float);count=len(verts)//2;faces=[]
    # Profile ring is supplied in a vertical plane; triangulate in its own chart.
    from modeling.mesh_builder import triangulate_rings
    axis=verts[1,:2]-verts[0,:2]
    # Use the longest plan direction of the ring (first edge can be tiny).
    axis=verts[np.argmax(np.linalg.norm(verts[:count,:2]-verts[0,:2],axis=1)),:2]-verts[0,:2]
    axis/=np.linalg.norm(axis)
    chart=np.column_stack(((verts[:count,:2]-verts[0,:2])@axis,
                           verts[:count,2]-np.array([height(plane,*p[:2]) for p in verts[:count]])))
    clean,tris=triangulate_rings(chart)
    lookup={tuple(np.round(v,9)):i for i,v in enumerate(chart)}
    for tri in tris:
        ids=[lookup[tuple(np.round(clean[k],9))] for k in tri]
        faces.extend((tuple(ids),tuple(count+k for k in ids[::-1])))
    for i in range(count):
        j=(i+1)%count;faces.extend(((i,j,count+j),(i,count+j,count+i)))
    faces=np.asarray(faces)
    # Repair global orientation only; ring/cap directions are made consistent below.
    import trimesh
    mesh=trimesh.Trimesh(verts,faces,process=False);mesh.fix_normals()
    if clip_shape is None:
        mb.member_mesh(mesh.vertices,mesh.faces,material,semantic)
    else:
        from shapely.geometry.polygon import orient
        from shapely import constrained_delaunay_triangles
        from modeling.vertical_member_sweep import clip_member_mesh
        for piece in polygons(clip_shape):
            parts=[piece] if piece.symmetric_difference(piece.convex_hull).area<1e-8 else list(constrained_delaunay_triangles(piece).geoms)
            for part in parts:
                ring=list(orient(part,1).exterior.coords);planes=[]
                for a,b in zip(ring,ring[1:]):
                    edge=np.asarray(b)-a;normal=np.array([-edge[1],edge[0],0.]);normal/=np.linalg.norm(normal)
                    planes.append(((*a,0.),normal))
                vv,ff=clip_member_mesh(mesh.vertices,mesh.faces,planes)
                if len(ff):mb.member_mesh(vv,ff,material,semantic)


def covering(mb,face,d):
    if d.covering=='none':return
    if d.form=='band' and np.linalg.norm(face.plane[:2])<1e-8:return
    poly=geometry(face);plane=face.plane
    slope=np.asarray(plane[:2]);norm=np.linalg.norm(slope)
    v=slope/norm if norm>1e-8 else np.array([0.,1.]);u=np.array([v[1],-v[0]])
    coords=np.asarray(poly.exterior.coords);xs=coords@u;ys=coords@v
    if d.covering=='panel' or d.detail=='light':
        mb.solid(poly,lambda x,y:height(plane,x,y)+.006,lambda x,y:height(plane,x,y)+.025,d.material,'roof_cover')
        if d.detail=='light':return
    pitch=d.tile_width_m
    length=d.tile_length_m;step=length-d.overlap_m
    if d.covering in ('corrugated','slats'):length=ys.max()-ys.min()+.01;step=length
    if d.covering=='panel':pitch=.65;length=step=ys.max()-ys.min()+.01
    budget=math.ceil((xs.max()-xs.min())/pitch)*math.ceil((ys.max()-ys.min())/step)
    if budget>18000:raise ValueError('Roof covering exceeds 18000-piece budget; increase module size')
    for row,y in enumerate(np.arange(ys.min(),ys.max()-1e-7,step)):
        offset=pitch*.5*(row%2) if d.covering=='flat_tile' else 0.
        for x in np.arange(xs.min()-offset,xs.max()-1e-7,pitch):
            w=pitch*.55 if d.covering=='slats' else pitch
            end=min(y+length,ys.max())
            tile=Polygon([u*a+v*b for a,b in ((x,y),(x+w,y),(x+w,end),(x,end))])
            cut=tile.intersection(poly)
            if cut.area<1e-7:continue
            curved=d.covering in ('curved_tile','corrugated')
            if curved:
                samples=5 if d.detail=='medium' else 9
                # Alternate concave channels and convex covers across the pitch.
                sign=1 if int(round((x-xs.min())/pitch))%2 else -1
                arch=[(a,.015+(w*.24)*(1+sign*math.sin(math.pi*a/w))) for a in np.linspace(0,w,samples)]
                section=arch+[(a,z-.012) for a,z in reversed(arch)]
                points=[(*(u*(x+a)+v*b),height(plane,*(u*(x+a)+v*b))+z) for b in (y,end) for a,z in section]
                tile_mesh(mb,points,plane,d.material,'roof_tile_piece' if d.covering=='curved_tile' else 'roof_corrugation',
                          None if poly.buffer(1e-7).covers(tile) else cut)
            else:
                for p in polygons(cut):
                    mb.solid(p,lambda a,b:height(plane,a,b)+.008,lambda a,b:height(plane,a,b)+(.035 if curved else .022),d.material,'roof_cut_tile' if curved else 'roof_'+d.covering)


def build_roof_assembly(mb,r,envelope):
    d=r.design;e=d.eave
    footprint=unary_union([geometry(f) for f in r.faces])
    with mb.assembly('roof_assembly/'+r.id):
        for f in r.faces:
            poly=geometry(f);p=f.plane
            if d.covering!='slats' and d.construction=='solid':
                mb.solid(poly,lambda x,y,p=p:height(p,x,y)-d.thickness_m,
                         lambda x,y,p=p:height(p,x,y),d.substrate_material,'roof_substrate')
            covering(mb,f,d)
            if r.canopy and d.covering!='slats' and d.substrate_material=='wood' and d.construction=='solid':
                # Visible soffit boards with metric pitch and a narrow real joint.
                normal=np.asarray(r.outward);tangent=np.array([normal[1],-normal[0]])
                xy=np.asarray(poly.exterior.coords);us=xy@tangent;vs=xy@normal
                for v in np.arange(vs.min(),vs.max(),.14):
                    board=Polygon([tangent*u+normal*w for u,w in ((us.min(),v),(us.max(),v),(us.max(),min(v+.136,vs.max())),(us.min(),min(v+.136,vs.max())))])
                    for part in polygons(board.intersection(poly)):
                        mb.solid(part,lambda x,y,p=p:height(p,x,y)-d.thickness_m-.012,
                                 lambda x,y,p=p:height(p,x,y)-d.thickness_m,'wood','roof_board')
            if not r.canopy:
                support=Polygon(r.support, r.support_holes)
                # Gable closure only laps the wall head: full-height duplication
                # flickers against the wall face. The 10 mm proud lip keeps one
                # visible plane; neighbors never receive another mass's closure.
                strip=support.buffer(.01).difference(support.buffer(-.13)).intersection(poly)
                for hole in r.neighbor_polygons:
                    # 5 mm weathering gap: no ragged cut face ends coplanar
                    # with the neighbor wall, and masses never touch directly.
                    strip=strip.difference(Polygon(hole).buffer(.005))
                finishes=[]
                for finish in r.wall_finishes:
                    region=strip.intersection(Polygon(finish.polygon))
                    finishes.extend((part,finish.material) for part in polygons(region))
                    strip=strip.difference(region)
                finishes.extend((part,'plaster') for part in polygons(strip))
                bite=.005 if d.construction=='solid' and d.covering!='slats' else .01
                bottom=r.base_z-.02
                for part,material in finishes:
                    if max(height(p,*xy) for xy in part.exterior.coords)>r.base_z+.02:
                        mb.solid(part,bottom,lambda x,y,p=p,b=bottom:max(b+.01,height(p,x,y)-d.thickness_m+bite),material,'roof_gable_closure')
        if r.canopy and r.posts:
            from domain.vertical_members import MemberDesign
            from modeling.vertical_member_assembly import build_member
            vertices=np.asarray(r.support);out=np.asarray(r.outward)
            front=vertices@out;max_d=front.max()
            for xy in vertices[np.abs(front-max_d)<1e-6]:
                xy=xy-out*.08
                tangent=np.array([-out[1],out[0]])
                centre=vertices.mean(axis=0)
                xy+=tangent*(.08 if np.dot(xy-centre,tangent)<0 else -.08)
                z=min(height(f.plane,*xy) for f in r.faces)-d.thickness_m
                build_member(mb,xy,tangent,out,r.post_base_z,.14,.14,z-r.post_base_z,MemberDesign(style='madera',variant='saddle_post',material=e.material),'freestanding')
        for line,kind,p,q in roof_edges(r.faces):
            coords=list(line.coords)
            for aa,bb in zip(coords,coords[1:]):
                a=np.asarray(aa);b=np.asarray(bb);length=np.linalg.norm(b-a)
                if length<.02:continue
                t=(b-a)/length;n=np.array([t[1],-t[0]])
                if footprint.covers(__import__('shapely').geometry.Point((a+b)/2+n*.001)):n=-n
                z0=height(p,*a);z1=height(p,*b)
                if kind in ('ridge','valley'):
                    average=tuple((np.asarray(p)+q)/2)
                    if kind=='ridge' and d.covering in ('curved_tile','flat_tile'):
                        count=max(1,math.ceil(length/.32))
                        section=[(x,.035+.09*math.sqrt(max(0,1-(x/.12)**2))) for x in np.linspace(-.12,.12,13)]
                        section+= [(x,z-.015) for x,z in reversed(section)]
                        for i in range(count):
                            start=length*i/count;end=min(length,length*(i+1)/count+.025)
                            points=[(*(a+t*s+n*x),height(average,*(a+t*s+n*x))+h) for s in (start,end) for x,h in section]
                            tile_mesh(mb,points,average,d.material,'roof_ridge_tile')
                    else:
                        section=[(-.13,.03),(0,-.025),(.13,.03),(.13,.02),(0,-.035),(-.13,.02)]
                        points=[(*(pt+n*x),height(average,*(pt+n*x))+h) for pt in (a,b) for x,h in section]
                        tile_mesh(mb,points,average,'metal','roof_'+kind)
                    continue
                if any(LineString([a,b]).difference(LineString(j).buffer(1e-5)).length<1e-5 for j in r.wall_joints):
                    timber(mb,(*a,z0+.025),(*b,z1+.025),.045,.06,'metal','roof_crown_flashing')
                    continue
                if kind=='abutment':
                    strip=line.buffer(.055,cap_style=2).intersection(footprint)
                    for part in polygons(strip):
                        mb.solid(part,lambda x,y:min(height(p,x,y),height(q,x,y)),
                            lambda x,y:max(height(p,x,y),height(q,x,y))+.02,'metal','roof_abutment')
                    continue
                if e.fascia:
                    timber(mb,(*a,z0-.07),(*b,z1-.07),.035,.16,e.fascia_material,'roof_fascia')
                if e.gutter and np.dot(np.asarray(p[:2]),n)<-1e-6 and abs(z1-z0)<.02:
                    section=[(.01,-.025),(.035,-.10),(.14,-.10),(.165,-.025),(.155,-.025),(.13,-.09),(.045,-.09),(.02,-.025)]
                    points=[(*(pt+n*x),height(p,*pt)+h) for pt in (a,b) for x,h in section]
                    # Profile elevation is relative to edge, not the extrapolated roof slope.
                    tile_mesh(mb,points,p,'metal','roof_gutter')
                if e.kind=='cornice':
                    from domain.crowns import CrownDesign
                    from modeling.crown_assembly import moulding_section
                    from modeling.elevation_sweep import emit_elevation_sweep
                    section=moulding_section(CrownDesign(style=d.style,moulding_width_m=.15,projection_m=.12))
                    emit_elevation_sweep(mb,a,t,n,[(0,z0),(length,z1)],section,'cornice','roof_edge_cornice')
                if e.soffit or e.kind=='closed':
                    strip=LineString([a,b]).buffer(max(.02,e.overhang_m),cap_style=2).intersection(footprint)
                    for part in polygons(strip):mb.solid(part,lambda x,y:height(p,x,y)-d.thickness_m-.035,lambda x,y:height(p,x,y)-d.thickness_m-.015,e.material,'roof_soffit')
                if e.kind in ('exposed','profiled','braces','curved'):
                    count=max(1,int(length/e.spacing_m))
                    reach=r.depth_m if r.canopy else e.overhang_m+.25
                    # On canopies the framing runs normal to the wall, only from outer edge.
                    if r.canopy and np.dot(n,r.outward)<.99:continue
                    for i in range(count):
                        pt=a+t*(i+.5)*length/count;back=pt-n*reach
                        z=height(p,*pt)-d.thickness_m-e.beam_height_m/2
                        zb=height(p,*back)-d.thickness_m-e.beam_height_m/2
                        timber(mb,(*back,zb),(*pt,z),e.beam_width_m,e.beam_height_m,e.material,'roof_rafter')
                        if e.kind=='profiled':
                            timber(mb,(*(pt-n*.12),z-.07),(*pt,z-.025),e.beam_width_m*.9,.06,e.material,'roof_rafter_tip')
                        if e.kind=='braces':
                            timber(mb,(*back,zb-reach*.55),(*(pt-n*.10),z-.04),e.beam_width_m,e.beam_height_m*.7,e.material,'roof_brace')
                        if e.kind=='curved':
                            curve=[(reach*.85*s,zb+(z-zb)*s-reach*.65*(1-s)**2) for s in np.linspace(0,1,33)]
                            shape=LineString(curve).buffer(e.beam_height_m*.3,cap_style=2)
                            # Ensure the extrusion frame has the same handedness as a facade.
                            normal=np.array([n[1],-n[0]])
                            mb.panel(back,n,normal,[shape],-e.beam_width_m/2,e.beam_width_m/2,lambda *args:e.material,'roof_curved_bracket')
        if d.parapet_m:
            ring=footprint.difference(footprint.buffer(-.14,join_style=2));head=r.base_z+d.parapet_m
            for p in polygons(ring):mb.solid(p,r.base_z,head,'plaster','roof_parapet')
            if d.cap!='none':
                from modeling.trim_sweep import emit_sweep
                # Existing sweep uses a closed plan path with depth/elevation profile.
                cap_section={'flat':((-.14,0),(.02,0),(.02,.05),(-.14,.05)),
                    'bevel':((-.14,0),(.02,0),(.02,.035),(-.01,.065),(-.11,.065),(-.14,.035)),
                    'pitched':((-.14,0),(.02,0),(.02,.04),(-.06,.075),(-.14,.04)),
                    'metal':((-.14,0),(.02,0),(.02,.018),(-.14,.018))}
                if d.cap=='moulded':
                    from domain.theta import CorniceControls
                    from modeling.trim_profiles import cornice_section
                    section=tuple((x-.14,z) for x,z in cornice_section(CorniceControls(height_m=.12,projection_m=.16),d.style))
                else:section=cap_section[d.cap]
                if d.cap_drip:
                    # Downturned front drip edge, independently switchable.
                    section=((-.14,0),(.01,0),(.01,-.02),(.02,-.02),(.02,.018),(-.14,.018))
                from shapely.geometry.polygon import orient
                for poly in polygons(footprint):emit_sweep(mb,list(orient(poly,1).exterior.coords),section,head,d.cap_material,'roof_parapet_cap',envelope)


def legacy_eave(mb,a,t,n,feature):
    from domain.roof_details import RoofDesign,EaveDesign
    from modeling.roof_detail_resolver import ResolvedRoofAssembly
    from modeling.roof_planes import plan_faces
    a,t,n=map(np.asarray,(a,t,n));u=feature.u_m;w=feature.width_m;depth=feature.depth_m
    poly=Polygon([a+t*x+n*y for x,y in ((u,0),(u+w,0),(u+w,depth),(u,depth))])
    if not mb.can_attach(poly):return
    d=RoofDesign(form='flat',covering='none',style='madera',thickness_m=feature.height_m*.45,
        substrate_material=feature.material_slot,eave=EaveDesign(kind='exposed',overhang_m=0,
        beam_height_m=feature.height_m*.55,spacing_m=.52))
    z=feature.v_m+feature.height_m
    roof=ResolvedRoofAssembly('legacy_eave','facade',d,tuple(plan_faces(poly,d,z)),tuple(poly.exterior.coords)[:-1],z,True,depth,tuple(n))
    class Adapter:
        names={'roof_substrate':'eave','roof_rafter':'rafter_tail','roof_fascia':'eave_fascia'}
        def __getattr__(self,name):return getattr(mb,name)
        def solid(self,p,z0,z1,material,semantic,**kwargs):return mb.solid(p,z0,z1,material,self.names.get(semantic,semantic),**kwargs)
        def member_mesh(self,v,f,material,semantic):return mb.member_mesh(v,f,material,self.names.get(semantic,semantic))
    build_roof_assembly(Adapter(),roof,mb.envelope)
