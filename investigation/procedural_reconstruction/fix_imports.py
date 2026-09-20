with open('src/procedural_modeling/grammar.py', 'r') as f:
    lines = f.readlines()

imports_to_add = """from domain.architecture import BuildingSpecificationV4
from domain.models import FacadeSpecification, Opening, RoofSpecification
from procedural_modeling.exposure import calculate_mass_exposures
from procedural_modeling.materials import appearance_for_style
from procedural_modeling.mesh_builder import MeshData
"""

lines.insert(11, imports_to_add)

with open('src/procedural_modeling/grammar.py', 'w') as f:
    f.writelines(lines)
