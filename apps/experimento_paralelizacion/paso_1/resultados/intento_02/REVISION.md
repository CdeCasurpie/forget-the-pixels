# Comparación con intento 01

Haiku 4.5: 113.26 s, 21189 tokens de entrada, 6190 de salida, end_turn.
Cambios simultáneos: prompt con diagnóstico diferencial y pares marcado/limpio.
Por ello no se puede atribuir una mejora exclusivamente al prompt.

## Veredicto
Mejor tratamiento explícito de algunas ambigüedades, pero no mejora suficiente
de fiabilidad espacial. No aprobado para traducción automática sin revisión.
No se ejecutó paso 2 ni una tercera llamada.

## Mejoras
- Conserva S1 como candidato a balcón/baranda y reconoce plataforma no demostrada.
- Ya no propone puerta centrada y vanos simétricos como completado.
- No convierte el seto en cerco vegetal-metálico como antes.
- Mantiene tercer nivel como impuesto/no reconocible, sin cambiar el registro.
- Intervalo 5–75% correctamente equivale a 70%.

## Errores persistentes o nuevos (líneas de descripcion.txt)
- 131–138: pasa de no identificar cerco a ausencia comprobada; la clasificación
  del cerramiento metálico frontal sigue sin resolverse. Quitar el cerco inventado
  anterior no demuestra ausencia de cerco real.
- 32: declara ausencia comprobable de cuerpo de azotea porque no lo ve, pese al follaje.
- 42: 'pocos centímetros' y vuelo 0.4–0.6 m son incoherentes.
- 79/84: borde a ~2 m sobre piso frente a barra superior a 1–1.1 m; falta resolver
  si habla de piezas distintas. Tampoco demuestra una plataforma.
- 51: ubica acceso no visible en 25–55% con altura 'esperada' 2.1 m: precisión
  sin evidencia aunque ya no proponga centrarlo.
- 59: llama 'esquina derecha' al intervalo 40–60%, que corresponde al centro.
- 117/125: eleva una franja beige a listones de madera/sol y sombra, sin demostrar
  separación entre listones ni material; podría ser otro recubrimiento. No aceptar
  automáticamente slats como tipo de cubierta.
- 5/27/28 frente a 29: identifica ancho/huella catastral con ancho/huella física
  del cuerpo pese a admitir correspondencia pendiente.
- 71 frente a 201: excluye un vecino de manera firme y luego admite incertidumbre
  sobre el límite. Las aristas del prisma no sustituyen correspondencia de fachadas.
- 89, 110, 123: varias ausencias se afirman sin delimitar zonas realmente visibles.

## Próximo cambio recomendado (no ejecutado)
Priorizar observación de regiones sobre nombres de catálogo: tabla de regiones
visibles con ubicación, rasgos y candidatos, manteniendo clase indeterminada.
Resolver asociación de frente y fotos mediante identificación visual de aristas
y recortes de detalle, sin fingir mediciones de profundidad. Enviar un vocabulario
visual reducido al paso 1, reservando el catálogo técnico completo para paso 2:
la respuesta está eligiendo slats/flat/band antes de demostrar el material real.
Conservar casos ocluidos como prueba difícil y añadir un lote despejado como control.
