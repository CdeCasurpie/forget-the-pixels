#!/usr/bin/env python3
"""Entrada ejecutable del Paso 1 usando el módulo común de adquisición."""

from __future__ import annotations

import sys
from pathlib import Path


SRC = Path(__file__).resolve().parents[2] / "src"
sys.path.insert(0, str(SRC))

from gsv_acquisition.acquisition import main  # noqa: E402


if __name__ == "__main__":
    main()

