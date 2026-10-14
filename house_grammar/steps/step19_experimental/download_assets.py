import os
import json
import urllib.request
import urllib.error
from pathlib import Path
import hashlib

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets" / "pbr"
ASSETS_DIR.mkdir(parents=True, exist_ok=True)

ASSETS = {
    "stucco_rough": "plaster_rough_01",
    "concrete_fine": "concrete_layers_01",
    "brick_red": "red_bricks_04",
    "wood_planks": "wood_planks",
    "metal_corrugated": "corrugated_iron_02",
    "pavement": "cobblestone_large_01"
}

def get_files(asset_id):
    url = f"https://api.polyhaven.com/files/{asset_id}"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode())
    except urllib.error.URLError as e:
        print(f"Error fetching {asset_id}: {e}")
        return None

def download_file(url, dest):
    print(f"Downloading {url} to {dest}...")
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as response:
        content = response.read()
    with open(dest, 'wb') as f:
        f.write(content)
    return hashlib.sha256(content).hexdigest()

catalog = {}

# Some assets might have 404, let's search via API if 404
def search_asset(query):
    url = f"https://api.polyhaven.com/assets?s={query}"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            if data: return list(data.keys())[0]
    except Exception: pass
    return None

for name, asset_id in ASSETS.items():
    print(f"\nProcessing {name} ({asset_id})...")
    files_data = get_files(asset_id)
    if not files_data:
        # try searching
        print("Trying to search...")
        new_id = search_asset(asset_id.split('_')[0])
        if new_id:
            asset_id = new_id
            print(f"Found {asset_id}")
            files_data = get_files(asset_id)
            
    if not files_data: continue
    
    asset_dir = ASSETS_DIR / name
    asset_dir.mkdir(exist_ok=True)
    
    maps = {}
    target_res = '1k'
    
    for map_type in ["Diffuse", "AO", "Rough", "nor_gl", "arm", "metallic", "Metalness"]:
        if map_type in files_data:
            res_data = files_data[map_type]
            # find resolution
            res = target_res if target_res in res_data else list(res_data.keys())[0]
            format_data = res_data[res]
            fmt = 'jpg' if 'jpg' in format_data else list(format_data.keys())[0]
            url = format_data[fmt]['url']
            
            filename = f"{name}_{map_type}.{fmt}"
            dest = asset_dir / filename
            
            if not dest.exists():
                download_file(url, dest)
                
            maps[map_type.lower()] = str(dest)
        
    catalog[name] = {
        "id": asset_id,
        "maps": maps,
        "scale_u": 2.0,
        "scale_v": 2.0,
        "normal_convention": "opengl"
    }

with open(ASSETS_DIR / "catalog.json", "w") as f:
    json.dump(catalog, f, indent=2)

print("Download complete.")
