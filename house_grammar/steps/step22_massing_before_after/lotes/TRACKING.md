# Recorrido por lote — before con gramática actual (plan de trabajo)

## Instrucciones internas y algoritmo de propuesta θ (no olvidar)
Meta: aproximarse **todo lo posible con la gramática actual** sin masas
explícitas. La máscara identifica el edificio, pero el contexto de cada foto
decide qué es jardín, cerco, vecino, oclusión y fachada. No confundir límites
del catastro con la silueta edificada ni inventar rasgos tras árboles.

### 1. Evidencia antes de parámetros
- Abrir **todas** las fotos `present`: JPG original, `_overlay.jpg`,
  `_masked.jpg` y `_lot.jpg`; descartar vistas `absent`. Anotar rasgos seguros,
  inciertos y ocluidos, y si las fotos muestran épocas/obras distintas.
- Preguntar: ¿qué parte es el edificio objetivo?, ¿cuáles son vecinos,
  árboles, autos, cerco y vereda? ¿El box calza en planta? ¿Qué vistas muestran
  frente y costados? Medir proporciones en píxeles con referencias entre
  vistas, sin convertir una altura aparente en altura catastral cierta.
- Escribir una ficha por lote con clasificación de uso/estilo y evidencia
  por foto: número de niveles, altura aproximada, orientación, ancho del
  frente, setback, fachada inferior y superior (pueden ser distintas),
  ventanas/puertas/garaje (número, ejes, anchuras, altura de antepecho,
  simetría, rejas, forma arqueada), balcones reales vs. barandas de ventana,
  voladizos/cuerpos salientes vs. toldos, cornisa/parapeto/techo, pintura,
  recubrimientos, cerco (material, altura, puerta, portón, tramos) y jardín.
  Estimar porcentaje ajardinado **como observación**, no como control θ.

### 2. Separar P, θ y ξ
- P = polígono del catastro original EPSG:32718, normalizado a metros locales;
  frentes = `street_edge_indices` de `lot_fronts.json` mapeados por extremos
  al orden del anillo (`build_lot_before.py:ring_fronts`). El desfase JSON
  sirve únicamente para la ubicación comparativa en las cámaras.
- θ = solo controles arquitectónicos compatibles con `src/domain/theta.py`
  y `src/modeling/theta.py`; ξ = semilla fija para comparación. Conservar el
  JSON solicitado, el θ resuelto, la validación y la justificación de cada
  parámetro importante. **No pasar `theta.masses` ni `pattern=explicit`.**

### 3. Árbol de decisión para usar la capacidad completa de src
1. **Implantación y altura:** ¿la construcción ocupa el frente o hay jardín
   entre fachada y calle? Probar `massing.front_setback_m` antes de añadir
   `site.fence` (un cerco no puede solaparse con el edificio). Elegir `single_block`,
   `stepped_back`, `podium_tower`, `front_tall_rear_low`,
   `front_low_rear_tall` o `corner_accent` solo si las fotos muestran esos
   volúmenes; un balcón/toldo no justifica una masa nueva. Altura/floors a
   partir de pisos visibles; en solares oblicuos validar exposición parcial.
2. **Fachadas:** ¿qué familia de `src/modeling/facade_program.py` produce la
   planta baja y la superior más próximas? Comparar `quiet_house`,
   `republicano`, `quinta`, `balcony_apartments`, `mixed_use`, `workshop`,
   `galeria_madera`, `esquina_comercial`, `brick_courtyard`, `ribbon_windows`.
   No elegir familia solo por color: comprobar programa de baja, ritmo de
   vanos arriba, barandas/cornisa. Si la composición repetida sobra, usar
   `facade.bay_count` o `bay_axes_m` y `window_ratio`, `window_height_m`,
   `sill_m`; `balconies=false` elimina balcones falsos. Para diferencias
   puntuales usar `opening_edits` (suppress/replace) y `added_openings`;
   para una cara distinta, `facades` con override por arista de **masa
   canónica**, que no equivale necesariamente al índice del catastro.
   Si el patrón repetido nunca sirve, `mode=explicit` para fachadas se permite
   (distinto de masas explícitas), con vanos individuales y material_regions;
   no asumir que produce arcos si el prefab no los implementa.
3. **Sitio:** ¿cerco sí/no? Elegir `site.fence` entre `reja`, `concreto`,
   `ladrillos`, `concreto_bajo`, `none`, o `site.runs` para tramos con portón/
   puerta sin solapamiento. `site.garden` es **booleano**: la gramática no
   controla porcentaje ajardinado. Registrar en la ficha observado vs.
   representable; no prometer 40% si θ solo dice true.
4. **Materiales/techo y detalle:** `primary_color` no basta si la baja usa
   piedra/gris por familia; probar `theta.materials` por slot (p. ej.
   `stone`, `plaster`, `frame`, `metal`, `accent`) con plantilla existente y
   color propio. `side_material`, `roof.kind` (`flat`, `corrugated`,
   `tile_shed`), `parapet_m`, `finish`, `facade.cladding`, `services`,
   `projections` solo cuando la observación los respalde. Verificar que
   `roof.props`/material_regions y prefabs tienen efecto real en el render.
