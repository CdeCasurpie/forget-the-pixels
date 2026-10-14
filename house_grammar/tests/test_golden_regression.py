"""Golden regression tests for generate_v4_mesh output.

These tests capture the *current* verified mesh output for representative
building specifications. During the planned refactoring this file is the
primary regression gate: a single failing assertion means geometry changed
unexpectedly.

Strategy
--------
- Each golden case is a self-contained ``BuildingSpecificationV4`` built with
  ``_make_spec``.  When output changes intentionally, run
  ``REBUILD_GOLDENS=true pytest tests/test_golden_regression.py`` to
  regenerate the fixture file.
- Hashes are ``SHA-256`` over concatenated ``vertices.tobytes() + faces.tobytes()``
  so floating-point round-trip is irrelevant: the same computation always
  produces the same bytes.
- ``components`` identity is asserted by semantic set + count, which is
  stable under code-cleanup refactors that don't change behaviour.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

import numpy as np
import pytest
from shapely.geometry import Polygon

# ---------------------------------------------------------------------------
# Path setup (mirrors test_detail.py)
# ---------------------------------------------------------------------------
_HERE = Path(__file__).resolve().parent
_SRC = _HERE.parent / "src"
_STEPS = _HERE.parent / "steps"
for _p in (_SRC, _STEPS, _HERE):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from domain.architecture import (  # noqa: E402
    BuildingProgram,
    BuildingSpecificationV4,
    MassSpec,
    ParcelContext,
    SitePlan,
)
from modeling.grammar import generate_v4_mesh  # noqa: E402

_FIXTURE_PATH = _HERE / "fixtures" / "golden_regression_hashes.json"
_REBUILD = os.environ.get("REBUILD_GOLDENS") == "true"

# ===========================================================================
# Spec factories
# ===========================================================================

LOT_1 = ((-5.0, -10.0), (5.0, -10.0), (5.0, 10.0), (-5.0, 10.0), (-5.0, -10.0))


def _make_spec(
    *,
    floors: int = 4,
    language: str = "balcony_apartments",
    finish: str = "premium",
    lot: tuple[tuple[float, float], ...] | None = None,
    seed: int = 7,
) -> BuildingSpecificationV4:
    """Return a minimal, deterministic ``BuildingSpecificationV4``."""
    lot = lot or LOT_1
    levels = tuple(float(i * 2.8) for i in range(floors + 1))
    mass = MassSpec(
        id="main",
        footprint=lot,
        base_z=0.0,
        roof_z=floors * 2.8,
        floor_levels=levels,
        role="tower",
        roof_spec=None,
    )
    return BuildingSpecificationV4(
        context=ParcelContext(polygon=lot, explicit_fronts=(0,)),
        program=BuildingProgram(
            use="residential",
            occupancy="medium",
            placement="flush",
            architectural_language=language,
            finish_profile=finish,
            maintenance="average",
            construction_state="completed",
            seed=seed,
            primary_color=(0.85, 0.84, 0.78),
            side_wall_finish="raw",
            has_fence=False,
            fence_type="none",
        ),
        site_plan=SitePlan(
            masses=(mass,),
            free_space=(),
            access_nodes=(),
            boundaries=(),
            exclusion_zones=(),
        ),
        facades=(),
        components=(),
        seed=seed,
    )


# ===========================================================================
# Golden cases — add / remove here when the spec matrix changes
# ===========================================================================

CASES: dict[str, BuildingSpecificationV4] = {
    # Base: 4-floor balcony_apartments, premium finish
    "balcony_4f_premium": _make_spec(floors=4, language="balcony_apartments", finish="premium"),
    # 2-floor quiet_house, standard finish
    "quiet_2f_standard": _make_spec(floors=2, language="quiet_house", finish="standard"),
    # 6-floor dense apartment
    "dense_6f": _make_spec(floors=6, language="dense_apartment", finish="premium"),
    # Heritage family triggers cornice / pilaster semantics
    "heritage_3f": _make_spec(floors=3, language="heritage", finish="premium"),
    # Plain lot shape (square) — exercises clipping path differently
    "square_lot": _make_spec(
        floors=3,
        lot=((-5.0, -5.0), (5.0, -5.0), (5.0, 5.0), (-5.0, 5.0), (-5.0, -5.0)),
    ),
}


# ===========================================================================
# Helpers
# ===========================================================================

def _mesh_hash(mesh) -> str:
    """SHA-256 of the vertex and face byte streams."""
    h = hashlib.sha256()
    h.update(np.ascontiguousarray(mesh.vertices).tobytes())
    h.update(np.ascontiguousarray(mesh.faces).tobytes())
    if mesh.face_materials is not None:
        h.update(np.ascontiguousarray(mesh.face_materials).tobytes())
    return h.hexdigest()


def _semantic_summary(mesh) -> dict[str, int]:
    """Count faces per semantic tag."""
    counts: dict[str, int] = {}
    for part in mesh.parts:
        tag = part.get("name", "unknown")
        # faces are referenced by index range or count
        face_count = part.get("face_count") or part.get("count") or 1
        counts[tag] = counts.get(tag, 0) + face_count
    return counts


def _load_expected() -> dict:
    if not _FIXTURE_PATH.exists():
        return {}
    return json.loads(_FIXTURE_PATH.read_text())


def _save_fixture(expected: dict) -> None:
    _FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _FIXTURE_PATH.write_text(json.dumps(expected, indent=2, sort_keys=True) + "\n")


# ===========================================================================
# Tests
# ===========================================================================

class TestGoldenRegression:
    """All golden cases run as parameterised tests below."""

    @staticmethod
    @pytest.mark.parametrize("case_name", list(CASES.keys()))
    def test_mesh_hash_is_frozen(case_name: str) -> None:
        """Mesh vertex+face hash must match the stored golden hash."""
        spec = CASES[case_name]
        mesh = generate_v4_mesh(spec)
        actual_hash = _mesh_hash(mesh)

        expected = _load_expected().get(case_name, {}).get("mesh_hash")

        if _REBUILD:
            # Regenerate mode: write current hash, skip assertion
            all_expected = _load_expected()
            all_expected.setdefault(case_name, {})["mesh_hash"] = actual_hash
            _save_fixture(all_expected)
            pytest.skip(f"rebuilt golden for {case_name}: {actual_hash[:16]}...")

        assert actual_hash == expected, (
            f"[{case_name}] mesh hash changed.\n"
            f"  expected: {expected[:16]}...\n"
            f"  actual:   {actual_hash[:16]}...\n"
            f"  Set REBUILD_GOLDENS=true to accept new output."
        )

    @staticmethod
    @pytest.mark.parametrize("case_name", list(CASES.keys()))
    def test_component_semantics_are_stable(case_name: str) -> None:
        """The set of semantic tags and their face counts must be stable.

        Unlike the raw hash, this assertion survives vertex-order changes
        from unrelated refactors (e.g. reordering component emission).
        """
        spec = CASES[case_name]
        mesh = generate_v4_mesh(spec)
        actual_summary = _semantic_summary(mesh)

        expected = _load_expected().get(case_name, {}).get("semantic_summary")

        if _REBUILD:
            all_expected = _load_expected()
            all_expected.setdefault(case_name, {})["semantic_summary"] = actual_summary
            _save_fixture(all_expected)
            return

        assert actual_summary == expected, (
            f"[{case_name}] semantic summary changed.\n"
            f"  expected: {expected}\n"
            f"  actual:   {actual_summary}\n"
            f"  Set REBUILD_GOLDENS=true to accept new output."
        )

    @staticmethod
    def test_golden_fixture_file_exists() -> None:
        """Sanity: the fixture file must be tracked in git."""
        assert _FIXTURE_PATH.exists(), (
            f"Golden fixture missing at {_FIXTURE_PATH}. "
            f"Run with REBUILD_GOLDENS=true to create it."
        )

    @staticmethod
    def test_all_golden_cases_have_both_keys() -> None:
        """Every case in the fixture must have both keys populated."""
        fixture = _load_expected()
        for case_name in CASES:
            assert case_name in fixture, f"Missing case '{case_name}' in fixture"
            assert "mesh_hash" in fixture[case_name], f"mesh_hash missing for {case_name}"
            assert "semantic_summary" in fixture[case_name], (
                f"semantic_summary missing for {case_name}"
            )


# ===========================================================================
# Entry-point: rebuild fixture when env-var is set
# ===========================================================================

if _REBUILD:
    print(f"\n=== REBUILD_GOLDENS: regenerating {_FIXTURE_PATH} ===")
    for name, spec in CASES.items():
        mesh = generate_v4_mesh(spec)
        entry = {
            "mesh_hash": _mesh_hash(mesh),
            "semantic_summary": _semantic_summary(mesh),
        }
        existing = _load_expected()
        existing[name] = entry
        _save_fixture(existing)
        print(f"  {name}: {entry['mesh_hash'][:16]}...  ({len(mesh.vertices)} verts, {len(mesh.faces)} faces)")
    print("=== done ===\n")
