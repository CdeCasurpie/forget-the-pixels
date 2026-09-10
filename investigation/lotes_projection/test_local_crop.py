import os
import json
import random
import cv2
import matplotlib.pyplot as plt
import matplotlib.patches as patches

def main():
    DIR_BASE = os.path.dirname(os.path.abspath(__file__))
    JSON_PATH = os.path.join(DIR_BASE, "crops_metadata.json")
    IMG_DIR = os.path.join(DIR_BASE, "../Lotes/images")

    if not os.path.exists(JSON_PATH):
        print("\033[91m[ERROR]\033[0m No se encontró crops_metadata.json. ¡Asegúrate de ejecutar 'make export-crops' primero!")
        return

    print("-> Leyendo metadatos...")
    with open(JSON_PATH, 'r') as f:
        metadata = json.load(f)

    if not metadata:
        print("[ERROR] El archivo JSON está vacío.")
        return

    # Elegir una imagen aleatoria
    img_names = list(metadata.keys())
    random_img_name = random.choice(img_names)
    lots_in_img = metadata[random_img_name]
    
    # Elegir un lote aleatorio de esa imagen
    random_lot = random.choice(lots_in_img)
    lot_id = random_lot['lot_id']
    bbox = random_lot['bbox'] # [xmin, ymin, xmax, ymax]
    
    img_path = os.path.join(IMG_DIR, random_img_name)
    if not os.path.exists(img_path):
        print(f"[ERROR] No se encontró la imagen {img_path}")
        return
        
    print(f"-> Simulando carga en GPU local para la imagen: {random_img_name}, Lote: {lot_id}")
    
    # Leer la imagen con OpenCV y pasar a RGB para Matplotlib
    img_bgr = cv2.imread(img_path)
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    
    xmin, ymin, xmax, ymax = map(int, bbox)
    
    # Preparamos el panel interactivo
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 7))
    fig.suptitle(f"Simulación Pre-SAM | Imagen: {random_img_name} | Lote: {lot_id}", fontsize=14)
    fig.canvas.manager.set_window_title("Auditoría de Cropping para SAM")

    # 1. Panel Izquierdo: Foto completa + Caja
    ax1.imshow(img_rgb)
    ax1.set_title("Foto Original + Bounding Box (Prompt Positivo)")
    rect = patches.Rectangle((xmin, ymin), xmax - xmin, ymax - ymin, 
                             linewidth=3, edgecolor='lime', facecolor='none')
    ax1.add_patch(rect)
    ax1.axis('off')
    
    # 2. Panel Derecho: El Recorte Exacto
    h_img, w_img = img_rgb.shape[:2]
    crop_xmin = max(0, xmin)
    crop_ymin = max(0, ymin)
    crop_xmax = min(w_img, xmax)
    crop_ymax = min(h_img, ymax)
    
    crop_img = img_rgb[crop_ymin:crop_ymax, crop_xmin:crop_xmax]
    
    if crop_img.size > 0:
        ax2.imshow(crop_img)
        ax2.set_title(f"Recorte Matemático a Procesar ({crop_xmax-crop_xmin}x{crop_ymax-crop_ymin} px)")
        ax2.axis('off')
    else:
        ax2.text(0.5, 0.5, "Error de Crop (Bounds Fuera)", ha="center", va="center")
        ax2.axis('off')
        
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    main()
