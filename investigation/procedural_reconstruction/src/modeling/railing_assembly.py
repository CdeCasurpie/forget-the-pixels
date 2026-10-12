"""Metric, modular railings along 3-D routes; uprights stay vertical on slopes."""
import math
import numpy as np
from shapely.geometry import Polygon, box, LineString
from modeling.trim_sweep import emit_sweep


def lathe(mb,xy,bottom,height,radius,material,semantic='balcony_baluster',double=False,turned=False):
    """Closed surface of revolution, with common vertices at profile rings."""
    profile=[(0,.65),(.06,.65),(.09,.40),(.18,.30),(.28,.75),(.42,1.),
             (.53,.70),(.60,.32),(.81,.25),(.88,.48),(.94,.60),(1.,.60)]
    if double:profile=[(i/24,.30+.60*math.sin(i/24*2*math.pi)**2) for i in range(25)]
    if turned:profile=[(i/24,.32+.35*math.sin(i/24*3*math.pi)**2) for i in range(25)]
    segments=12
    with mb.component(semantic):
        rings=[[mb.vert((xy[0]+radius*r*math.cos(q*2*math.pi/segments),
                         xy[1]+radius*r*math.sin(q*2*math.pi/segments),bottom+z*height))
                for q in range(segments)] for z,r in profile]
        mat=mb.mat_index(material)
        for lo,hi in zip(rings,rings[1:]):
            for j in range(segments):
                k=(j+1)%segments
                mb.quad(lo[j],lo[k],hi[k],hi[j],((0,0),(1,0),(1,1),(0,1)),mat)
        for ring,z,reverse in ((rings[0],bottom,True),(rings[-1],bottom+height,False)):
            center=mb.vert((*xy,z))
            for j in range(segments):
                k=(j+1)%segments
                ids=(center,ring[k],ring[j]) if reverse else (center,ring[j],ring[k])
                mb.tri(*ids,((0,0),(1,0),(0,1)),mat)


