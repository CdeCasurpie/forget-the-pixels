import re
with open('/home/cesar/Escritorio/UTEC/PFC1_Lima/forget-the-pixels/investigation/street_view/interactive_route_selector.py', 'r') as f:
    code = f.read()

old_logic = """    full_p = sv.find_panorama_by_id(p.id)
    target_year = full_p.date.year"""

new_logic = """    # Buscar especificamente el año 2022 en el historial
    target_p = None
    if p.date.year == 2022:
        target_p = p
    else:
        for hist in p.historical:
            if hist.date.year == 2022:
                target_p = hist
                break
    
    if not target_p:
        print("No se encontro un panorama de 2022 en este punto exacto, usando el mas cercano disponible.")
        target_p = p

    full_p = sv.find_panorama_by_id(target_p.id)
    target_year = full_p.date.year
    max_count = 70 # Reducido a 70 para que la descarga de metadatos sea 2x mas rapida (suficiente para 2 cuadras)"""

code = code.replace(old_logic, new_logic)

with open('/home/cesar/Escritorio/UTEC/PFC1_Lima/forget-the-pixels/investigation/street_view/interactive_route_selector.py', 'w') as f:
    f.write(code)
print("Parche 2022 aplicado.")
