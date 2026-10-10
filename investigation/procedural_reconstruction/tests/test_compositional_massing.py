"""Structural invariants of the inferable, non-XY theta 0.3 interface."""
from dataclasses import replace
import json
import numpy as np
import pytest
from shapely.geometry import Polygon, Point, box
from shapely.ops import unary_union

from domain.theta import *
from domain.models import Opening, FacadeProjection
from modeling.theta import resolve_theta, generate_resolved, ResolvedArchitecture
from modeling.assembly import mass_polygon
from modeling.apertures import opening_shape
from modeling.validation import validate_mesh
from pipeline.theta import reconstruct

P=ReconstructionContext(((0.,0.),(12.,0.),(12.,20.),(0.,20.)),(0,))
BLIND=FacadeControls(mode='explicit',openings=())


def body(id='main',u=(0.,1.),depth=(0.,1.),levels=(0.,3.,6.),**kw):
    return MassComponent(id,PlanRegion(u=u,depth=depth),levels,**kw)


def solve(*components,site=SiteControls()):
    return resolve_theta(P,ThetaCandidate(schema_version='0.3',massing=MassingControls(components=components),site=site,roof=RoofControls(parapet_m=0.)))


def semantic_vertices(mesh,name):
    faces=[mesh.faces[c['face_start']:c['face_start']+c['face_count']] for c in mesh.parts if c['name']==name]
    return mesh.vertices[np.concatenate(faces).reshape(-1)] if faces else np.empty((0,3))


def test_setback_garden_and_fence_are_distinct_geometry():
    c=replace(body(),region=PlanRegion(depth_m=(3.,16.)))
    r=solve(c,site=SiteControls(fence='reja',zones=(SiteZone('front','garden',PlanRegion(depth_m=(0.,3.))),)))
    assert mass_polygon(r.masses[0]).bounds==(0.,3.,12.,16.)
    garden=next(z for z in r.site_zones if z.kind=='garden')
    assert Polygon(garden.polygon,garden.holes).area==pytest.approx(36.)
    assert any(b.is_street for b in r.boundaries)
    mesh=generate_resolved(r)
    assert len(semantic_vertices(mesh,'site_garden'))>0
    assert len(semantic_vertices(mesh,'fence_bar'))>0


def test_front_rear_disconnected_and_depths():
    r=solve(body('front',depth=(.1,.4)),body('rear',depth=(.7,.95),levels=(0.,3.)))
    a,b=map(mass_polygon,r.masses)
    assert a.distance(b)==pytest.approx(6.)
    assert [m.roof_z for m in r.masses]==[6.,3.]
    assert sum(p.area for p in (a,b))==pytest.approx(132.)


@pytest.mark.parametrize('upper',[PlanRegion(u=(0.,.5)),PlanRegion(depth_m=(3.,20.))])
def test_partial_upper_and_setback_roof_area(upper):
    r=solve(body(levels=(0.,3.)),MassComponent('upper',upper,(3.,6.)))
    lower=next(m for m in r.masses if m.role=='main');top=next(m for m in r.masses if m.role=='upper')
    roof=next(p for p in r.roofs if p.mass_id==lower.id)
    area=sum(Polygon(s.polygon,s.holes).area for s in roof.surfaces)
    assert area==pytest.approx(mass_polygon(lower).area-mass_polygon(top).area,abs=.01)
    assert all(w.base_z>=3 for w in r.walls if w.mass_role==top.id)


def test_courtyard_hole_survives_roof_and_site():
    c=body(cutouts=(PlanRegion(u=(.3,.7),depth=(.3,.7)),))
    r=solve(c)
    p=mass_polygon(r.masses[0]);assert len(p.interiors)==1
    assert len(r.walls)==8
    assert len(r.roofs[0].surfaces[0].holes)==1
    assert sum(Polygon(z.polygon,z.holes).area for z in r.site_zones)==pytest.approx(38.4)
    mesh=generate_resolved(r)
    roof=semantic_vertices(mesh,'roof_slab')
    assert not any(box(3.61,6.01,8.39,13.99).contains(Point(x,y)) for x,y,_ in roof)


def test_cutout_corridor_retains_both_components():
    r=solve(body(cutouts=(PlanRegion(u=(.4,.6)),)))
    assert len(r.masses)==2
    assert [m.id for m in r.masses]==['main:0','main:1']
    assert mass_polygon(r.masses[0]).distance(mass_polygon(r.masses[1]))==pytest.approx(2.4)


def test_partial_wall_exposure_area_and_fixed_opening_coordinates():
    op=Opening('window',1.,.7,8.,1.5,prefab='slim_window')
    rear=body('rear',depth=(.4,1.),facade=FacadeControls(mode='explicit',openings=(op,)))
    # Use just front face: other edge lengths differ.
    rear=replace(rear,facade=None,faces=(FaceBand('front',rear.facade),))
    r=solve(rear,body('low',u=(0.,.5),depth=(0.,.4),levels=(0.,3.)))
    wall=next(w for w in r.walls if w.mass_role=='rear:0' and w.edge==0)
    assert wall.facade.openings==(op,)
    assert unary_union([box(*d) for d in wall.visible_domains]).area==pytest.approx(54.,abs=1e-5)
    mesh=generate_resolved(r)
    vertices=semantic_vertices(mesh,'slim_frame')
    assert len(vertices)>0
    # No frame remains in the hidden lower-left half of the rear front.
    assert not np.any((vertices[:,0]<5.99)&(vertices[:,1]>7.8)&(vertices[:,1]<8.2)&(vertices[:,2]<2.99))


