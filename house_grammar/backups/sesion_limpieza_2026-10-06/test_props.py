import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path("src").resolve()))
from domain.theta import ReconstructionContext, ThetaCandidate, GrammarConfig, NuisanceParameters, decode
from modeling.theta import resolve_theta

path = Path("steps/step18_theta_interface/examples/04_mixed.json")
data = json.loads(path.read_text())
ctx = decode(ReconstructionContext, data["context"])
cand = decode(ThetaCandidate, data["theta"])
nuisance = NuisanceParameters(seed=0)
config = GrammarConfig(detail=3)
resolved = resolve_theta(ctx, cand)
print("Roofs:")
for r in resolved.roofs:
    print(f"  {r.mass_id}: {len(r.props)} props, surfaces: {r.surfaces[0].kind if r.surfaces else 'None'}")