5. **Candidatos controlados:** crear al menos 2 hipótesis si son plausibles
   (familia, setback/cerco, ritmo de vanos, material baja) manteniendo P,
   cámaras y ξ. Resolver y validar antes de exportar. Comparar silueta,
   altura, ubicación, vacíos, color de baja/alta, cercos y jardines en TODAS
   las vistas `compare_<cam>.jpg`, con prioridad a geometría/frente y luego
   estilo. Rechazar mejoras de una sola vista que empeoren las demás.

### 4. Entrega por lote
- Crear `lotes/<id>_<slug>/README.md` con ficha, incertidumbres,
  parámetros probados, elección y brechas comprobadas de la gramática.
- Generar `before/`: `request.json`, GLB, `resolved_theta.json`,
  `render_<cam>.jpg` mismo ojo/orientación/FOV y `compare_<cam>.jpg` foto |
  render por vista present. Ajustar el generador si se necesitan controles
  adicionales **ya existentes** en src: no limitar θ a los flags actuales
  del CLI. Inspeccionar el render final; después actualizar este checklist.
- `after/` queda vacío hasta ampliar la gramática. No modificar `src` en
  esta fase; documentar las limitaciones que requieran una ampliación.

## Checklist (20 lotes)
- [x] 1135847_local_comercial_bajo (3 present / 2 absent) — before revisado: storefront + pantalla de lamas
- [x] 1135369_esquina_demolicion (5 present) — before H3: 2 niveles, vanos asimétricos; H1/H2 descartadas
- [x] 1134299_casa_salmon_republicana (4 present / 1 absent) — before revisado: vanos explícitos, baja salmón; setback falla en lote irregular
- [x] 1134486_restaurante_terraza (4 present) — before generado
- [x] 1137173_grifo_marquesina (3 present) — before generado; marquesina exenta fuera del vocabulario
- [x] 1135384_comercio_ladrillo_blanco (2 present) — before generado
- [x] 1135382_casa_blanca_esquina (5 present) — before generado
- [x] 1135572_casa_ladrillo_balcon (3 present) — before generado
- [x] 1135370_edificio_crema_balcones (3 present) — before generado
- [x] 1137568_comercio_blanco_dos_plantas (2 present) — before generado
- [x] 1138261_edificio_azul_cristal (3 present) — before generado
- [x] 1137619_banco_neoclasico (5 present) — before generado
- [x] 1138323_casona_amarilla_esquina (5 present) — before generado
- [x] 1138316_muro_local_bajo (4 present) — before generado; evidencia fragmentaria
- [x] 1138310_lote_sin_vista_etiquetada (0 present / 5 absent) — malla tentativa + 5 renders sin comparativas: fachada no identificable
- [x] 1138283_vivienda_verde_tres_pisos (2 present) — before generado
- [x] 1138401_comercio_rojo_rejas (2 present) — before generado
- [x] 1138477_edificio_blanco_balcones (2 present) — before generado
- [x] 1138183_bloque_moderno_balcones (5 present) — before generado
- [x] 1138209_casona_amarilla_galeria (2 present) — before generado

## En curso
20/20 lotes tienen `before/` con malla validada, 19/20 con comparativas.
**Área libre:** ver `AREA_LIBRE_AUDIT.md`; `1135370` regenerado con retiro
0.5 m y cerco bajo. En los otros 19 lotes probados, retiros 0.5–4 m son
rechazados por la geometría actual de θ; no marcar jardín o cerco como
renderizados solo porque aparecen como booleanos en un JSON.
Los 17 casos de `build_remaining.py` son **primeras propuestas clasificadas
manualmente**, no optimizaciones exhaustivas ni semejanza comprobada al
100 %. Para una segunda pasada: comenzar por mayores fallas volumétricas
1137173 (marquesina), 1137619/1138323 (casonas de una planta en lotes
grandes) y 1138183 (bloque de balcones). Ajustar fachadas explícitas solo
tras inspeccionar cada comparativa a tamaño completo.

## Regla: ningún lote se descarta
Si hay demolición, obra, oclusión o información parcial, reconstruir la
configuración visible más defendible con la gramática actual; anotar qué
partes están ocultas y qué controles faltan. En 1135369 hay cinco fotos
del edificio en demolición: usar esas vistas segmentadas, no inferir sin
evidencia una supuesta fachada anterior. Nunca marcarlo como descartado.

## Segunda pasada: gramática composicional 0.3

- [x] Implementación P0/P1 y tests geométricos de cuerpos, huecos, exposición,
  cercos, áreas libres, cubiertas parciales y estructuras abiertas.
- [x] 19/19 lotes disponibles con `after/request.json`, GLB, θ resuelto,
  validación de envolvente y 64/64 comparativas de vistas `present`.
- [x] Revisión visual por lote y limitaciones restantes en
  `../AFTER_REVIEW.md`; arquitectura y diagnóstico en
  `../MASSING_REDESIGN.md`.
- [ ] Ajuste multivista automático de parámetros por máscaras/rooflines:
  futuro módulo de inferencia, fuera de esta iteración de gramática.

`1138310`: cinco vistas `absent`, sin carpeta actual ni `after` evaluable.
El checklist anterior describe el *before* en el momento de aquella pasada;
no implica que exista actualmente su carpeta.
