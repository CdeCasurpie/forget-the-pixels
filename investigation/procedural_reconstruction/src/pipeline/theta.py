"""Public Step18 interface. Observation/evidence never modifies geometry implicitly."""
from dataclasses import asdict, dataclass
import re
from shapely.geometry import Polygon
from domain.theta import ReconstructionRequest, decode
from domain.models import MeshData
from modeling.theta import ResolvedArchitecture, resolve_theta, generate_resolved, generate_from_theta


@dataclass(frozen=True)
class ReconstructionResult:
    requested: ReconstructionRequest
    resolved: ResolvedArchitecture
    mesh: MeshData


def _evidence_value(theta, path):
    """Stable selectors; list positions are intentionally not evidence IDs."""
    if path.startswith("theta."):
        path=path[6:]
    parts=re.split(r"\.(?![^\[]*\])",path)
    value=asdict(theta)
    for part in parts:
        match=re.fullmatch(r"([a-z_]+)\[([^\]]+)\]",part)
        if not match:
            if not isinstance(value,dict) or part not in value:
                raise ValueError(f"Invalid evidence path: {path}")
            value=value[part]
            continue
        name,selector=match.groups()
        if not isinstance(value,dict) or name not in value or value[name] is None:
            raise ValueError(f"Invalid evidence selector: {path}")
        entries=value[name]
        if name=='facades':
            ref,sep,edge=selector.partition(',edge:')
            if not sep or not edge.isdigit():
                raise ValueError(f"Invalid facade selector: {path}")
            matches=[x for x in entries if x['mass_role']==ref and x['edge']==int(edge)]
        elif name=='roofs':
            matches=[x for x in entries if x['mass_ref']==selector]
        elif name=='opening_edits':
            match_edit=re.fullmatch(r'floor:(\d+),bay:(\d+)',selector)
            if not match_edit:
                raise ValueError(f"Invalid opening edit selector: {path}")
            floor,bay=map(int,match_edit.groups())
            matches=[x for x in entries if x['floor']==floor and x['bay']==bay]
        elif name=='masses':
            ordered=sorted(entries,key=lambda x:(x['role'],round(Polygon(x['footprint']).centroid.x,6),
                         round(Polygon(x['footprint']).centroid.y,6),round(x['levels_m'][0],6),
                         round(Polygon(x['footprint']).area,6),tuple(map(tuple,x['footprint'])),tuple(x['levels_m'])))
            counts={}
            keys={}
            for item in ordered:
                role=item['role']; index=counts.get(role,0); counts[role]=index+1
                keys[f'{role}:{index}']=item
            matches=[keys[selector]] if selector in keys else []
        else:
            raise ValueError(f"Unsupported evidence selector: {name}")
        if len(matches)!=1:
            raise ValueError(f"Evidence selector is missing or ambiguous: {path}")
        value=matches[0]
    return value


def reconstruct(request: ReconstructionRequest) -> ReconstructionResult:
    request = decode(ReconstructionRequest, asdict(request))
    views = [v.view_id for v in request.observations]
    if len(set(views)) != len(views):
        raise ValueError("Duplicate observation view_id")
    for path, evidence in request.evidence.items():
        if evidence.state not in ("observed", "inferred", "unknown", "externally_known"):
            raise ValueError(f"Invalid evidence state: {path}")
        if evidence.confidence is not None and not 0 <= evidence.confidence <= 1:
            raise ValueError(f"Invalid confidence: {path}")
        if set(evidence.view_ids)-set(views):
            raise ValueError(f"Evidence references missing views: {path}")
        value = _evidence_value(request.theta,path)
        if evidence.state == "unknown" and value is not None:
            raise ValueError(f"unknown evidence must reference a null value: {path}")
        if evidence.state in ("observed", "externally_known") and value is None:
            raise ValueError(f"Known evidence must have a value: {path}")
    resolved = resolve_theta(request.context, request.theta)
    mesh = generate_resolved(resolved, request.nuisance, request.config)
    return ReconstructionResult(request, resolved, mesh)
