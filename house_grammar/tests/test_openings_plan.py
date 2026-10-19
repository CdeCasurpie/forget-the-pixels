"""R3 bay solver: disjoint families, exact margins and honest infeasibility."""
import pytest

from planning import openings_plan as plan


def test_family_bands_keep_mains_clear_of_vents():
    # The ventilator is the only family disjoint from every larger one, which
    # is what guarantees "respiradero" never reads as a main window.
    vent_high = plan.band('small_high')[1]
    assert vent_high < plan.band('square')[0]
    assert vent_high < plan.band('vertical')[0]
    assert vent_high < plan.band('horizontal')[0]
    assert plan.band('horizontal')[0] >= plan.band('vertical')[0]


def test_portal_and_moulding_volume_is_reserved_in_the_margin():
    assert plan.margin_for(kind='window') == pytest.approx(.85)
    assert plan.margin_for(kind='door') == pytest.approx(1.0)
    assert plan.margin_for(kind='door', portal='none') == pytest.approx(1.0)
    expected = 1.0 + plan.PORTAL_GAP_M + plan.PORTAL_WIDTH_M
    assert plan.margin_for(kind='door', portal='pilasters') == pytest.approx(expected)
    assert plan.margin_for(kind='door', portal='columns') == pytest.approx(expected)
    assert plan.portal_reserve('none') == 0.


@pytest.mark.parametrize('families,span', [
    (['vertical'], 3.0),
    (['vertical', 'vertical'], 5.0),
    (['vertical'] * 3, 6.0),
    (['horizontal', 'vertical', 'small_high'], 9.6),
    (['small_high'], 2.5),
    (['storefront'], 9.6),
])
def test_solver_fits_every_bay_inside_its_band_and_the_panel(families, span):
    bays = plan.solve_bays(span, families)
    assert bays is not None
    assert [bay['family'] for bay in bays] == families
    for bay in bays:
        low, high = plan.band(bay['family'])
        assert low - 1e-9 <= bay['width'] <= high + 1e-9
    assert bays[0]['start'] >= plan.WINDOW_EDGE_M - 1e-6
    last = bays[-1]
    assert last['start'] + last['width'] <= span - plan.WINDOW_EDGE_M + 1e-6
    for left, right in zip(bays, bays[1:]):
        assert right['start'] - (left['start'] + left['width']) >= plan.PIER_M - 1e-6


def test_solver_reports_infeasibility_instead_of_tiny_windows():
    assert plan.solve_bays(3.0, ['vertical', 'vertical', 'vertical']) is None
    assert plan.solve_bays(2.0, ['horizontal', 'horizontal']) is None
    assert plan.solve_bays(1.4, ['vertical']) is None


def test_solver_never_cuts_a_bay_below_its_family_minimum_when_trimming():
    bays = plan.solve_bays(6.0, ['horizontal', 'horizontal'])
    assert bays is not None
    for bay in bays:
        assert bay['width'] >= plan.band('horizontal')[0] - 1e-9


def test_distribution_places_bays_at_the_requested_end():
    left, = plan.solve_bays(6.0, ['vertical'], distribution='left')
    right, = plan.solve_bays(6.0, ['vertical'], distribution='right')
    grouped, = plan.solve_bays(6.0, ['vertical'], distribution='grouped')
    assert left['start'] == pytest.approx(plan.WINDOW_EDGE_M)
    assert right['start'] == pytest.approx(6.0 - plan.WINDOW_EDGE_M - right['width'])
    assert grouped['start'] == pytest.approx((6.0 - grouped['width']) / 2, abs=1e-6)


def test_weights_widen_the_requested_bay_without_leaving_its_band():
    wide, narrow = plan.solve_bays(6.0, ['vertical', 'vertical'], weights=[2, 1])
    assert wide['width'] > narrow['width']
    assert narrow['width'] >= plan.band('vertical')[0] - 1e-9


def test_storefront_fills_a_lone_glazed_front():
    bay, = plan.solve_bays(9.6, ['storefront'])
    assert bay['width'] == pytest.approx(plan.band('storefront')[1])
    assert bay['width'] >= 3.5


def test_storefront_still_needs_a_minimum_frontage():
    assert plan.solve_bays(2.2, ['storefront']) is None
    bay, = plan.solve_bays(4.0, ['storefront'])
    assert bay['width'] == pytest.approx(4.0 - 2*plan.WINDOW_EDGE_M)


def test_assign_spreads_families_across_free_pieces():
    loads = plan.assign([5.15, 5.15], ['vertical', 'vertical'])
    assert loads == [['vertical'], ['vertical']]


def test_assign_uses_asymmetric_margins_at_a_door_cut():
    # A piece that ends at a door has no wall end there: only the true panel
    # end keeps the 0.85 m margin.
    fills = plan.assign([3.4], ['vertical', 'vertical'], margins=[(0., .85)])
    assert fills == [['vertical', 'vertical']]
    assert plan.assign([3.4], ['vertical', 'vertical'], margins=[(.85, .85)]) is None


def test_catalogue_proportion_is_exposed_per_family():
    assert plan.proportion_of('storefront') == 'horizontal'
    assert plan.proportion_of('small_high') == 'small_high'
    assert plan.proportion_of('vertical') == 'vertical'
