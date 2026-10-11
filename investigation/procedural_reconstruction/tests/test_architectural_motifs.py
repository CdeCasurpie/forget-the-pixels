"""One opt-in portal compiled from an existing opening and facade projections."""
from dataclasses import replace
from collections import Counter
import pytest

from domain.theta import ArchitecturalMotif, FacadeControls, FacadeZone, OpeningEdit, BayGroup
from domain.models import Opening
from modeling.theta import _facade_controls, generate_resolved
from modeling.facade_composition import compose_facade
from test_facade_zones import body, solve, front
from test_bay_groups import GROUPS, controls
from test_facade_composition import cases, signatures
from test_compositional_massing import semantic_vertices


M=ArchitecturalMotif('monumental_portal',3)


def compose(c=None,length=24.,family='republicano',levels=(0.,5.9)):
    return compose_facade(_facade_controls(c or controls(motifs=(M,)),family),family,
                          length,levels,levels[-1],True,True)


def test_motif_empty_is_legacy_identical():
    import json
    from pathlib import Path
    expected=json.loads((Path(__file__).parent/'fixtures/facade_composition_hashes.json').read_text())
    assert all(signatures(component)==tuple(expected[key]) for key,component in cases().items())
    assert compose(controls(motifs=())).openings==compose_facade(
        _facade_controls(controls(), 'republicano'),'republicano',24.,(0.,5.9),5.9,True,True).openings


def test_monumental_portal_targets_central_bay():
    out=compose()
    doors=[o for o in out.openings if o.kind=='door']
    assert len(doors)==1
    op=doors[0]
    assert out.axes_m[3]-op.width_m/2==pytest.approx(op.u_m)
    pieces=[p for p in out.projections if p.source=='monumental_portal']
    assert Counter(p.kind for p in pieces)=={'pilaster':2,'frame':1,'cornice':1,'pediment':1}
    left,right=(p for p in pieces if p.kind=='pilaster')
    assert left.u_m+left.width_m<op.u_m<op.u_m+op.width_m<right.u_m
    assert next(p for p in pieces if p.kind=='frame').u_m<op.u_m
    assert all(0<=p.u_m and p.u_m+p.width_m<=24. for p in pieces)


def test_monumental_portal_not_first_bay():
    out=compose()
    assert out.openings[0].kind=='window'
    assert out.openings[3].kind=='door'
    assert not any(p.source=='monumental_portal' and p.u_m<out.axes_m[0]-.5 for p in out.projections)


def test_monumental_portal_arch():
    out=compose(controls(motifs=(replace(M,opening_shape='arch'),)))
    op=out.openings[3]
    assert op.shape=='arch' and 0<op.arch_rise_m<=op.width_m/2


def test_monumental_portal_inside_facade_zone():
    from test_facade_zones import P
    p=replace(P,parcel=((0.,0.),(40.,0.),(40.,20.),(0.,20.)))
    c=controls(motifs=(replace(M,opening_shape='arch'),))
    component=replace(body((FacadeZone('front',c,(.2,.8)),)),levels_m=(0.,5.9))
    plan=solve(component,context=p)
    wall=next(w for w in front(plan) if '/zone' in w.facade.edge_id)
    local=compose(c,family='quiet_house')
    assert wall.facade.openings==tuple(replace(o,u_m=o.u_m+8) for o in local.openings)
    assert wall.facade.projections==tuple(replace(f,u_m=f.u_m+8) for f in local.projections)
    mesh=generate_resolved(plan)
    assert len(semantic_vertices(mesh,'pediment'))>0


def test_monumental_portal_suppressed_opening_fails():
    with pytest.raises(ValueError,match='requires an opening'):
        compose(controls(motifs=(M,),opening_edits=(OpeningEdit(0,3,'suppress'),)))


def test_monumental_portal_out_of_range_fails():
    with pytest.raises(ValueError,match='target bay/floor'):
        compose(controls(motifs=(replace(M,bay=99),)))


def test_motif_does_not_duplicate_global_relief():
    old=compose(controls())
    new=compose()
    base=[p for p in old.projections if p.source!='monumental_portal']
    inherited=[p for p in new.projections if p.source!='monumental_portal']
    assert base==inherited
    assert sum(p.kind in ('cornice','denticulated_cornice','denticulated')
               and p.source=='family_rule' for p in new.projections)==1
    assert sum(p.kind=='pediment' and p.source=='monumental_portal' for p in new.projections)==1


def test_motif_replace_and_invalid_targets():
    replacement=Opening('gate',8.3,.1,2.,3.,prefab='roller')
    out=compose(controls(motifs=(M,),opening_edits=(OpeningEdit(0,3,'replace',replacement),)))
    assert out.openings[3]==replacement
    with pytest.raises(ValueError,match='door or gate'):
        compose(controls(motifs=(M,),opening_edits=(OpeningEdit(0,3,'replace',replace(replacement,kind='window')),)))
    with pytest.raises(ValueError,match='does not fit'):
        compose(controls(motifs=(replace(M,pediment=True),)),levels=(0.,3.))


def test_motif_schema_validation_and_optional_pediment():
    from domain.theta import ReconstructionContext, ThetaCandidate, canonical, from_json, ReconstructionRequest
    from modeling.theta import resolve_theta
    from test_facade_zones import P
    c=controls(motifs=(replace(M,pediment=False),))
    assert Counter(p.kind for p in compose(c).projections if p.source=='monumental_portal')['pediment']==0
    with pytest.raises(ValueError,match='schema_version=0.3'):
        resolve_theta(P,ThetaCandidate(facade=c))
    assert from_json(canonical(ReconstructionRequest(P,ThetaCandidate(schema_version='0.3',facade=c)))).theta.facade.motifs==c.motifs
    for motifs,match in [((M,M),'Duplicate motif'),((replace(M,floor=1),),'Invalid monumental_portal'),
                         ((replace(M,kind='unsupported'),),'Invalid monumental_portal')]:
        with pytest.raises(ValueError,match=match):compose(controls(motifs=motifs))
