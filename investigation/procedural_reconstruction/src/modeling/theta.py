"""Resolve architectural decisions first; only then emit geometry.

The legacy V4 entry point is deliberately not called: it discards explicit
facades and replans roofs. This adapter shares its geometry primitives instead.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import hashlib
import json
import numpy as np
from shapely.geometry import Polygon, LineString, Point
from shapely.geometry.polygon import orient
from shapely.affinity import translate
from shapely.ops import unary_union

from domain.theta import *
from domain.architecture import MassSpec, ParcelContext, SitePlan, RoofSurface, RoofPlan, RoofProp, BuildingProgram
from domain.models import FacadeSpecification, BuildingAppearance
from modeling.detail import DetailBudget
from modeling.geometry_constraints import apply_edge_setbacks, front_lines, outward_normal
from modeling.exposure import calculate_mass_exposures
from modeling.facade_program import FAMILY_RULES, _relief
from modeling.grammar import facade, ZOffsetMeshBuilder, street_envelope
from modeling.mesh_builder import MeshBuilder
from modeling.materials import DEFAULT_MATERIALS, resolve_materials
from modeling.roofscape import build_roof, _prop_footprint
from modeling.prefabs_roof import BUILDERS
from modeling.boundaries import generate_boundaries, BoundarySpec
from modeling.site import draw_fence, plant_garden, entrance_step


@dataclass(frozen=True)
class ResolvedWall:
    mass_role: str
    edge: int
    base_z: float
    height_m: float
    axes_m: tuple[float, ...]
    facade: FacadeSpecification


@dataclass(frozen=True)
class ResolvedBoundary:
    line: tuple[tuple[float, float], ...]
    kind: str
    height: float
    gate_u: float | None
    gate_width: float
    garage_u: float | None
    garage_width: float
    is_street: bool


@dataclass(frozen=True)
class ResolvedArchitecture:
    schema_version: str
    context: ReconstructionContext
    theta: ThetaCandidate
    # Explicit expanded semantic entities, not tessellation or mesh vertices.
    masses: tuple[MassSpec, ...]
    walls: tuple[ResolvedWall, ...]
    roofs: tuple[RoofPlan, ...]
    boundaries: tuple[ResolvedBoundary, ...]
    completed: dict[str, str]


def _check(condition, message):
    if not condition:
        raise ValueError(message)


def _ring(poly):
    _check(poly.geom_type == "Polygon" and poly.is_valid and not poly.interiors,
           "Only valid single polygons without holes are supported; no silent repair")
    points = list(orient(poly, 1).exterior.coords)[:-1]
    i = min(range(len(points)), key=lambda j: points[j])
    return tuple(points[i:] + points[:i])


def _polygon(poly, label):
    _check(poly.geom_type == "Polygon" and poly.is_valid and not poly.interiors and
           poly.area >= 6 and not poly.buffer(-.9).is_empty,
           label + ": disconnected, holed, tiny or too narrow geometry")
    return poly


def _context(p):
    _check(len(p.parcel) >= 3 and p.fronts, "P requires a parcel and at least one known front")
    original = list(p.parcel)
    if original[0] == original[-1]:
        original.pop()
    _check(len(set(original)) == len(original), "Repeated parcel vertices")
    _check(all(0 <= i < len(original) for i in p.fronts), "Invalid front edge index")
    ring = _ring(_polygon(Polygon(original), "parcel"))
    edges = [{original[i], original[(i+1) % len(original)]} for i in p.fronts]
    fronts = tuple(i for i in range(len(ring)) if {ring[i], ring[(i+1)%len(ring)]} in edges)
    return replace(p, parcel=ring, fronts=fronts)


def _complete(theta, p):
    completed = {}
    def fill(value, default, path):
        if value is None:
            completed[path] = "prior/completed"
            return default
        return value
    _check(theta.schema_version == "0.1", "Unsupported theta schema")
    if theta.masses is not None:
        _check(theta.masses and theta.height_m is None and theta.floors is None,
               "Explicit masses replace height/floors, not supplement them")
        _check(theta.massing == MassingControls(pattern="explicit"),
               "Explicit masses require only massing.pattern=explicit")
        for mass in theta.masses:
            _check(len(mass.levels_m)>=2 and mass.levels_m[0]>=0 and
                   all(2.2<=b-a<=6 for a,b in zip(mass.levels_m,mass.levels_m[1:])), "Invalid explicit floor levels")
        theta=replace(theta,height_m=max(m.levels_m[-1] for m in theta.masses),
                      floors=max(len(m.levels_m)-1 for m in theta.masses))
    height = fill(theta.height_m, p.locked_height_m or 8.4, "height_m")
    if p.locked_height_m is not None:
        _check(abs(height-p.locked_height_m) < 1e-8, "theta height conflicts with externally locked height")
        completed["height_m"] = "external"
    floors = fill(theta.floors, max(1, round(height/2.8)), "floors")
    _check(1 <= floors <= 60 and (theta.masses is not None or 2.2 <= height/floors <= 6), "Invalid floors/height (storeys must be 2.2..6m)")
    family = fill(theta.family, "quiet_house", "family")
    _check(family in FAMILY_RULES, "Unknown architectural family")
    m = theta.massing
    pattern = fill(m.pattern, "single_block", "massing.pattern")
    _check(pattern in ("single_block", "stepped_back", "podium_tower", "front_tall_rear_low", "front_low_rear_tall", "corner_accent", "explicit"), "Unsupported massing pattern")
    _check(pattern != "explicit" or theta.masses is not None, "Explicit pattern requires masses")
    _check(pattern == "corner_accent" or m.corner_reach_m is None, "corner_reach inactive")
    upper = pattern in ("stepped_back", "podium_tower")
    split = pattern.startswith("front_")
    _check(upper or m.upper_setback_m is None, "upper_setback_m inactive for this pattern")
    _check(pattern == "podium_tower" or m.podium_floors is None, "podium_floors inactive")
    _check(split or (m.front_depth_m is None and m.low_floors is None), "front_depth/low_floors inactive")
    m = replace(m, pattern=pattern,
                front_setback_m=fill(m.front_setback_m, 0., "massing.front_setback_m"),
                upper_setback_m=fill(m.upper_setback_m, 2.5, "massing.upper_setback_m") if upper else None,
                podium_floors=fill(m.podium_floors, 1, "massing.podium_floors") if pattern == "podium_tower" else None,
                front_depth_m=fill(m.front_depth_m, 6., "massing.front_depth_m") if split else None,
                low_floors=fill(m.low_floors, max(1, floors-1), "massing.low_floors") if split else None,
                corner_reach_m=fill(m.corner_reach_m,5.,"massing.corner_reach_m") if pattern=="corner_accent" else None)
    if pattern=="corner_accent":
        _check(len(p.fronts)>=2 and floors>=2 and m.corner_reach_m>0,"Corner accent needs 2 fronts, >=2 floors and positive reach")
    _check(m.front_setback_m >= 0, "Negative front setback")
    if upper:
        _check(floors >= 2 and m.upper_setback_m > 0, "Upper setback requires multiple floors and positive depth")
    if m.podium_floors is not None:
        _check(1 <= m.podium_floors < floors, "Invalid podium floors")
    if split:
        _check(m.front_depth_m > 0 and 1 <= m.low_floors < floors, "Invalid front/rear massing")
    roof = theta.roof
    kind = fill(roof.kind, "flat", "roof.kind")
    _check(kind in ("flat", "corrugated", "tile_shed"), "Unsupported roof")
    _check(kind == "tile_shed" or roof.slope_deg is None, "slope_deg inactive for flat/corrugated roof")
    parapet = fill(roof.parapet_m, 0. if kind == "tile_shed" else .5, "roof.parapet_m")
    _check(0 <= parapet <= 2 and (kind != "tile_shed" or parapet == 0), "Shed parapet unsupported; use zero")
    slope = fill(roof.slope_deg, 12., "roof.slope_deg") if kind == "tile_shed" else None
    _check(slope is None or 1 <= slope <= 35, "Shed slope must be 1..35 degrees")
    site = replace(theta.site, fence=fill(theta.site.fence, "none", "site.fence"), garden=fill(theta.site.garden, False, "site.garden"))
    _check(site.runs is None or site.fence == "none", "Explicit fence runs replace automatic fence kind")
    _check(site.fence in ("none", "reja", "concreto", "ladrillos", "concreto_bajo"), "Unsupported fence")
    color = fill(theta.primary_color, (.78, .78, .72), "primary_color")
    _check(all(0 <= x <= 1 for x in color), "RGB must be within 0..1")
    _check(theta.side_material in ("brick", "concrete", "plaster"), "Unsupported side material")
    _check(theta.finish in ("standard","premium"),"Unsupported finish")
    catalog={m.slot:m for m in resolve_materials(BuildingAppearance())}
    _check(len({m.slot for m in theta.materials})==len(theta.materials),"Duplicate material override")
    for mat in theta.materials:
        _check(mat.slot in catalog and mat.template in catalog,"Unknown material slot/template")
        _check(mat.color is None or all(0<=v<=1 for v in mat.color),"Invalid material color")
    theta = replace(theta, height_m=height, floors=floors, family=family, massing=m,
                    roof=replace(roof,kind=kind,parapet_m=parapet,slope_deg=slope), site=site, primary_color=color)
    return theta, completed


def _masses(p, theta):
    ctx = ParcelContext(p.parcel, explicit_fronts=p.fronts)
    parcel = Polygon(p.parcel)
    fronts = front_lines(ctx)
    m = theta.massing
    if theta.masses is not None:
        _check(len({x.role for x in theta.masses})==len(theta.masses),"Mass roles must be unique")
        result=[]
        for x in theta.masses:
            _check(x.role and '/' not in x.role,"Invalid semantic mass role")
            poly=_polygon(Polygon(x.footprint),x.role)
            _check(parcel.covers(poly),"Mass outside parcel")
            result.append(MassSpec(x.role,_ring(poly),x.levels_m[0],x.levels_m[-1],x.levels_m,x.role,None))
        for i,a in enumerate(result):
            for b in result[i+1:]:
                _check(min(a.roof_z,b.roof_z)<=max(a.base_z,b.base_z)+1e-7 or
                       Polygon(a.footprint).intersection(Polygon(b.footprint)).area<1e-7,"Interpenetrating masses")
            if a.base_z>0:
                support=unary_union([Polygon(b.footprint) for b in result if abs(b.roof_z-a.base_z)<1e-7])
                _check(support.buffer(1e-7).covers(Polygon(a.footprint)),"Unsupported floating mass")
        return tuple(sorted(result,key=lambda m:m.role))
    body = _polygon(apply_edge_setbacks(parcel, fronts, m.front_setback_m), "front setback") if m.front_setback_m else parcel
    fh = theta.height_m/theta.floors
    pattern = m.pattern
    if pattern == "single_block":
        raw = [("main", body, 0, theta.floors)]
    elif pattern == "corner_accent":
        bands=[body.difference(apply_edge_setbacks(body,[line],m.corner_reach_m+m.front_setback_m)) for line in fronts[:2]]
        corner=_polygon(bands[0].intersection(bands[1]),"corner accent")
        raw=[("main",body,0,theta.floors-1),("corner",corner,theta.floors-1,theta.floors)]
    elif pattern in ("stepped_back", "podium_tower"):
        top = _polygon(apply_edge_setbacks(body, fronts, m.upper_setback_m+m.front_setback_m), "upper setback")
        floor = theta.floors-1 if pattern == "stepped_back" else m.podium_floors
        raw = [("main" if pattern == "stepped_back" else "podium", body, 0, floor),
               ("setback" if pattern == "stepped_back" else "tower", top, floor, theta.floors)]
    else:
        rear = _polygon(apply_edge_setbacks(body, fronts, m.front_depth_m+m.front_setback_m), "rear mass")
        front = _polygon(body.difference(rear), "front mass")
        tall_front = pattern == "front_tall_rear_low"
        raw = [("front", front, 0, theta.floors if tall_front else m.low_floors),
               ("rear", rear, 0, m.low_floors if tall_front else theta.floors)]
    return tuple(MassSpec(role, _ring(poly), lo*fh, hi*fh,
                          tuple(i*fh for i in range(lo, hi+1)), role, None)
                 for role, poly, lo, hi in raw)


def _facade_controls(c, family):
    _check(c.mode in ("repeat", "explicit"), "Facade mode must be repeat or explicit")
    _check(c.cladding in ("stucco", "horizontal"), "Invalid cladding")
    if c.mode == "explicit":
        _check(c.openings is not None, "Explicit facade needs openings ([] means none)")
        _check(all(getattr(c, x) is None for x in ("bay_count", "bay_axes_m", "window_ratio", "window_height_m", "sill_m", "balconies", "balcony_depth_m", "gallery_depth_m", "awning_depth_m")), "Repeat fields inactive on explicit facade")
        for op in c.openings:
            _check(op.kind in ('window','door','gate','balcony_window'), 'Invalid opening kind')
            _check(op.prefab in ('legacy','slim_window','wood_panel','metal_gate','roller','storefront','louver'), 'Invalid opening prefab')
            _check(op.frame_width_m>0 and op.recess_m>0 and op.mullion_columns>=1 and op.mullion_rows>=1, 'Invalid frame/recess/mullions')
            _check(op.curtain==0, 'Curtain coverage belongs to xi, not explicit theta openings')
            _check(op.prefab=='legacy' or op.style=='sliding', 'style only controls legacy opening; inactive for this prefab')
        return c
    _check(c.openings is None, "openings require explicit mode")
    _check(c.bay_count is None or c.bay_axes_m is None, "bay_count and bay_axes_m are alternatives")
    rules = FAMILY_RULES[family]
    balcony = bool(rules["balcony_every"]) if c.balconies is None else c.balconies
    _check(balcony or c.balcony_depth_m is None, "balcony_depth_m inactive when balconies=false")
    _check(rules["upper"] == "gallery" or c.gallery_depth_m is None, "gallery_depth inactive for family")
    _check(rules.get("awning") or c.awning_depth_m is None, "awning_depth inactive for family")
    c = replace(c, window_ratio=c.window_ratio if c.window_ratio is not None else rules["window_ratio"],
                window_height_m=c.window_height_m if c.window_height_m is not None else rules["window_h"],
                sill_m=c.sill_m if c.sill_m is not None else rules["sill"],
                balconies=balcony, balcony_depth_m=(c.balcony_depth_m if c.balcony_depth_m is not None else .9) if balcony else None,
                gallery_depth_m=(c.gallery_depth_m if c.gallery_depth_m is not None else 1.1) if rules["upper"] == "gallery" else None,
                awning_depth_m=(c.awning_depth_m if c.awning_depth_m is not None else 1.) if rules.get("awning") else None)
    _check(.1 <= c.window_ratio <= .85 and .5 <= c.window_height_m <= 4 and 0 <= c.sill_m <= 3, "Invalid window geometry")
    _check(c.bay_count is None or 1 <= c.bay_count <= 24, "Invalid bay_count")
    _check(c.balcony_depth_m is None or .2 <= c.balcony_depth_m <= 1.2, "Balcony depth outside supported overhang")
    _check(c.gallery_depth_m is None or .2<=c.gallery_depth_m<=1.2,'Invalid gallery depth')
    _check(c.awning_depth_m is None or .2<=c.awning_depth_m<=1.2,'Invalid awning depth')
    return c


def _composition(c, family, length, levels, height, ground, top):
    if c.mode == "explicit":
        return (), c.openings, c.projections, c.material_regions
    rules = dict(FAMILY_RULES[family])
    count = c.bay_count or max(1, round((length-.64)/3.1))
    axes = c.bay_axes_m if c.bay_axes_m is not None else tuple(.32+(i+.5)*(length-.64)/count for i in range(count))
    _check(bool(axes) and tuple(sorted(set(axes))) == axes and axes[0] > .4 and axes[-1] < length-.4, "Invalid bay axes")
    pitch = min([length-.64] + [b-a for a,b in zip(axes, axes[1:])] + [2*(axes[0]-.32), 2*(length-.32-axes[-1])])
    ops = []
    for floor, (z0,z1) in enumerate(zip(levels, levels[1:])):
        for i, axis in enumerate(axes):
            kind, prefab = "window", rules["prefab"]
            width, sill, h = pitch*c.window_ratio, c.sill_m, c.window_height_m
            if ground and floor == 0 and i == 0:
                kind = "gate" if rules["ground"] == "garage" else "door"
                prefab = "roller" if kind == "gate" else "wood_panel"
                width, sill, h = min(pitch*.75, 3.2) if kind == "gate" else min(pitch*.42, 1.2), .04, min(2.3,z1-z0-.3)
            elif ground and floor == 0 and rules["ground"] == "shopfront":
                prefab, sill = "storefront", .15
            if floor > 0 and c.balconies and i % 2 == 0:
                kind, sill = "balcony_window", .18
            h = min(h, z1-z0-sill-.2)
            _check(h >= .5 and width >= .4, "Openings cannot fit: reduce bays or window dimensions")
            ops.append(Opening(kind, axis-width/2, z0+sill, width,h,
                               prefab=prefab, grille=rules["grille"],
                               balcony_depth_m=c.balcony_depth_m or .75, curtain=0))
    # Family relief is reused; its two random depths are always overwritten by
    # resolved architectural controls. This RNG never sees xi.
    projections, regions = _relief(length, levels, axes, pitch, ops, rules, height,
                                  ground, top, np.random.default_rng(0), [], DetailBudget(2))
    projections = tuple(replace(x, depth_m=c.gallery_depth_m) if x.kind == "gallery" else
                        replace(x, depth_m=c.awning_depth_m) if x.kind == "awning" else x for x in projections)
    ops = tuple(replace(x, kind="window") if x.kind == "balcony_window" else x for x in ops)
    return axes, ops, projections+c.projections, tuple(regions)+c.material_regions


def resolve_theta(context: ReconstructionContext, theta: ThetaCandidate) -> ResolvedArchitecture:
    requested=asdict(theta)
    context = _context(decode(ReconstructionContext, asdict(context)))
    theta, completed = _complete(decode(ThetaCandidate, asdict(theta)), context)
    default = _facade_controls(theta.facade, theta.family)
    overrides = {(x.mass_role,x.edge): _facade_controls(x.controls,theta.family) for x in theta.facades}
    _check(len(overrides) == len(theta.facades), "Duplicate facade override")
    theta = replace(theta, facade=default, facades=tuple(replace(x, controls=overrides[x.mass_role,x.edge]) for x in theta.facades))
    masses = _masses(context, theta)
    site = SitePlan(masses, (), (), (), ())
    exposures = calculate_mass_exposures(site)
    pctx = ParcelContext(context.parcel, explicit_fronts=context.fronts)
    fronts = front_lines(pctx)
    front_normals = [outward_normal(Polygon(context.parcel), *list(line.coords))[1] for line in fronts]
    walls, roofs, used = [], [], set()
    for mass in masses:
        ring = mass.footprint
        for edge,a in enumerate(ring):
            b = ring[(edge+1)%len(ring)]
            line = LineString([a,b])
            t,n,length = outward_normal(Polygon(ring),a,b)
            is_front = any(float(np.dot(n,normal))>.85 for normal in front_normals)
            key = (mass.role,edge)
            control = overrides.get(key, default if is_front else FacadeControls(mode="explicit",openings=()))
            for band in exposures[mass.id]["walls"]:
                segment = line.intersection(band["exposed_segments"])
                if segment.is_empty or segment.length < .1:
                    continue
                if key in overrides:
                    used.add(key)
                # Explicit edge coordinates cannot silently migrate to a shorter
                # segment. Reject partial exposure until structured interval UI.
                _check(abs(segment.length-length)<1e-5, "Partially exposed edges require a future interval schema")
                base, roof = band["z_bottom"], band["z_top"]
                levels = tuple(sorted(set([0.,roof-base]+[z-base for z in mass.floor_levels if base<z<roof])))
                has_entities=bool(control.openings or control.projections or control.material_regions or control.stairs)
                _check(control.mode != "explicit" or not has_entities or (abs(base-mass.base_z)<1e-7 and abs(roof-mass.roof_z)<1e-7), "Explicit facade crossing exposure bands is unsupported")
                axes, ops, projections, regions = _composition(control,theta.family,length,levels,roof-base,base<.01,abs(roof-mass.roof_z)<.01)
                f = FacadeSpecification(f"{mass.role}/edge{edge}/z{base:g}", a,b,length,tuple(n),levels,
                                        openings=ops,is_front=is_front or key in overrides,wall_material="plaster" if is_front else theta.side_material,
                                        projections=projections,material_regions=regions,exterior_stairs=control.stairs,
                                        services=control.services,cladding=control.cladding,ornamented=False,style=theta.finish)
                walls.append(ResolvedWall(mass.role,edge,base,roof-base,axes,f))
        area = exposures[mass.id].get("roof")
        area = area["exposed_area"] if area else Polygon()
        surfaces = []
        for part in ([area] if area.geom_type=="Polygon" else getattr(area,"geoms",())):
            if part.is_empty:
                continue
            coords = _ring(part)
            n = front_normals[0]
            anchor = min(coords,key=lambda xy: np.dot(xy,-n))
            surfaces.append(RoofSurface(coords,theta.roof.kind,mass.roof_z,theta.roof.slope_deg or 0,anchor,tuple(-n)))
        if surfaces:
            props=[]
            footprints=[]
            for prop in theta.roof.props:
                if prop.mass_role != mass.role:
                    continue
                _check(theta.roof.kind != "tile_shed", "Props on sloped surfaces not supported")
                _check(prop.kind in BUILDERS and .2<=prop.scale<=3,"Invalid roof prop kind/scale")
                shape=_prop_footprint(prop.kind,prop.xy,prop.rotation_deg,prop.scale)
                _check(area.buffer(-.55).covers(shape),"Roof prop outside free roof clearance")
                _check(all(not shape.buffer(.28).intersects(other) for other in footprints),"Roof props overlap")
                footprints.append(shape)
                props.append(RoofProp(prop.kind,prop.xy,prop.rotation_deg,prop.scale,0))
            roofs.append(RoofPlan(mass.id,tuple(surfaces),tuple(props),parapet_height_m=theta.roof.parapet_m,roof_z=mass.roof_z))
    _check(all(prop.mass_role in {r.mass_id for r in roofs} for prop in theta.roof.props),"Roof prop references absent/exhausted roof")
    _check(used == set(overrides), "Facade override refers to nonexistent mass/edge")
    program = BuildingProgram("residential","","","","standard","","",0,has_fence=theta.site.fence!="none",fence_type=theta.site.fence)
    boundaries=[]
    for b in generate_boundaries(pctx, program, site):
        _check(b.gate_u is None or b.gate_u+b.gate_width<=b.line.length, "Fence run cannot fit default gate")
        if b.kind == "concreto_bajo":
            b = replace(b,height=1.2,garage_u=None,garage_width=0.)
        boundaries.append(ResolvedBoundary(tuple(b.line.coords),b.kind,b.height,b.gate_u,b.gate_width,b.garage_u,b.garage_width,b.is_street))
    if theta.site.runs is not None:
        boundaries=[]
        built=unary_union([Polygon(m.footprint) for m in masses if m.base_z<.01])
        occupied={}
        for run in theta.site.runs:
            _check(0<=run.edge<len(context.parcel),"Fence edge out of range")
            a=np.asarray(context.parcel[run.edge]); b=np.asarray(context.parcel[(run.edge+1)%len(context.parcel)])
            length=float(np.linalg.norm(b-a)); tangent=(b-a)/length
            _check(0<=run.start_m<run.end_m<=length and .65<=run.height_m<=4,"Invalid fence extent/height")
            _check(run.kind in ("reja","concreto","ladrillos","concreto_bajo"),"Invalid explicit fence kind")
            _check(run.kind!="concreto_bajo" or (run.height_m==1.2 and run.garage_u is None),"Low fence has fixed height1.2 and no garage")
            gates=[]
            for u,w in ((run.gate_u,run.gate_width),(run.garage_u,run.garage_width)):
                _check((u is None and w==0) or (u is not None and u>=0 and w>0 and u+w<=run.end_m-run.start_m),"Invalid fence gate")
                if u is not None:
                    gates.append((u,u+w))
            _check(len(gates)<2 or gates[0][1]<=gates[1][0] or gates[1][1]<=gates[0][0],"Overlapping fence gates")
            _check(all(run.end_m<=lo or run.start_m>=hi for lo,hi in occupied.get(run.edge,[])),"Overlapping fence runs")
            occupied.setdefault(run.edge,[]).append((run.start_m,run.end_m))
            line=LineString([a+tangent*run.start_m,a+tangent*run.end_m])
            _check(line.intersection(built).length<1e-6,"Fence overlaps building")
            boundaries.append(ResolvedBoundary(tuple(line.coords),run.kind,run.height_m,run.gate_u,run.gate_width,run.garage_u,run.garage_width,run.edge in context.fronts))
    def track(old,new,path=''):
        if old is None and new is not None:
            completed.setdefault(path,'prior/completed')
        elif isinstance(old,dict) and isinstance(new,dict):
            for key in old:
                track(old[key],new[key],f'{path}.{key}' if path else key)
        elif isinstance(old,(tuple,list)) and isinstance(new,(tuple,list)):
            for i,(a,b) in enumerate(zip(old,new)):
                track(a,b,f'{path}.{i}')
    track(requested,asdict(theta))
    if theta.masses is not None:
        completed['height_m']=completed['floors']='derived/explicit_mass_levels'
    return ResolvedArchitecture("0.1",context,theta,masses,tuple(walls),tuple(roofs),tuple(boundaries),completed)


class _BandBuilder(ZOffsetMeshBuilder):
    def panel(self,a,t,n,polys,w1,w2,mat_fn,semantic,**kwargs):
        offset=self._z_offset
        lifted=[translate(p,yoff=offset) for p in polys]
        kwargs["cuts_z"]=tuple(z+offset for z in kwargs.get("cuts_z",()))
        depth=kwargs.get("depth_fn")
        if depth:
            kwargs["depth_fn"]=lambda u,v: depth(u,v-offset)
        return self._builder.panel(a,t,n,lifted,w1,w2,
            lambda kind,u,v,w: mat_fn(kind,u,v-offset,w),semantic,**kwargs)


def _rng(seed, label):
    digest=hashlib.sha256(f"{seed}:{label}".encode()).digest()
    return np.random.default_rng(int.from_bytes(digest[:8],"little"))


def generate_resolved(resolved: ResolvedArchitecture, nuisance=NuisanceParameters(), config=GrammarConfig()):
    nuisance=decode(NuisanceParameters,asdict(nuisance))
    config=decode(GrammarConfig,asdict(config))
    _check(config.implementation=="theta-candidate-v0" and config.grammar_reference=="grammar-v1.0" and config.completion_policy=="conservative-0.1", "Unsupported config version")
    _check(0<=nuisance.seed<2**63,"Invalid nuisance seed")
    p,theta=resolved.context,resolved.theta
    parcel=Polygon(p.parcel)
    materials={m.slot:m for m in resolve_materials(BuildingAppearance())}
    materials['plaster']=replace(materials['plaster'],base_color_rgb=theta.primary_color)
    materials['accent']=replace(materials['accent'],base_color_rgb=tuple(x*.72 for x in theta.primary_color))
    templates=dict(materials)
    for control in theta.materials:
        original=templates[control.template]
        materials[control.slot]=replace(original,slot=control.slot,base_color_rgb=control.color or original.base_color_rgb)
    appearance=BuildingAppearance(tuple(materials.values()))
    builder=MeshBuilder(parcel,appearance,envelope=street_envelope(ParcelContext(p.parcel,explicit_fronts=p.fronts)),budget=DetailBudget(config.detail))
    entrances=[]
    for wall in resolved.walls:
        f=wall.facade
        ops=tuple(replace(op,curtain=float(_rng(nuisance.seed,f"{f.edge_id}/curtain/{i}").uniform(.15,.55)))
                  if nuisance.curtains and op.kind=="window" and op.prefab in ("slim_window","storefront","legacy") else op
                  for i,op in enumerate(f.openings))
        facade(_BandBuilder(builder,wall.base_z),replace(f,openings=ops),wall.height_m)
        a,b=np.asarray(f.vertex_a),np.asarray(f.vertex_b)
        t=(b-a)/f.width_m
        for op in f.openings:
            if wall.base_z<.01 and op.kind in ("door","gate") and op.v_m<.6:
                entrances.append(dict(origin=a+t*op.u_m,tangent=t,normal=np.asarray(f.normal_xy),width=op.width_m,base_z=op.v_m))
    for roof in resolved.roofs:
        props=tuple(replace(prop,seed=int(_rng(nuisance.seed,f"roof/{roof.mass_id}/{prop.kind}/{prop.position}").integers(0,2**31))) for prop in roof.props)
        build_roof(builder,replace(roof,props=props),_rng(nuisance.seed,"roof/"+roof.mass_id))
    boundaries=[]
    styles={"reja":("plaster","reja"),"ladrillos":("brick","solid"),"concreto":("plaster","solid"),"concreto_bajo":("plaster","low")}
    for i,record in enumerate(resolved.boundaries):
        boundary=BoundarySpec(**{**asdict(record),"line":LineString(record.line)})
        boundaries.append(boundary)
        a,b=record.line[0],record.line[-1]
        t,n,length=outward_normal(parcel,a,b)
        material,style=styles.get(record.kind,("brick","wall"))
        with builder.assembly(f"site/fence/{i}"):
            draw_fence(builder,np.asarray(a),t,n,length,boundary,_rng(nuisance.seed,"fence"),material,style)
    for i,entry in enumerate(entrances):
        with builder.assembly(f"site/entrance/{i}"):
            entrance_step(builder,entry,_rng(nuisance.seed,"entry"))
    if theta.site.garden:
        built=unary_union([Polygon(m.footprint) for m in resolved.masses])
        plant_garden(builder,parcel,built,boundaries,entrances,_rng(nuisance.seed,"garden"))
    return builder.finish()


def generate_from_theta(context, theta, nuisance=NuisanceParameters(), config=GrammarConfig()):
    return generate_resolved(resolve_theta(context,theta),nuisance,config)
