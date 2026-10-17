"""Boundary-only union of piecewise-prismatic solids, without a Boolean backend.

Node XY boundaries into common cells and use common Z levels. Shared triangles
cancel exactly, so slab/wall contacts do not leave duplicate internal surfaces.
"""
from collections import defaultdict

import numpy as np
import trimesh
from shapely import constrained_delaunay_triangles, set_precision
from shapely.geometry.polygon import orient
from shapely.ops import unary_union, polygonize


def layered_mesh(sections):
    sections=[(set_precision(g,1e-8),round(a,8),round(b,8)) for g,a,b in sections if not g.is_empty and b>a]
    heights=sorted({h for _,a,b in sections for h in (a,b)})
    cells=list(polygonize(unary_union([g.boundary for g,_,_ in sections])))
    vertices=[];indices={};faces=defaultdict(list)

    def vertex(xy,z):
        key=(round(xy[0],8),round(xy[1],8),z)
        if key not in indices:
            indices[key]=len(vertices);vertices.append(key)
        return indices[key]

    def face(points):
        faces[tuple(sorted(points))].append(points)

    for cell in cells:
        cell=orient(cell);point=cell.representative_point()
        intervals=[(a,b) for g,a,b in sections if g.covers(point)]
        if not intervals:continue
        triangles=[list(orient(t).exterior.coords)[:3] for t in constrained_delaunay_triangles(cell).geoms]
        for low,high in zip(heights,heights[1:]):
            if not any(a<=(low+high)/2<=b for a,b in intervals):continue
            for tri in triangles:
                face([vertex(p,low) for p in reversed(tri)])
                face([vertex(p,high) for p in tri])
            for ring in [cell.exterior,*cell.interiors]:
                for a,b in zip(ring.coords,list(ring.coords)[1:]):
                    # Same diagonal on both sides of an internal cell edge.
                    forward=tuple(a)<tuple(b)
                    u,v=(a,b) if forward else (b,a)
                    quad=[vertex(u,low),vertex(v,low),vertex(v,high),vertex(u,high)]
                    for tri in ([quad[0],quad[1],quad[2]],[quad[0],quad[2],quad[3]]):
                        face(tri if forward else tri[::-1])
    boundary=[]
    for instances in faces.values():
        if len(instances)==1:boundary.append(instances[0])
        elif len(instances)!=2:raise ValueError('nonmanifold layered interface')
    mesh=trimesh.Trimesh(vertices=np.asarray(vertices),faces=np.asarray(boundary),process=False)
    mesh.remove_unreferenced_vertices()
    return mesh
