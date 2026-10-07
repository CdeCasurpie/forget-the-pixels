# Step 20 — Triangulación esférica de cuatro panoramas (plan, sin implementar)

## Objetivo y alcance

Elegir cuatro panoramas consecutivos con solapamiento y comprobar si sus poses
de Street View permiten triangular correspondencias sobre fachadas. No hace
falta cerrar un ciclo alrededor de la cuadra. Taira aporta la extracción y
comparación de features; Jiang aporta el modelo de cámara esférica y la
geometría de rayos. Aquí las poses se toman de la metadata y se **validan**:
no se ejecuta el SfM incremental de Jiang (estimación de E, P3P ni BA).

## Entradas

Rutas relativas a `investigation/procedural_reconstruction/`:

- `data/poses_barranco/metadata.json`: entradas bajo `panoramas`, indexadas
  por `pano_id`; contienen `lat`, `lon`, `heading_deg`, `pitch_deg`,
  `roll_deg`, `neighbor_ids` e `image_downloaded`. No contienen altitud.
- `data/fotos_barranco/<pano_id>.jpg`: panoramas ERP disponibles localmente;
  comprobar existencia y dimensiones reales al escoger las cuatro cámaras.

## Experimento mínimo

1. Escoger C0–C3 adyacentes usando `neighbor_ids`, comprobando visualmente
   que están en la misma calle, comparten fachadas con textura y tienen
   separación suficiente. Registrar IDs, dimensiones y posiciones.
2. Construir coordenadas métricas locales: `lat/lon` → ECEF → ENU con origen
   en C0 (alternativamente proyección métrica local). **No hay altitud en
   este JSON**: para la primera prueba asumir una altura común y documentar
   la hipótesis `up=0`; si aparece una fuente fiable de elevación, incorporarla
   y repetir. No triangular usando grados de latitud/longitud como metros.
3. Validar la interpretación de `heading/pitch/roll_deg`: signo, orden de
   rotaciones, sistema de ejes y orientación del ERP. Contrastar el horizonte
   y direcciones visibles con la trayectoria C0–C3 y, si hace falta, matches
   entre cámaras. No dar por exactas las orientaciones solo por estar presentes.
   Definir y comprobar la transformación cámara→mundo antes de reconstruir.
4. Aplicar rectificación panorámica de Taira: rotar la esfera, detectar SIFT
   solo en regiones ecuatoriales poco deformadas y devolver los keypoints a
   coordenadas del ERP original. Usar `n=6` como configuración del paper;
   `n=4` como comparación opcional. Match de pares (C0,C1), (C1,C2),
   (C2,C3); opcionalmente (C0,C2) y (C1,C3). Lowe ratio 0.7.
5. Convertir píxeles ERP (con las dimensiones reales) a rayos unitarios según
   la convención esférica de Jiang. A partir de las poses, obtener la pose
   relativa de cada par y `E=[t_rel]× R_rel` con una convención de marcos
   documentada. Medir el **residual epipolar angular normalizado** de cada
   match y registrar su distribución. Filtrar con un umbral elegido a partir
   de los datos; el equivalente a 4 px de Jiang es referencia, no umbral fijo,
   porque la metadata puede contener errores. No estimar E por RANSAC.
6. Transformar los rayos aceptados al marco ENU y triangular cada par; usar
   closest point entre dos rayos como **elección nuestra de implementación**,
   no como algoritmo especificado por Jiang. Rechazar bajo paralaje,
   separación excesiva entre rayos y puntos con profundidad negativa en
   cualquiera de las dos cámaras. Registrar también el error de reproyección
   angular y detectar puntos duplicados entre pares antes de interpretarlos.
7. Exportar una nube `.ply` con puntos y colores, más las cuatro posiciones
   y segmentos que indiquen frente/derecha de cada cámara (en un PLY que
   admita aristas o en un archivo adicional). Conservar IDs y parámetros
   utilizados para poder reproducir la visualización.

## Qué observar

Por par: `matches_raw`, `matches_ratio`, `matches_geometry` y
`points_triangulated`, además de distribuciones de residual angular, paralaje
y distancia entre rayos. Inspeccionar que puntos y cámaras dibujen una calle
coherente, particularmente fachadas compartidas, en lugar de imponer un mínimo
de inliers tomado de la selección de cámaras seed del SfM de Jiang. Si los
residuales son altos o la nube incoherente, revisar primero convención de
orientación, alturas supuestas y precisión de poses antes de escalar.
