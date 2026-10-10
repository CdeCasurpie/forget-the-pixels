"""Resolve architectural decisions first; only then emit geometry.

The legacy V4 entry point is deliberately not called: it discards explicit
facades and replans roofs. This adapter shares its geometry primitives instead.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace, field, fields
import hashlib
import json
import re
import shapely
import numpy as np
from shapely.geometry import Polygon, LineString, Point, box as rect
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
from modeling.assembly import (compose_masses, mass_polygon, ring as assembly_ring,
    holes, resolve_supports, resolve_zones, StructuralPiece, ResolvedSiteZone, region_frame)
from modeling.exposure import wall_domains
from modeling.visibility import VisibleFacadeBuilder, patch_domains


@dataclass(frozen=True)
class ResolvedWall:
    mass_role: str
    edge: int
    base_z: float
    height_m: float
    axes_m: tuple[float, ...]
    facade: FacadeSpecification
    visible_domains: tuple[tuple[float,float,float,float], ...] = ()


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
    completion_details: dict[str, dict] = field(default_factory=dict)
    structures: tuple[StructuralPiece, ...] = ()
    site_zones: tuple[ResolvedSiteZone, ...] = ()


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
    requested_height = theta.height_m
    def fill(value, default, path):
        if value is None:
            completed[path] = "prior/completed"
            return default
        return value
    _check(theta.schema_version in ("0.1", "0.2", "0.3"), "Unsupported theta schema")
    if theta.massing.components:
        _check(theta.masses is None, "components replace explicit masses")
        _check(theta.schema_version=="0.3", "components require schema_version=0.3")
        _check(all(len(c.levels_m)>=2 for c in theta.massing.components), "Invalid component levels")
        height=max(c.levels_m[-1] for c in theta.massing.components)
        _check(theta.height_m is None or abs(theta.height_m-height)<1e-7, "height conflicts with component levels")
        floors=max(len(c.levels_m)-1 for c in theta.massing.components)
        _check(theta.floors is None or theta.floors==floors,"floors conflict with component levels")
        theta=replace(theta,height_m=height,floors=floors)
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
    _check(p.locked_height_m is None or p.locked_height_m > 0, "Locked height must be positive")
    prior_height = (theta.floors * 2.8 if theta.floors is not None else 8.4)
    height = fill(theta.height_m, p.locked_height_m if p.locked_height_m is not None else prior_height, "height_m")
    if p.locked_height_m is not None:
        _check(abs(height-p.locked_height_m) < 1e-8, "theta height conflicts with externally locked height")
        completed["height_m"] = "external" if theta.masses is None and requested_height is None else "external/matched"
    floors = fill(theta.floors, max(1, round(height/2.8)), "floors")
    _check(1 <= floors <= 60 and (theta.masses is not None or theta.massing.components or 2.2 <= height/floors <= 6), "Invalid floors/height (storeys must be 2.2..6m)")
    family = fill(theta.family, "quiet_house", "family")
    _check(family in FAMILY_RULES, "Unknown architectural family")
    m = theta.massing
    pattern = fill(m.pattern, "composition" if m.components else "single_block", "massing.pattern")
    _check(pattern in ("single_block", "stepped_back", "podium_tower", "front_tall_rear_low", "front_low_rear_tall", "corner_accent", "explicit", "composition"), "Unsupported massing pattern")
    _check((pattern=="composition")==bool(m.components), "composition needs components exclusively")
    _check(m.components or m.parcel_tolerance_m==0., "parcel_tolerance_m requires composition")
    _check(not m.components or m.front_setback_m in (None,0.), "Use component regions for setbacks")
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
    _check(kind in ("flat", "corrugated", "tile_shed", "gable"), "Unsupported roof")
    _check(kind in ("tile_shed","gable") or roof.slope_deg is None, "slope_deg inactive for flat/corrugated roof")
    parapet = fill(roof.parapet_m, 0. if kind in ("tile_shed","gable") else .5, "roof.parapet_m")
    _check(0 <= parapet <= 2 and (kind not in ("tile_shed","gable") or parapet == 0), "Sloped parapet unsupported; use zero")
    slope = fill(roof.slope_deg, 12., "roof.slope_deg") if kind in ("tile_shed","gable") else None
    _check(slope is None or 1 <= slope <= 35, "Shed slope must be 1..35 degrees")
    site = replace(theta.site, fence=fill(theta.site.fence, "none", "site.fence"), garden=fill(theta.site.garden, False, "site.garden"))
    _check(site.runs is None or site.fence == "none", "Explicit fence runs replace automatic fence kind")
    _check(site.fence in ("none", "reja", "concreto", "ladrillos", "concreto_bajo"), "Unsupported fence")
    color = fill(theta.primary_color, (.78, .78, .72), "primary_color")
    _check(all(0 <= x <= 1 for x in color), "RGB must be within 0..1")
    side_material = fill(theta.side_material, "brick", "side_material")
    finish = fill(theta.finish, "standard", "finish")
    _check(side_material in ("brick", "concrete", "plaster"), "Unsupported side material")
    _check(finish in ("standard","premium"),"Unsupported finish")
    catalog={m.slot:m for m in resolve_materials(BuildingAppearance())}
    _check(len({m.slot for m in theta.materials})==len(theta.materials),"Duplicate material override")
    for mat in theta.materials:
        _check(mat.slot in catalog and mat.template in catalog,"Unknown material slot/template")
        _check(mat.color is None or all(0<=v<=1 for v in mat.color),"Invalid material color")
    theta = replace(theta, height_m=height, floors=floors, family=family, massing=m,
                    roof=replace(roof,kind=kind,parapet_m=parapet,slope_deg=slope,
                                 props=fill(roof.props,(),"roof.props")), site=site, primary_color=color,
                    side_material=side_material, finish=finish, schema_version="0.3" if theta.schema_version=="0.3" else "0.2")
    return theta, completed


def _masses(p, theta):
    ctx = ParcelContext(p.parcel, explicit_fronts=p.fronts)
    parcel = Polygon(p.parcel)
    fronts = front_lines(ctx)
    m = theta.massing
    if m.components:
        return compose_masses(p,m)
    if theta.masses is not None:
        result=[]
        for x in theta.masses:
            _check(bool(re.fullmatch(r'[a-z][a-z0-9_]*',x.role)),"Invalid semantic mass role")
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
        return _canonical_masses(result)
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
    return _canonical_masses(tuple(MassSpec(role, _ring(poly), lo*fh, hi*fh,
                          tuple(i*fh for i in range(lo, hi+1)), role, None)
                 for role, poly, lo, hi in raw))


def _canonical_masses(masses):
    """Role-local indices ordered by metric geometry, independent of JSON order."""
    def key(m):
        poly=Polygon(m.footprint)
        return (m.role, round(poly.centroid.x, 6), round(poly.centroid.y, 6),
                round(m.base_z, 6), round(poly.area, 6), tuple(m.footprint), m.floor_levels)
    ordered=sorted(masses,key=key)
    counts={}
    output=[]
    for mass in ordered:
        index=counts.get(mass.role,0)
        counts[mass.role]=index+1
        output.append(replace(mass,id=f"{mass.role}:{index}"))
    return tuple(output)


def _mass_ref(value, masses):
    ids={m.id for m in masses}
    if value in ids:
        return value
    matches=[m.id for m in masses if m.role==value]
    _check(len(matches)==1, f"Mass reference {value!r} missing or ambiguous; use role:index")
    return matches[0]


def _facade_controls(c, family):
    _check(c.mode in ("repeat", "explicit"), "Facade mode must be repeat or explicit")
    c=replace(c, cladding=c.cladding if c.cladding is not None else "stucco",
              services=c.services if c.services is not None else False,
              stairs=c.stairs if c.stairs is not None else (),
              opening_edits=c.opening_edits if c.opening_edits is not None else (),
              added_openings=c.added_openings if c.added_openings is not None else ())
    _check(c.cladding in ("stucco", "horizontal"), "Invalid cladding")
    if c.mode == "explicit":
        _check(c.openings is not None, "Explicit facade needs openings ([] means none)")
        _check(not c.opening_edits and not c.added_openings,"Sparse edits belong to repeat mode")
        _check(all(getattr(c, x) is None for x in ("bay_count", "bay_axes_m", "window_ratio", "window_height_m", "sill_m", "balconies", "balcony_depth_m", "gallery_depth_m", "awning_depth_m")), "Repeat fields inactive on explicit facade")
        for op in c.openings:
            _check(op.kind in ('window','door','gate','balcony_window'), 'Invalid opening kind')
            _check(op.prefab in ('legacy','slim_window','wood_panel','metal_gate','roller','storefront','louver','open','screen'), 'Invalid opening prefab')
            _check(op.frame_width_m>0 and op.recess_m>0 and op.mullion_columns>=1 and op.mullion_rows>=1, 'Invalid frame/recess/mullions')
            _check(op.curtain==0, 'Curtain coverage belongs to xi, not explicit theta openings')
            _check(op.prefab=='legacy' or op.style=='sliding', 'style only controls legacy opening; inactive for this prefab')
        return c
    _check(c.openings is None, "openings require explicit mode")
    _check(len({(e.floor,e.bay) for e in c.opening_edits})==len(c.opening_edits),"Duplicate sparse opening edit")
    for edit in c.opening_edits:
        _check(edit.floor>=0 and edit.bay>=0 and edit.action in ("suppress","replace"),"Invalid sparse opening edit")
        _check((edit.action=="replace")==(edit.opening is not None),"Replace needs one opening; suppress needs none")
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


def _facade_override_controls(local, global_controls, family):
    if local.mode == 'explicit':
        return _facade_controls(local,family)
    template=global_controls if global_controls.mode=='repeat' else _facade_controls(FacadeControls(),family)
    patch={field_.name:getattr(local,field_.name) for field_ in fields(FacadeControls)
           if field_.name!='mode' and getattr(local,field_.name) is not None}
    if 'bay_count' in patch:
        patch['bay_axes_m']=None
    if 'bay_axes_m' in patch:
        patch['bay_count']=None
    if patch.get('balconies') is False:
        patch['balcony_depth_m']=None
    return _facade_controls(replace(template,**patch),family)


def _composition(c, family, length, levels, height, ground, top, floor_indices=None):
    if c.mode == "explicit":
        return (), c.openings, c.projections or (), c.material_regions or ()
    rules = dict(FAMILY_RULES[family])
    count = c.bay_count or max(1, round((length-.64)/3.1))
    axes = c.bay_axes_m if c.bay_axes_m is not None else tuple(.32+(i+.5)*(length-.64)/count for i in range(count))
    _check(bool(axes) and tuple(sorted(set(axes))) == axes and axes[0] > .4 and axes[-1] < length-.4, "Invalid bay axes")
    pitch = min([length-.64] + [b-a for a,b in zip(axes, axes[1:])] + [2*(axes[0]-.32), 2*(length-.32-axes[-1])])
    ops = []
    found=set()
    edits={(e.floor,e.bay):e for e in c.opening_edits}
    for local_floor, (z0,z1) in enumerate(zip(levels, levels[1:])):
        floor=local_floor if floor_indices is None else floor_indices[local_floor]
        for i, axis in enumerate(axes):
            kind, prefab = "window", rules["prefab"]
            width, sill, h = pitch*c.window_ratio, c.sill_m, c.window_height_m
            if ground and local_floor == 0 and i == 0:
                kind = "gate" if rules["ground"] == "garage" else "door"
                prefab = "roller" if kind == "gate" else "wood_panel"
                width, sill, h = min(pitch*.75, 3.2) if kind == "gate" else min(pitch*.42, 1.2), .04, min(2.3,z1-z0-.3)
            elif ground and local_floor == 0 and rules["ground"] == "shopfront":
                prefab, sill = "storefront", .15
            if floor > 0 and c.balconies and i % 2 == 0:
                kind, sill = "balcony_window", .18
            h = min(h, z1-z0-sill-.2)
            _check(h >= .5 and width >= .4, "Openings cannot fit: reduce bays or window dimensions")
            opening=Opening(kind, axis-width/2, z0+sill, width,h,
                               prefab=prefab, grille=rules["grille"],
                               balcony_depth_m=c.balcony_depth_m or .75, curtain=0)
            key=(floor,i)
            found.add(key)
            edit=edits.get(key)
            if edit is None:
                ops.append(opening)
            elif edit.action=="replace":
                ops.append(edit.opening)
    _check(set(edits)<=found,"Sparse edit targets nonexistent floor/bay")
    ops.extend(c.added_openings)
    rectangles=[]
    for op in ops:
        _check(op.u_m>=.12 and op.v_m>=0 and op.width_m>0 and op.height_m>0 and
               op.u_m+op.width_m<=length-.12 and op.v_m+op.height_m<=height-.1,
               "Opening edit/add outside facade")
        shape=rect(op.u_m,op.v_m,op.u_m+op.width_m,op.v_m+op.height_m)
        _check(all(shape.intersection(other).area<1e-8 for other in rectangles),"Opening edit/add overlaps another opening")
        rectangles.append(shape)
    # Family relief is reused; its two random depths are always overwritten by
    # resolved architectural controls. This RNG never sees xi.
    projections, regions = _relief(length, levels, axes, pitch, ops, rules, height,
                                  ground, top, np.random.default_rng(0), [], DetailBudget(2))
    projections = tuple(replace(x, depth_m=c.gallery_depth_m) if x.kind == "gallery" else
                        replace(x, depth_m=c.awning_depth_m) if x.kind == "awning" else x for x in projections)
    ops = tuple(replace(x, kind="window") if x.kind == "balcony_window" else x for x in ops)
    return axes, ops, projections if c.projections is None else c.projections, tuple(regions) if c.material_regions is None else c.material_regions


def _validate_facade_zones(component, family):
    """Validate before exposure, including zones on completely hidden faces."""
    height=component.levels_m[-1]-component.levels_m[0]
    previous=[]
    _check(not component.zones or component.kind=='enclosed', 'Facade zones require an enclosed component')
    for zone in component.zones:
        label=f'Facade zone {component.id}/{zone.role or zone.face}'
        _check(zone.face in ('all','front','back','left','right'), label+': invalid face')
        _check(0<=zone.u[0]<zone.u[1]<=1, label+': invalid u (expected 0 <= u0 < u1 <= 1)')
        low,high=zone.z_m if zone.z_m is not None else (0.,height)
        _check(0<=low<high<=height, label+': invalid z_m (outside component height)')
        shape=rect(zone.u[0],low,zone.u[1],high)
        for other,area in previous:
            if zone.face==other.face or 'all' in (zone.face,other.face):
                _check(shape.intersection(area).area==0, label+': overlapping facade zones')
        previous.append((zone,shape))
        _facade_controls(zone.controls,family)


def _facade_zone_wall(zone, index, mass, edge, a, b, normal, length, domains, theta, is_front):
    """Compose once locally, then translate entities to the original wall chart."""
    height=mass.roof_z-mass.base_z
    low,high=zone.z_m if zone.z_m is not None else (0.,height)
    start,end=(u*length for u in zone.u)
    width=end-start
    control=_facade_controls(zone.controls,theta.family)
    _check(control.mode!='repeat' or width>=1.5, 'Facade zone too narrow for repeat; use explicit controls')
    base=mass.base_z+low
    roof=mass.base_z+high
    levels=tuple(sorted({0.,high-low,*[z-base for z in mass.floor_levels if base<z<roof]}))
    # A horizontal neighbour never changes this zone's floor/bay indexing.
    # A vertical zone retains the original component floor numbers for edits
    # and upper-storey rules, even when its first local level is zero.
    floor_indices=tuple(next(i for i,(lo,hi) in enumerate(zip(mass.floor_levels,mass.floor_levels[1:]))
                             if lo<=base+(z0+z1)/2<hi) for z0,z1 in zip(levels,levels[1:]))
    axes,ops,projections,regions=_composition(control,theta.family,width,levels,high-low,
                                             base<.01,abs(roof-mass.roof_z)<.01,floor_indices)
    # User entities belong to their zone, not merely somewhere on the wall.
    # Generated relief may have small prefab overhangs; the domain clips them.
    for entities in (ops, control.projections or (), control.material_regions or ()):
        for entity in entities:
            _check(entity.width_m>0 and entity.height_m>0 and entity.u_m>=0 and entity.v_m>=0 and
                   entity.u_m+entity.width_m<=width+1e-8 and entity.v_m+entity.height_m<=high-low+1e-8,
                   'Facade zone entity outside local bounds')
    for stair in control.stairs:
        _check(0<=stair.u_m and stair.u_m+stair.flight_width_m<=width and
               0<=stair.base_z_m<stair.target_z_m<=high-low, 'Facade zone stair outside local bounds')
    def shifted(entities):
        return tuple(replace(x,u_m=x.u_m+start,v_m=x.v_m+low) for x in entities)
    stairs=tuple(replace(s,u_m=s.u_m+start,base_z_m=s.base_z_m+low,target_z_m=s.target_z_m+low)
                 for s in control.stairs)
    f=FacadeSpecification(f'{mass.id}/edge{edge}/zone{index}',a,b,length,tuple(normal),
                          tuple(z-mass.base_z for z in mass.floor_levels),
                          openings=shifted(ops),projections=shifted(projections),material_regions=shifted(regions),
                          exterior_stairs=stairs,is_front=is_front,program_enabled=True,wall_material='plaster',
                          services=control.services,cladding=control.cladding,ornamented=False,style=theta.finish)
    visible=patch_domains(domains,(start,low,end,high))
    return ResolvedWall(mass.id,edge,mass.base_z,height,tuple(x+start for x in axes),f,visible)


def resolve_theta(context: ReconstructionContext, theta: ThetaCandidate) -> ResolvedArchitecture:
    requested=asdict(theta)
    context = _context(decode(ReconstructionContext, asdict(context)))
    theta, completed = _complete(decode(ThetaCandidate, asdict(theta)), context)
    for component in theta.massing.components:
        _validate_facade_zones(component,theta.family)
    masses = _masses(context, theta)
    if theta.masses is not None:
        theta=replace(theta,masses=tuple(ArchitecturalMass(m.role,m.footprint,m.floor_levels) for m in masses))
    default = _facade_controls(theta.facade, theta.family)
    facade_refs = tuple(replace(x,mass_role=_mass_ref(x.mass_role,masses),
                                controls=_facade_override_controls(x.controls,default,theta.family)) for x in theta.facades)
    overrides = {(x.mass_role,x.edge): x.controls for x in facade_refs}
    _check(len(overrides) == len(facade_refs), "Duplicate facade override")
    roof_refs = tuple(replace(x,mass_ref=_mass_ref(x.mass_ref,masses)) for x in theta.roofs)
    roof_overrides = {x.mass_ref:x for x in roof_refs}
    _check(len(roof_overrides)==len(roof_refs),"Duplicate roof override")
    props=tuple(replace(x,mass_role=_mass_ref(x.mass_role,masses)) for x in theta.roof.props)
    theta = replace(theta, facade=default,
                    facades=tuple(sorted(facade_refs,key=lambda x:(x.mass_role,x.edge))),
                    roofs=tuple(sorted(roof_refs,key=lambda x:x.mass_ref)),
                    roof=replace(theta.roof,props=props))
    site = SitePlan(masses, (), (), (), ())
    exposures = calculate_mass_exposures(site)
    pctx = ParcelContext(context.parcel, explicit_fronts=context.fronts)
    fronts = front_lines(pctx)
    front_normals = [outward_normal(Polygon(context.parcel), *list(line.coords))[1] for line in fronts]
    walls, roofs, used = [], [], set()
    for mass in masses:
        component=next((c for c in theta.massing.components if c.id==mass.role),None)
        rings=(mass.footprint,)+mass.footprint_holes
        edges=[(a,r[(i+1)%len(r)]) for r in rings for i,a in enumerate(r)]
        for edge,(a,b) in enumerate(edges):
            if mass.kind=='open':
                continue
            line = LineString([a,b])
            length=line.length
            t=(np.asarray(b)-a)/length
            n=np.array([t[1],-t[0]])
            is_front = any(float(np.dot(n,normal))>.85 for normal in front_normals)
            key = (mass.id,edge)
            control = overrides.get(key, default if is_front else _facade_controls(FacadeControls(mode="explicit",openings=()),theta.family))
            domains=wall_domains(mass,masses,a,b)
            selected_zones=[]
            if component:
                _,ct,cn,_=region_frame(context,component.region)
                face=max((('front',-cn),('back',cn),('left',-ct),('right',ct)),key=lambda x:np.dot(n,x[1]))[0]
                selected_zones=[(i,z) for i,z in enumerate(component.zones) if z.face in ('all',face)]
            # Resolve even hidden zones: bad local coordinates must not depend
            # on the presence or height of an adjacent mass.
            zone_walls=[_facade_zone_wall(z,i,mass,edge,a,b,n,length,domains,theta,is_front) for i,z in selected_zones]
            if not domains:
                continue
            if key in overrides:
                used.add(key)
            # Compose in the original edge chart. Exposure clips geometry only;
            # it must never relocate a door or restart a floor/bay sequence.
            programs=[(0.,mass.roof_z-mass.base_z,control)]
            if component and key not in overrides:
                blind=FacadeControls(mode='explicit',openings=())
                control=_facade_controls(component.facade or blind,theta.family)
                selected=[f for f in component.faces if f.face in ('all',face)]
                _check(all(f.face in ('all','front','back','left','right') for f in component.faces),'Invalid component face')
                cuts={0.,mass.roof_z-mass.base_z}
                for f in selected:
                    if f.z_m:
                        _check(0<=f.z_m[0]<f.z_m[1]<=mass.roof_z-mass.base_z,'Invalid face band')
                        cuts.update(f.z_m)
                programs=[]
                zs=sorted(cuts)
                for low,high in zip(zs,zs[1:]):
                    active=[f for f in selected if f.z_m is None or f.z_m[0]<=low and f.z_m[1]>=high]
                    local=_facade_controls(active[-1].controls,theta.family) if active else control
                    programs.append((low,high,local))
            # Explicit body/edge programs can dress non-street-facing walls.
            program_enabled=is_front or component is not None or key in overrides
            for low,high,control in programs:
                visible=tuple((u0,max(z0,low)-low,u1,min(z1,high)-low) for u0,z0,u1,z1 in domains if min(z1,high)>max(z0,low)+1e-7)
                if selected_zones:
                    excluded=tuple((z.u[0]*length,(z.z_m or (0.,mass.roof_z-mass.base_z))[0]-low,
                                    z.u[1]*length,(z.z_m or (0.,mass.roof_z-mass.base_z))[1]-low)
                                   for _,z in selected_zones)
                    visible=patch_domains(visible,(0.,0.,length,high-low),excluded)
                if not visible:
                    continue
                base,roof=mass.base_z+low,mass.base_z+high
                levels = tuple(sorted(set([0.,roof-base]+[z-base for z in mass.floor_levels if base<z<roof])))
                if length<1.5 and control.mode=='repeat':
                    control=_facade_controls(FacadeControls(mode='explicit',openings=()),theta.family)
                axes, ops, projections, regions = _composition(control,theta.family,length,levels,roof-base,base<.01,abs(roof-mass.roof_z)<.01)
                f = FacadeSpecification(f"{mass.id}/edge{edge}/z{base:g}", a,b,length,tuple(n),levels,
                                        openings=ops,is_front=is_front,program_enabled=program_enabled,
                                        wall_material="plaster" if is_front or component and key not in overrides else theta.side_material,
                                        projections=projections,material_regions=regions,exterior_stairs=control.stairs,
                                        services=control.services,cladding=control.cladding,ornamented=False,style=theta.finish)
                walls.append(ResolvedWall(mass.id,edge,base,roof-base,axes,f,visible))
            walls.extend(w for w in zone_walls if w.visible_domains)
        area = exposures[mass.id].get("roof")
        area = area["exposed_area"] if area else Polygon()
        surfaces = []
        for part in ([area] if area.geom_type=="Polygon" else getattr(area,"geoms",())):
            if part.is_empty:
                continue
            coords = assembly_ring(part)
            n = front_normals[0]
            anchor = min(coords,key=lambda xy: np.dot(xy,-n))
            surfaces.append(RoofSurface(coords,theta.roof.kind,mass.roof_z,theta.roof.slope_deg or 0,anchor,tuple(-n),holes=holes(part)))
        if surfaces:
            override=roof_overrides.get(mass.id)
            if component and component.roof and not override:
                override=RoofOverride(mass.id,component.roof.kind,component.roof.parapet_m,component.roof.slope_deg)
            selected_kind=override.kind if override and override.kind is not None else theta.roof.kind
            _check(selected_kind in ("flat","corrugated","tile_shed","gable"),"Invalid per-mass roof kind")
            selected_parapet=(override.parapet_m if override and override.parapet_m is not None else
                              0. if mass.kind=='open' or override and override.kind in ("tile_shed","gable") else theta.roof.parapet_m)
            selected_slope=(override.slope_deg if override and override.slope_deg is not None else
                             theta.roof.slope_deg if selected_kind==theta.roof.kind else 12.) if selected_kind in ("tile_shed","gable") else None
            selected_slope=selected_slope or (12. if selected_kind in ('tile_shed','gable') else None)
            _check(not override or selected_kind in ("tile_shed","gable") or override.slope_deg is None,"Inactive per-mass slope")
            _check(0<=selected_parapet<=2 and (selected_kind not in ("tile_shed","gable") or selected_parapet==0),"Invalid per-mass parapet")
            _check(selected_slope is None or 1<=selected_slope<=35,"Invalid per-mass slope")
            surfaces=[replace(s,kind=selected_kind,slope_deg=selected_slope or 0.,thickness_m=component.slab_m if component else s.thickness_m) for s in surfaces]
            if component and selected_kind in ('gable','tile_shed'):
                _,ct,cn,_=region_frame(context,component.region)
                direction=ct if selected_kind=='gable' else cn
                surfaces=[replace(s,inward_normal=tuple(direction),eave_point=min(s.polygon,key=lambda xy:np.dot(xy,direction))) for s in surfaces]
            if selected_kind=='gable':
                from modeling.roofscape import gable_surfaces
                surfaces=[patch for s in surfaces for patch in gable_surfaces(s)]
            props=[]
            footprints=[]
            for prop in theta.roof.props:
                if prop.mass_role != mass.id:
                    continue
                _check(selected_kind != "tile_shed", "Props on sloped surfaces not supported")
                _check(prop.kind in BUILDERS and .2<=prop.scale<=3,"Invalid roof prop kind/scale")
                shape=_prop_footprint(prop.kind,prop.xy,prop.rotation_deg,prop.scale)
                _check(area.buffer(-.55).covers(shape),"Roof prop outside free roof clearance")
                _check(all(not shape.buffer(.28).intersects(other) for other in footprints),"Roof props overlap")
                footprints.append(shape)
                props.append(RoofProp(prop.kind,prop.xy,prop.rotation_deg,prop.scale,0))
            roofs.append(RoofPlan(mass.id,tuple(surfaces),tuple(props),parapet_height_m=selected_parapet,roof_z=mass.roof_z))
    _check(all(prop.mass_role in {r.mass_id for r in roofs} for prop in theta.roof.props),"Roof prop references absent/exhausted roof")
    _check(all(ref in {r.mass_id for r in roofs} for ref in roof_overrides),"Roof override references mass without exposed roof")
    _check(used == set(overrides), "Facade override refers to nonexistent mass/edge")
    theta=replace(theta,roofs=tuple(RoofOverride(ref,
                  next(plan.surfaces[0].kind for plan in roofs if plan.mass_id==ref),
                  next(plan.parapet_height_m for plan in roofs if plan.mass_id==ref),
                  next(plan.surfaces[0].slope_deg for plan in roofs if plan.mass_id==ref)
                  if next(plan.surfaces[0].kind for plan in roofs if plan.mass_id==ref)=="tile_shed" else None)
                  for ref in sorted(roof_overrides)))
    program = BuildingProgram("residential","","","","standard","","",0,has_fence=theta.site.fence!="none",fence_type=theta.site.fence)
    boundaries=[]
    for b in generate_boundaries(pctx, program, site):
        _check(b.gate_u is None or b.gate_u+b.gate_width<=b.line.length, "Fence run cannot fit default gate")
        if b.kind == "concreto_bajo":
            b = replace(b,height=1.2,garage_u=None,garage_width=0.)
        boundaries.append(ResolvedBoundary(tuple(b.line.coords),b.kind,b.height,b.gate_u,b.gate_width,b.garage_u,b.garage_width,b.is_street))
    if theta.site.runs is not None:
        boundaries=[]
        built=unary_union([mass_polygon(m) for m in masses if m.base_z<.01 and m.kind=='enclosed'])
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
                if not path and key in ('facades','roofs','masses'):
                    continue
                track(old[key],new[key],f'{path}.{key}' if path else key)
        elif isinstance(old,(tuple,list)) and isinstance(new,(tuple,list)):
            for i,(a,b) in enumerate(zip(old,new)):
                track(a,b,f'{path}.{i}')
    track(requested,asdict(theta))
    if theta.masses is not None:
        completed['height_m']=completed['floors']='derived/explicit_mass_levels'
    elif theta.massing.components:
        completed['height_m']=completed['floors']='derived/component_levels'
    detailed={}
    values=asdict(theta)
    for path,source in completed.items():
        value=values
        try:
            for part in path.split('.'):
                value=value[int(part)] if isinstance(value,(tuple,list)) else value[part]
        except (KeyError,IndexError,ValueError,TypeError):
            continue
        detailed[path]={"value":value,"source":source,"policy":"conservative-0.2" if source=="prior/completed" else None}
    for override in theta.roofs:
        original=next(x for x in requested['roofs'] if _mass_ref(x['mass_ref'],masses)==override.mass_ref)
        for name in ('kind','parapet_m','slope_deg'):
            value=getattr(override,name)
            if original[name] is None and value is not None:
                path=f'roofs[{override.mass_ref}].{name}'
                completed[path]='prior/completed'
                detailed[path]={"value":value,"source":"prior/completed","policy":"conservative-0.2"}
    for override in theta.facades:
        original=next(x for x in requested['facades'] if _mass_ref(x['mass_role'],masses)==override.mass_role and x['edge']==override.edge)
        for name,value in asdict(override.controls).items():
            if original['controls'].get(name) is None and value is not None:
                path=f'facades[{override.mass_role},edge:{override.edge}].controls.{name}'
                source='inherited/global' if override.controls.mode=='repeat' and default.mode=='repeat' and value==asdict(default)[name] else 'prior/completed'
                completed[path]=source
                detailed[path]={"value":value,"source":source,"policy":"global facade" if source=='inherited/global' else 'conservative-0.2'}
    for field_name in ('projections','material_regions'):
        if requested['facade'][field_name] is None:
            path=f'facade.{field_name}'
            completed[path]='derived/family'
            detailed[path]={"value":{wall.facade.edge_id:[asdict(entity) for entity in getattr(wall.facade,field_name)]
                                      for wall in walls if wall.facade.has_program},
                            "source":"derived/family","policy":"FAMILY_RULES"}
    for override in theta.facades:
        original=next(x for x in requested['facades'] if _mass_ref(x['mass_role'],masses)==override.mass_role and x['edge']==override.edge)
        for field_name in ('projections','material_regions'):
            if original['controls'][field_name] is None:
                path=f'facades[{override.mass_role},edge:{override.edge}].controls.{field_name}'
                completed[path]='derived/family' if override.controls.mode=='repeat' else 'prior/completed'
                detailed[path]={"value":{wall.facade.edge_id:[asdict(entity) for entity in getattr(wall.facade,field_name)]
                                          for wall in walls if wall.mass_role==override.mass_role and wall.edge==override.edge},
                                "source":completed[path],"policy":"FAMILY_RULES" if override.controls.mode=='repeat' else 'conservative-0.2'}
    structures=resolve_supports(context,theta.massing,masses) if theta.massing.components else ()
    if theta.massing.components:
        masses=tuple(replace(m,support_ids=tuple(sorted(
            [s.id for s in structures if s.mass_id==m.id and s.semantic=='support_column']+
            [b.id for b in masses if m.base_z>0 and abs(b.roof_z-m.base_z)<1e-6 and mass_polygon(b).intersection(mass_polygon(m)).area>1e-6]
        ))) for m in masses)
    zones=resolve_zones(context,theta.site,masses,structures) if theta.schema_version=='0.3' or theta.site.zones else ()
    return ResolvedArchitecture(theta.schema_version,context,theta,masses,tuple(walls),tuple(roofs),tuple(boundaries),completed,detailed,structures,zones)


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
    _check(config.implementation=="theta-candidate-v0" and config.grammar_reference=="grammar-v1.0" and config.completion_policy in ("conservative-0.1","conservative-0.2"), "Unsupported config version")
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
    tolerance=theta.massing.parcel_tolerance_m
    builder=MeshBuilder(parcel.buffer(tolerance,join_style=2) if tolerance else parcel,appearance,envelope=street_envelope(ParcelContext(p.parcel,explicit_fronts=p.fronts)).buffer(tolerance),budget=DetailBudget(config.detail))
    entrances=[]
    zoned_edges={(w.mass_role,w.edge) for w in resolved.walls if '/zone' in w.facade.edge_id}
    for wall in resolved.walls:
        f=wall.facade
        ops=tuple(replace(op,curtain=float(_rng(nuisance.seed,f"{f.edge_id}/curtain/{i}").uniform(.15,.55)))
                  if nuisance.curtains and op.kind=="window" and op.prefab in ("slim_window","storefront","legacy") else op
                  for i,op in enumerate(f.openings))
        local=_BandBuilder(builder,wall.base_z)
        if wall.visible_domains and wall.visible_domains!=((0.,0.,f.width_m,wall.height_m),):
            local=VisibleFacadeBuilder(local,f.vertex_a,(np.asarray(f.vertex_b)-f.vertex_a)/f.width_m,wall.visible_domains)
        facade(local,replace(f,openings=ops),wall.height_m)
        a,b=np.asarray(f.vertex_a),np.asarray(f.vertex_b)
        t=(b-a)/f.width_m
        for op in f.openings:
            if wall.base_z<.01 and op.kind in ("door","gate") and op.v_m<.6:
                spans=[(op.u_m,op.width_m)]
                if (wall.mass_role,wall.edge) in zoned_edges:
                    spans=[(max(op.u_m,u0),min(op.u_m+op.width_m,u1)-max(op.u_m,u0))
                           for u0,z0,u1,z1 in wall.visible_domains if z0<=op.v_m<z1]
                for lo,width in spans:
                    if width>1e-7:
                        entrances.append(dict(origin=a+t*lo,tangent=t,normal=np.asarray(f.normal_xy),width=width,base_z=op.v_m))
    for piece in resolved.structures:
        with builder.assembly(piece.id):
            builder.solid(Polygon(piece.polygon,piece.holes),piece.base_z,piece.top_z,'concrete',piece.semantic)
    for zone in resolved.site_zones:
        if zone.kind=='unclassified':continue
        poly=Polygon(zone.polygon,zone.holes)
        slope=np.tan(np.radians(zone.slope_deg))
        def top(x,y,z=zone,s=slope):
            return .025+s*max(0.,np.dot(np.array([x,y])-z.origin,z.inward))
        with builder.assembly('site/zone/'+zone.id):
            builder.solid(poly,0.,top,'soil' if zone.kind=='garden' else 'pavement','site_'+zone.kind)
            if zone.kind=='garden':
                plant_garden(builder,poly,Polygon(),[],[],_rng(nuisance.seed,zone.id))
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
    if theta.site.garden and not theta.site.zones:
        built=unary_union([mass_polygon(m) for m in resolved.masses if m.base_z<.01 and m.kind=='enclosed'])
        plant_garden(builder,parcel,built,boundaries,entrances,_rng(nuisance.seed,"garden"))
    return builder.finish()


def generate_from_theta(context, theta, nuisance=NuisanceParameters(), config=GrammarConfig()):
    return generate_resolved(resolve_theta(context,theta),nuisance,config)
