import json
from pathlib import Path
from PIL import Image
import numpy as np

from domain.models import TextureSet

class MaterialLibrary:
    def __init__(self, catalog_path: str | Path):
        self.catalog_path = Path(catalog_path)
        self.base_dir = self.catalog_path.parent
        self.texture_sets = {}
        self.image_cache = {}
        self._load_catalog()
        
    def _load_catalog(self):
        if not self.catalog_path.exists():
            print(f"Warning: Catalog not found at {self.catalog_path}")
            return
            
        with open(self.catalog_path, "r") as f:
            data = json.load(f)
            
        for name, info in data.items():
            maps = info.get("maps", {})
            # Resolve absolute paths or relative to catalog
            def resolve(p):
                if not p: return None
                pp = Path(p)
                if pp.is_absolute(): return str(pp)
                return str(self.base_dir / pp.name) # simplified
                
            tset = TextureSet(
                name=name,
                base_color_path=maps.get("diffuse"),
                normal_path=maps.get("nor_gl"),
                orm_path=maps.get("arm"),
                roughness_path=maps.get("rough"),
                metallic_path=maps.get("metallic"),
                ao_path=maps.get("ao"),
                scale_u=info.get("scale_u", 1.0),
                scale_v=info.get("scale_v", 1.0),
                normal_convention=info.get("normal_convention", "opengl"),
                provenance=info.get("id", "unknown")
            )
            self.texture_sets[name] = tset
            
    def get_texture_set(self, name: str) -> TextureSet | None:
        return self.texture_sets.get(name)
        
    def get_image(self, path: str) -> Image.Image | None:
        if not path:
            return None
        if path in self.image_cache:
            return self.image_cache[path]
            
        p = Path(path)
        if not p.exists():
            p = self.base_dir / p.name
        if not p.exists():
            print(f"Warning: Image not found {path}")
            return None
            
        try:
            img = Image.open(p)
            img.load()
            self.image_cache[path] = img
            return img
        except Exception as e:
            print(f"Error loading image {path}: {e}")
            return None
            
    def clear_cache(self):
        self.image_cache.clear()
