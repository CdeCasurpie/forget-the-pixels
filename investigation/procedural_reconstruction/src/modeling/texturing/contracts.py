"""Input contract reserved for texture generation after procedural geometry exists."""
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FacadeTextureRequest:
    edge_index: int
    pano_id: str
    source_image: Path
    facade_corners_xy: tuple[tuple[float, float], tuple[float, float]]
    height_m: float
    target_yaw_deg: float
