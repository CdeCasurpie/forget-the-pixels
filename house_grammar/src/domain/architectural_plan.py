"""Serializable massing IR, independent of the legacy theta request."""
from dataclasses import asdict, dataclass, field


class PlanningError(ValueError):
    def __init__(self, code, path, message):
        self.code, self.path = code, path
        super().__init__(f'{code} at {path}: {message}')


@dataclass
class MassingPlan:
    version: str
    request: dict
    fronts: dict
    storeys: list[dict]
    supports: list[dict]
    site: dict
    operations: list[dict]
    decisions: list[dict]
    pending: list[dict]
    checks: dict = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)