def test_open_canopy_has_columns_roof_and_no_facade_shells():
    r=solve(body(levels=(0.,4.5),kind='open',support=SupportControls(kind='columns')),
        site=SiteControls(zones=(SiteZone('forecourt','parking'),)))
    assert not r.walls
    assert all(s.semantic=='support_column' for s in r.structures)
    mesh=generate_resolved(r)
    assert len(semantic_vertices(mesh,'wall'))==0
    assert len(semantic_vertices(mesh,'support_column'))>0
    assert len(semantic_vertices(mesh,'roof_slab'))>0
    assert sum(Polygon(z.polygon,z.holes).area for z in r.site_zones)<240.


def test_pilotis_upper_mass_and_soffit():
    r=solve(body(levels=(3.,6.,9.),support=SupportControls(kind='columns')))
    assert all(w.base_z==3. for w in r.walls)
    assert any(s.semantic=='soffit' for s in r.structures)
    assert all(s.base_z==0 and s.top_z==3 for s in r.structures if s.semantic=='support_column')
    assert len(semantic_vertices(generate_resolved(r),'soffit'))>0


def test_open_ground_floor_supports_upper_body():
    r=solve(body('ground',levels=(0.,3.),kind='open'),body('upper',levels=(3.,6.)))
    assert all(w.mass_role=='upper:0' for w in r.walls)
    assert len(r.structures)>=4
    assert any(s.semantic=='open_floor_slab' and s.top_z==3. for s in r.structures)
    assert next(m for m in r.masses if m.role=='upper').support_ids==('ground:0',)


def test_cantilever_requires_bearing_and_bounded_reach():
    lower=body('lower',u=(.15,.85),levels=(0.,3.))
    upper=body('upper',levels=(3.,6.),support=SupportControls(kind='cantilever',max_cantilever_m=2.))
    r=solve(lower,upper)
    soffits=[Polygon(s.polygon,s.holes) for s in r.structures if s.semantic=='soffit']
    assert sum(p.area for p in soffits)==pytest.approx(72.)
    with pytest.raises(ValueError,match='Unsupported'):
        solve(lower,replace(upper,support=replace(upper.support,max_cantilever_m=1.)))
    with pytest.raises(ValueError,match='Unsupported'):
        solve(replace(upper,support=SupportControls()))


def test_partial_gallery_and_continuous_balcony_reuse_prefabs():
    f=FacadeControls(mode='explicit',openings=(),projections=(
        FacadeProjection('gallery',1.,3.,4.,2.5,.8),
        FacadeProjection('balcony',5.5,3.,5.5,1.,.8)))
    r=solve(body(depth=(.1,1.),faces=(FaceBand('front',f),)))
    mesh=generate_resolved(r)
    gallery=semantic_vertices(mesh,'gallery_post');balcony=semantic_vertices(mesh,'balcony_slab')
    assert len(gallery)>0 and len(balcony)>0
    assert gallery[:,0].max()<5.2
    assert balcony[:,0].min()==pytest.approx(5.5) and balcony[:,0].max()==pytest.approx(11.)


def test_corner_faces_and_height_bands_are_independent():
    door=FacadeControls(mode='explicit',openings=(Opening('gate',1.,0.,5.,2.5,prefab='metal_gate'),))
    windows=FacadeControls(bay_count=2,balconies=False,projections=())
    r=solve(body(faces=(FaceBand('front',door,(0.,3.)),FaceBand('front',windows,(3.,6.)),FaceBand('left',BLIND))))
    front=[w for w in r.walls if w.edge==0]
    assert len(front)==2 and front[0].facade.openings[0].kind=='gate'
    assert all(op.kind=='window' for op in front[1].facade.openings)
    assert not next(w for w in r.walls if w.edge==3).facade.openings


def test_compound_roof_gable_and_shed_have_distinct_planes():
    r=solve(body('house',u=(0.,.6),roof=RoofControls(kind='gable',slope_deg=20.,parapet_m=0.)),
            body('garage',u=(.6,1.),levels=(0.,3.),roof=RoofControls(kind='tile_shed',slope_deg=10.,parapet_m=0.)))
    assert sorted(len(p.surfaces) for p in r.roofs)==[1,2]
    house=next(p for p in r.roofs if p.mass_id=='house:0')
    assert np.dot(house.surfaces[0].inward_normal,house.surfaces[1].inward_normal)==pytest.approx(-1.)
    assert len(semantic_vertices(generate_resolved(r),'tile_roof'))>0


