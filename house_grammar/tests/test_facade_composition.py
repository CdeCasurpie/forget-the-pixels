"""Frozen pre-extraction mesh and resolved-plan regression cases."""
from dataclasses import replace
import hashlib

import pytest

from domain.theta import (FacadeControls, FacadeZone, FaceBand, OpeningEdit,
                          Opening, NuisanceParameters, canonical)
from modeling.theta import generate_resolved
from test_facade_zones import body, solve, explicit


def cases():
    repeat=FacadeControls(bay_count=2,balconies=False)
    edits=replace(repeat,opening_edits=(OpeningEdit(0,0,'suppress'),))
    return {
        'base':body(faces=(FaceBand('front',repeat),)),
        'zone':body((FacadeZone('front',repeat,(.2,.8)),)),
        'explicit':body(faces=(FaceBand('front',explicit('fixed')),)),
        'edits':body(faces=(FaceBand('front',edits),)),
        'vertical':body((FacadeZone('front',replace(repeat,opening_edits=(
            OpeningEdit(1,0,'replace',Opening('window',.5,.6,1.,1.5)),)),(.2,.8),(3.,6.)),)),
        'back':body((FacadeZone('back',repeat,(.2,.8)),)),
    }


def signatures(component):
    resolved=solve(component)
    mesh=generate_resolved(resolved,NuisanceParameters(curtains=False))
    geometry=hashlib.sha256(mesh.vertices.tobytes()+mesh.faces.tobytes()+mesh.face_materials.tobytes()).hexdigest()
    return geometry,hashlib.sha256(canonical(resolved).encode()).hexdigest()


@pytest.mark.parametrize('name',cases())
def test_composer_preserves_pre_extraction_output(name):
    import json
    from pathlib import Path
    expected=json.loads((Path(__file__).parent/'fixtures/facade_composition_hashes.json').read_text())
    assert signatures(cases()[name])==tuple(expected[name])
