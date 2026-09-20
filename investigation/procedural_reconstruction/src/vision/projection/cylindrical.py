"""Extracción de franjas angulares desde panoramas equirectangulares."""

from __future__ import annotations

import cv2
import numpy as np


def extract_full_vertical_strip(
    panorama: np.ndarray,
    center_yaw_deg: float,
    horizontal_fov_deg: float = 120.0,
    width: int = 1600,
    height: int | None = None,
) -> np.ndarray:
    """Extrae una franja centrada en ``center_yaw_deg`` de nadir a cenit.

    La longitud horizontal y la latitud vertical se muestrean linealmente. Es
    la variante angular de una proyección cilíndrica y, a diferencia del
    cilindro tangente clásico, puede representar los polos ±90° sin divergir.

    ``center_yaw_deg`` es relativo al centro original de la equirectangular:
    positivo hacia la derecha y negativo hacia la izquierda.
    """
    if not 0.0 < horizontal_fov_deg <= 360.0:
        raise ValueError("horizontal_fov_deg debe estar en (0, 360]")
    if width <= 0:
        raise ValueError("width debe ser positivo")
    if height is None:
        height = max(1, round(width * 180.0 / horizontal_fov_deg))

    pano_h, pano_w = panorama.shape[:2]
    horizontal_offsets = np.linspace(
        -horizontal_fov_deg / 2.0,
        horizontal_fov_deg / 2.0,
        width,
        endpoint=False,
        dtype=np.float32,
    )
    source_x = (
        0.5 + (center_yaw_deg + horizontal_offsets) / 360.0
    ) * pano_w
    source_x = np.mod(source_x, pano_w)

    # La equirectangular ya representa cenit en la fila superior y nadir en
    # la inferior. El muestreo completo conserva exactamente ese intervalo.
    source_y = np.linspace(0.0, pano_h - 1.0, height, dtype=np.float32)
    map_x, map_y = np.meshgrid(source_x, source_y)
    return cv2.remap(
        panorama,
        map_x,
        map_y,
        interpolation=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_WRAP,
    )
