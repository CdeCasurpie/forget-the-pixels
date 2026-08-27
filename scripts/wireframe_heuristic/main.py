import cv2
import numpy as np
import itertools
import argparse
import sys
from edge_detector import EdgeDetector

def print_progress_bar(iteration, total, length=50):
    """Muestra una barra de carga en la terminal."""
    percent = ("{0:.1f}").format(100 * (iteration / float(total)))
    filled_length = int(length * iteration // total)
    bar = '█' * filled_length + '-' * (length - filled_length)
    sys.stdout.write(f'\rProgreso: |{bar}| {percent}% Completado')
    sys.stdout.flush()
    if iteration == total:
        print()

def main():
    parser = argparse.ArgumentParser(description="Heurística de Extracción Estructural de Aristas")
    parser.add_argument('--animation', action='store_true', help="Muestra la animación visual evaluando arista por arista")
    args = parser.parse_args()

    image_path = "maps.png"
    image = cv2.imread(image_path)
    if image is None:
        print(f"Error: No se pudo cargar {image_path}")
        return

    print("--- FLUJO DE WIREFRAME HEURÍSTICO ---")

    print("1. Seleccionando nodos estructurales (Simulando Co-PLNet)...")
    print("Haz clic en las esquinas reales de los edificios. Presiona ENTER al terminar.")
    
    # Importar MockCoPLNet localmente si no estaba importado arriba
    from mock_coplnet import MockCoPLNet
    mock_net = MockCoPLNet()
    vertices = mock_net.detect(image)
    
    if len(vertices) < 2:
        print("Se necesitan al menos 2 vértices. Saliendo...")
        return

    print("2. Procesando bordes (Canny Dilatado)...")
    detector = EdgeDetector(blur_kernel=(5,5), canny_low=40, canny_high=120)
    edge_map = detector.process_image(image)

    all_pairs = list(itertools.combinations(vertices, 2))
    total_edges = len(all_pairs)
    print(f"Nodos extraídos (SIFT): {len(vertices)} | Aristas a evaluar: {total_edges}")
    
    valid_edges = []
    threshold = 0.70 # Filtro más riguroso (70% de la recta debe tocar Canny)
    
    print("3. Evaluando intersecciones espaciales...")
    
    if args.animation:
        cv2.namedWindow("Evaluando Aristas")
        
    for i, (pt1, pt2) in enumerate(all_pairs):
        score = detector.evaluate_line(pt1, pt2)
        
        # Guardar si pasa el umbral
        if score > threshold:
            valid_edges.append((pt1, pt2))

        # Render visual solo si --animation está activo
        if args.animation:
            vis_img = image.copy()
            colored_canny = cv2.cvtColor(edge_map, cv2.COLOR_GRAY2BGR)
            vis_img = cv2.addWeighted(vis_img, 0.7, colored_canny, 0.3, 0)
            
            for v in vertices:
                cv2.circle(vis_img, v, 3, (0, 0, 255), -1)
                
            color = (0, 255, 0) if score > threshold else (0, 0, 255)
            cv2.line(vis_img, pt1, pt2, color, 1)
            
            estado = "ACEPTADA" if score > threshold else "RECHAZADA"
            cv2.putText(vis_img, f"Score: {score:.2f} (Umbral: {threshold}) -> {estado}", (10, 30), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
            
            cv2.imshow("Evaluando Aristas", vis_img)
            cv2.waitKey(10) # Rápido para no demorar horas
        else:
            # Barra de carga en consola si no hay animación
            print_progress_bar(i + 1, total_edges)
            
    if args.animation:
        cv2.destroyAllWindows()
    
    print(f"4. Proceso finalizado. Aristas válidas que pasaron el filtro: {len(valid_edges)}")
    
    # Dibujar resultado final
    final_img = image.copy()
    for pt1, pt2 in valid_edges:
        cv2.line(final_img, pt1, pt2, (0, 255, 0), 2)
    for v in vertices:
        cv2.circle(final_img, v, 4, (0, 0, 255), -1)
        
    cv2.imshow("Wireframe Estructural Final (SIFT)", final_img)
    print("Presiona la tecla 'q' en la ventana de la imagen para cerrar el programa.")
    while True:
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
            
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
