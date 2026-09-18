# Paso 11 — regeneración procedural por cuadra

Este paso conecta cuatro datos sin fingir que todos ya existen:

```text
catastro EPSG:32718 ──► aristas con espacio exterior libre ──► frentes
        │                                                    │
        └── lote central + radio ──► lote de trabajo          ▼
Step 9 height_fit.json ─► altura revisable ─► gramática ─► OBJ / GLB
```

La arista vial no se define por ser larga. Se orienta el contorno del lote en
sentido antihorario y se mide, en cinco puntos interiores, la distancia al
próximo lote en su lado exterior. Una arista es candidata si al menos 2/3 de
las muestras tienen 1.25 m libres. Esto elimina paredes medianeras y pasajes
estrechos. Es una inferencia catastral: cuando dispongamos de una capa vial,
esa capa deberá confirmar o reemplazar esta clasificación.

Las alturas **no se inventan**. El lote se genera solo si se entrega su
`height_fit.json` de Step 9; el manifiesto enumera los lotes sin altura como
`missing_height`. Por ahora es normal que una cuadra produzca pocas mallas: el
objetivo es hacer visible qué mediciones faltan, no esconderlas con pisos
aleatorios.

Desde `investigation/`:

```bash
/home/cesar/Escritorio/UTEC/PFC1_Lima/venv310/bin/python \
  proy_geom/steps/step11_block_generation/run.py \
  --objectid 1134979 \
  --height-fit proy_geom/steps/step9_height_fit/outputs/height_fit.json
```

Repetir `--height-fit` para cada lote medido. Salidas:

- `fronts.png`: gris = catastro, verde = frente vial inferido, azul = generado.
- `block_manifest.json`: decisión/rechazo por lote, umbrales y validaciones.
- `lot_<id>.json`, `.obj`, `.mtl`, `.glb`: mallas locales y su
  `metadata.local_origin_utm` para ubicarlas de nuevo en EPSG:32718.

## Siguiente ciclo de producción

1. Seleccionar la cuadra por una capa de ejes viales, no solo radio alrededor
   de un lote.
2. Ejecutar pasos 7–9 por cada lote con frente y cámaras visibles; guardar un
   `height_fit.json` por `objectid` tras revisión de calidad.
3. Correr este paso con todos esos fits. Revisar `height_quality` y conservar los lotes omitidos en el
   manifiesto como cola de adquisición.
4. Reemplazar `propose_building` por fachadas inferidas de imágenes: vanos,
   retiro, color y tipología por arista. La gramática no cambia.
5. Empaquetar las mallas locales en un tileset/scene graph georreferenciado;
   no exportar un único OBJ con coordenadas UTM gigantes.
