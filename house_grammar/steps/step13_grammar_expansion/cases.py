import numpy as np
from shapely.geometry import Polygon

# Definimos una serie de lotes de prueba según la Fase 0 del plan.
# Cada caso tiene: nombre, polígono, aristas frontales (índices), y familia recomendada.

def create_rectangle(x, y, w, d):
    return Polygon([(x, y), (x+w, y), (x+w, y+d), (x, y+d)])

CASES = [
    {
        "name": "01_rectangle_standard",
        "parcel": create_rectangle(0, 0, 10, 20),
        "front_edges": [0], # Arista inferior (0,0) a (10,0)
        "family": "quiet_house",
        "floors": 2,
        "style": "courtyard",
        "setback": 2.0
    },
    {
        "name": "02_narrow_flush",
        "parcel": create_rectangle(0, 0, 4, 15),
        "front_edges": [0],
        "family": "workshop",
        "floors": 1,
        "style": "narrow",
        "setback": 0.0
    },
    {
        "name": "03_corner_mixed",
        "parcel": create_rectangle(0, 0, 12, 12),
        "front_edges": [0, 3], # Inferior e Izquierda
        "family": "mixed_use",
        "floors": 4,
        "style": "corner",
        "setback": 0.0
    },
    {
        "name": "04_l_shape",
        "parcel": Polygon([(0,0), (10,0), (10,10), (5,10), (5,20), (0,20)]),
        "front_edges": [0], # Inferior
        "family": "balcony_apartments",
        "floors": 5,
        "style": "narrow",
        "setback": 0.0
    },
    {
        "name": "05_acute_angle",
        "parcel": Polygon([(0,0), (15,5), (5,20)]),
        "front_edges": [0],
        "family": "ribbon_windows",
        "floors": 3,
        "style": "narrow",
        "setback": 0.0
    },
    {
        "name": "06_segmented_front",
        "parcel": Polygon([(0,0), (2,1), (4,0), (6,1), (8,0), (10,0), (10,15), (0,15)]),
        "front_edges": [0, 1, 2, 3, 4], # Curva segmentada
        "family": "brick_courtyard",
        "floors": 2,
        "style": "corner",
        "setback": 0.0
    },
    {
        "name": "07_no_front",
        "parcel": create_rectangle(0, 0, 8, 8),
        "front_edges": [0], # Forzamos una arista, layout no acepta vacío sin fallar actualmente
        "family": "quiet_house",
        "floors": 1,
        "style": "courtyard",
        "setback": 2.0
    },
    {
        "name": "08_tower_baseline",
        "parcel": create_rectangle(0, 0, 20, 20),
        "front_edges": [0, 1], 
        "family": "balcony_apartments",
        "floors": 20,
        "style": "corner",
        "setback": 3.0
    }
]
