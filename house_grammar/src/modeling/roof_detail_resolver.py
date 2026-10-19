"""Explicit roof replacement and anchored canopy resolution."""
from dataclasses import dataclass,replace,asdict
import math
import numpy as np
from shapely.geometry import Polygon,LineString
from shapely.ops import unary_union
from domain.roof_details import RoofDesign
from domain.architecture import RoofProp
from modeling.assembly import mass_polygon
from modeling.roof_planes import RoofFace,plan_faces,compound_faces,geometry,height,faces
from modeling.crown_catalog import STYLES


@dataclass(frozen=True)
class RoofWallFinish:
    polygon: tuple[tuple[float,float],...]
    material: str


@dataclass(frozen=True)
class ResolvedRoofAssembly:
    id: str
    mass_ref: str
    design: RoofDesign
    faces: tuple[RoofFace,...]
    support: tuple[tuple[float,float],...]
    base_z: float
    canopy: bool = False
    depth_m: float = 0.
    outward: tuple[float,float] = (0.,0.)
    posts: bool = False
    crown_ref: str | None = None
    wall_joints: tuple[tuple[tuple[float,float],...],...] = ()
    source_masses: tuple[str,...] = ()
    post_base_z: float = 0.
    props_mode: str = 'preserve'
    props: tuple[RoofProp,...] = ()
    wall_finishes: tuple[RoofWallFinish,...] = ()
    neighbor_polygons: tuple[tuple[tuple[float,float],...],...] = ()
    support_holes: tuple[tuple[tuple[float,float],...],...] = ()


def wall_finishes(mass,walls):
    """Continue the upper wall finish, not the roof or decorative coping slot."""
    result=[]
    for w in walls:
        if w.mass_role!=mass.id or abs(w.base_z+w.height_m-mass.roof_z)>1e-6:continue
        f=w.facade;t=(np.asarray(f.vertex_b)-f.vertex_a)/f.width_m;n=np.asarray(f.normal_xy)
        a=np.asarray(f.vertex_a)+n*w.plane_offset_m
        top=w.height_m-1e-6
        regions=[r for r in f.material_regions if r.v_m<=top<=r.v_m+r.height_m]
        cuts=sorted({0.,f.width_m,*[max(0.,min(f.width_m,u)) for r in regions for u in (r.u_m,r.u_m+r.width_m)]})
        first=f.floor_levels_m[1] if len(f.floor_levels_m)>1 else w.height_m
        base=f.ground_floor_material if f.ground_floor_material and top<first else f.wall_material
        segments=[]
        for lo,hi in zip(cuts,cuts[1:]):
            material=base
            for region in regions:
                if region.u_m<=(lo+hi)/2<=region.u_m+region.width_m:material=region.material_slot
            segments.append((lo,hi,material))
        # Outer corner squares of the proud lip lie past both walls' end
        # points; classify them with the adjoining end segment's material.
        if segments:
            segments.insert(0,(segments[0][0]-.16,segments[0][0],segments[0][2]))
            segments.append((segments[-1][1],segments[-1][1]+.16,segments[-1][2]))
        for lo,hi,material in segments:
            # Outer lip covers the 10 mm proud gable closure, not just the wall face.
            poly=Polygon([a+t*u+n*d for u,d in ((lo, .015),(hi,.015),(hi,-.16),(lo,-.16))])
            result.append(RoofWallFinish(tuple(poly.exterior.coords)[:-1],material))
    return tuple(result)


