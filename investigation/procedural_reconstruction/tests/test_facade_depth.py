from dataclasses import replace
import numpy as np
import pytest
from domain.theta import FacadeZone, FacadeControls
from modeling.theta import generate_resolved
from test_facade_zones import body, solve, front, semantic_vertices


@pytest.mark.parametrize('depth',[-1.,.6])
def test_plane_and_returns(depth):
    control=FacadeControls(mode='explicit',openings=(),projections=(),material_regions=())
    zone=FacadeZone('front',control,(.2,.8),offset_m=depth)
    result=solve(body((zone,)))
    plain=solve(body((replace(zone,offset_m=0.),)))
    assert result.masses==plain.masses and result.roofs==plain.roofs
    wall=next(w for w in front(result) if '/zone' in w.facade.edge_id)
    assert wall.plane_offset_m==depth
    vertices=semantic_vertices(generate_resolved(result),'facade_depth_return')
    assert len(vertices)>0
    assert np.ptp(vertices[:,1])==pytest.approx(abs(depth),abs=1e-5)


def test_legacy_empty_depth():
    from test_bay_groups import test_bay_groups_legacy_empty_is_identical
    test_bay_groups_legacy_empty_is_identical()


def test_openings_move_with_plane_and_visibility():
    from domain.theta import Opening, MassComponent, PlanRegion
    control=FacadeControls(mode='explicit',openings=(Opening('window',1.,1.,1.,1.,prefab='slim_window'),))
    zone=FacadeZone('front',control,(.2,.8),offset_m=-.8)
    baseline=generate_resolved(solve(body((replace(zone,offset_m=0.),))))
    displaced=generate_resolved(solve(body((zone,))))
    a=semantic_vertices(baseline,'slim_frame')
    b=semantic_vertices(displaced,'slim_frame')
    assert b[:,1].mean()-a[:,1].mean()==pytest.approx(.8,abs=1e-5)
    blocker=MassComponent('blocker',PlanRegion(u=(0.,.5),depth_m=(0.,4.)),(0.,3.,6.))
    masked=generate_resolved(solve(body((zone,)),blocker))
    assert len(semantic_vertices(masked,'slim_frame'))==0


@pytest.mark.parametrize('depth',[-2.1,1.1,float('nan')])
def test_invalid_depth(depth):
    with pytest.raises(ValueError):
        solve(body((FacadeZone('front',FacadeControls(mode='explicit',openings=()),offset_m=depth),)))
