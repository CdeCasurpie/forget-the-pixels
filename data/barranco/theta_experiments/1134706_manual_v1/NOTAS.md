# 1134706 — autoría manual desde cero (sin herencia de Haiku)

Fotos: `data/barranco/theta_author/runs/380ddc17a3ad40cd8bd4ec779dbc0946/evidence/`
Parcela/frentes: catastro fijo del paquete (5 vértices, frente 0 de 10.22 m).
Niveles humanos: [0, 3.0, 5.6] (2 pisos). Estilo global: null (fachada austera).

## Lo observado y su traducción a theta (`request.json`)
- Volumen único `principal`, región `front_edge 0, u [0,1], depth_m [2,14]`
  (retiro 2 m de jardín con plantas visibles tras el cerco).
- Frente explícito: 2 ventanas bajas con reja vertical (ocultas tras cerco,
  no se inventa puerta de edificio: el acceso visible es el portón del cerco).
- 2 ventanas altas 1.9×1.5 con reja vertical + alféizar + 4 contraventanas
  verdes (`shutter`, observadas en foto 001).
- Banda de piedra en planta baja como `material_regions` (v 0–3.0).
- Techo plano con parapeto 0.3, sin props (azotea no visible).
- Cerco `reja` h 1.7 sobre base de piedra + portón verde como `garage`
  (u 6.2, ancho 2.4, coincide en superposición) + zona `garden` [0,2].
- Sin balcones, miembros, frontones, entablamentos ni entradas (no observados).
- Trim apagado: los muros van sobre el lindero y cualquier relieve vuela
  fuera de la envolvente (falla `resolve_trims`); además no se ve moldura.
- Materiales: revoque beige [0.85,0.80,0.68], piedra marrón, marcos verde
  oscuro, metal verdoso (portón verde / rejas casi negras), madera verde.

## Resultado (`run05/`)
- `building.glb` (2336 vértices, 3788 triángulos, 234 partes)
- envolvente: passed · violaciones topológicas: 0
- `comparisons/01–03_comparison.jpg`: render angular-enu-v1 vs foto +
  superposición; el contorno calza con la casa en las 3 cámaras.
