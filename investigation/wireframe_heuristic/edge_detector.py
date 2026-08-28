import cv2
import numpy as np
import math

class EdgeDetector:
    def __init__(self, blur_kernel=(5, 5), canny_low=40, canny_high=120):
        self.blur_kernel = blur_kernel
        self.canny_low = canny_low
        self.canny_high = canny_high
        self.edge_map = None
        self.image_shape = None

    def process_image(self, image):
        """Aplica desenfoque y Canny puro para obtener la máscara de bordes."""
        self.image_shape = image.shape[:2]
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, self.blur_kernel, 0)
        
        raw_canny = cv2.Canny(blurred, self.canny_low, self.canny_high)
        
        # Al usar clics manuales (Nodos Semánticos), podemos relajar el filtro de Hough
        # para que no borre las líneas estructurales cortas (como ventanas o rejas).
        # minLineLength=50 borra casi todos los árboles pero mantiene arquitectura útil.
        clean_lines_mask = np.zeros(self.image_shape, dtype=np.uint8)
        lines = cv2.HoughLinesP(raw_canny, 1, np.pi/180, threshold=40, minLineLength=50, maxLineGap=10)
        if lines is not None:
            for line in lines:
                x1, y1, x2, y2 = line[0]
                cv2.line(clean_lines_mask, (x1, y1), (x2, y2), 255, 1)
        
        # Ahora sí, dilatamos el esqueleto estructural limpio para darle la tolerancia al grosor
        kernel = np.ones((3,3), np.uint8)
        self.edge_map = cv2.dilate(clean_lines_mask, kernel, iterations=1)
        
        return self.edge_map

    def evaluate_line(self, pt1, pt2):
        """
        Dibuja una recta estrictamente unidimensional (grosor=1) y cruza con Canny dilatado.
        """
        if self.edge_map is None:
            raise ValueError("Primero debes llamar a process_image")
            
        line_mask = np.zeros(self.image_shape, dtype=np.uint8)
        # Recta ESTRICTAMENTE 1D
        cv2.line(line_mask, pt1, pt2, 255, 1)
        
        intersection = cv2.bitwise_and(self.edge_map, line_mask)
        pixels_in_intersection = cv2.countNonZero(intersection)
        
        length = math.dist(pt1, pt2)
        if length == 0:
            return 0.0
            
        score = pixels_in_intersection / length
        return min(1.0, score)
