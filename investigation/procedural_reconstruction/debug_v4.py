import sys; sys.path.insert(0, 'src')
from domain.architecture import *
from procedural_modeling.v4_grammar import generate_v4_mesh
import procedural_modeling.v4_grammar

# Monkey patch facade to print what it receives
original_facade = procedural_modeling.v4_grammar.facade
def logging_facade(mb, f, band_height):
    print(f"FACADE CALLED: id={f.edge_id}, a={f.vertex_a}, b={f.vertex_b}, len={f.width_m}, mat={f.wall_material}")
    original_facade(mb, f, band_height)
procedural_modeling.v4_grammar.facade = logging_facade

import debug_walls
