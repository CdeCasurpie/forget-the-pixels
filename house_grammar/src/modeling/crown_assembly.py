"""Thick bodies, recessed fields, continuous mouldings and optional ornaments."""
from dataclasses import replace
import math
import numpy as np
from shapely.geometry import Polygon, Point, box, LineString
from shapely.affinity import translate, scale
from domain.crowns import CrownDesign
from domain.theta import CorniceControls
from modeling.trim_profiles import cornice_section
from modeling.crown_paths import paths, body_shapes
from modeling.elevation_sweep import emit_elevation_sweep
from modeling.mesh_builder import polygons


def moulding_section(d,back=0.,factor=1.):
    c=CorniceControls(profile=d.style,height_m=d.moulding_width_m*factor,projection_m=d.projection_m*factor)
    return tuple((back+x,z) for x,z in cornice_section(c,d.style))


def aperture_shape(kind,width,height,sill,center):
    if kind=='none':return Polygon()
    if kind=='oculus':return translate(scale(Point(0,0).buffer(1,quad_segs=24),width/2,height/2),center,sill+height/2)
    if kind=='roundhead':
        rise=min(width/2,height*.45)
        arc=[(center+width/2*math.cos(q),sill+height-rise+rise*math.sin(q)) for q in np.linspace(0,math.pi,49)]
        return Polygon([(center-width/2,sill),(center+width/2,sill),*arc])
    if kind=='pointed':
        left=[(center-width/2+width/2*f,sill+height*.6+height*.4*(1-(1-f)**1.7)) for f in np.linspace(0,1,25)]
        return Polygon([(center-width/2,sill),(center+width/2,sill),*[(2*center-x,z) for x,z in left],*left[-2::-1]])
    raise ValueError('Unknown crown aperture')


