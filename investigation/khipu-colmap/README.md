# 🔧 khipu-colmap

Mini-framework para ejecutar COLMAP en el clúster **Khipu** de UTEC sin morir en el intento.

Nacido de **5 iteraciones fallidas** y **7 bugs distintos**, este framework valida automáticamente todo antes de gastar un solo segundo de GPU.

## Quick Start

```bash
# 1. Copiar el framework a Khipu
scp -r investigation/khipu-colmap/ cesar.perales@khipu:~/tesis_colmap/khipu-colmap/

# 2. En Khipu: editar un config YAML
cp ~/tesis_colmap/khipu-colmap/examples/tomasa_1fps.yaml mi_config.yaml
nano mi_config.yaml

# 3. Validar (sin gastar GPU)
python ~/tesis_colmap/khipu-colmap/colmap_pipeline.py validate mi_config.yaml

# 4. Ejecutar
python ~/tesis_colmap/khipu-colmap/colmap_pipeline.py run mi_config.yaml

# 4b. Ejecutar borrando workspace anterior (start fresh)
python ~/tesis_colmap/khipu-colmap/colmap_pipeline.py run --clean mi_config.yaml
```

## Estructura del Config YAML

```yaml
experiment_name: "mi_experimento"       # Nombre de la carpeta de trabajo
workspace_base: "~/tesis_colmap"        # Directorio padre

video_source: "~/ruta/al/video.MP4"     # Video fuente

gps_source:
  type: "dji_srt"                       # "dji_srt" | "exif" | "csv" | "none"
  file: "~/ruta/al/archivo.SRT"         # Archivo GPS (no requerido si type=none)

extraction:
  fps: 1.0                              # Fotogramas por segundo a extraer
  resolution: 1080                      # Altura en píxeles (ancho se escala auto)
  quality: 2                            # Calidad JPEG (1=mejor, 31=peor)

pipeline:
  preset: "sparse_only"                 # "sparse_only" | "sparse_and_dense" | "dense_resume"
  camera_model: "OPENCV"                # Modelo de cámara COLMAP
  single_camera: true                   # ¿Todas las fotos son de la misma cámara?
  sequential_overlap: 20                # Overlap para matching secuencial
  alignment_max_error: 3.0              # Tolerancia GPS en metros
  fusion_use_cache: true                # Usar caché de disco (anti-OOM)
  fusion_cache_size: 32                 # Tamaño de caché en GB

slurm:
  partition: "gpu"
  mem: "64G"                            # Máximo en Khipu: 64G
  time: "12:00:00"
  cpus: 16
```

## Presets

| Preset | Qué hace | Tiempo estimado |
|--------|----------|-----------------|
| `sparse_only` | Poses de cámara + nube dispersa `.ply` | 15-30 min |
| `sparse_and_dense` | Todo + nube densa + malla 3D | 1-3 horas |
| `dense_resume` | Solo fusion + malla (para retomar tras OOM) | 5-20 min |

## Parsers de GPS

| Tipo | Descripción | Ejemplo |
|------|-------------|---------|
| `dji_srt` | Archivo `.SRT` de dron DJI | Auto-detecta FPS del SRT |
| `exif` | Fotos de celular con EXIF GPS | Lee lat/lon de cada `.jpg` |
| `csv` | CSV manual (`filename,lat,lon,alt`) | Para GPS externo/RTK |
| `none` | Sin GPS | Nube en coordenadas locales |

## Validaciones Automáticas

El comando `validate` ejecuta **10 chequeos** antes de enviar el job:

1. ✅ ¿El video fuente existe?
2. ✅ ¿El archivo GPS existe y es parseable?
3. ✅ ¿El regex detecta coordenadas?
4. ✅ ¿El workspace está limpio?
5. ✅ ¿El binario de COLMAP existe?
6. ✅ ¿FFmpeg existe?
7. ✅ ¿Python del conda env existe?
8. ✅ ¿Memoria ≤ 64GB (límite Khipu)?
9. ✅ ¿Flags compatibles con COLMAP 3.13.0?
10. ✅ ¿GPS y frames están sincronizados?

## Bugs Conocidos que este Framework Previene

| Bug | Cómo lo previene |
|-----|-----------------|
| `$COLMAP: command not found` | Usa rutas absolutas hardcodeadas |
| `--robust_alignment` crash | Blacklist de flags incompatibles |
| `sparse/0_aligned/` vacía | Guard que detecta fallo y usa fallback |
| `geo_priors.txt` vacío | Validación de regex + conteo pre-submit |
| OOM en stereo_fusion | Flags de caché obligatorios en preset |
| Desincronización GPS/frames | Auto-detección de FPS del SRT |
| Mapper escribe en `sparse/0/0/` | Auto-detección con `find` |

## Documentación COLMAP

- **CLI Reference:** https://colmap.github.io/cli.html
- **Tutorial:** https://colmap.github.io/tutorial.html
- **Versión en Khipu:** COLMAP 3.13.0 (con CUDA)
