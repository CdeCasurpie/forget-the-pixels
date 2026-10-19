"""Parametric fence assemblies: shared style across infill and access leaves."""
import math
import numpy as np
from shapely.geometry import Polygon
from domain.fence_catalog import FENCE_STYLES, validate_fence_style

STYLES = FENCE_STYLES


def build_fence(mb, a, t, n, length, boundary):
    validate_fence_style(boundary.kind)
    h = boundary.height
    high = boundary.height_mode == 'high'
    style = boundary.kind
    wall = boundary.wall_material
    metal = 'wood' if style == 'madera' else 'metal'
    openness = boundary.openness
    form = getattr(boundary, 'form', 'auto')
    a, t, n = map(np.asarray, (a, t, n))

    def point(u, z, d=-.08):
        return (* (a+t*u+n*d), z)

    def rod(u, z, v, w, r=.016, mat=metal, name='fence_bar'):
        mb.beam(point(u,z), point(v,w), r, material=mat, semantic=name)

    def box(u,v,z,w,depth=.12,mat=wall,name='fence_panel'):
        c=getattr(boundary,'plinth',None)
        if c is not None and c.enabled and mat==wall and z<c.height_m and name in ('boundary_base','boundary_post','fence_wall'):
            mid=min(w,c.height_m)
            mb.box(a,t,n,u,v,z,mid,-depth,0,c.material,name)
            if w>mid:mb.box(a,t,n,u,v,mid,w,-depth,0,mat,name)
            return
        mb.box(a,t,n,u,v,z,w,-depth,0,mat,name,chamfer=min(.014,depth/6,(v-u)/6,(w-z)/6))

    def curve(points, name='fence_scroll'):
        for (u,z),(v,w) in zip(points,points[1:]):
            rod(u,z,v,w,.012,name=name)

    def spear(u, top):
        # Actual tapered silhouette, rather than a square cap.
        shape=Polygon([(u-.035,top-.14),(u-.055,top-.08),(u,top),
                       (u+.055,top-.08),(u+.035,top-.14)])
        mb.panel(a,t,n,[shape],-.10,-.06,lambda *args: metal,'fence_spear')

    def infill(lo,hi,bottom,top,leaf=False):
        if hi-lo < .12:return
        if form == 'solid' and not leaf:
            box(lo,hi,bottom,top,.16,wall,'fence_wall')
            return
        if style == 'clasico':
            box(lo,hi,bottom,top,.10,metal if leaf else wall,
                'gate_panel' if leaf else 'fence_wall')
            if leaf:
                # Raised framing around individually recessed panels.
                for x in (lo+.035,hi-.07):box(x,x+.035,bottom+.03,top-.03,.14,metal,'gate_stile')
                for z in (bottom+.04,(bottom+top)/2,top-.08):box(lo+.035,hi-.035,z,z+.035,.14,metal,'gate_rail')
            return
        if style in ('moderno','madera'):
            if style == 'moderno':
                count=max(2,math.ceil((top-bottom)/.16))
                pitch=(top-bottom)/count
                for i in range(count):box(lo,hi,bottom+i*pitch,bottom+(i+1-openness)*pitch,.075,metal,'fence_louver')
            else:
                count=max(2,math.ceil((hi-lo)/.16)); pitch=(hi-lo)/count
                for i in range(count):
                    x=lo+i*pitch+pitch*openness/2
                    width=pitch*(1-openness)
                    shape=Polygon([(x,bottom),(x+width,bottom),(x+width,top-.06),
                                   (x+width/2,top),(x,top-.06)])
                    mb.panel(a,t,n,[shape],-.12,-.065,lambda *args:'wood','fence_picket')
                for z in (bottom+.12,top-.18):rod(lo,z,hi,z,.03,name='wood_rail')
                if leaf:rod(lo,bottom+.12,hi,top-.18,.027,name='gate_brace')
            return
        tip=.16 if high else .02
        count=max(2,math.ceil((hi-lo)/.16)); pitch=(hi-lo)/count
        for i in range(count):
            x=lo+(i+.5)*pitch
            rod(x,bottom,x,top-tip,.014)
            if high:spear(x,top)
        for z in (bottom+.06,top-tip-.04):rod(lo,z,hi,z,.021,name='fence_rail')
        count=max(1,int((hi-lo)/.30)); pitch=(hi-lo)/count
        for i in range(count):
            x=lo+(i+.5)*pitch
            if style=='republicano':
                radius=min(.10,pitch*.38,(top-bottom)*.18)
                curve([(x+radius*math.cos(q),top-tip-.16+radius*math.sin(q))
                       for q in np.linspace(0,2*math.pi,21)],'fence_ring')
            else:
                # Mirrored spiral scrolls, repeated without stretching their wire.
                for sign in (-1,1):
                    curve([(x+sign*(.025+.065*q/(2*math.pi))*math.cos(q),
                            (bottom+top)/2+.19*math.sin(q)) for q in np.linspace(0,2*math.pi,25)])

    gates=[]
    for u,w,mode,kind in ((boundary.gate_u,boundary.gate_width,boundary.gate_mode,'pedestrian'),
                          (boundary.garage_u,boundary.garage_width,boundary.garage_mode,'garage')):
        if u is not None:gates.append((u,u+w,mode,kind))
    if form == 'partial':
        # A partial fence leaves one supported span open, like an open gate.
        gates.append((length*.38,length*.62,'open','pedestrian'))
    cuts=sorted({0.,length,*[x for g in gates for x in g[:2]]})
    posts={0.,length,*[x for g in gates for x in g[:2]]}
    for lo,hi in zip(cuts,cuts[1:]):
        access=next((g for g in gates if g[0]<=lo and hi<=g[1]),None)
        if access:
            if access[2]=='open':continue
            leaves=2 if access[3]=='garage' else 1
            for i in range(leaves):
                left=lo+(hi-lo)*i/leaves+.045; right=lo+(hi-lo)*(i+1)/leaves-.045
                infill(left+.04,right-.04,.09,h-.08,True)
                for x in (left,right):rod(x,.05,x,h-.08,.025,name='gate_frame')
                for z in (.06,h-.10):rod(left,z,right,z,.025,name='gate_frame')
                rod(right-.09,h*.48,right-.09,h*.48+.12,.02,name='gate_handle')
                for z in (h*.23,h*.76):rod(left,z,left,z+.07,.035,name='gate_hinge')
        else:
            count=max(1,math.ceil((hi-lo)/2.4))
            for i in range(count):
                left=lo+(hi-lo)*i/count; right=lo+(hi-lo)*(i+1)/count
                posts.update((left,right))
                if form == 'solid':
                    box(left,right,0,h,.16,wall,'fence_wall')
                    continue
                base=getattr(boundary,'base_height_m',None)
                if base is None:base=.40 if high else .24
                if form == 'open':base=min(base,.18)
                elif form == 'base_and_rail':base=max(base,.75)
                if style!='madera':box(left,right,0,base,.20,wall,'boundary_base')
                infill(left+.08,right-.08,base if style!='madera' else .06,h-.04)
                if style=='moderno':
                    # Recessed courses and a projecting cap on the masonry base.
                    if getattr(boundary,'plinth',None) is None:box(left+.02,right-.02,base-.07,base-.025,.24,wall,'modern_reveal')
                    if boundary.planters and right-left>.8:
                        xy=lambda u,d: a+t*u+n*d
                        footprint=Polygon([xy(u,d) for u,d in
                            ((left+.16,-.55),(right-.16,-.55),(right-.16,-.20),(left+.16,-.20))])
                        if mb.can_attach(footprint):
                            inner=footprint.buffer(-.045,join_style=2)
                            mb.solid(footprint.difference(inner),0,.36,wall,'planter_wall')
                            mb.solid(inner,.04,.29,'soil','planter_soil')
                            for j,u in enumerate(np.linspace(left+.35,right-.35,max(1,int((right-left)/.5)))):
                                center=xy(u,-.375)
                                mb.foliage((*center,.46),(.18,.14,.22),np.random.default_rng(j),semantic='planter_shrub')
    for x in sorted(posts):
        half=.07 if style=='madera' else .10
        lo,hi=max(0,x-half),min(length,x+half)
        box(lo,hi,0,h,.20,'wood' if style=='madera' else wall,'boundary_post')
        box(max(0,lo-.025),min(length,hi+.025),h-.06,h+.025,.24,
            'wood' if style=='madera' else wall,'post_cap')
