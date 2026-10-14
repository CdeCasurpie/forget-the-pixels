"""Load, validate, and cache PBR texture sets from the on-disk catalog.

Paths in catalog.json are relative to the catalog file itself.
Resolution is done via catalog_path.resolve().parent / relative_path,
preserving all subdirectories.  Absolute paths in the cache key
guarantee deduplication regardless of the caller's working directory.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image

from domain.models import TextureSet


def find_project_root(start: str | Path | None = None,
                      max_up: int = 6) -> Path | None:
    """Nearest ancestor containing ``assets/pbr/catalog.json``.

    Deterministic and bounded: walks up at most ``max_up`` levels from
    ``start`` (default: this file, i.e. ``src/modeling/texturing/``) and
    returns the first directory holding the catalog, else None. No silent
    filesystem-wide search.
    """
    here = Path(start).resolve() if start else Path(__file__).resolve().parent
    for _ in range(max_up + 1):
        if (here / "assets" / "pbr" / "catalog.json").is_file():
            return here
        if here.parent == here:
            break
        here = here.parent
    return None


def default_catalog_path() -> Path | None:
    """The shipped PBR catalog, or None when the checkout lacks assets."""
    root = find_project_root()
    if root is None:
        return None
    return root / "assets" / "pbr" / "catalog.json"


class ValidationError(Exception):
    """Raised when a texture set fails integrity checks."""


class MaterialLibrary:
    def __init__(self, catalog_path: str | Path, *, validate: bool = True):
        self.catalog_path = Path(catalog_path).resolve()
        self.base_dir = self.catalog_path.parent
        self.texture_sets: dict[str, TextureSet] = {}
        self.image_cache: dict[str, Image.Image] = {}
        self.warnings: list[str] = []
        self._load_catalog(validate=validate)

    # ── Loading ──────────────────────────────────────────────────────

    def _load_catalog(self, *, validate: bool) -> None:
        if not self.catalog_path.exists():
            raise FileNotFoundError(f"Catalog not found: {self.catalog_path}")

        with open(self.catalog_path, "r") as fh:
            data = json.load(fh)

        for name, info in data.items():
            if name.startswith("hdri_"):
                continue  # HDRIs are not texture sets

            maps = info.get("maps", {})

            # Resolve every map path to an absolute path via base_dir
            resolved = {}
            for map_key, rel_path in maps.items():
                if not rel_path:
                    continue
                abs_path = self.base_dir / rel_path
                resolved[map_key] = str(abs_path)

            tset = TextureSet(
                name=name,
                base_color_path=resolved.get("base_color"),
                normal_path=resolved.get("normal"),
                orm_path=resolved.get("orm"),
                roughness_path=resolved.get("roughness"),
                metallic_path=resolved.get("metallic"),
                ao_path=resolved.get("ao"),
                scale_u=info.get("scale_u", 1.0),
                scale_v=info.get("scale_v", 1.0),
                normal_convention=info.get("normal_convention", "opengl"),
                provenance=info.get("provenance", "unknown"),
            )
            self.texture_sets[name] = tset

            if validate:
                self._validate_texture_set(name, tset, info)

    # ── Validation ───────────────────────────────────────────────────

    def _validate_texture_set(
        self, name: str, tset: TextureSet, catalog_info: dict
    ) -> None:
        """Check files exist, dimensions match, scales are positive, and
        SHA-256 hashes match the recorded metadata when present."""

        # Scale sanity
        if tset.scale_u <= 0 or tset.scale_v <= 0:
            raise ValidationError(
                f"{name}: scale_u={tset.scale_u}, scale_v={tset.scale_v} "
                "must be positive"
            )

        metadata = catalog_info.get("metadata", {})

        map_fields = {
            "base_color": tset.base_color_path,
            "normal": tset.normal_path,
            "orm": tset.orm_path,
            "roughness": tset.roughness_path,
            "metallic": tset.metallic_path,
            "ao": tset.ao_path,
        }

        for map_key, abs_path in map_fields.items():
            if abs_path is None:
                continue

            p = Path(abs_path)
            if not p.exists():
                raise ValidationError(
                    f"{name}/{map_key}: file not found: {abs_path}"
                )

            # Dimension check
            try:
                img = Image.open(p)
                w, h = img.size
            except Exception as exc:
                raise ValidationError(
                    f"{name}/{map_key}: cannot open image: {exc}"
                ) from exc

            expected_meta = metadata.get(map_key, {})
            expected_res = expected_meta.get("resolution")
            if expected_res and [w, h] != expected_res:
                raise ValidationError(
                    f"{name}/{map_key}: resolution {[w,h]} != "
                    f"expected {expected_res}"
                )

            # SHA-256 check
            expected_sha = expected_meta.get("sha256")
            if expected_sha:
                actual_sha = hashlib.sha256(p.read_bytes()).hexdigest()
                if actual_sha != expected_sha:
                    raise ValidationError(
                        f"{name}/{map_key}: SHA-256 mismatch\n"
                        f"  expected: {expected_sha}\n"
                        f"  actual:   {actual_sha}"
                    )

            img.close()

    # ── Accessors ────────────────────────────────────────────────────

    def get_texture_set(self, name: str) -> TextureSet | None:
        return self.texture_sets.get(name)

    def get_image(self, path: str | None) -> Image.Image | None:
        """Load an image by its absolute path, with caching."""
        if not path:
            return None

        # Canonicalize the key
        abs_key = str(Path(path).resolve())

        if abs_key in self.image_cache:
            return self.image_cache[abs_key]

        p = Path(abs_key)
        if not p.exists():
            self.warnings.append(f"Image not found: {abs_key}")
            return None

        try:
            img = Image.open(p)
            img.load()
            self.image_cache[abs_key] = img
            return img
        except Exception as exc:
            self.warnings.append(f"Error loading {abs_key}: {exc}")
            return None

    def load_all_maps(self, name: str) -> dict[str, Image.Image]:
        """Load every available map for the named texture set."""
        tset = self.get_texture_set(name)
        if tset is None:
            return {}
        result = {}
        for key in ("base_color", "normal", "orm", "roughness", "metallic", "ao"):
            path = getattr(tset, f"{key}_path", None)
            img = self.get_image(path)
            if img is not None:
                result[key] = img
        return result

    def clear_cache(self) -> None:
        self.image_cache.clear()
