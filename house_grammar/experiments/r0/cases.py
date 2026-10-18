"""Minimal self-contained reference cases, one group per catalogue (R0).

Every case is a small theta request authored *here*, deliberately outside
``steps/``, so the capability conservation matrix never depends on historical
JSON.  Each case exercises exactly one catalogue through the real pipeline
(``pipeline.theta.reconstruct``), so a green run proves the constructor is
reachable and produces finite, closed geometry on the new contract.

The cases are intentionally bare: a single rectangular mass, one flat roof and
no ornaments except the catalogue under test.  That is what makes them usable
as a per-catalogue regression baseline during the R1-R6 migration.
"""
from __future__ import annotations

PARCEL = [[0, 0], [20, 0], [20, 20], [0, 20]]
FOOTPRINT = [[3, 3], [15, 3], [15, 13], [3, 13]]

WINDOW_PROFILES = ('republicano', 'barroco', 'clasico', 'madera', 'moderno')
FENCE_STYLES = ('republicano', 'moderno')


def _request(style, masses, *, parcel=None, fronts=(0,), **theta):
    """Minimal theta scaffold: explicit masses, no ornaments unless overridden."""
    spec = dict(
        schema_version='0.3', architectural_style=style,
        massing=dict(pattern='explicit'), masses=list(masses),
        facade=dict(mode='explicit', openings=[], projections=[], material_regions=[]),
        roof=dict(kind='flat', parapet_m=0, props=[]),
        site=dict(fence='none', runs=[], garden=False),
        trim=dict(cornice=dict(enabled=False), plinth=dict(enabled=False)),
    )
    spec.update(theta)
    return dict(context=dict(parcel=parcel or PARCEL, fronts=list(fronts)), theta=spec)


def _house(levels=(0, 4)):
    return [dict(role='house', footprint=FOOTPRINT, levels_m=list(levels))]


# --- ventanas ---------------------------------------------------------------

def ventanas(profile):
    """One facade with rectangle, arch and ellipse windows of one profile."""
    openings = [
        dict(kind='window', u_m=1.4, v_m=.9, width_m=1.4, height_m=1.6,
             shape='rectangle', frame_profile=profile, grille=True,
             grille_pattern='grid', sill=True),
        dict(kind='window', u_m=4.6, v_m=.9, width_m=1.5, height_m=1.7,
             shape='arch', arch_rise_m=.5, frame_profile=profile, sill=True),
        dict(kind='window', u_m=8.0, v_m=.9, width_m=1.4, height_m=1.4,
             shape='ellipse', frame_profile=profile, grille=True,
             grille_pattern='diamond'),
    ]
    return _request(profile, _house(), facade=dict(
        mode='explicit', openings=openings, projections=[], material_regions=[]))


# --- puertas ----------------------------------------------------------------

def puertas(style, portal):
    """A gate with an explicit door catalogue block; portal optional."""
    door = dict(model='auto', portal=portal, cornice=portal == 'columns',
                transom_height_m=.45, transom_infill='glass',
                grille_pattern='auto', construction='auto')
    opening = dict(kind='gate', u_m=1.6, v_m=.12, width_m=2.6, height_m=2.9,
                   shape='arch', arch_rise_m=.5, frame_profile=style, door=door)
    return _request(style, _house(), facade=dict(
        mode='explicit', openings=[opening], projections=[], material_regions=[]))


# --- entradas ---------------------------------------------------------------

def entradas(kind):
    """An existing doorway plus its stair/ramp assembly."""
    rise = .48 if kind == 'steps' else .30
    opening = dict(kind='door', u_m=5.0, v_m=rise, width_m=1.5, height_m=2.5)
    controls = dict(id='access', mass_ref='house:0', edge=0, opening_index=0,
                    kind=kind, cheek_height_m=.3)
    if kind == 'ramp':
        controls.update(run_m=2.5)
    return _request('republicano', _house(), facade=dict(
        mode='explicit', openings=[opening], projections=[], material_regions=[]),
        entrances=[controls])


# --- balcones ---------------------------------------------------------------

def _first_variant(style):
    from modeling.balcony_catalog import CATALOG
    return sorted(CATALOG[style])[0]


