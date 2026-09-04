import streetlevel.streetview as sv
import matplotlib.pyplot as plt
import numpy as np
import os

pano_id = 'YTjFREHWWf3WLOhibSFgkA'
pano = sv.find_panorama_by_id(pano_id, download_depth=True)
img = sv.get_panorama(pano, zoom=1)
img_array = np.array(img)

depth_map = pano.depth.data

plt.figure(figsize=(14, 6))
plt.subplot(1, 2, 1)
plt.imshow(img_array)
plt.title('Imagen 360 Original')
plt.axis('off')

plt.subplot(1, 2, 2)
depth_vis = np.copy(depth_map)
max_depth = np.max(depth_vis[depth_vis > 0])
depth_vis[depth_vis <= 0] = max_depth + 10

plt.imshow(depth_vis, cmap='turbo')
plt.title('Mapa de Profundidad 3D Nativo (Distancia en metros)')
plt.axis('off')

plt.tight_layout()
out_path = "/home/cesar/Escritorio/UTEC/PFC1_Lima/forget-the-pixels/investigation/street_view/gsv_depth_preview.png"
plt.savefig(out_path, bbox_inches='tight', dpi=150)
print(out_path)
