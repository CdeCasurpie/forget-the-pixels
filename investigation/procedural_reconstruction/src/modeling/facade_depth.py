"""Materialize displaced facade planes and closed perimeter returns.

Visibility stays in the original chart: no reflow and no replacement mass.
The existing facade materializer moves all openings and relief with the wall.
"""
import numpy as np
from shapely.geometry import box
from shapely.ops import unary_union
from modeling.mesh_builder import polygons


class DepthEnvelopeBuilder:
    def __init__(self,builder):self._builder=builder

    def __getattr__(self,name):return getattr(self._builder,name)

    def panel(self,*args,**kwargs):
        if kwargs.get('clip')=='parcel':kwargs['clip']='envelope'
        return self._builder.panel(*args,**kwargs)


def emit_returns(builder,wall):
    """Thin closed return shells only on the exposed patch perimeter.

    A union removes seams created by horizontal visibility decomposition.
    Return thickness is 20 mm in chart coordinates, independent of depth.
    """
    f=wall.facade
    mask=unary_union([box(*d) for d in wall.visible_domains])
    rim=mask.difference(mask.buffer(-.02,join_style=2))
    a=np.asarray(f.vertex_a)
    t=(np.asarray(f.vertex_b)-a)/f.width_m
    depth=wall.plane_offset_m
    builder.panel(a,t,np.asarray(f.normal_xy),polygons(rim),min(0.,depth),max(0.,depth),
                  lambda *args:f.wall_material,'facade_depth_return',clip='envelope',
                  assembly_id=f.edge_id,component_id=f.edge_id+'/depth_returns')


def section_geometry(section,start,end,low,high,depth):
    """Closed boxes in (u,z,normal depth); the middle remains empty."""
    s=section
    parts=[(start,end,low,low+s.slab_m,depth,0.,'portico_floor'),
           (start,end,high-s.slab_m,high,depth,0.,'portico_soffit')]
    for axis in s.column_axes_u:
        u=start+(end-start)*axis
        h=s.column_width_m/2
        parts.append((u-h,u+h,low+s.slab_m,high-s.slab_m,
                      -s.column_width_m,0.,'portico_column'))
    return parts


def emit_section(builder,wall,zone):
    f=wall.facade
    a=np.asarray(f.vertex_a);t=(np.asarray(f.vertex_b)-a)/f.width_m
    lo,hi=zone.z_m if zone.z_m is not None else (0.,wall.height_m)
    start,end=(u*f.width_m for u in zone.u)
    mask=unary_union([box(*d) for d in wall.visible_domains])
    for i,(u0,u1,z0,z1,w0,w1,semantic) in enumerate(section_geometry(
            wall.section,start,end,lo,hi,wall.plane_offset_m)):
        shape=box(u0,z0,u1,z1).intersection(mask)
        builder.panel(a,t,np.asarray(f.normal_xy),polygons(shape),w0,w1,
                      lambda *args:'concrete',semantic,clip='envelope',
                      assembly_id=f.edge_id,component_id=f.edge_id+'/'+semantic+str(i))
