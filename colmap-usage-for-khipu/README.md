# Khipu COLMAP + Deep Learning Pipeline

Este framework automatiza la reconstrucción 3D (Structure-from-Motion y Multi-View Stereo) a partir de videos de drones (con metadata GPS opcional) para ejecutarse en supercomputadoras bajo sistemas SLURM (como Khipu).

Soporta extracción tradicional (SIFT) e integración profunda de estado del arte usando `hloc` (SuperPoint + LightGlue).

## Requisitos

El entorno destino (clúster) debe tener instalado:
- `colmap` (versión >= 3.13.0 recomendada)
- `ffmpeg`
- `python >= 3.10`
- Paquetes de Python: `pycolmap`, `hloc`, `torch` (con soporte CUDA).

## Uso

El pipeline es manejado enteramente mediante archivos de configuración en formato JSON o YAML.

### Comando Principal

```bash
python colmap_pipeline.py run config.json
```

Si deseas reiniciar un espacio de trabajo desde cero (borrar la reconstrucción anterior), usa el flag `--clean`:

```bash
python colmap_pipeline.py run --clean config.json
```

## Estructura de la Configuración (JSON)

Ejemplo de configuración completa:

```json
{
  "experiment_name": "reconstruccion_prueba",
  "workspace_base": "~/tesis_colmap",
  "video_source": "~/videos_dji/PasaarAColmapTomasa.MP4",
  "gps_source": {
    "type": "dji_srt",
    "file": "~/videos_dji/DJI_20260827101346_0116_D.SRT"
  },
  "extraction": {
    "fps": 2.0,
    "resolution": 1080,
    "quality": 2
  },
  "pipeline": {
    "feature_extractor": "superpoint_lightglue",
    "preset": "sparse_and_dense",
    "dense_max_image_size": 854,
    "sequential_overlap": 25
  },
  "slurm": {
    "partition": "gpu",
    "cpus": 16,
    "mem": "64G",
    "time": "48:00:00"
  }
}
```

### Explicación de los Parámetros

#### `video_source` y `gps_source`
- Rutas absolutas a tu video y archivo de metadatos (opcional). Actualmente se soporta parsing nativo de subtítulos DJI `.SRT` para la alineación geográfica. Si no hay GPS, simplemente elimina la llave `gps_source`.

#### `extraction`
- **fps**: Fotogramas a extraer por segundo. `1.0` a `2.0` suele ser ideal.
- **resolution**: Altura de la imagen extraída (ej. `1080` para FullHD). 

#### `pipeline`
- **feature_extractor**: `sift` para extractor clásico de COLMAP. `superpoint_lightglue` para inyectar un script en tiempo de ejecución que utilizará `hloc` con soporte GPU para pareo de puntos.
- **dense_max_image_size**: Resolución máxima (en el lado más largo) para calcular los mapas de profundidad estéreo (PatchMatch). `854` (480p) es súper rápido, `1280` (720p) ofrece más detalle pero toma horas, y más de `1920` (1080p) puede agotar la VRAM de la GPU.
- **sequential_overlap**: Si usas `sift`, la cantidad de fotogramas adyacentes a emparejar. 

#### `slurm`
Configura los recursos del clúster. Es **vital** reservar suficiente tiempo (`time`) si usas MVS denso a alta resolución (se recomiendan al menos `24:00:00` o `48:00:00`).

## ¿Qué hace exactamente el framework bajo la capota?

1. Verifica las instalaciones locales y estima la cantidad de frames.
2. Extrae las imágenes mediante `FFmpeg`.
3. Convierte las coordenadas WGS84 a Cartesianas para alinear el modelo.
4. Genera automáticamente un archivo de trabajo `colmap_job.sh` con los parámetros exactos y lo despacha a la cola de SLURM (`sbatch`).
5. Parchea internamente la configuración (como el `max_depth_error` a 0.5) para solucionar problemas de tolerancia espacial donde COLMAP descarta la nube densa al escalar el mundo con datos GPS reales.

## Autor / Tesis
Desarrollado para la tesis de reconstrucción estructural urbana basada en segmentación de planos.