def build_railing(mb,path,c,pattern,material,envelope,ornate=False):
    if not c.enabled:return
    path=np.asarray(path,float)
    h=c.height_m
    stone=pattern in ('vase','double_vase','mixed')
    radius=.018 if material=='wood' else .009
    post_width=max(c.post_width_m,.16 if stone else .04)
    posted=set()
    def rod(a,b,r=radius,mat=material,name='balcony_bar'):
        mb.beam(a,b,r,mat,name,clip='envelope')
    def curve(points,r=radius,name='balcony_ornament'):
        for a,b in zip(points,points[1:]):rod(a,b,r,name=name)
    def post(p):
        key=tuple(np.round(p,7))
        if key in posted or pattern=='frameless':return
        posted.add(key)
        xy=p[:2]; w=post_width/2
        mb.solid(box(xy[0]-w,xy[1]-w,xy[0]+w,xy[1]+w),p[2],p[2]+h,
                 material,'balcony_post',clip='envelope')
        if stone or ornate:
            mb.solid(box(xy[0]-w*1.2,xy[1]-w*1.2,xy[0]+w*1.2,xy[1]+w*1.2),
                     p[2]+h-.035,p[2]+h+.025,material,'balcony_post_cap',clip='envelope')
    # Continuous horizontal profiles have mitred corners. Sloped rails use beams.
    horizontal=np.ptp(path[:,2])<1e-7
    if c.handrail and horizontal:
        w=.12 if stone else (.07 if material=='wood' else .045)
        section=((-w/2,0),(w/2,0),(w/2,.055 if stone else .035),(-w/2,.055 if stone else .035))
        emit_sweep(mb,path[:,:2],section,path[0,2]+h,material,'balcony_handrail',envelope)
    for a,b in zip(path,path[1:]):
        delta=b-a; length=np.linalg.norm(delta[:2]); t=delta[:2]/length; n=np.array([t[1],-t[0]])
        def p(x,z=0,depth=0):return np.r_[a[:2]+t*x+n*depth,a[2]+delta[2]*x/length+z]
        def panel(lo,hi,low,high,mat=material,depth=.025,name='balcony_panel'):
            poly=Polygon([(lo,p(lo,low)[2]),(hi,p(hi,low)[2]),(hi,p(hi,high)[2]),(lo,p(lo,high)[2])])
            mb.panel(a[:2],t,n,[poly],-depth/2,depth/2,lambda *args:mat,name,clip='envelope')
        if c.handrail and not horizontal:rod(p(0,h),p(length,h),.025 if stone else .018,name='balcony_handrail')
        if pattern!='frameless':rod(p(0,.10),p(length,.10),.03 if stone else .018,name='balcony_lower_rail')
        else:panel(0,length,0,.075,depth=.05,name='balcony_glass_channel')
        bays=max(1,math.ceil(length/c.post_spacing_m))
        for i in range(bays+1):post(p(length*i/bays))
        for bay in range(bays):
            lo=length*bay/bays+post_width/2+.015
            hi=length*(bay+1)/bays-post_width/2-.015
            if hi-lo<.08:continue
            if pattern in ('glass','frameless'):
                panel(lo,hi,.10,h-.035,c.glass_material,.012,'balcony_glass')
                if pattern=='glass':
                    for x in (lo,hi):
                        for z in (.24,h-.18):rod(p(x-.018,z),p(x+.018,z),.018,name='balcony_glass_clamp')
            elif pattern in ('cross','grid','lattice'):
                for x in (lo,hi):rod(p(x,.12),p(x,h-.06),.024,name='balcony_panel_frame')
                if pattern=='cross':
                    rod(p(lo,.12),p(hi,h-.06),.024);rod(p(hi,.12),p(lo,h-.06),.024)
                else:
                    # Clip the lattice in (u, relative z), including slope afterwards.
                    shape=box(lo,.12,hi,h-.06)
                    for x in np.arange(lo-h,hi+h,c.spacing_m):
                        segs=([(x,.12),(x,h-.06)],) if pattern=='grid' else (
                            [(x,.12),(x+h,h-.06)],[(x,.12),(x-h,h-.06)])
                        for seg in segs:
                            line=LineString(seg).intersection(shape)
                            if line.geom_type=='LineString' and line.length>1e-6:
                                rod(p(*line.coords[0]),p(*line.coords[-1]),.012)
                    if pattern=='grid':
                        for z in np.arange(.12,h-.06,c.spacing_m):rod(p(lo,z),p(hi,z),.012)
            elif pattern in ('horizontal','cables','louvers'):
                if pattern=='louvers':panel(lo,hi,.10,h*.35,depth=.055,name='balcony_solid_base')
                low=h*.40 if pattern=='louvers' else .15
                for z in np.linspace(low,h-.08,max(2,math.ceil((h-low)/c.spacing_m))):
                    if pattern=='louvers':panel(lo,hi,z,min(h-.04,z+.06),depth=.025,name='balcony_louver')
                    else:
                        rod(p(lo,z),p(hi,z),.004 if pattern=='cables' else .012)
                        if pattern=='cables':
                            for x in (lo,hi-.04):rod(p(x,z),p(x+.04,z),.012,name='balcony_tensioner')
            elif pattern=='panels' or pattern=='mixed' and bay%2==0:
                panel(lo,hi,.10,h-.05,depth=.06)
                for x in (lo+.04,hi-.04):rod(p(x,.16),p(x,h-.12),.025,name='balcony_panel_moulding')
                for z in (.16,h-.12):rod(p(lo+.04,z),p(hi-.04,z),.025,name='balcony_panel_moulding')
                if ornate:
                    center=(lo+hi)/2
                    curve([p(center+(hi-lo)*.28*math.cos(q),h*.52+h*.22*math.sin(q),.045)
                           for q in np.linspace(0,2*math.pi,25)],.012)
            else:
                spacing=max(c.spacing_m,.20 if stone else .06)
                count=max(1,math.floor((hi-lo)/spacing))
                for j in range(count):
                    x=lo+(hi-lo)*(j+.5)/count
                    if pattern in ('vase','double_vase','mixed','turned'):
                        center=p(x,.12)
                        lathe(mb,center[:2],center[2],h-.20,min(.075,spacing*.30),material,
                              double=pattern=='double_vase',turned=pattern=='turned')
                    elif pattern=='bowed':
                        curve([p(x,z,.15*math.sin(math.pi*z/h)) for z in np.linspace(.12,h-.05,16)],name='balcony_bowed_bar')
                    else:rod(p(x,.12),p(x,h-.04))
                if pattern in ('rings','scrolls'):
                    motifs=max(1,math.floor((hi-lo)/.34))
                    for j in range(motifs):
                        x=lo+(hi-lo)*(j+.5)/motifs
                        if pattern=='rings':
                            r=min(.09,(hi-lo)/motifs*.35)
                            curve([p(x+r*math.cos(q),h-.20+r*math.sin(q)) for q in np.linspace(0,2*math.pi,21)])
                        else:
                            for sign in (-1,1):
                                curve([p(x+sign*(.02+.09*q/(2*math.pi))*math.cos(q),h*.5+h*.28*math.sin(q))
                                       for q in np.linspace(0,2*math.pi,24)])
