import os
import cv2
import csv

def main():
    csv_file = "/home/cesar/Escritorio/UTEC/PFC1_Lima/forget-the-pixels/investigation/street_view/data_custom_route/gps.csv"
    img_dir = "/home/cesar/Escritorio/UTEC/PFC1_Lima/forget-the-pixels/investigation/street_view/data_custom_route/images"
    
    if not os.path.exists(csv_file):
        print(f"Error: No se encontró {csv_file}")
        return

    # Leer el orden exacto en el que fueron descargadas
    filenames = []
    with open(csv_file, 'r') as f:
        reader = csv.reader(f)
        next(reader) # Saltar cabecera
        for row in reader:
            filenames.append(row[0])

    print(f"Total de imágenes en la secuencia: {len(filenames)}")
    print("Controles: Presiona 'Enter' o cualquier tecla para avanzar. Presiona 'Q' para salir.")
    
    window_name = "Recorrido GSV (Simulacion de Video)"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, 1024, 1024)
    
    for i, fname in enumerate(filenames):
        img_path = os.path.join(img_dir, fname)
        if not os.path.exists(img_path):
            continue
        # Evitar mareos: Mostrar solo la vista frontal para simular manejo real
        if 'view0' not in fname:
            continue
            
        img = cv2.imread(img_path)
        if img is None: continue
        
        # Poner texto para saber cual es
        pano_id = fname.split('_')[0]
        view_id = fname.split('_')[1].replace('.jpg', '')
        text = f"[{i+1}/{len(filenames)}] Pano: {pano_id[:8]}... | Vista: {view_id}"
        cv2.putText(img, text, (30, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 0), 3)
        
        cv2.imshow(window_name, img)
        key = cv2.waitKey(0) & 0xFF
        if key == ord('q') or key == ord('Q'):
            break

    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
