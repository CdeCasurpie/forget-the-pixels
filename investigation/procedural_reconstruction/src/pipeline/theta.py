"""Public Step18 interface. Observation/evidence never modifies geometry implicitly."""
from dataclasses import asdict, dataclass
from domain.theta import ReconstructionRequest, decode
from domain.models import MeshData
from modeling.theta import ResolvedArchitecture, resolve_theta, generate_resolved, generate_from_theta


@dataclass(frozen=True)
class ReconstructionResult:
    requested: ReconstructionRequest
    resolved: ResolvedArchitecture
    mesh: MeshData


def reconstruct(request: ReconstructionRequest) -> ReconstructionResult:
    request = decode(ReconstructionRequest, asdict(request))
    views = [v.view_id for v in request.observations]
    if len(set(views)) != len(views):
        raise ValueError("Duplicate observation view_id")
    values = asdict(request.theta)
    for path, evidence in request.evidence.items():
        if evidence.state not in ("observed", "inferred", "unknown", "externally_known"):
            raise ValueError(f"Invalid evidence state: {path}")
        if evidence.confidence is not None and not 0 <= evidence.confidence <= 1:
            raise ValueError(f"Invalid confidence: {path}")
        if set(evidence.view_ids)-set(views):
            raise ValueError(f"Evidence references missing views: {path}")
        value = values
        try:
            for key in path.split("."):
                value = value[int(key)] if isinstance(value, (list,tuple)) else value[key]
        except (KeyError, IndexError, ValueError, TypeError) as exc:
            raise ValueError(f"Invalid evidence path: {path}") from exc
        if evidence.state == "unknown" and value is not None:
            raise ValueError(f"unknown evidence must reference a null value: {path}")
        if evidence.state in ("observed", "externally_known") and value is None:
            raise ValueError(f"Known evidence must have a value: {path}")
    resolved = resolve_theta(request.context, request.theta)
    mesh = generate_resolved(resolved, request.nuisance, request.config)
    return ReconstructionResult(request, resolved, mesh)
