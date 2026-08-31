import os
from streetlevel import streetview

def download_5_panos(lat, lon):
    print(f"Buscando el panorama principal cerca de {lat}, {lon}...")
    pano = streetview.find_panorama(lat, lon)
    if not pano:
        print("Error: No se encontró ningún panorama.")
        return

    target_year = pano.date.year
    print(f"Año objetivo encontrado: {target_year}.")

    # Obtenemos la metadata completa del panorama principal
    full_pano = streetview.find_panorama_by_id(pano.id)
    
    valid_panos = [full_pano]
    seen_ids = {full_pano.id}
    
    # Cola para búsqueda en anchura (BFS) por la calle
    queue = [full_pano]
    
    print("Recorriendo la calle mediante la metadata de vecinos (BFS)...")
    while queue and len(valid_panos) < 5:
        current = queue.pop(0)
        for n in current.neighbors:
            if len(valid_panos) >= 5:
                break
            if n.id not in seen_ids:
                seen_ids.add(n.id)
                # Obtenemos la info completa del vecino para asegurar que tenemos la fecha real
                full_n = streetview.find_panorama_by_id(n.id)
                if full_n and full_n.date and full_n.date.year == target_year:
                    valid_panos.append(full_n)
                    queue.append(full_n)

    print(f"\nSe recolectaron {len(valid_panos)} panoramas válidos del año {target_year}.")
    
    out_dir = "imagenes_gsv"
    os.makedirs(out_dir, exist_ok=True)
    
    for i, p in enumerate(valid_panos):
        filename = os.path.join(out_dir, f"barranco_{target_year}_{i+1}_{p.id}.jpg")
        print(f"[{i+1}/5] Descargando panorama {p.id} en alta resolución...")
        streetview.download_panorama(p, filename)
    
    print("\n¡Descarga completada con éxito! Las imágenes están en la carpeta 'imagenes_gsv'.")

if __name__ == "__main__":
    LATITUDE = -12.135862
    LONGITUDE = -77.021966
    download_5_panos(LATITUDE, LONGITUDE)
