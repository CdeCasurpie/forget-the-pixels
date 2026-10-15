# Prompt y flujo guía para escribir una gramática

Aquí «escribir una gramática» significa **describir una instancia theta de las reglas implementadas**. Añadir un nuevo tipo de pieza exigiría modificar contrato, resolver, constructor y validación; una clave inventada en JSON no extiende el motor.

## Flujo recomendado

### Paso 1 — Preparar evidencia y coordenadas

Entregar al autor humano/modelo:

- parcela local y frentes confirmados;
- cotas conocidas y cuáles están bloqueadas;
- fotos del mismo edificio con cámara/orientación y aclaración de oclusiones;
- esquema legible de aristas canónicas;
- catálogos pertinentes, con nombres exactos;
- indicación de si se busca reconstrucción fiel o diseño libre.

Un prisma proyectado identifica una hipótesis de lote/altura; no es una segmentación ni prueba de la altura real. No usar sus líneas como medición independiente si proceden del formulario que se intenta estimar.

### Paso 2 — Redactar una descripción antes de elegir piezas

1. Cuerpos principales, relación frente/fondo y número de pisos por cuerpo.
2. Altura del primer piso y de los superiores por separado.
3. Ejes de vanos por cada cara visible.
4. Puertas/ventanas/portones: forma, tamaño, material, marco, reja.
5. Balcones: abierto/cajón/galería, soporte, cubierta y baranda.
6. Orden vertical, bandas horizontales, zócalo y coronación.
7. Cubierta detrás del remate, cuerpos de azotea y props realmente visibles.
8. Retiro, cerco y suelo libre.

Registrar incertidumbre separada de descripción. Una pared lisa no demuestra automáticamente estilo moderno; una puerta de madera no convierte todo el edificio al estilo `madera`.

### Paso 3 — Traducir a theta por capas

1. Contexto + modalidad volumétrica.
2. Resolver y comprobar masas, niveles e IDs.
3. Construir fachadas; resolver y comprobar ejes/vanos.
4. Añadir un grupo de ensambles por vez usando referencias resueltas.
5. Resolver y materializar; atender el error exacto, sin cambiar valores observados para ocultarlo.
6. Validar envolvente/topología, exportar y mirar frente + vista oblicua.
7. Registrar correcciones humanas y evidencia. Conservar `request` y `resolved` por separado.

Para muchos edificios con componentes repetidos, guardar recetas comprobadas con parámetros acotados. La IA elige/ajusta la receta; el motor produce molduras, barrotes y tejas. No pedirle miles de primitivas ni vértices.

## Texto base reutilizable

```text
Eres autor de solicitudes para la gramática theta de este repositorio.
Tu salida final es un JSON válido ReconstructionRequest, no Python ni MeshData.
Usa exclusivamente los campos de REFERENCIA_CAMPOS y los valores de CATALOGOS.
Escribe schema_version="0.3". No inventes nuevas claves ni aliases en español.

Objetivo: [reconstrucción fiel / diseño libre].
Contexto fijo: [parcel, fronts, crs, metric_origin, alturas bloqueadas].
Evidencia disponible: [imágenes y observaciones identificadas].
Restricciones confirmadas: [dimensiones y decisiones humanas].

Antes de entregar JSON:
1. Distingue volúmenes, fachada, piezas ancladas y materiales.
2. Selecciona UNA vía de volumetría:
   - patrón compacto + height_m/floors para niveles iguales;
   - masses explícitas + massing.pattern="explicit", sin height_m/floors;
   - massing.components para regiones relativas al catastro.
3. Para primer piso distinto escribe niveles acumulados en levels_m.
4. family es composición; architectural_style es lenguaje de piezas.
   family NO acepta moderno, madera ni clasico.
5. No uses atributos nominales de estilo para agregar ornamentación no vista.
6. Elige repeat o explicit por superficie. En explicit incluye openings,
   y no incluyas controles exclusivos de repeat. [] significa vacío; null
   solo está permitido si el contrato lo admite y puede disparar completado.
7. Usa coordenadas de la arista/banda/zona, no coordenadas de la foto.
   Abertura u_m es borde izquierdo; miembro vertical u_m es su eje.
8. Reutiliza IDs canónicos obtenidos del resolver; índices desde cero.
9. Selecciona shape, relleno/prefab, perfil y reja por separado.
   Las puertas detalladas necesitan el bloque door.
10. No dupliques un balcón, pilastra o frontón con dos mecanismos distintos.
11. Un frontón no es una habitación ni un techo. Describe por separado la
    cubierta que existe detrás y cualquier cuerpo adicional apoyado.
12. Un balcón terrace/juliet/stair necesita slab=false y anclaje válido.
13. Los pisos superiores y piezas voladas deben tener apoyo/envolvente válidos.
14. Declara lo desconocido con null solo donde sea admisible; no cambies
    evidencia observada para facilitar la generación. Si falta información
    indispensable, solicítala antes de inventar geometría.
15. Usa nuisance.seed fijo y curtains=false durante la revisión geométrica.

Si se te da acceso a ejecución:
- Decodifica con domain.theta.from_json.
- Ejecuta resolve_theta, inspecciona masas/vanos y después reconstruct.
- Ejecuta validate_mesh con street_envelope y analyze_topology por separado.
- Inspecciona la vista frontal y oblicua.
- Corrige únicamente decisiones permitidas, conserva los datos fijos.
- No declares éxito total por el solo hecho de obtener JSON o exportar GLB.

Si no hay ejecución disponible, entrega la propuesta como pendiente de
validación geométrica. No afirmes que un modelo se ha probado o renderizado.
```

## Salida que conviene almacenar alrededor del JSON

Esta información pertenece al flujo de autoría, **no a nuevas claves de theta**:

```text
request.json           solicitud editable
resolved_theta.json    decisiones expandidas y completados
validation.json        contención y malla básica
topology_summary.json  componentes y problemas de identidad/topología
building.glb           resultado visible
revision_humana        decisiones corregidas y motivo (en almacenamiento externo)
```

La procedencia compatible con el contrato puede ir en `observations/evidence`. Los selectores disponibles no cubren todas las colecciones nuevas; para anotaciones que no encajan, usar el almacenamiento externo del flujo, no inventar rutas aceptadas.

## Qué enviar al modelo para ahorrar contexto

- Siempre: estructura raíz, reglas de coordenadas, familia/estilo y restricciones observadas.
- Según necesidad: contrato de la pieza y filas de sus variantes; por ejemplo, catálogo de balcones solo si hay balcón.
- Para silueta compleja: contratos `CrownControls` o `FacadeTopProfile` y una referencia visual del catálogo real.
- Mantener el diccionario completo como consulta: [campos.json](campos.json) permite recuperar contratos individuales sin reenviar todos los módulos.

Los ejemplos [mínimo](ejemplos/minimo.json) y [primer piso diferente](ejemplos/primer_piso_diferente.json) sirven como arranque; la [demo](DEMOSTRACION.md) muestra una composición rica sin depender de una inferencia automática de fotos.
