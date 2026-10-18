"""Neutral body and facade-surface contract for the piece catalog.

The catalog resolvers place crowns, balconies, members and openings onto an
exposed wall. They used to receive a legacy ``theta`` candidate plus two
implicit geometry lists (``masses`` and ``walls``). This module names that
geometry once so the same resolvers can be driven by any authoring front end:

* the legacy theta pipeline builds a chart from its resolved masses and walls;
* the new planning pipeline builds a chart from massing storeys and surfaces.

A chart is pure geometry: bodies (massing volumes) plus wall surfaces (facade
charts with a local frame, exposure domains and the facade specification the
resolvers read). It carries no benchmark identity, no camera and no style.
"""
from dataclasses import dataclass
from typing import Any

import numpy as np

from domain.architecture import MassSpec
from domain.models import FacadeSpecification


@dataclass(frozen=True)
class WallSurface:
    """One facade chart on one body edge.

    ``facade.vertex_a`` -> ``facade.vertex_b`` spans the full edge; the exposed
    intervals are ``visible_domains`` in local ``(u0, z0, u1, z1)`` metres, and
    ``plane_offset_m`` shifts the facade plane along its own normal (recessed
    or projected zones). ``thickness_m`` is the built wall depth behind that
    plane: openings recess into it and a piece must not be authored as if the
    facade were a zero-thickness sheet. ``0.0`` means the front end does not
    declare one.
    """

    mass_role: str
    edge: int
    base_z: float
    height_m: float
    axes_m: tuple[float, ...]
    facade: FacadeSpecification
    visible_domains: tuple[tuple[float, float, float, float], ...] = ()
    plane_offset_m: float = 0.0
    thickness_m: float = 0.0
    section: Any = None

    @property
    def width_m(self) -> float:
        return float(self.facade.width_m)

    @property
    def top_z(self) -> float:
        return self.base_z + self.height_m

    def frame(self):
        """Local frame ``(origin, tangent, normal)`` of the facade plane.

        The origin is ``vertex_a`` displaced to the facade plane ``plane_offset_m``
        along its normal, so anchors land on the built plane, not the cadastral
        line. ``tangent`` runs toward ``vertex_b`` and ``normal`` is the facade
        normal (outward with respect to the body).
        """
        a = np.asarray(self.facade.vertex_a, float)
        b = np.asarray(self.facade.vertex_b, float)
        width = float(self.facade.width_m)
        tangent = (b - a) / width
        normal = np.asarray(self.facade.normal_xy, float)
        origin = a + normal * self.plane_offset_m
        return origin, tangent, normal

    def local_point(self, u_m: float, z_m: float, offset_m: float = 0.0):
        """World XYZ of the local ``(u, z)`` point, ``offset_m`` along the normal."""
        origin, tangent, normal = self.frame()
        xy = origin + tangent * u_m + normal * offset_m
        return (float(xy[0]), float(xy[1]), float(z_m))


@dataclass(frozen=True)
class SurfaceChart:
    """Bodies and their exposed wall surfaces, in placement order."""

    bodies: tuple[MassSpec, ...]
    surfaces: tuple[WallSurface, ...]

    def body(self, mass_ref: str) -> MassSpec | None:
        return next((m for m in self.bodies if m.id == mass_ref), None)

    def surfaces_of(self, mass_ref: str) -> tuple[WallSurface, ...]:
        return tuple(w for w in self.surfaces if w.mass_role == mass_ref)

    def surface(self, mass_ref: str, edge: int, edge_id: str | None = None) -> WallSurface | None:
        candidates = [w for w in self.surfaces if w.mass_role == mass_ref and w.edge == edge]
        if edge_id is not None:
            candidates = [w for w in candidates if w.facade.edge_id == edge_id]
        return candidates[0] if len(candidates) == 1 else None

    def candidates(self, mass_ref: str, edge: int) -> tuple[WallSurface, ...]:
        return tuple(w for w in self.surfaces if w.mass_role == mass_ref and w.edge == edge)


def chart_from_walls(bodies, walls) -> SurfaceChart:
    """Chart from already-resolved theta geometry (compatibility path)."""
    return SurfaceChart(tuple(bodies), tuple(walls))
