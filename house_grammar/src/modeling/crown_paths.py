"""Dimensioned silhouettes; metric radii, shared endpoints, no mesh templates."""
import math
import numpy as np
from shapely.geometry import Polygon, LineString
from modeling.crown_catalog import classify, STYLES


def validate(design,width,height):
    family,reason=classify(design)
    if design.style not in STYLES:raise ValueError('Unknown/unresolved crown style')
    if not all(math.isfinite(v) for v in (width,height,design.thickness_m,design.recess_m,design.moulding_width_m,design.projection_m)):
        raise ValueError('Nonfinite crown dimensions')
    if not .6<=width<=30 or not .2<=height<=5:raise ValueError('Crown dimensions exceed supported range')
    if not .12<=design.thickness_m<=1 or not 0<=design.recess_m<design.thickness_m*.7:raise ValueError('Invalid crown thickness/recess')
    if not .02<=design.moulding_width_m<=min(.5,width*.18,height*.48):raise ValueError('Crown moulding too large')
    if not .02<=design.projection_m<=.7 or design.detail not in (1,2,3):raise ValueError('Invalid crown profile/detail')
    if design.ornament not in ('none','keystone','cartouche','volutes','dentils'):raise ValueError('Unknown crown ornament')
    if family=='semicircular' and abs(height-width/2)>1e-5:raise ValueError('Semicircular crown requires height = width / 2; use segmental')
    if family=='segmental' and height>width/2:raise ValueError('Segmental crown rise exceeds half width')
    return family,reason


def paths(design,width,height):
    family,_=validate(design,width,height)
    count=16*design.detail
    def arc(left,right,base,rise):
        half=(right-left)/2;radius=(half*half+rise*rise)/(2*rise)
        xs=np.linspace(left,right,count+1)
        return [(float(x),base+math.sqrt(max(0,radius*radius-(x-(left+right)/2)**2))-radius+rise) for x in xs]
    if family=='triangular':out=[[(0,0),(width/2,height),(width,0)]]
    elif family in ('segmental','semicircular'):out=[arc(0,width,0,height)]
    elif family=='stepped':out=[[(0,0),(0,height*.25),(width*.17,height*.25),(width*.17,height*.55),
         (width*.33,height*.55),(width*.33,height),(width*.67,height),(width*.67,height*.55),
         (width*.83,height*.55),(width*.83,height*.25),(width,height*.25),(width,0)]]
    elif family=='stepped_segmental':
        rise=min(height*.60,width*.22); shoulder=height-rise
        out=[[(0,0),(0,shoulder*.5),(width*.16,shoulder*.5),(width*.16,shoulder),
             (width*.28,shoulder),*arc(width*.28,width*.72,shoulder,rise),
             (width*.84,shoulder),(width*.84,shoulder*.5),(width,shoulder*.5),(width,0)]]
    elif family=='curved_pointed':
        left=[(width*.5*f,height*(1-(1-f)**1.8)) for f in np.linspace(0,1,count+1)]
        out=[left+[(width-x,z) for x,z in left[-2::-1]]]
    elif family in ('concave_shoulders','compound_curve'):
        left=[]
        for f in np.linspace(0,1,count+1):
            z=height*(f*f*.72 if family=='concave_shoulders' else .72*(f*f*(3-2*f)))
            left.append((width*.36*f,z))
        out=[left+[(width*.36,height),(width*.64,height)]+[(width-x,z) for x,z in left[::-1]]]
    elif family=='broken':out=[[(0,0),(width*.39,height)],[(width*.61,height),(width,0)]]
    else:out=[[(0,0),(0,height*.4),(width*.3,height*.4),(width*.3,height),
              (width*.7,height),(width*.7,height*.4),(width,height*.4),(width,0)]]
    cleaned=[]
    for route in out:
        points=[]
        for p in route:
            if not points or np.linalg.norm(np.asarray(p)-points[-1])>1e-7:points.append(tuple(map(float,p)))
        if not LineString(points).is_simple:raise ValueError('Self-intersecting crown contour')
        cleaned.append(tuple(points))
    return tuple(cleaned)


def body_shapes(routes):
    result=[]
    for route in routes:
        poly=Polygon([(route[0][0],-.015),*route,(route[-1][0],-.015)])
        if not poly.is_valid or poly.area<1e-6:raise ValueError('Invalid crown body')
        result.append(poly)
    return result
