import sys; sys.path.insert(0, 'src')
import procedural_modeling.v4_grammar
original = procedural_modeling.v4_grammar.facade
def hook(mb, f, bh):
    print(f"FACADE: a={f.vertex_a}, n={f.normal_xy}")
    original(mb, f, bh)
procedural_modeling.v4_grammar.facade = hook
import debug_walls
