# Datos compartidos

Los datos de Barranco viven físicamente en `data/barranco/`, fuera del motor
`investigation/procedural_reconstruction`. La migración conserva el contenido y
la estructura interna existentes:

- `lotes/`: catastro y archivos geográficos originales.
- `poses_barranco/`: metadata y estado de adquisición de panoramas.
- `fotos_barranco/`: panoramas descargados; los archivos nuevos siguen excluidos
  de Git. Las fotografías que ya estaban versionadas conservan su seguimiento.
- `panoramas/`: imágenes previamente almacenadas en ese directorio.
- `cadastral_offset.json`: desplazamiento catastral existente; no se aplica ni se
  modifica durante la migración.

`investigation/procedural_reconstruction/data` es un enlace simbólico relativo
a `../../data/barranco`, sin una segunda copia de las imágenes. Permite seguir
ejecutando los steps históricos con sus rutas originales. El visor de lotes y
el descargador acceden directamente a la ubicación nueva, independientemente
del directorio desde donde se ejecutan.

El visor mantiene su comando habitual desde `investigation/procedural_reconstruction`:

```sh
python steps/step21_lot_fronts/lot_photo_viewer.py
```

No se ha reorganizado aún el dataset en revisiones, manzanas o ejecuciones de IA;
esa estructura corresponde a la implementación futura descrita en los tres
documentos de aplicaciones situados en la raíz del repositorio.
