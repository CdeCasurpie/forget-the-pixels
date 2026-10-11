"""Compact cadastral base recipes compiled to existing mass components.

Recipe edge indices refer to the canonical parcel, like PlanRegion. Secondary
components are ordinary MassComponents and retain supports, zones and facades.
This opt-in adapter does not change existing theta requests.
"""
from dataclasses import dataclass, replace
import math

from domain.theta import MassComponent, PlanRegion
from modeling.theta import _context


@dataclass(frozen=True)
class Setback:
    edge: int
    depth_m: float


@dataclass(frozen=True)
class Bite:
    edge: int
    end: str
    width_m: float
    depth_m: float


@dataclass(frozen=True)
class BaseFloor:
    height_m: float
    setbacks: tuple[Setback, ...] = ()
    bites: tuple[Bite, ...] = ()


def compile_base(context, floors, *, prefix='base'):
    """Return one cadastral component per floor, with free areas subtracted.

    Two fronts must share a vertex. A bite may use either endpoint of either
    front, so all three vertices of a corner are accessible. Upper floors may
    have different footprints; their structural support remains validated by
    the existing resolver, rather than silently adding supports.
    """
    context = _context(context)
    p = context.parcel
    fronts = set(context.fronts)
    if len(fronts) == 2:
        a, b = sorted(fronts)
        if (a + 1) % len(p) != b and (b + 1) % len(p) != a:
            raise ValueError('Two-front base requires adjacent fronts')
    if not floors:
        raise ValueError('Base requires at least one floor')
    result = []
    z = 0.
    for index, floor in enumerate(floors):
        if not math.isfinite(floor.height_m) or floor.height_m < .5:
            raise ValueError('Invalid floor height')
        if len({s.edge for s in floor.setbacks}) != len(floor.setbacks):
            raise ValueError('Duplicate setback edge')
        if len(fronts) > 2 and (floor.bites or
                floor.setbacks and {s.edge for s in floor.setbacks} != fronts):
            raise ValueError('Three-plus fronts allow full extrusion or all-front setbacks')
        cuts = []
        for s in floor.setbacks:
            if s.edge not in fronts or not math.isfinite(s.depth_m) or s.depth_m <= 0:
                raise ValueError('Invalid front setback')
            cuts.append(PlanRegion(front_edge=s.edge, depth_m=(0., s.depth_m)))
        for b in floor.bites:
            if b.edge not in fronts or b.end not in ('start', 'end'):
                raise ValueError('Invalid bite vertex')
            length = math.dist(p[b.edge], p[(b.edge + 1) % len(p)])
            if not all(math.isfinite(v) and v > 0 for v in (b.width_m, b.depth_m)) or b.width_m >= length:
                raise ValueError('Invalid bite dimensions')
            fraction = b.width_m / length
            u = (0., fraction) if b.end == 'start' else (1.-fraction, 1.)
            cuts.append(PlanRegion(front_edge=b.edge, u=u,
                                  depth_m=(0., b.depth_m), width_reference='edge'))
        result.append(MassComponent(id=f'{prefix}_{index}', region=PlanRegion(),
                                    levels_m=(z, z+floor.height_m), cutouts=tuple(cuts)))
        z += floor.height_m
    return tuple(result)


def with_base(request, floors, *, secondary=(), prefix='base'):
    """Adapt a request; explicit secondary bodies remain available unchanged.

    Facade/roof references must target the generated IDs. Existing overrides
    are deliberately not guessed or silently remapped.
    """
    components = compile_base(request.context, floors, prefix=prefix) + tuple(secondary)
    massing = replace(request.theta.massing, pattern=None, components=components,
                      front_setback_m=None, upper_setback_m=None, podium_floors=None,
                      front_depth_m=None, low_floors=None, corner_reach_m=None)
    return replace(request, theta=replace(request.theta, massing=massing,
                                          masses=None, height_m=None, floors=None))
