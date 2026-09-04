import re
with open('/home/cesar/Escritorio/UTEC/PFC1_Lima/forget-the-pixels/investigation/street_view/download_custom_route.py', 'r') as f:
    code = f.read()

old_logic = """        # Objeto panorama basico para pasarlo al descargador
        pano_obj = sv.StreetViewPanorama(id=pid, lat=p_info["lat"], lon=p_info["lon"])
        img_pil = sv.get_panorama(pano_obj, zoom=2)"""

new_logic = """        # Descargar metadata completa para poder sacar la imagen
        full_p = sv.find_panorama_by_id(pid)
        img_pil = sv.get_panorama(full_p, zoom=2)"""

code = code.replace(old_logic, new_logic)

with open('/home/cesar/Escritorio/UTEC/PFC1_Lima/forget-the-pixels/investigation/street_view/download_custom_route.py', 'w') as f:
    f.write(code)
print("Patched.")
