# Recorrido dual: GSV vs modelo, misma posición y ángulo

Para cazar errores lote por lote caminando la cuadra.

```bash
# 1) precomputar (una vez): panorama del modelo desde cada camara GSV
python steps/step19_experimental/cuadra_fotos/recorrido/generar_panoramas_modelo.py \
    --cuadra steps/step19_experimental/cuadra_fotos/cuadra_seed_123 \
    --salida steps/step19_experimental/cuadra_fotos/recorrido/recorrido_seed_123

# 2) recorrer:
python steps/step19_experimental/cuadra_fotos/recorrido/ver_recorrido.py \
    --recorrido steps/step19_experimental/cuadra_fotos/recorrido/recorrido_seed_123
```

- Izquierda: Street View real · Derecha: nuestro `cuadra_completa` raytrazado
  (open3d CPU, sin GPU) desde la misma cámara (2.5 m) y heading.
- **W**/Espacio: siguiente panorama (la ruta va ordenada angularmente =
  vuelta a la cuadra) · **S**: anterior · **arrastrar**: mirar ·
  **R**: centrar · **+⁄−**: zoom · **Q**: salir.
- Convención verificada: centro del panorama = heading (igual que
  `extract_full_vertical_strip`), así que el mismo crop vale para ambos.
