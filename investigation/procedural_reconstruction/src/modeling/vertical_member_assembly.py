"""One geometric engine for independent, embedded and facade vertical members."""
from dataclasses import replace
import math
import numpy as np
from shapely.geometry import Polygon
from domain.vertical_members import MemberDesign
from modeling.vertical_member_catalog import member_preset, SECTIONS
from modeling.vertical_member_profiles import section_ring, moulding_profile
from modeling.vertical_member_sweep import emit_loft
from modeling.vertical_member_ornaments import emit_ornaments


def validate_design(d,width,depth,height):
    name,p=member_preset(d)
    section=p.section if d.section=='auto' else d.section
    if section not in SECTIONS:raise ValueError('Unknown member section')
    if d.base_profile not in ('auto','attic','simple','minimal'):raise ValueError('Unknown base profile')
    if not all(math.isfinite(v) and v>0 for v in (width,depth,height)):
        raise ValueError('Invalid member dimensions')
    if not .06<=min(width,depth) or max(width,depth)>3 or not .25<=height<=20:
        raise ValueError('Member dimensions outside supported range')
    if d.detail not in (1,2,3) or not 3<=d.flute_count<=32:raise ValueError('Invalid member detail/flutes')
    if not math.isfinite(d.turns) or abs(d.turns)>5:raise ValueError('Invalid member twist')
    if not math.isfinite(d.pedestal_m) or not 0<=d.pedestal_m<height*.35:raise ValueError('Invalid pedestal')
    taper=p.taper if d.taper is None else d.taper
    if not math.isfinite(taper) or not 0<=taper<=.45 or not math.isfinite(d.entasis) or not 0<=d.entasis<=.12:
        raise ValueError('Invalid member taper/entasis')
    if section=='circle' and abs(width-depth)>1e-6:raise ValueError('Circular section requires equal width and depth; use ellipse')
    if p.shaft=='panel' and section not in ('rectangle','chamfered','rounded'):
        raise ValueError('Recessed panels require a rectangular section')
    if p.shaft=='twisted' and section not in ('circle','ellipse'):raise ValueError('Salomonic shaft requires round/oval section')
    for h in (d.base_height_m,d.capital_height_m):
        if h is not None and (not math.isfinite(h) or not .02<=h<=height*.3):raise ValueError('Invalid moulding height')
    return name,p,section,taper


