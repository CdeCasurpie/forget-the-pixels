# Casa salmón: base simplificada con detalle completo

`base.json` describe dos pisos de 3,5 m, retiro frontal de 1,4 m y mordida lateral hasta 5 m. `request.json` es el theta completo compilado, consumible por `from_json` y `reconstruct`; incluye fachadas, cubierta, materiales, cercado y zonas exteriores.

Se reutilizó el programa detallado de `fresh/request.json` para probar específicamente el cambio de base. Las fachadas se corresponden por su plano físico, no por índices antiguos. Los vanos se distribuyen por piso y conservan posición mundial; la bajante continua se divide al pasar de piso. Se verifican el número de vanos y la igualdad de los tramos de cerco.

Generado con `../build_base_completa.py`, ejecutable desde `investigation/procedural_reconstruction`. Hay cuatro renders y comparativas en las cámaras originales. Validación de envolvente aprobada.

## Diferencias pendientes

- La base ocupa el fondo catastral, mientras el anterior `fresh` terminaba a 15 m.
- El render frontal muestra una junta/banda gris entre componentes de piso: la separación por pisos necesita revisión para no introducir un remate visual ajeno a la fachada.
- El cercado conserva la simplificación anterior (portones macizos y barras sencillas); no reproduce la reja ornamental de la foto.

Esta prueba demuestra integración con detalles, no equivalencia visual exacta con `fresh` ni fidelidad completa a Street View.