def build_crown(mb,a,t,n,u,z,width,height,d,aperture=None,custom_routes=None):
    routes=paths(d,width,height) if custom_routes is None else custom_routes
    shapes=body_shapes(routes)
    hole=Polygon() if aperture is None else aperture
    def panel(shape,back,front,mat,semantic):
        mb.panel(a,t,n,list(polygons(translate(shape,xoff=u,yoff=z))),back,front,
                 lambda *args:mat,semantic,clip='envelope')
    for shape in shapes:
        if not hole.is_empty and not shape.buffer(-d.moulding_width_m*1.3).covers(hole):
            raise ValueError('Crown aperture does not fit inside recessed field')
        # Full-thickness body except at the real aperture. Rim and field have
        # different front depths, not a painted rectangle over a solid opening.
        core=shape.difference(hole)
        panel(core,-d.thickness_m, -d.recess_m,d.field_material or d.material,'crown_body')
        rim=shape.difference(shape.buffer(-d.moulding_width_m*.9,join_style=2)).difference(hole)
        panel(rim,-d.recess_m,0.,d.material,'crown_rim')
    for route in routes:
        world=[(u+x,z+y) for x,y in route]
        emit_elevation_sweep(mb,a,t,n,world,moulding_section(d),d.moulding_material,'crown_moulding')
        # A separate inner bead defines the recessed field and reads in relief.
        if d.style!='moderno':
            from modeling.trim_sweep import stations
            ss,_=stations(route)
            inner=[(u+p[0]+m[0]*d.moulding_width_m*1.08,z+p[1]+m[1]*d.moulding_width_m*1.08) for p,m in ss]
            emit_elevation_sweep(mb,a,t,n,inner,moulding_section(d,-d.recess_m,.23),d.moulding_material,'crown_inner_bead')
    if d.base:
        for route in routes:
            # Direction reversed: the section rises into the crown from its base.
            base=[(u+route[-1][0],z),(u+route[0][0],z)]
            emit_elevation_sweep(mb,a,t,n,base,moulding_section(d),d.moulding_material,'crown_base_cornice')
    if not hole.is_empty:
        reveal=hole.buffer(.055).difference(hole)
        panel(reveal,-d.thickness_m-.002,.035,d.moulding_material,'crown_aperture_reveal')
        panel(hole,-d.thickness_m*.65,-d.thickness_m*.65+.012,'glass','crown_glass')
        x0,y0,x1,y1=hole.bounds
        for x in np.linspace(x0,x1,max(2,math.ceil((x1-x0)/.3))+1)[1:-1]:
            panel(box(x-.015,y0,x+.015,y1).intersection(hole),-.05,0.,d.moulding_material,'crown_mullion')
        for y in np.linspace(y0,y1,max(2,math.ceil((y1-y0)/.4))+1)[1:-1]:
            panel(box(x0,y-.015,x1,y+.015).intersection(hole),-.05,0.,d.moulding_material,'crown_mullion')
    if d.ornament=='keystone':
        w=min(.22,width*.07);h=min(.35,height*.3)
        panel(Polygon([(width/2-w*.65,height-h),(width/2+w*.65,height-h),
                       (width/2+w,height),(width/2-w,height)]),.01,d.projection_m+.05,d.moulding_material,'crown_keystone')
    elif d.ornament=='cartouche':
        outer=translate(scale(Point(0,0).buffer(1,quad_segs=24),width*.09,height*.20),width/2,height*.43)
        if outer.intersects(hole):raise ValueError('Cartouche conflicts with crown aperture')
        panel(outer,-d.recess_m,.025,d.material,'crown_cartouche_field')
        panel(outer.difference(outer.buffer(-min(.04,width*.015))),.025,.09,d.moulding_material,'crown_cartouche_frame')
    elif d.ornament=='volutes':
        for sign in (-1,1):
            center=width*(.22 if sign<0 else .78)
            radius=min(width*.12,height*.25)
            curve=[(center+sign*radius*(1-q/(3.2*math.pi))*math.cos(q),height*.25+radius*(1-q/(3.2*math.pi))*math.sin(q)) for q in np.linspace(0,2.7*math.pi,48*d.detail)]
            panel(LineString(curve).buffer(.018),0,.065,d.moulding_material,'crown_volute')
    elif d.ornament=='dentils':
        pitch=.22;count=max(1,int(width/pitch))
        for i in range(count):
            x=width*(i+.5)/count
            panel(box(x-.04,.025,x+.04,min(.13,height*.25)),.01,d.projection_m*.7,d.moulding_material,'crown_dentil')


def legacy_crown(mb,a,t,n,feature,family):
    d=getattr(feature,'crown',None) or CrownDesign(family=family,style='republicano',
        thickness_m=max(.12,feature.depth_m),material=feature.material_slot,
        moulding_material=feature.material_slot,moulding_width_m=min(.12,feature.height_m*.25,feature.width_m*.07),
        projection_m=min(.16,max(.04,feature.depth_m*.5)))
    if d.style=='auto':d=replace(d,style='republicano')
    if feature.kind.startswith('crown_'):
        mb=CrownBuilder(mb,feature.v_m,feature.v_m+feature.height_m)
    build_crown(mb,a,t,n,feature.u_m,feature.v_m,feature.width_m,feature.height_m,d)


class CrownBuilder:
    """Extend only crown-visible intervals, preserving band-local Z lifting."""
    def __init__(self,builder,base,top):self.builder,self.base,self.top=builder,base,top
    def __getattr__(self,name):return getattr(self.builder,name)
    def panel(self,*args,**kwargs):
        target=getattr(self.builder,'crown_body_panel',None)
        if target:return target(*args,base=self.base,top=self.top,**kwargs)
        return getattr(self.builder,'crown_panel',self.builder.panel)(*args,**kwargs)
    def member_mesh(self,vertices,faces,material,semantic):
        target=getattr(self.builder,'crown_member_mesh',None)
        if target:return target(vertices,faces,material,semantic,self.base,self.top)
        return self.builder.member_mesh(vertices,faces,material,semantic)
