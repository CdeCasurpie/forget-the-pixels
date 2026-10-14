"""Closed profiled mouldings in a facade's (u,z) plane, including curved paths."""
import numpy as np
from shapely.geometry import Polygon
from modeling.trim_sweep import stations
from modeling.mesh_builder import triangulate_rings, _oriented


def sweep_mesh(a,t,n,path,section):
    a,t,n=map(np.asarray,(a,t,n))
    ss,closed=stations(path)
    section,triangles=triangulate_rings(section)
    triangles=_oriented(triangles,section,ccw=True)
    if len(section)<3:raise ValueError('Empty elevation sweep section')
    low,high=section[:,1].min(),section[:,1].max()
    inner=[p+m*low for p,m in ss];outer=[p+m*high for p,m in ss]
    if not closed and not Polygon(inner+outer[::-1]).is_valid:
        raise ValueError('Crown moulding offset self-intersects; reduce width')
    vertices=[]
    for p,m in ss:
        for depth,inset in section:
            uv=p+m*inset
            vertices.append((* (a+t*uv[0]+n*depth),uv[1]))
    count=len(section);faces=[]
    for k in range(len(ss)-1):
        for j in range(count):
            q=(j+1)%count;l=k*count;r=(k+1)*count
            faces.extend(((l+j,r+j,r+q),(l+j,r+q,l+q)))
    if not closed:
        for i,j,k in triangles:
            faces.extend(((i,j,k),((len(ss)-1)*count+k,(len(ss)-1)*count+j,(len(ss)-1)*count+i)))
    vertices=np.asarray(vertices);faces=np.asarray(faces,int)
    # Facade handedness differs from plan sweeps; orient the complete shell.
    v0,v1,v2=vertices[faces[:,0]],vertices[faces[:,1]],vertices[faces[:,2]]
    if np.einsum('ij,ij->i',v0,np.cross(v1,v2)).sum()<0:faces=faces[:,::-1]
    return vertices,faces


def emit_elevation_sweep(mb,a,t,n,path,section,material,semantic):
    vertices,faces=sweep_mesh(a,t,n,path,section)
    mb.member_mesh(vertices,faces,material,semantic)