def validate(d,style,materials):
    d=replace(d,style=style if d.style=='auto' else d.style)
    if d.style not in STYLES:raise ValueError('Roof style needs explicit style or building inheritance')
    if d.eave.kind=='auto':
        d=replace(d,eave=replace(d.eave,kind={'republicano':'profiled','barroco':'cornice','clasico':'cornice','madera':'exposed','moderno':'clean'}[d.style]))
    if d.form not in ('flat','shed','gable','hip','pavilion','band','compound'):raise ValueError('Unknown roof form')
    if d.covering not in ('none','curved_tile','flat_tile','corrugated','panel','slats'):raise ValueError('Unknown roof covering')
    if d.construction not in ('solid','frame'):raise ValueError('Unknown roof construction')
    if d.construction=='frame' and d.covering in ('curved_tile','flat_tile'):raise ValueError('Tile roofs require a continuous substrate')
    if d.detail not in ('light','medium','full'):raise ValueError('Unknown roof detail')
    def finite(value):
        if isinstance(value,dict):return all(finite(v) for v in value.values())
        return not isinstance(value,(float,int)) or math.isfinite(value)
    if not finite(asdict(d)):raise ValueError('Nonfinite roof controls')
    if not (1<=d.slope_deg<=45 and .1<=d.ridge_fraction<=.9 and .025<=d.thickness_m<=.5
            and .08<=d.tile_width_m<=.8 and .15<=d.tile_length_m<=1.2 and 0<=d.overlap_m<d.tile_length_m*.6
            and .2<=d.band_depth_m<=8 and 0<=d.parapet_m<=2):raise ValueError('Invalid roof dimensions')
    if d.parapet_m and d.form!='flat':raise ValueError('Parapets require a flat assembly; use separate roof regions')
    if d.cap not in ('none','flat','bevel','pitched','moulded','metal'):raise ValueError('Unknown coping profile')
    if d.cap_drip and d.cap!='metal':raise ValueError('Folded drip edge requires metal coping')
    e=d.eave
    if e.kind not in ('clean','closed','exposed','profiled','braces','curved','cornice'):raise ValueError('Unknown eave kind')
    if not (0<=e.overhang_m<=1.5 and .2<=e.spacing_m<=2 and .03<=e.beam_width_m<=.3 and .04<=e.beam_height_m<=.5):raise ValueError('Invalid eave dimensions')
    for material in (d.material,d.substrate_material,d.cap_material,e.material,e.fascia_material):
        if material not in materials:raise ValueError('Unknown roof material '+material)
    return d