def member_rings(design,width,depth,height):
    """Return all primary closed sweeps in local coordinates and ornament bounds."""
    name,p,section,taper=validate_design(design,width,depth,height)
    d=design
    base=p.base if d.base is None else d.base
    cap=p.capital!='none' if d.capital is None else d.capital
    bh=(d.base_height_m or min(height*.10,width*.45)) if base else 0.
    ch=(d.capital_height_m or min(height*.17 if p.capital in ('leaves','composite','volutes') else height*.09,
                                width*(.85 if p.capital in ('leaves','composite','volutes') else .45))) if cap else 0.
    low=d.pedestal_m+bh; high=height-ch
    if high-low<height*.3:raise ValueError('Member has insufficient shaft height')
    plain=section_ring(section,width,depth,d.detail)
    def scaled(ring,z,scale=1.):return np.column_stack((ring*scale,np.full(len(ring),z)))
    parts=[]
    if d.pedestal_m:
        parts.append(('pedestal',d.base_material or d.material,[scaled(plain,0,1.18),scaled(plain,d.pedestal_m,1.18)]))
    if base:
        profile='base' if d.base_profile=='auto' else d.base_profile
        parts.append(('base',d.base_material or d.material,[scaled(plain,d.pedestal_m+z*bh,r) for z,r in moulding_profile(profile,d.detail)]))
    ring=section_ring(section,width,depth,d.detail,d.flute_count if p.shaft=='fluted' else 0)
    if p.shaft=='panel':
        # A rectangular boundary with explicit recess transition vertices.
        xs=np.array([-.5,-.38,-.32,.32,.38,.5])*width
        ring=np.array([(x,-depth/2) for x in xs]+[(x,depth/2) for x in xs[::-1]])
    samples=max(20*d.detail,int(abs(d.turns)*48*d.detail) if p.shaft=='twisted' else 0)
    fractions=np.unique(np.r_[np.linspace(0,1,samples+1),.06,.09,.91,.94])
    if p.shaft=='rusticated':
        courses=max(2,round((high-low)/.35))
        fractions=np.unique(np.r_[fractions,[(i+f)/courses for i in range(courses) for f in (0,.07,.93)],1.])
    rings=[]
    for f in fractions:
        scale=1-taper*f+(d.entasis if d.style not in ('moderno','madera') else 0)*np.sin(np.pi*f)
        if p.shaft=='turned':scale*=.78+.18*np.sin(np.pi*f*3)**2+.12*np.exp(-((f-.18)/.09)**2)
        if p.shaft=='estipite':scale*=np.interp(f,[0,.12,.15,.50,.56,.69,.78,1],[.68,.68,1.05,.47,.47,1.05,.78,1.])
        xy=ring.copy()*scale
        if p.shaft=='panel':
            recess=min(depth*.20,.045)*np.clip(min(f-.06,.94-f)/.03,0,1)
            factor=np.clip((width*.38-np.abs(ring[:,0]))/(width*.06),0,1)
            xy[:,1]-=np.sign(xy[:,1])*recess*factor
        if p.shaft=='rusticated':
            courses=max(2,round((high-low)/.35))
            phase=(f*courses)%1
            xy*=1-.08*max(0,1-min(phase,1-phase)/.07)
        if p.shaft=='twisted':
            q=f*d.turns*2*np.pi
            angles=np.arctan2(ring[:,1]/depth,ring[:,0]/width)
            xy*= (1+.12*np.cos(angles*3-q*3))[:,None]
        rings.append(np.column_stack((xy,np.full(len(xy),low+(high-low)*f))))
    parts.append(('shaft',d.material,rings))
    if cap:
        profile=moulding_profile(p.capital,d.detail)
        if not d.collar:profile=tuple((z,1. if z<.25 else r) for z,r in profile)
        if not d.abacus:profile=tuple((z,min(r,1.16) if z>.73 else r) for z,r in profile)
        parts.append(('capital',d.capital_material or d.material,
                      [scaled(plain,high+z*ch,r*(1-taper)) for z,r in profile]))
    return parts,(high,ch,p.capital if cap else 'none')


def build_member(mb,center,t,n,bottom,width,depth,height,design=MemberDesign(),placement='freestanding'):
    center,t,n=map(np.asarray,(center,t,n))
    parts,ornament=member_rings(design,width,depth,height)
    for name,material,rings in parts:
        world=[]
        for ring in rings:
            xy=center+ring[:,:1]*t+ring[:,1:2]*n
            world.append(np.column_stack((xy,ring[:,2]+bottom)))
        emit_loft(mb,world,material,'member_'+name)
    high,ch,kind=ornament
    if design.ornament and ch and kind in ('volutes','leaves','composite','saddle'):
        emit_ornaments(mb,center,t,n,bottom+high,width,depth,ch,kind,
                       design.capital_material or design.material,design.detail,placement in ('attached','embedded'))


def facade_member(mb,a,t,n,feature,variant='smooth_moulded',style='republicano'):
    """Translation adapter for old projection names; no legacy mesh generator."""
    design=getattr(feature,'member',None) or MemberDesign(style=style,variant=variant,material=feature.material_slot)
    if design.style=='auto':design=replace(design,style=style)
    depth=max(.06,feature.depth_m+.02)
    center=np.asarray(a)+np.asarray(t)*(feature.u_m+feature.width_m/2)+np.asarray(n)*(depth/2-.02)
    build_member(mb,center,t,n,feature.v_m,feature.width_m,depth,feature.height_m,design,'attached')