def test_arch_real_hole_screen_and_pediment_geometry():
    arch=Opening('door',1.,.1,2.,2.6,prefab='open',shape='arch')
    assert opening_shape(arch).area<arch.width_m*arch.height_m
    f=FacadeControls(mode='explicit',openings=(arch,Opening('window',4.,.5,3.,2.,prefab='screen')),
        projections=(FacadeProjection('pediment',.5,5.,3.,1.2,.2),))
    r=solve(body(faces=(FaceBand('front',f),)))
    mesh=generate_resolved(r)
    assert len(semantic_vertices(mesh,'arched_frame'))>0
    assert len(semantic_vertices(mesh,'perforated_screen'))>0
    assert len(semantic_vertices(mesh,'pediment'))>0
    assert len(semantic_vertices(mesh,'door_panel'))==0


def test_evidence_roundtrip_stability_and_export(tmp_path):
    from modeling.exporters.glb_exporter import export_glb
    theta=ThetaCandidate(schema_version='0.3',massing=MassingControls(components=(body(),)))
    request=ReconstructionRequest(P,theta,evidence={'massing.components[main].region.depth':Evidence('prior',.2)})
    a=reconstruct(from_json(canonical(request)))
    decoded=decode(ResolvedArchitecture,json.loads(canonical(a.resolved)))
    assert canonical(decoded)==canonical(a.resolved)
    assert np.array_equal(generate_resolved(decoded).vertices,a.mesh.vertices)
    path=tmp_path/'assembly.glb';export_glb(a.mesh,path);assert path.read_bytes()[:4]==b'glTF'
    from modeling.grammar import street_envelope
    from domain.architecture import ParcelContext
    assert validate_mesh(a.mesh,Polygon(P.parcel),envelope=street_envelope(ParcelContext(P.parcel,explicit_fronts=P.fronts)))['envelope_test']=='passed'


def test_invalid_composition_does_not_silently_fallback():
    with pytest.raises(ValueError,match='Interpenetrating'):solve(body('a'),body('b'))
    with pytest.raises(ValueError,match='unique'):solve(body(),body())
    with pytest.raises(ValueError,match='Overlapping site'):solve(body(u=(0.,.5)),site=SiteControls(zones=(SiteZone('a','garden'),SiteZone('b','parking'))))


def test_oblique_setback_no_partial_exposure_exception():
    p=replace(P,parcel=((0.,0.),(12.,1.),(11.,20.),(0.,19.)),fronts=(0,3))
    r=resolve_theta(p,ThetaCandidate(height_m=6.,floors=2,massing=MassingControls(front_setback_m=2.)))
    assert sum(mass_polygon(m).area for m in r.masses)<Polygon(p.parcel).area
    assert len(generate_resolved(r).faces)>0


def test_booth_under_canopy_is_not_interpenetrating_solid():
    r=solve(body('canopy',levels=(0.,4.5),kind='open'),body('booth',u=(.7,1.),depth=(.7,1.),levels=(0.,2.7)))
    assert len(r.masses)==2
    assert all(w.mass_role=='booth:0' for w in r.walls)
    assert any(s.base_z==2.7 for s in r.structures if s.semantic=='support_column')


def test_tolerant_rectangle_is_retained_not_hard_clipped():
    p=replace(P,parcel=((0.,0.),(12.,0.),(11.7,20.),(.3,20.)))
    c=MassComponent('main',PlanRegion(fit='rectangle'),(0.,3.))
    theta=ThetaCandidate(schema_version='0.3',massing=MassingControls(components=(c,),parcel_tolerance_m=.4))
    r=resolve_theta(p,theta)
    assert mass_polygon(r.masses[0]).area==pytest.approx(240.)
    assert mass_polygon(r.masses[0]).difference(Polygon(p.parcel)).area>1.
    assert len(generate_resolved(r).faces)>0
    with pytest.raises(ValueError,match='tolerance'):
        resolve_theta(p,replace(theta,massing=replace(theta.massing,parcel_tolerance_m=0.)))


def test_ramp_has_real_rise_and_column_footprints_are_not_paved():
    r=solve(body(u=(0.,.5)),site=SiteControls(zones=(SiteZone('drive','driveway',PlanRegion(u=(.5,1.),depth_m=(0.,6.)),5.),)))
    vertices=semantic_vertices(generate_resolved(r),'site_driveway')
    assert vertices[:,2].max()==pytest.approx(.025+np.tan(np.radians(5.))*6.)


def test_arch_wall_oblique_parcel_stays_in_envelope():
    from modeling.grammar import street_envelope
    from domain.architecture import ParcelContext
    p=replace(P,parcel=((0.,0.),(12.,2.),(11.,20.),(1.,18.)))
    c=body(faces=(FaceBand('front',FacadeControls(mode='explicit',openings=(Opening('door',2.,.1,3.,2.6,prefab='open',shape='arch'),))),))
    r=resolve_theta(p,ThetaCandidate(schema_version='0.3',massing=MassingControls(components=(c,))))
    mesh=generate_resolved(r)
    report=validate_mesh(mesh,Polygon(p.parcel),envelope=street_envelope(ParcelContext(p.parcel,explicit_fronts=p.fronts)))
    assert report['envelope_test']=='passed'
