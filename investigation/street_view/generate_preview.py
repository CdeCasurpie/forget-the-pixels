import cv2
import numpy as np
import streetlevel.streetview as sv
import matplotlib.pyplot as plt

pano_id = 'YTjFREHWWf3WLOhibSFgkA'
p = sv.find_panorama_by_id(pano_id)
img_pil = sv.get_panorama(p, zoom=2)
img = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)

# Split perspective view 0
fov = 90
h, w = img.shape[:2]
out_size = 1024
K = np.array([
    [out_size / (2 * np.tan(np.radians(fov) / 2)), 0, out_size / 2],
    [0, out_size / (2 * np.tan(np.radians(fov) / 2)), out_size / 2],
    [0, 0, 1]
], dtype=np.float32)

theta = np.radians(0)
phi = np.radians(0)

Rx = np.array([[1, 0, 0], [0, np.cos(phi), -np.sin(phi)], [0, np.sin(phi), np.cos(phi)]])
Ry = np.array([[np.cos(theta), 0, np.sin(theta)], [0, 1, 0], [-np.sin(theta), 0, np.cos(theta)]])
R = Ry @ Rx

u, v = np.meshgrid(np.arange(out_size), np.arange(out_size))
x = (u - K[0, 2]) / K[0, 0]
y = (v - K[1, 2]) / K[1, 1]
z = np.ones_like(x)

rays = np.stack([x, y, z], axis=-1)
rays_rot = rays @ R.T

sph_theta = np.arctan2(rays_rot[..., 0], rays_rot[..., 2])
sph_phi = np.arcsin(rays_rot[..., 1] / np.linalg.norm(rays_rot, axis=-1))

map_x = (sph_theta / (2 * np.pi) + 0.5) * w
map_y = (sph_phi / np.pi + 0.5) * h

map_x = np.mod(map_x, w).astype(np.float32)
map_y = map_y.astype(np.float32)

persp = cv2.remap(img, map_x, map_y, cv2.INTER_LINEAR)
persp_rgb = cv2.cvtColor(persp, cv2.COLOR_BGR2RGB)

# Crear imagen con regla (ruler) en el eje Y
fig, ax = plt.subplots(figsize=(8, 8))
ax.imshow(persp_rgb)
ax.set_yticks(np.arange(0, 1025, 100))
ax.set_xticks([])
ax.grid(color='red', linestyle='--', linewidth=1, axis='y', alpha=0.7)
ax.set_ylabel('Eje Y (Píxeles)', fontsize=14)
ax.set_title('Vista Perspectiva (1024x1024) sin máscara', fontsize=16)

out_path = "/home/cesar/Escritorio/UTEC/PFC1_Lima/forget-the-pixels/investigation/street_view/mask_preview.png"
plt.savefig(out_path, bbox_inches='tight', dpi=150)
print(out_path)
