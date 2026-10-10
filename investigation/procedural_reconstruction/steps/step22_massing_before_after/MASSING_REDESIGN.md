# Step22: diagnóstico y decisión de arquitectura

## Inspección previa

Rama `step22-compositional-massing`, base `de59f9a`. Se inspeccionaron los
19 request/resolved originales y las 64 comparativas disponibles mediante
planchas que incluyen todas las cámaras (no un muestreo). Se consultaron
TRACKING, AREA_LIBRE_AUDIT y AUDITORIA_COMPARATIVAS y el código fuente real.
1138310 no está disponible. Las auditorías anteriores son hipótesis: por
ejemplo, las lamas del banco son horizontales dentro de marcos verticales,
y el cuerpo amarillo parece vecino del banco gris, no evidencia suficiente
para incorporarlo al mismo lote. Las vistas del grifo muestran épocas distintas.

## Diagnóstico técnico

- **θ:** 19 `single_block`; alturas y cantidad de pisos mal estimadas en
  casa de esquina/crema; repetición comercial indiscriminada, caras ciegas
  y ventanas inventadas. La fachada explícita y sus regiones ya existen.
- **Massing:** seis patrones cortan el lote entero; no hay selector de
  tramo/profundidad por cuerpo ni hueco/patio. La vía explícita exige XY y
  soporte completo; es IR útil pero mala interfaz de inferencia.
- **Exposición:** el cálculo ya resta masas por bandas Z, pero theta aborta
  ante aristas parciales o entidades explícitas atravesando bandas. Snapping
  de líneas oblicuas añade falsos cortes. Techo con hueco también aborta.
- **Retiros:** `linemerge` junta frentes quebrados; la máscara se extiende
  desde extremos de una polilínea como si fuera una recta, recortando solar
  indebidamente. No confundir fallo geométrico con imposibilidad física.
- **Site:** garden booleano no define superficie; cercos por tramos ya
  existen, pero se resta proyección de masas elevadas como si tocaran suelo.
- **Estructuras:** no hay IR para postes/losas independientes. Ocultar ventanas
  no convierte una masa cerrada en marquesina o pilotis.
- **Fachadas:** balcones de longitud arbitraria, galerías parciales, pilastras,
  cornisas y bay windows YA están en prefabs_facade. Falta controlar bandas
  por cuerpo y preservar composición cuando cambia exposición.
- **Techos:** RoofPlan ya admite superficies múltiples, pero el adaptador θ
  solo produce un tipo por cuerpo y rechaza huecos. No requiere un CAD nuevo.
- **Datos:** profundidad posterior, ocupación oculta y alturas absolutas no
  están medidas; catastro/cámara tienen incertidumbre. Árboles/autos/vecinos
  no deben incorporarse al edificio para mejorar artificialmente un render.

## Arquitectura elegida antes de implementar

1. Añadir schema opt-in 0.3: `massing.components` compone **regiones en un
   marco de frente** (arista canónica, tramo normalizado, retiro y profundidad
   métricos o relativos) + niveles Z. Cada cuerpo conserva ID semántico,
   programa de fachada y cubierta. Intersección con parcela configurable;
   tolerancia explícita para ajuste posterior, no deformación implícita.
2. Región menos regiones permite patio/corredor; conservar todas las
   componentes y huecos, sin elegir silenciosamente la mayor. Los polígonos
   resultantes solo son IR, nunca parámetros XY escritos por edificio.
3. Tipo `open` con cubierta/losas y retícula de columnas; masa elevada con
   soporte por cuerpo inferior, columnas o vuelo acotado. Verificación
   geométrica de apoyo, no cálculo de ingeniería estructural.
4. Resolver visibilidad como dominios (u,z) sobre la arista completa.
   Componer fachada una sola vez y recortar geometría emitida a esos dominios;
   no reiniciar ventanas/puertas ni cambiar sus coordenadas en cada banda.
5. Site: regiones tipadas del remanente al suelo, diferenciadas de área
   cubierta; conservar runs de cerco. Reusar Material/MeshData/export GLB.
6. Reusar prefabs; añadir arcos y pantallas/frontones solo tras P0. Exponer
   bandas por cara, cubiertas por cuerpo y techo con huecos. Evidencia con
   selectores estables por ID, incluyendo `prior`; posterior no observado
   permanece inferido/prior.
7. Benchmark: recetas declarativas por carpeta, sin IDs en el generador;
   cámaras/P/semilla originales y BEFORE inmutables. Reportar hipótesis,
   cambios de altura y resultados visuales por lote, no solo malla válida.
