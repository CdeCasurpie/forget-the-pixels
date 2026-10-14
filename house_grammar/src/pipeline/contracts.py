from dataclasses import dataclass
from typing import Any
from domain.architecture import SitePlan, BuildingSpecificationV4

@dataclass(frozen=True)
class BuildingRequest:
    lot: Any
    context: Any
    evidence: Any
    preferences: dict
    seed: int

@dataclass(frozen=True)
class GenerationReport:
    accepted_features: list[str]
    rejected_features: list[str]
    fallback_reasons: dict[str, str]

def propose_site(request: BuildingRequest, config: Any) -> SitePlan:
    raise NotImplementedError("Phase 2")
    
def resolve_building(plan: SitePlan, evidence: Any) -> BuildingSpecificationV4:
    raise NotImplementedError("Phase 3")