def resolve_roof_assemblies(theta,masses,walls,roofs,crowns,envelope,materials):
    result=[];ids=set();managed=set()
    for c in theta.roof_assemblies:
        if not c.enabled:continue
        if not c.id or c.id in ids or c.mass_ref in managed:raise ValueError('Duplicate roof id or mass replacement')
        ids.add(c.id);managed.add(c.mass_ref)
        m=next((m for m in masses if m.id==c.mass_ref),None)
        old=next((r for r in roofs if r.mass_id==c.mass_ref),None)
        if m is None or old is None:raise ValueError('Roof assembly mass missing or covered')
        d=validate(c.design,theta.architectural_style or 'republicano',materials)
        support=mass_polygon(m)
        if support.interiors:raise ValueError('Detailed roof courtyard requires separate masses')
        exposed=unary_union([Polygon(s.polygon,s.holes) for s in old.surfaces])
        poly=support.buffer(d.eave.overhang_m,join_style=2)
        clearance=max(.13 if d.eave.kind=='cornice' else
                      .025 if d.eave.fascia or d.eave.kind!='clean' or d.parapet_m and d.cap!='none' else 0,
                      .18 if d.eave.gutter else 0)
        # Existing upper masses carve out covered roof regions.
        blockers=unary_union([support.difference(exposed),*[mass_polygon(other) for other in masses
            if other.id!=m.id and other.roof_z>m.roof_z+1e-6 and other.base_z<=m.roof_z]])
        available=poly.difference(blockers)
        if available.geom_type!='Polygon':raise ValueError('Disconnected roof requires separate assemblies')
        if c.junction not in ('none','behind','gable'):raise ValueError('Unknown crown junction')
        if (c.crown_ref is None)!=(c.junction=='none'):raise ValueError('Crown junction requires crown_ref')
        from modeling.roof_assembly import lines
        joints=tuple(tuple(line.coords) for line in lines(available.boundary.intersection(blockers.boundary)))
        if c.crown_ref:
            crown=next((r for r in crowns if r.controls.id==c.crown_ref),None)
            if crown is None or crown.controls.mass_ref!=m.id or crown.controls.anchor!='wall_top':raise ValueError('Roof needs wall-top crown on same mass')
            cc=crown.controls;a=np.asarray(crown.origin);t=np.asarray(crown.tangent);n=np.asarray(crown.normal)
            if c.junction=='gable':
                if cc.design.family!='triangular' or d.form!='gable':raise ValueError('Gable junction needs triangular crown and gable roof')
                extent=np.asarray(support.exterior.coords)@t
                if abs(cc.width_m-(extent.max()-extent.min()))>.02:raise ValueError('Structural gable crown must span roof width')
                d=replace(d,rotation_deg=math.degrees(math.atan2(t[1],t[0])),slope_deg=math.degrees(math.atan2(cc.height_m,cc.width_m/2)),ridge_fraction=.5,
                          eave=replace(d.eave,overhang_m=0))
                d=validate(d,theta.architectural_style or 'republicano',materials)
                poly=support
                available=support.difference(blockers)
            # Reserve body thickness and a small weathering joint behind crown.
            cut=Polygon([a+t*u+n*v for u,v in ((cc.u_m,-cc.design.thickness_m-.035),(cc.u_m+cc.width_m,-cc.design.thickness_m-.035),
                        (cc.u_m+cc.width_m,2.),(cc.u_m,2.))])
            available=available.difference(cut)
            if available.geom_type!='Polygon' or available.is_empty:raise ValueError('Crown leaves no connected roof')
            from modeling.roof_assembly import lines
            joints+=tuple(tuple(line.coords) for line in lines(available.boundary.intersection(cut.boundary)))
        # The cadastral envelope carries a precision grid; sub-grid buffers
        # round to zero. One 0.1 mm tolerance handles boundary roundoff only.
        if not envelope.buffer(1e-4).covers(available.buffer(clearance)):
            raise ValueError('Roof overhang outside permitted envelope; reduce overhang')
        if d.form=='compound':
            if len(c.regions)<2:raise ValueError('Compound needs at least two explicit lobe regions')
            regions=[Polygon(r) for r in c.regions]
            if any(not p.is_valid or p.area<.5 or p.symmetric_difference(p.minimum_rotated_rectangle).area>1e-6 for p in regions):raise ValueError('Compound lobes must be rectangles')
            if unary_union(regions).symmetric_difference(support).area>1e-5:raise ValueError('Compound regions must cover supporting footprint exactly')
            ff=compound_faces([p.buffer(d.eave.overhang_m,join_style=2) for p in regions],d,m.roof_z)
            clipped=[]
            from modeling.mesh_builder import polygons
            for f in ff:
                for p in polygons(geometry(f).intersection(available)):clipped+=faces(p,[f.plane])
            ff=clipped
        else:
            # Plan on the complete support before clipping. An upper body or
            # crown must not move the ridge or change the slope datum.
            from modeling.mesh_builder import polygons
            ff=[patch for f in plan_faces(poly,d,m.roof_z)
                for part in polygons(geometry(f).intersection(available))
                for patch in faces(part,[f.plane])]
        if c.crown_ref:
            # Check the entire opening against the back-wall roof section.
            if crown.controls.aperture!='none':
                from modeling.crown_assembly import aperture_shape
                aperture=aperture_shape(cc.aperture,cc.aperture_width_m,cc.aperture_height_m,cc.aperture_sill_m,cc.width_m/2)
                start=a+t*cc.u_m-n*(cc.design.thickness_m+.04)
                cut_line=LineString([start,start+t*cc.width_m])
                for f in ff:
                    for line in lines(geometry(f).intersection(cut_line)):
                        xy=np.asarray(line.coords);us=(xy-start)@t
                        lo,hi=us.min(),us.max()
                        zl=height(f.plane,*(start+t*lo))-crown.base_z
                        zh=height(f.plane,*(start+t*hi))-crown.base_z
                        section=Polygon([(lo,-.1),(hi,-.1),(hi,max(-.09,zh)),(lo,max(-.09,zl))])
                        if section.intersection(aperture).area>1e-7:raise ValueError('Roof backs crown aperture; lower roof or move aperture')
        if c.props_mode not in ('preserve','auto','off'):raise ValueError('Unknown roof props mode')
        if d.form!='flat' and (c.props_mode=='auto' or old.props and c.props_mode=='preserve'):raise ValueError('Azotea props require a flat detailed roof')
        props=()
        if c.props_mode=='auto':
            import hashlib
            from modeling.roofscape import scatter_props
            # Style influences optional defaults, not the geometry of utility objects.
            weights={'republicano':{'planter':3,'laundry':1,'water_tank':1,'skylight':1},
                     'barroco':{'planter':3,'skylight':1,'water_tank':.5},
                     'clasico':{'planter':2,'skylight':2,'water_tank':.5},
                     'madera':{'planter':3,'laundry':2,'water_tank':1},
                     'moderno':{'hvac':2,'skylight':2,'planter':2,'water_tank':1}}[d.style]
            seed=int.from_bytes(hashlib.sha256(c.id.encode()).digest()[:4],'little')
            props=scatter_props(available.intersection(support),weights,np.random.default_rng(seed),density=.04,limit=6)
        from modeling.mesh_builder import polygons as _polys
        neighbors=tuple(tuple(p.exterior.coords)[:-1] for other in masses
            if other.id!=m.id and other.kind=='enclosed' and other.base_z<m.roof_z+4 and other.roof_z>m.base_z
            for p in _polys(mass_polygon(other).intersection(support.buffer(.02))) if p.area>1e-6)
        result.append(ResolvedRoofAssembly(c.id,m.id,d,tuple(ff),tuple(support.exterior.coords)[:-1],m.roof_z,crown_ref=c.crown_ref,wall_joints=joints,props_mode=c.props_mode,props=props,wall_finishes=wall_finishes(m,walls),
            neighbor_polygons=neighbors))
    groups={}
    for c in theta.roof_assemblies:
        if c.enabled and c.join_group:groups.setdefault(c.join_group,[]).append(c)
    for name,controls in groups.items():
        members=[r for r in result if r.id in {c.id for c in controls}]
        if len(members)<2:raise ValueError('Roof join_group requires at least two roofs')
        if any(r.props_mode!='preserve' for r in members):raise ValueError('Joined roofs use explicit preserved props')
        first=members[0]
        if any(abs(r.base_z-first.base_z)>1e-6 for r in members):raise ValueError('Joined roofs require equal base elevations; use independent abutment roofs')
        if any(replace(r.design,rotation_deg=0,ridge_fraction=.5)!=replace(first.design,rotation_deg=0,ridge_fraction=.5) for r in members):
            raise ValueError('Joined roofs require compatible construction and finishes')
        support=unary_union([Polygon(r.support) for r in members])
        if support.geom_type!='Polygon' or support.interiors:raise ValueError('Joined roof supports must form one connected footprint')
        from modeling.roof_planes import merge_roof_faces
        combined=tuple(merge_roof_faces([r.faces for r in members]))
        result=[r for r in result if r not in members]
        result.append(replace(first,id='joined_'+name,faces=combined,support=tuple(support.exterior.coords)[:-1],
                      source_masses=tuple(r.mass_ref for r in members),wall_joints=tuple(j for r in members for j in r.wall_joints),
                      wall_finishes=tuple(f for r in members for f in r.wall_finishes),
                      neighbor_polygons=tuple(n for r in members for n in r.neighbor_polygons)))
    for c in theta.canopies:
        if not c.id or c.id in ids:raise ValueError('Duplicate canopy id')
        ids.add(c.id)
        d=validate(c.design,theta.architectural_style or 'republicano',materials)
        if d.form not in ('flat','shed'):raise ValueError('Canopy supports flat or shed form')
        ws=[w for w in walls if w.mass_role==c.mass_ref and w.edge==c.edge]
        if len(ws)!=1:raise ValueError('Canopy needs unambiguous facade')
        w=ws[0];f=w.facade;t=(np.asarray(f.vertex_b)-f.vertex_a)/f.width_m;n=np.asarray(f.normal_xy)
        u=c.u_m;z=w.base_z+c.height_m
        if c.opening_index is not None:
            if not 0<=c.opening_index<len(f.openings):raise ValueError('Canopy opening missing')
            op=f.openings[c.opening_index];u=op.u_m+(op.width_m-c.width_m)/2
            z=w.base_z+op.v_m+op.height_m+.25
        if not np.isfinite((u,z,c.width_m,c.depth_m)).all() or not .5<=c.width_m<=20 or not .3<=c.depth_m<=6 or u<0 or u+c.width_m>f.width_m or z<=w.base_z:
            raise ValueError('Invalid canopy dimensions')
        high=z+(math.tan(math.radians(d.slope_deg))*c.depth_m if d.form=='shed' else 0)
        if not c.posts and high>w.base_z+w.height_m+.02:raise ValueError('Wall-mounted canopy exceeds supporting wall')
        a=np.asarray(f.vertex_a)+n*w.plane_offset_m
        poly=Polygon([a+t*x+n*y for x,y in ((u,0),(u+c.width_m,0),(u+c.width_m,c.depth_m),(u,c.depth_m))])
        if not envelope.buffer(1e-6).covers(poly.buffer(.18 if d.eave.gutter else .025)):raise ValueError('Canopy outside permitted envelope')
        for m in masses:
            if m.base_z<z and m.roof_z>z and poly.intersection(mass_polygon(m)).area>1e-6:raise ValueError('Canopy intersects occupied mass')
        d=replace(d,rotation_deg=math.degrees(math.atan2(-n[1],-n[0])),eave=replace(d.eave,overhang_m=0))
        result.append(ResolvedRoofAssembly(c.id,c.mass_ref,d,tuple(plan_faces(poly,d,z)),tuple(poly.exterior.coords)[:-1],z,True,c.depth_m,tuple(n),c.posts,post_base_z=w.base_z))
    for i,r in enumerate(result):
        for other in result[:i]:
            for f in r.faces:
                for g in other.faces:
                    overlap=geometry(f).intersection(geometry(g))
                    if overlap.area<1e-6:continue
                    from modeling.roof_planes import keep
                    diff=np.asarray(f.plane)-g.plane
                    conflict=keep(overlap,(*diff[:2],diff[2]+other.design.thickness_m))
                    conflict=keep(conflict,(*(-diff[:2]),r.design.thickness_m-diff[2]))
                    if conflict.area>1e-6:raise ValueError(f'Roof assemblies {r.id}/{other.id} intersect; use join_group or separate elevations')
    return tuple(result)
