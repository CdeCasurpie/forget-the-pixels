import pytest
from shapely.geometry import Polygon

from domain.theta import ReconstructionContext, MassingControls
from modeling.assembly import compose_masses
from modeling.base_massing import BaseFloor, Bite, Setback, compile_base


def context(fronts=(0,)):
    return ReconstructionContext(parcel=((0., 0.), (10., 0.), (10., 10.), (0., 10.)), fronts=fronts)


def area(ctx, floor):
    components = compile_base(ctx, (floor,))
    return sum(Polygon(m.footprint, m.footprint_holes).area
               for m in compose_masses(ctx, MassingControls(components=components)))


def test_full_setback_and_corner_bite():
    assert area(context(), BaseFloor(3.)) == pytest.approx(100.)
    assert area(context(), BaseFloor(3., (Setback(0, 2.),))) == pytest.approx(80.)
    assert area(context(), BaseFloor(3., (), (Bite(0, 'end', 3., 4.),))) == pytest.approx(88.)


def test_double_front_setback_does_not_double_subtract_corner():
    assert area(context((0, 1)), BaseFloor(3., (Setback(0, 2.), Setback(1, 2.)))) == pytest.approx(64.)


def test_each_corner_vertex_can_be_selected():
    for edge, end in ((0, 'start'), (0, 'end'), (1, 'end')):
        assert area(context((0, 1)), BaseFloor(3., bites=(Bite(edge, end, 2., 3.),))) == pytest.approx(94.)


def test_heights_and_floor_specific_footprints():
    floors = (BaseFloor(3.2), BaseFloor(2.8, (Setback(0, 2.),)))
    components = compile_base(context(), floors)
    assert [c.levels_m for c in components] == [(0., 3.2), (3.2, 6.)]
    masses = compose_masses(context(), MassingControls(components=components))
    assert [Polygon(m.footprint).area for m in masses] == pytest.approx([100., 80.])


def test_opposite_fronts_are_not_a_corner():
    with pytest.raises(ValueError, match='adjacent'):
        compile_base(context((0, 2)), (BaseFloor(3.),))


def test_many_fronts_policy():
    ctx = context((0, 1, 2, 3))
    assert area(ctx, BaseFloor(3., tuple(Setback(e, 1.) for e in ctx.fronts))) == pytest.approx(64.)
    with pytest.raises(ValueError, match='all-front'):
        compile_base(ctx, (BaseFloor(3., (Setback(0, 1.),)),))