def balcones(style):
    controls = dict(id='sample', mass_ref='house:0', edge=0, floor_m=4.,
                    u_m=.5, width_m=3.2, variant=_first_variant(style),
                    brackets=True)
    return _request(style, _house(levels=(0, 4, 8)), balconies=[controls])


# --- pilastras --------------------------------------------------------------

def _first_member(style):
    from modeling.vertical_member_catalog import CATALOG
    return sorted(CATALOG[style])[0]


def pilastras(style):
    controls = dict(id='p1', mass_ref='house:0', edge=0, u_m=2.0, bottom_m=0.,
                    height_m=8., width_m=.42, depth_m=.42, placement='attached',
                    design=dict(style=style, variant=_first_member(style)))
    return _request(style, _house(levels=(0, 4, 8)), vertical_members=[controls])


# --- frontones --------------------------------------------------------------

def frontones(style='republicano'):
    controls = dict(id='crown', mass_ref='house:0', edge=0, u_m=4.0,
                    width_m=6.0, height_m=2.0,
                    design=dict(silhouette='mixed', stepped=True))
    return _request(style, _house(), crowns=[controls])


# --- remates ----------------------------------------------------------------

def remates(style='republicano'):
    return _request(style, _house(levels=(0, 4, 8)), side_material='plaster',
                    trim=dict(cornice=dict(enabled=True), plinth=dict(enabled=True)))


# --- cercos -----------------------------------------------------------------

def cercos(style):
    run = dict(edge=0, start_m=0., end_m=20., kind=style, height_m=2.4,
               height_mode='high', wall_material='plaster',
               gate_u=5.0, gate_width=1.1, garage_u=12.0, garage_width=2.9,
               gate_mode='auto', garage_mode='auto', openness=.3,
               planters=False, plinth=None, base_height_m=None)
    site = dict(fence='none', runs=[run], zones=[], garden=False)
    return _request(style, _house(), site=site)


# --- techos -----------------------------------------------------------------

def techos(form, covering):
    design = dict(form=form, covering=covering, detail='full', slope_deg=22.,
                  rotation_deg=0., ridge_fraction=.5,
                  eave=dict(kind='profiled', overhang_m=.35))
    assembly = dict(id='roof', mass_ref='house:0', props_mode='off', design=design)
    return _request('republicano', _house(), roof_assemblies=[assembly])


def all_cases():
    """Yield ``(name, request)`` for every R0 reference case."""
    for profile in WINDOW_PROFILES:
        yield f'ventanas_{profile}', ventanas(profile)
    yield 'puertas_republicano_portal', puertas('republicano', 'columns')
    yield 'puertas_moderno_plain', puertas('moderno', 'none')
    yield 'entradas_steps', entradas('steps')
    yield 'entradas_ramp', entradas('ramp')
    yield 'balcones_republicano', balcones('republicano')
    yield 'balcones_moderno', balcones('moderno')
    yield 'pilastras_republicano', pilastras('republicano')
    yield 'pilastras_moderno', pilastras('moderno')
    yield 'frontones_republicano', frontones()
    yield 'remates_republicano', remates()
    for style in FENCE_STYLES:
        yield f'cercos_{style}', cercos(style)
    yield 'techos_gable_tile', techos('gable', 'curved_tile')
    yield 'techos_shed_corrugated', techos('shed', 'corrugated')


# What each case must produce (any-of), checked by the runner and the
# regression test.  A catalogue may emit different semantics depending on the
# selected variant (a moderno fence is louvers, not bars; a ramp is not a step).
EXPECTED = {
    'ventanas': ['window_glass'],
    'puertas': ['door_leaf_frame'],
    'entradas': ['entrance_step', 'entrance_ramp', 'entrance_passage'],
    'balcones': ['balcony_platform'],
    'pilastras': ['pilaster', 'member_shaft'],
    'frontones': ['crown_body'],
    'remates': ['trim_cornice'],
    'cercos': ['fence_bar', 'fence_louver', 'fence_wall'],
    'techos': ['roof_substrate', 'roof_tile_piece', 'roof_corrugation', 'roof_panel'],
}
