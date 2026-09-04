import os
import json
import cv2
import numpy as np
import streetlevel.streetview as sv
import csv

def main():
    route_file = "/home/cesar/Escritorio/UTEC/PFC1_Lima/forget-the-pixels/custom_route.json"
    out_dir = "/home/cesar/Escritorio/UTEC/PFC1_Lima/forget-the-pixels/investigation/street_view/data_pano_route/images"
    os.makedirs(out_dir, exist_ok=True)
    
    with open(route_file, 'r') as f:
        route = json.load(f)
        
    print(f"Descargando ruta de {len(route)} panoramas crudos (360)...")
    
    metadata = {}
    for i, p_info in enumerate(route):
        pid = p_info['id']
        print(f"[{i+1}/{len(route)}] Procesando {pid}...")
        
        full_p = sv.find_panorama_by_id(pid)
        img_pil = sv.get_panorama(full_p, zoom=2)
        img_cv2 = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
        
        # Ocultar el carro
        h, w = img_cv2.shape[:2]
        img_cv2[int(h*0.75):, :] = 0
        
        out_name = os.path.join(out_dir, f"{pid}.jpg")
        cv2.imwrite(out_name, img_cv2)
        
        metadata[f"{pid}.jpg"] = {
            "lat": p_info['lat'],
            "lon": p_info['lon'],
            "alt": 100.0
        }
            
    csv_file = "/home/cesar/Escritorio/UTEC/PFC1_Lima/forget-the-pixels/investigation/street_view/data_pano_route/gps.csv"
    with open(csv_file, "w", newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["filename", "lat", "lon", "alt"])
        for fname, m in metadata.items():
            writer.writerow([fname, m["lat"], m["lon"], m["alt"]])
            
if __name__ == "__main__":
    main()
