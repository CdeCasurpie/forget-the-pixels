import cv2
import numpy as np

class MockCoPLNet:
    def __init__(self):
        self.vertices = []

    def detect(self, image):
        """
        Abre una ventana interactiva para recolectar puntos.
        Actúa como si fuese la inferencia de la red neuronal.
        """
        self.vertices = []
        img_copy = image.copy()
        
        def click_event(event, x, y, flags, params):
            if event == cv2.EVENT_LBUTTONDOWN:
                self.vertices.append((x, y))
                cv2.circle(img_copy, (x, y), 4, (0, 0, 255), -1)
                cv2.imshow("Mock Co-PLNet: Haz click para anadir nodos (Presiona Enter al terminar)", img_copy)

        cv2.imshow("Mock Co-PLNet: Haz click para anadir nodos (Presiona Enter al terminar)", img_copy)
        cv2.setMouseCallback("Mock Co-PLNet: Haz click para anadir nodos (Presiona Enter al terminar)", click_event)
        
        while True:
            key = cv2.waitKey(1) & 0xFF
            if key == 13 or key == ord('q'):
                break
                
        cv2.destroyAllWindows()
        return self.vertices
