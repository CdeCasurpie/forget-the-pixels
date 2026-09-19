# Paso 6 procedural: validación de reproyección

## Ajuste interactivo XY

`make view-gsv-alignment` muestra todas las cámaras simultáneamente. Flechas
izquierda/derecha desplazan el lote en UTM oeste/este; abajo/arriba sur/norte.
El paso inicial es 0.1 m; `[` lo divide entre dos, `]` lo duplica (1 mm–10 m).
`+`/`-` cambia altura, `r` restablece XY y `s` guarda `outputs/alignment.json`.
La siguiente apertura recupera ese ajuste. Hacer clic en la ventana para que
reciba teclado; zoom/pan de la barra de Matplotlib permite inspección fina.
`make view-gsv-alignment GSV_ALIGNMENT_STEP=0.01` empieza con pasos de 1 cm.

El movimiento es geográfico, no horizontal/vertical de pantalla: cada cámara
verá un desplazamiento distinto. Se traslada exclusivamente el lote objetivo
y se mantiene la misma corrección en todas sus vistas; el shapefile se conserva.
Una corrección visual para un lote no demuestra un desfase global de Barranco.
Si las cámaras requieren ajustes distintos, revisar GPS/heading y huella real.

Para comprobar el desfase con varios lotes:

```bash
make view-gsv-alignment-batch GSV_ALIGNMENT_STEP=0.01
```

Si existe la corrección individual `outputs/alignment.json`, el visor la carga
como posición inicial. Al guardar, añade la lista de OBJECTID seleccionados al
mismo archivo; el shapefile nunca se modifica.

El visor selecciona cinco lotes únicos más cercanos al conjunto de cámaras
que tengan al menos una arista catastral visible desde alguna cámara y estén a
menos de 100 m (`--max-distance` para cambiarlo). Cada lote
usa un color, pero todos reciben el mismo desplazamiento Este/Norte. La altura
común es 10 m porque aquí evaluamos principalmente el desfase horizontal;
`+` y `-` permiten cambiarla. El título muestra los OBJECTID y `s` guarda la
corrección junto con la lista de lotes seleccionados.

Para aplicar la corrección a los renders por lotes:

```bash
python proy_geom/steps/step6_reprojection_sanity/run.py \
  --correction proy_geom/steps/step6_reprojection_sanity/outputs/alignment.json
```

Este comando aplica XY y genera una única evidencia: `outputs/comparison.png`.
La imagen contiene una fila con las panorámicas completas y otra con las
proyecciones cilíndricas, usando todas las cámaras del manifiesto. La altura
se controla con `--height` y la altura de cámara se toma de `alignment.json`.

La integración experimental de SAM queda como código reutilizable en
`src/facade_segmentation`; no forma parte de este experimento geométrico y no
se mantiene una segunda carpeta Step 6 aquí. Este paso no estima todavía
alturas.

Desde `investigation/`:

```bash
make run-gsv-reprojection
make test-gsv-projection
```

Reutiliza el manifiesto e imágenes originales del Paso 5, identifica el lote
por OBJECTID y dibuja prismas de alturas conocidas en cada panorama completo
y franja angular. No requiere red ni GPU. Las salidas se regeneran en
`outputs/`; usar `--output` en el script para conservar otra ejecución.

## Geometría y convenciones

`src/geometry_projection/spherical.py` contiene `PanoramaCamera`,
`strip_pixels`, `prism_edges` y el render de aristas muestreadas. El punto
mundial se expresa en metros ENU (este, norte geográfico, arriba); la pose
contiene el centro óptico y heading horario desde norte, pitch positivo
hacia arriba y roll que gira el eje derecho hacia el superior de cámara.
La cámara predeterminada está 2.5 m sobre el terreno; es una hipótesis
configurable, no metadata medida.

El ejecutable transforma los vértices UTM a WGS84 y calcula azimut/distancia
geodésica desde cada cámara, aproximando un plano local horizontal. Esto evita
confundir norte de cuadrícula con norte geográfico. No modela pendientes ni
curvatura vertical terrestre a escala de lote. `--base-z` es relativo al plano
de suelo de las cámaras; `--camera-height` fija el centro respecto a ese plano.

Las imágenes se asumen niveladas como en el Paso 1. Pitch/roll del proveedor
se registran, pero no se aplican automáticamente: su convención aún no está
calibrada. `--pitch`, `--roll` y `--heading-offset` permiten ensayos explícitos
comunes a las cámaras. No se optimizan ni ajustan en secreto.

La imagen equirectangular usa u=W(1/2+yaw/360), v=H(1/2-pitch/180).
La franja invierte exactamente el muestreo del Paso 5, incluida su escala
vertical (H_salida-1)/(H_panorama-1). Se conserva el yaw del recorte guardado.
Aristas muestreadas cada 20 cm; cortes en la costura horizontal y clipping
contra límites de imagen. Todas las aristas se muestran, incluso ocultas:
este wireframe no incorpora z-buffer, vegetación ni otros edificios.

## Evidencias e interpretación

`comparison.png`: única evidencia visual; fila superior con panorámicas y fila
inferior con proyecciones cilíndricas. Incluye las 4 cámaras y los 8 lotes
seleccionados, ya alineados con la corrección guardada.

Las pruebas sintéticas verifican cardinales, elevación, pose rotada, costura,
extrusión y correspondencia con el muestreo del Paso 5. Su aprobación no prueba
la calibración física del catastro y Street View. Verificar visualmente bases,
verticales y movimiento del techo al aumentar altura. Un prisma arbitrario
de 10 m no tiene por qué coincidir con el techo real; el polígono catastral
tampoco equivale necesariamente a la huella del edificio. Registrar desfases
antes de implementar la detección de techo y optimización multivista.
