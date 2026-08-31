import os
import json
from streetlevel import streetview

def download_panos(lat, lon, count=15):
    print(f"Buscando panorama inicial en {lat}, {lon}...")
    pano = streetview.find_panorama(lat, lon)
    if not pano:
        print("Error: No se encontró panorama.")
        return

    target_year = pano.date.year
    full_pano = streetview.find_panorama_by_id(pano.id)
    
    valid_panos = [full_pano]
    seen_ids = {full_pano.id}
    queue = [full_pano]
    
    print(f"Recolectando hasta {count} panoramas del {target_year}...")
    while queue and len(valid_panos) < count:
        current = queue.pop(0)
        for n in current.neighbors:
            if len(valid_panos) >= count:
                break
            if n.id not in seen_ids:
                seen_ids.add(n.id)
                full_n = streetview.find_panorama_by_id(n.id)
                if full_n and full_n.date and full_n.date.year == target_year:
                    valid_panos.append(full_n)
                    queue.append(full_n)

    print(f"Se recolectaron {len(valid_panos)} panoramas.")
    
    out_dir = "data/imagenes_gsv_ampliado"
    os.makedirs(out_dir, exist_ok=True)
    
    metadata = {}
    for i, p in enumerate(valid_panos):
        filename = os.path.join(out_dir, f"{i:03d}_{p.id}.jpg")
        print(f"[{i+1}/{len(valid_panos)}] Descargando {p.id}...")
        streetview.download_panorama(p, filename)
        
        metadata[f"{i:03d}_{p.id}"] = {
            "lat": p.lat,
            "lon": p.lon,
            "heading": p.heading
        }
        
    with open(os.path.join(out_dir, "metadata.json"), "w") as f:
        json.dump(metadata, f, indent=4)
        
    print("¡Descarga completada con metadata!")

if __name__ == "__main__":
    download_panos(-12.135862, -77.021966, count=15)
