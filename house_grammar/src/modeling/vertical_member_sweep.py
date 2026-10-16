"""Closed ring loft, supporting concave cross sections and cap triangulation."""
import numpy as np
from shapely import constrained_delaunay_triangles
from shapely.geometry import Polygon, MultiPoint


def emit_loft(mb,rings,material,semantic):
    rings=np.asarray(rings,float)
    if rings.ndim!=3 or rings.shape[0]<2 or rings.shape[1]<3 or not np.isfinite(rings).all():
        raise ValueError('Invalid member loft')
    if not Polygon(rings[0,:,:2]).exterior.is_ccw:rings=rings[:,::-1,:]
    count=rings.shape[1]; ids=np.arange(rings.shape[0]*count).reshape(-1,count); faces=[]
    for lower,upper in zip(ids,ids[1:]):
        for i in range(count):
            j=(i+1)%count
            faces.extend(((lower[i],lower[j],upper[j]),(lower[i],upper[j],upper[i])))
    for index,reverse in ((0,True),(-1,False)):
        lookup={tuple(np.round(v[:2],10)):i for i,v in enumerate(rings[index])}
        for tri in constrained_delaunay_triangles(Polygon(rings[index,:,:2])).geoms:
            points=list(tri.exterior.coords)[:3]
            if not tri.exterior.is_ccw:points.reverse()
            a,b,c=(ids[index][lookup[tuple(np.round(v,10))]] for v in points)
            faces.append((a,c,b) if reverse else (a,b,c))
    mb.member_mesh(rings.reshape(-1,3),np.asarray(faces),material,semantic)


def clip_member_mesh(vertices,faces,planes):
    """Closed clipping at visibility/envelope planes; preserves moulding shape."""
    import trimesh
    mesh=trimesh.Trimesh(vertices,faces,process=False)
    for origin,normal in planes:
        if not len(mesh.faces):break
        distances=(mesh.vertices-np.asarray(origin))@np.asarray(normal)
        if distances.min()>=-1e-8:continue
        if distances.max()<=1e-8:return np.empty((0,3)),np.empty((0,3),int)
        mesh=trimesh.intersections.slice_mesh_plane(mesh,normal,origin,cap=False)
        mesh.merge_vertices(digits_vertex=9)
        # GEOS constrained caps retain collinear boundary vertices. Earcut's
        # almost-zero cap triangles are otherwise dropped by MeshBuilder and
        # leave T-junctions at sampled moulding rings.
        edges=mesh.edges_sorted
        unique,counts=np.unique(edges,axis=0,return_counts=True)
        boundary=unique[counts==1]
        unit=np.asarray(normal,float);unit/=np.linalg.norm(unit)
        axis=np.eye(3)[np.argmin(np.abs(unit))]
        tangent=np.cross(unit,axis);tangent/=np.linalg.norm(tangent)
        bitangent=np.cross(unit,tangent)
        xy=np.column_stack((mesh.vertices@tangent,mesh.vertices@bitangent))
        from shapely import build_area
        from shapely.geometry import MultiLineString
        if len(boundary):
            shape=build_area(MultiLineString([xy[e] for e in boundary]))
            lookup={tuple(v):i for i,v in enumerate(xy)}
            caps=[]
            for tri in constrained_delaunay_triangles(shape).geoms:
                points=list(tri.exterior.coords)[:3]
                if tri.exterior.is_ccw:points.reverse()
                caps.append([lookup[tuple(v)] for v in points])
            if caps:mesh.faces=np.vstack((mesh.faces,caps))
    return mesh.vertices,mesh.faces


def emit_member_mesh(mb,vertices,faces,material,semantic):
    footprint=Polygon() if not len(vertices) else MultiPoint(vertices[:,:2]).convex_hull
    if footprint.is_empty:return
    # Match the roof resolver's 0.1 mm numerical tolerance. The envelope has a
    # precision grid: a sub-grid buffer rounds to zero, needlessly slicing
    # already clipped corrugations into almost-zero cap loops at lot edges.
    if not mb.envelope.buffer(1e-4).covers(footprint):
        from shapely.geometry.polygon import orient
        from modeling.mesh_builder import polygons
        intersection=mb.envelope.intersection(footprint)
        for poly in polygons(intersection):
            cells=[poly] if poly.equals(poly.convex_hull) else list(constrained_delaunay_triangles(poly).geoms)
            for cell in cells:
                points=list(orient(cell,sign=1).exterior.coords)
                planes=[((a[0],a[1],0),(a[1]-b[1],b[0]-a[0],0)) for a,b in zip(points,points[1:])]
                vv,ff=clip_member_mesh(vertices,faces,planes)
                _write_mesh(mb,vv,ff,material,semantic)
        return
    _write_mesh(mb,vertices,faces,material,semantic)


def _write_mesh(mb,vertices,faces,material,semantic):
    if not len(faces):return
    center=(vertices[:,:2].min(axis=0)+vertices[:,:2].max(axis=0))/2
    angle=np.arctan2(vertices[:,1]-center[1],vertices[:,0]-center[0])/(2*np.pi)+.5
    circumference=max(np.ptp(vertices[:,0]),np.ptp(vertices[:,1]))*np.pi
    with mb.component(semantic):
        ids=[mb.vert(v) for v in vertices]; mat=mb.mat_index(material)
        for a,b,c in faces:
            indices=np.array((a,b,c));points=vertices[indices]
            if np.ptp(points[:,2])<1e-9:uv=points[:,:2]
            else:
                u=angle[indices].copy()
                if np.ptp(u)>.5:u[u<.5]+=1.
                uv=np.column_stack((u*circumference,points[:,2]))
            mb.tri(ids[a],ids[b],ids[c],uv,mat)
