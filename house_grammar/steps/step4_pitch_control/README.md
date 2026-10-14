# Paso 4 — Elevación paramétrica

Desde `investigation/`:

```bash
make run-gsv-step4
make run-gsv-step4 GSV_STEP4_PITCHES="-20 0 25 50"
```

Comparte entrada y parámetros de resolución/FOV del Paso 3. Genera cuatro
elevaciones por cámara por defecto: -30°, 0°, 30°, 60°. Positivo mira al cielo;
negativo al suelo. Mantiene el yaw hacia la misma arista. Cambiar pitch cambia
el rayo central, no estima una altura real ni fija un punto físico 3D.

Las imágenes limpias, comparación y parámetros de cada cámara virtual se
guardan en `outputs/`. Son vistas del mismo centro óptico: no añaden baseline
ni observaciones independientes para triangulación.

Para apuntar mediante un vector XYZ, usar `angles_from_direction(direction)`
y pasar el yaw/pitch resultante a `PinholeCamera`. XYZ se expresa en el marco
del panorama (X derecha, Y arriba, Z centro); no son coordenadas GPS/UTM.
El vector debe ser finito y distinto de cero. En ±90° el yaw determina la
orientación de la imagen alrededor del eje vertical.
