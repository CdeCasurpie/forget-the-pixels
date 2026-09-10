import os
import json
import argparse
import cv2
import torch
import numpy as np
import sys

try:
    from mobile_sam import sam_model_registry, SamPredictor
except ImportError:
    print("[ERROR] No se encontró mobile_sam. Asegúrate de instalarlo en el entorno de Khipu.")
    sys.exit(1)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--metadata', type=str, required=True, help="Ruta a crops_metadata.json")
    parser.add_argument('--images', type=str, required=True, help="Carpeta de imagenes")
    parser.add_argument('--output', type=str, required=True, help="Carpeta destino para PNGs transparentes")
    parser.add_argument('--weights', type=str, required=True, help="Ruta offline a mobile_sam.pt")
    args = parser.parse_args()
    
    os.makedirs(args.output, exist_ok=True)
    
    print("[INFO] Cargando Metadata...")
    with open(args.metadata, 'r') as f:
        metadata = json.load(f)
        
    print(f"[INFO] Cargando MobileSAM (Modo Offline) desde {args.weights}...")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[INFO] Dispositivo de Inferencia: {device.upper()}")
    
    sam = sam_model_registry["vit_t"](checkpoint=args.weights)
    sam.to(device=device)
    predictor = SamPredictor(sam)
    
    total_imgs = len(metadata)
    for idx, (img_name, crops) in enumerate(metadata.items()):
        print(f"[{idx+1}/{total_imgs}] Procesando {img_name} ({len(crops)} lotes)...")
        img_path = os.path.join(args.images, img_name)
        if not os.path.exists(img_path):
            print(f"  [WARN] No se encontró {img_path}")
            continue
            
        img_bgr = cv2.imread(img_path)
        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        h_img, w_img = img_rgb.shape[:2]
        
        predictor.set_image(img_rgb)
        
        for crop in crops:
            lot_id = crop['lot_id']
            bbox = np.array(crop['bbox']) # [xmin, ymin, xmax, ymax]
            
            # --- Expansión del Bounding Box (Padding Asimétrico) ---
            # Le damos 20px extra a los lados, pero hacia ABAJO le damos 100px.
            # Esto obliga a SAM a mirar más abajo del polígono del techo (el catastro), 
            # forzándolo a descubrir la fachada entera hasta chocar con la vereda.
            pad_side = 20
            pad_bottom = 120
            bbox_padded = np.array([
                max(0, bbox[0] - pad_side),
                max(0, bbox[1] - pad_side),
                min(w_img, bbox[2] + pad_side),
                min(h_img, bbox[3] + pad_bottom)
            ])
            
            # --- Inferencia en GPU ---
            masks, scores, _ = predictor.predict(
                box=bbox_padded,
                multimask_output=False
            )
            best_mask = masks[0]
            
            # --- Guardado como PNG Transparente Aislado ---
            # Crear una imagen RGBA completamente transparente
            mask_rgba = np.zeros((h_img, w_img, 4), dtype=np.uint8)
            # Copiar los colores originales donde la máscara de SAM es True
            mask_rgba[best_mask] = np.concatenate((img_rgb[best_mask], np.full((np.sum(best_mask), 1), 255)), axis=1)
            
            # Recortar la imagen basándonos en lo que SAM descubrió, NO en el catastro.
            # Encontramos los límites de la máscara que generó SAM
            y_indices, x_indices = np.where(best_mask)
            if len(y_indices) > 0 and len(x_indices) > 0:
                mask_ymin, mask_ymax = y_indices.min(), y_indices.max()
                mask_xmin, mask_xmax = x_indices.min(), x_indices.max()
                
                # Le damos un pequeño margen de 5 px a la imagen final
                m = 5
                mask_ymin = max(0, mask_ymin - m)
                mask_ymax = min(h_img, mask_ymax + m)
                mask_xmin = max(0, mask_xmin - m)
                mask_xmax = min(w_img, mask_xmax + m)
                
                final_crop = mask_rgba[mask_ymin:mask_ymax, mask_xmin:mask_xmax]
                
                out_path = os.path.join(args.output, f"lot_{lot_id}_from_{img_name.split('.')[0]}.png")
                cv2.imwrite(out_path, cv2.cvtColor(final_crop, cv2.COLOR_RGBA2BGRA))
            else:
                print(f"  [WARN] SAM devolvió una máscara vacía para el lote {lot_id}")
            
    print("[INFO] Proceso Batch Completado. Revisa la carpeta:", args.output)

if __name__ == "__main__":
    main()
