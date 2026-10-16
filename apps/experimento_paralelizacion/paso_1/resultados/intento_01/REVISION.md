# Revisión del primer resultado

Modelo: claude-haiku-4-5-20251001. Duración: 117.41 s. Entrada: 18159 tokens;
salida: 6045 tokens. Terminó con end_turn, sin truncamiento.
Comparación manual contra las tres fotografías proyectadas, sin ground truth geométrico.

## Veredicto
Útil como inventario preliminar, insuficiente para traducir automáticamente a theta fiel.
No se ejecutó paso 2. Se conserva la respuesta original sin corregir sus afirmaciones.

## Aciertos
- Registra las restricciones humanas y la fuerte oclusión por árboles/vehículos.
- Distingue el prisma de la silueta observada; no rellena el tercer nivel con ventanas inventadas.
- Recorre todos los grupos del cuestionario, da IDs y separa una propuesta hipotética final.
- No añade frontones/pilastras por la sugerencia republicana y reconoce que el fondo es desconocido.

## Problemas concretos
- Líneas 19 y 91: afirma coronación observada a ~6 m mientras en 99 declara cubierta/coronación oculta. La discrepancia con los 9 m debe ser una hipótesis, no una medición demostrada.
- Líneas 77–78: clasifica rejas como barandas/balcones continuos sin demostrar plataforma ni relación con la fachada. En las fotos hay cerramientos metálicos altos; falta distinguir cerco, portón, reja de vano y baranda. No aceptaría B1/B2 directamente como balcones.
- Línea 105: convierte un seto de acera en C1, cerco del lote. No demuestra pertenencia catastral ni su supuesto componente metálico. Riesgo de generar un cerco inexistente o en lugar incorrecto.
- Línea 116: 'no hay portón visible' pasa a 'descarta acceso vehicular', pese a la oclusión y a los paños metálicos visibles. Esa ausencia no está comprobada.
- Línea 77: intervalo 10–90% ocupa 80%, pero dice ancho ~90%. Tabla de vanos introduce cotas 3.3–5.5 m sin justificar su relación con alturas estimadas de 1.2–1.8 m.
- Ventanas agrupadas como 2–4 o 2–3 sin ubicaciones individuales: prudencia adecuada si no son visibles, pero deja sin resolver lo necesario para el paso 2.
- Línea 180: puerta centrada y ventanas simétricas son propuestas sin evidencia; aunque etiquetadas como hipótesis, el segundo modelo puede materializarlas como hechos.
- La asociación de planos/aristas e izquierda/derecha cambia entre secciones; no se ha demostrado con correspondencias proyectadas. No usarla como geometría fiable sin revisión.

## Siguiente prueba recomendada
Mantener este intento como baseline. Proporcionar pares marcado/limpio de cada vista
y un recorte de detalle de la fachada, conservando la referencia de lote. Exigir que
la clasificación cerco/portón/baranda/plataforma cite señales visuales diferenciadoras.
No sugerir puerta centrada ni simetría como completado visual. Un conflicto de niveles
debe quedar pendiente cuando la coronación está oculta. Revisar estos puntos antes
de convertir el texto actual en theta; no hace falta abandonar el flujo de dos pasos.
