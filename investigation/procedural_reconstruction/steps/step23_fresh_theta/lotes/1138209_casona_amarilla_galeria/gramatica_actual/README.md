# 1138209 casona amarilla — regenerada con la gramática actual

Base: `fresh/request.json`. Masas, parcela, techos, vanos y accesos **sin cambios**
(posiciones y tamaños de los 11 vanos verificados idénticos).

## Estilo elegido: `republicano`
Casona limeña con galería doble de madera, reja de fierro con aros, surrounds
moldurados y reja diamante. Es la familia que cubre fierro + madera + molduras
sobrias sin inventar ornamentación barroca ni simplificación moderna.

## Qué cambió por gramática
- **Ventanas**: `frame_profile: auto` → perfil republicano, `sill: true`,
  `frame_depth_m: 0.14`; reja diamante conservada (`grille_spacing_m`).
  Nuevas semánticas: `window_profile`, `window_sill`, `window_mullion`.
- **Puertas**: `door.model: auto` en las 3 (vestíbulo + 2 storefront de galería),
  hojas vidriadas, sin portales inventados (`portal: none`).
- **Cercos**: `reja` → `republicano/high` (1.65 m, fotos), con aros
  (`fence_ring`) y puntas (`fence_spear`), base 0.40 m y zócalo escalonado
  de piedra (`trim_plinth`). Portón y posición del acceso intactos.
- **Pilastras/columnas**: las galerías usan el motor nuevo automáticamente
  (`member_shaft`, `member_saddle`, `member_capital`); antes eran cajas
  (`gallery_post`, `gallery_bracket`, `column_capital_echinus/abacus`).
- **Remates**: zócalo del cerco vía gramática de remates. Sin trim perimetral
  global: las cuatro masas comparten medianeras y techos `tile_shed`, y el
  sweep continuo no tiene recorrido expuesto válido (falla verificada en
  `resolve_trims`); los muros conservan su panel, cornisa denticulada y alero
  de evidencia.
- **Balcones**: ninguno nuevo — la casa no tiene balcones volados en fotos,
  solo galerías (que se conservan). No se inventó acceso ni plataforma.

## Resultado
- `building.glb`: 56 388 triángulos / 1 370 partes (fresh: 20 284 / 733).
- `validation.json`: `envelope_test: passed`, 0 área fuera de envolvente.
- `semantics.txt`: lista de semánticas del GLB.
- Script reproducible: `../build_gramatica_actual.py`.
