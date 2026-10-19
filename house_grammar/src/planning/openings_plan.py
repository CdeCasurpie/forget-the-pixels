"""Deterministic facade-bay solver: sizes, margins and rhythm of apertures.

The intent states count, proportion, weights and distribution qualitatively.
This module turns that into metric bays that respect the wall ends, the masonry
pier between apertures and the volume a catalogue portal or moulding reserves.
No mesh is authored here: the resulting widths are handed to the same
:class:`domain.models.Opening` the catalog builders already consume, so the
wall cut and the piece share one contour.

The width bands are deliberately disjoint, which guarantees the R3 reading:
a main window is always wider than a ventilator, and a vertical casona window
can never collapse into a slot.
"""
import math

# Family -> catalogue proportion and the admissible clear width band (metres).
# ``storefront`` is internal: it is a commercial continuous glazing, not a
# proportion the intent can name.
FAMILIES = {
    'storefront': dict(proportion='horizontal', width=(2.00, 4.50), fill=True),
    'horizontal': dict(proportion='horizontal', width=(1.20, 3.00)),
    'vertical': dict(proportion='vertical', width=(1.00, 1.55)),
    'square': dict(proportion='square', width=(0.90, 1.45)),
    'small_high': dict(proportion='small_high', width=(0.45, 0.80)),
}
WINDOW_EDGE_M = .85   # opening edge to panel end, requested composition rule
DOOR_EDGE_M = 1.00
PIER_M = .55          # nominal masonry between two apertures of one panel
PORTAL_GAP_M = .10
PORTAL_WIDTH_M = .24


def proportion_of(family):
    """Catalogue proportion a family resolves to (for height/aspect solving)."""
    return FAMILIES[family]['proportion']


def band(family):
    return FAMILIES[family]['width']


def preferred_width(family):
    low, high = band(family)
    return (low + high) / 2


def portal_reserve(portal):
    """Lateral half-extent a catalogue portal adds beyond the door opening."""
    return 0. if portal in (None, 'none') else PORTAL_GAP_M + PORTAL_WIDTH_M


def margin_for(*, kind='window', portal='none'):
    """Distance from the opening edge to the panel end, including its reserve."""
    base = WINDOW_EDGE_M if kind == 'window' else DOOR_EDGE_M
    return base + portal_reserve(portal)


def _normalize_margin(margin):
    """A scalar margin applies to both ends; a pair sets the left/right ends.

    A free panel cut by a door has no wall end there: the door clearance is
    already inside the piece, so only genuine panel ends carry the edge margin.
    """
    if isinstance(margin, (tuple, list)):
        left, right = margin
    else:
        left = right = margin
    return float(left), float(right)


def solve_bays(span, families, *, weights=None, margin=WINDOW_EDGE_M, pier=PIER_M,
               distribution='balanced', tolerance=1e-9):
    """Return ``[dict(start, width, family)]`` or ``None`` when it cannot fit.

    The solver keeps each bay inside its family band, never widens a
    ventilator into a main window, and never silently shrinks below the band
    minimum: an infeasible panel returns ``None`` and the caller reports it.
    """
    count = len(families)
    if not families:
        return []
    left, right = _normalize_margin(margin)
    usable = span - left - right - pier * (count - 1)
    if usable <= tolerance:
        return None
    lower = [band(family)[0] for family in families]
    widths = [preferred_width(family) for family in families]
    if weights is not None:
        if len(weights) != count or any(not math.isfinite(w) or w <= 0 for w in weights):
            raise ValueError('one positive weight per bay is required')
        average = sum(weights) / count
        widths = [min(band(f)[1], max(band(f)[0], w * weight / average))
                  for f, w, weight in zip(families, widths, weights)]
    if count == 1 and FAMILIES[families[0]].get('fill'):
        # A lone continuous glazing takes the glazed front, not a mid-band slot,
        # but still needs its own minimum frontage to read as a storefront.
        if usable < lower[0]-tolerance:
            return None
        widths = [min(band(families[0])[1], usable)]
    total = sum(widths)
    if total > usable + tolerance:
        # Scale the surplus off every bay's slack above its family minimum. The
        # exact solution keeps each bay at or above the band minimum, so a
        # main window is never squeezed into a ventilator slot.
        floor = sum(lower)
        if floor > usable + tolerance:
            return None
        ratio = (usable - floor) / (total - floor)
        widths = [low + (w - low) * ratio for w, low in zip(widths, lower)]
    leftover = usable - sum(widths)
    if leftover < -tolerance:
        return None
    gaps = [0.] * (count - 1)
    if count == 1:
        lead = leftover / 2 if distribution in ('balanced', 'grouped') else (
            leftover if distribution == 'right' else 0.)
    elif distribution == 'balanced':
        share = leftover / (count - 1)
        gaps = [share] * (count - 1)
        lead = 0.
    elif distribution == 'right':
        lead = leftover
    elif distribution == 'grouped':
        lead = leftover / 2
    else:  # left (also the fallback): masonry slack accumulates at the rear end
        lead = 0.
    bays = []
    cursor = left + lead
    for index, family in enumerate(families):
        bays.append(dict(start=round(cursor, 9), width=round(widths[index], 9),
                         family=family))
        cursor += widths[index] + pier + (gaps[index] if index < count - 1 else 0.)
    return bays


def assign(spans, families, *, margins=None, pier=PIER_M):
    """Greedy, deterministic packing of families onto free wall spans.

    Returns one family list per span, or ``None`` when some family has no panel
    with room for it. The span with the most slack after the trial wins, which
    spreads bays instead of clustering them at one end.
    """
    margins = list(margins) if margins is not None else [WINDOW_EDGE_M]*len(spans)
    loads = [[] for _ in spans]
    for family in families:
        best = None
        for index, span in enumerate(spans):
            trial = loads[index] + [family]
            if solve_bays(span, trial, margin=margins[index], pier=pier) is None:
                continue
            left, right = _normalize_margin(margins[index])
            slack = (span - left - right - pier * (len(trial) - 1)
                     - sum(preferred_width(f) for f in trial))
            if best is None or slack > best[1] + 1e-9:
                best = (index, slack)
        if best is None:
            return None
        loads[best[0]].append(family)
    return loads
