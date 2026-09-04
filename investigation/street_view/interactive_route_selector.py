import cv2
import numpy as np
import streetlevel.streetview as sv
import json
import math
import asyncio
import time

async def fetch_tile_panos_async(lat, lon, target_year):
    print("Descargando tile de cobertura global (Estilo Google Maps)...")
    start = time.time()
    # Descargar todos los puntos del tile
    panos_tile = sv.get_coverage_tile_by_latlon(lat, lon)
    print(f"Tile descargado en {time.time()-start:.2f}s. Encontrados {len(panos_tile)} panoramas brutos.")
    
    print("Filtrando asincronamente el historial para el año", target_year, "...")
    start = time.time()
    async with sv.ClientSession() as session:
        tasks = [sv.find_panorama_by_id_async(p.id, session) for p in panos_tile]
        results = await asyncio.gather(*tasks)
        
    valid_panos = []
    for r in results:
        if not r: continue
        if r.date and r.date.year == target_year:
            valid_panos.append(r)
        else:
            # Buscar en el historial
            for hist in r.historical:
                if hist.date.year == target_year:
                    valid_panos.append(hist)
                    break
                    
    print(f"Filtrado instantaneo completado en {time.time()-start:.2f}s. {len(valid_panos)} panoramas utiles de {target_year}.")
    return valid_panos

def main():
    lat_center = -12.137248
    lon_center = -77.020423
    target_year = 2022
    
    # Ejecutar async
    panos = asyncio.run(fetch_tile_panos_async(lat_center, lon_center, target_year))
    
    if not panos:
        print("No se encontraron panoramas.")
        return
    
    # Normalizar coordenadas para dibujarlas en una ventana 1000x1000
    lats = [p.lat for p in panos]
    lons = [p.lon for p in panos]
    
    min_lat, max_lat = min(lats), max(lats)
    min_lon, max_lon = min(lons), max(lons)
    
    W, H = 1000, 1000
    margin = 50
    points_px = []
    for p_obj in panos:
        x = int(margin + (p_obj.lon - min_lon) / (max_lon - min_lon + 1e-9) * (W - 2*margin))
        y = int(H - margin - (p_obj.lat - min_lat) / (max_lat - min_lat + 1e-9) * (H - 2*margin))
        points_px.append((x, y, p_obj))
        
    selected_panos = []
    selected_pts = []
    
    def mouse_callback(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            closest = None
            min_dist = float('inf')
            for px, py, p_obj in points_px:
                dist = math.hypot(px - x, py - y)
                if dist < min_dist:
                    min_dist = dist
                    closest = (px, py, p_obj)
            
            if closest and min_dist < 30:
                if len(selected_panos) == 0 or selected_panos[-1].id != closest[2].id:
                    selected_panos.append(closest[2])
                    selected_pts.append((closest[0], closest[1]))
                    print(f"Seleccionado: {closest[2].id} ({len(selected_panos)} nodos)")
    
    window_name = "Creador de Rutas GSV (Carga Ultra Rapida)"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.setMouseCallback(window_name, mouse_callback)
    
    while True:
        img = np.ones((H, W, 3), dtype=np.uint8) * 30 
        
        for px, py, p_obj in points_px:
            cv2.circle(img, (px, py), 4, (200, 150, 50), -1)
            
        if len(selected_pts) > 0:
            for i in range(len(selected_pts) - 1):
                cv2.line(img, selected_pts[i], selected_pts[i+1], (0, 255, 0), 2)
            for pt in selected_pts:
                cv2.circle(img, pt, 6, (0, 255, 255), -1)
                
        cv2.putText(img, "Haz click en los puntos para armar tu ruta cronologica (2022).", (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.putText(img, f"Seleccionados: {len(selected_panos)}", (20, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.putText(img, "Presiona ENTER para guardar y salir.", (20, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 1)
        
        cv2.imshow(window_name, img)
        key = cv2.waitKey(20) & 0xFF
        if key == 13 or key == ord('q'):
            break
            
    cv2.destroyAllWindows()
    
    if len(selected_panos) > 0:
        out_data = [{"id": p.id, "lat": p.lat, "lon": p.lon, "heading": p.heading} for p in selected_panos]
        with open('custom_route.json', 'w') as f:
            json.dump(out_data, f, indent=4)
        print(f"\nRuta guardada exitosamente en custom_route.json con {len(selected_panos)} panoramas.")
    else:
        print("\nNo se selecciono ningun punto.")

if __name__ == "__main__":
    main()
