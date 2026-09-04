import cv2
import numpy as np
import streetlevel.streetview as sv

def main():
    print("Descargando imagen 360 de prueba...")
    p = sv.find_panorama_by_id('YTjFREHWWf3WLOhibSFgkA')
    img_pil = sv.get_panorama(p, zoom=2) # 2048x1024
    img = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
    
    h, w = img.shape[:2]
    points = []

    def mouse_callback(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            points.append((x, y))

    window_name = "Dibuja la linea (Click Izq). ENTER para terminar, 'C' para borrar"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, 1280, 640)
    cv2.setMouseCallback(window_name, mouse_callback)

    print("Ventana abierta. Dibuja una linea de izquierda a derecha sobre el auto de Google.")
    
    while True:
        display = img.copy()
        if len(points) > 0:
            for i in range(len(points) - 1):
                cv2.line(display, points[i], points[i+1], (0, 0, 255), 2)
            for p_pt in points:
                cv2.circle(display, p_pt, 4, (0, 255, 0), -1)
        
        cv2.imshow(window_name, display)
        key = cv2.waitKey(1) & 0xFF
        
        if key == 13 or key == 32: # Enter o Espacio
            break
        elif key == ord('c') or key == ord('C'):
            points.clear()

    cv2.destroyAllWindows()

    if len(points) >= 2:
        # Asegurarnos de que el primer punto toque el borde izquierdo y el ultimo el derecho
        pts_list = points.copy()
        pts_list.insert(0, (0, pts_list[0][1]))
        pts_list.append((w-1, pts_list[-1][1]))
        
        # Cerrar el poligono por la parte de abajo
        pts_list.append((w-1, h-1))
        pts_list.append((0, h-1))
        
        mask = np.ones((h, w), dtype=np.uint8) * 255
        pts_arr = np.array([pts_list], dtype=np.int32)
        
        # Llenar de negro TODO lo que este debajo de la linea
        cv2.fillPoly(mask, pts_arr, 0)
        
        cv2.imwrite("base_mask_360.png", mask)
        print("\n¡Máscara maestra guardada en base_mask_360.png!")
        
        # Mostrar preview rapido
        img_masked = cv2.bitwise_and(img, img, mask=mask)
        cv2.imshow("Preview de la mascara aplicada", img_masked)
        cv2.waitKey(0)
        cv2.destroyAllWindows()
    else:
        print("\nSe necesitaban al menos 2 puntos. Vuelve a intentarlo.")

if __name__ == "__main__":
    main()
