# Paso 5: vistas cilíndricas de fachada

Este experimento localiza el lote asociado a una coordenada WGS84, selecciona
las cuatro cámaras visibles más cercanas desde el archivo local de Barranco,
descarga únicamente esos cuatro panoramas y genera franjas centradas en la
fachada.

La salida cubre verticalmente todo el panorama, de cenit `+90°` a nadir
`-90°`, con centro vertical en `pitch=0`. Horizontalmente usa por defecto un
FOV de `120°`.

```bash
make run-gsv-step5
```

La coordenada predeterminada es `-12.135895, -77.019184`. Debido a diferencias
de precisión, está a 0.136 m del lote seleccionado (`row=743`,
`objectid=1134979`), dentro de la tolerancia de un metro.

Se guardan panoramas originales, vistas limpias para procesamiento, previews
anotados, mapa de cámaras y metadata de proyección en `outputs/`.
