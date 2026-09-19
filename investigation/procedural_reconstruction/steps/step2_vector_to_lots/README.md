# Paso 2: vector hacia lotes y visibilidad 2D

Este experimento relaciona cada panorámica del Paso 1 con un lote catastral
objetivo. Para cada cámara:

1. transforma su GPS de WGS84 a UTM 18S (`EPSG:32718`);
2. calcula el punto medio de cada arista exterior del lote;
3. asigna a cada arista `1` si su punto medio es visible y `0` si la línea
   corta otro polígono catastral;
4. ordena las cámaras por distancia al lote y selecciona las 5 más cercanas;
5. calcula el `bearing`/`yaw` hacia la arista más cercana por punto medio;
6. dibuja norte en gris, heading de la cámara en rojo y dirección al lote en verde.

## Ejecución

Desde `investigation/`:

```bash
make run-gsv-step2
```

El lote de demostración es la fila `1515` del shapefile. También puede
seleccionarse un `objectid` real:

```bash
make run-gsv-step2 GSV_STEP2_OBJECTID=1135751
```

O directamente:

```bash
/home/cesar/Escritorio/UTEC/PFC1_Lima/venv310/bin/python \
  proy_geom/steps/step2_vector_to_lots/visualize.py \
  --lot-row 1515
```

Se generan:

```text
outputs/step2_vectors_map.png
outputs/step2_analysis.json
```

Los números junto a las cámaras corresponden a la secuencia del
`metadata.json` del Paso 1. En las cinco cámaras seleccionadas aparece además
su distancia al lote entre paréntesis. Una `x` naranja indica score geométrico
cero; ese score se conserva como diagnóstico y ya no decide la selección.

Antes de puntuar, se eliminan panorámicas repetidas y se conservan únicamente
las cámaras cuya posición está dentro del radio configurado alrededor del lote.
El valor predeterminado es 100 m y se puede cambiar así:

```bash
make run-gsv-step2 GSV_STEP2_MAX_DISTANCE_M=150
```

Si ninguna panorámica cae dentro del radio, el experimento solicita descargar
una ruta más cercana o aumentar el radio; no inventa cámaras lejanas como
candidatas válidas.

## Selección aleatoria sin imágenes

Para probar el flujo completo con otro lote usando el archivo local de
Barranco:

```bash
make run-gsv-step2-random
```

Este comando no consulta Google. Escoge aleatoriamente entre todos los lotes
del shapefile que tengan al menos una cámara cercana en el archivo maestro,
filtra esas cámaras y ejecuta el Top 5 por distancia.

Primero se construye o reanuda el archivo maestro:

```bash
make download-gsv-metadata-barranco
```

El recolector muestra progreso, guarda checkpoints y puede detenerse con
`Ctrl+C`. Al ejecutarlo otra vez continúa desde
`data/barranco_metadata/harvest_state.json`. Nunca llama a `get_panorama` y no
descarga JPG.

La antigua prueba que consulta metadata en vivo alrededor de una coordenada se
conserva como `make run-gsv-step2-random-live`. Ese comando:

- selecciona aleatoriamente un lote cuyo centroide cae dentro de
  `GSV_STEP2_AREA_RADIUS_M`;
- consulta panoramas vecinos de Street View alrededor del centroide;
- guarda únicamente `pano_id`, GPS, fecha y orientación;
- filtra las cámaras a menos de `GSV_STEP2_MAX_DISTANCE_M`;
- ejecuta el ranking Top 5 por distancia con esos candidatos.

No se llama a `get_panorama` y no se crean archivos JPG. Los candidatos quedan
en `data/random_candidates/metadata.json` y `selection.json`.

La puntuación también considera auto-oclusión: una arista recibe cero cuando el
rayo hacia su punto medio atraviesa el interior del propio lote objetivo. Las
El score no elimina una cámara del Top 5; permite revisar posteriormente si una
de las cinco más cercanas tiene colisiones o mala frontalidad.

También se aplican controles de calidad espacial:

- si la cámara cae dentro de un polígono por el desfase GPS, ese polígono se
  ignora como oclusor de sus propios rayos; los demás lotes siguen bloqueando;
- la fachada debe verse con suficiente frontalidad. El valor por defecto
  `GSV_STEP2_MIN_FRONTAL_COSINE=0.5` acepta como máximo 60° respecto a la
  normal de la arista.

La posición original y los polígonos contenedores quedan registrados en el
JSON para auditar el desfase; no se mueve artificialmente la cámara.

El score es binario y auditable:

```text
score(cámara) = suma(score(arista_i))
score(arista_i) = 1 si el punto medio está libre, no está auto-oculto
                    y la vista supera el umbral de frontalidad
                  0 en cualquier otro caso
```

El reporte JSON conserva el resultado de cada arista, sus puntos medios, los
lotes bloqueadores y el ranking completo de cámaras.

## Interpretación geométrica

El bearing se mide en sentido horario desde el norte:

```text
bearing = atan2(delta_este, delta_norte)
yaw_relativo = wrap(bearing - heading, [-180°, 180°))
```

El `yaw_relativo` es el giro que necesitaría una vista centrada en el heading
original para mirar hacia la arista del lote. En el siguiente paso se usará
para construir la proyección rectilínea/cilíndrica de la fachada.

## Limitación importante

El shapefile disponible representa lotes catastrales, no necesariamente la
huella exacta de cada edificación. Por eso la oclusión de este paso es una
prueba 2D conservadora basada en polígonos de lotes: sirve para filtrar y
auditar cámaras, pero no demuestra todavía visibilidad arquitectónica completa.
Más adelante convendrá sustituir o complementar estos polígonos con huellas de
edificación, alturas y/o un modelo 3D.
