# df7d867f — autoría manual desde cero (casa amarilla, paquete bcda015f)

Fotos: `data/barranco/theta_author/runs/bcda015f.../evidence/`
Parcela: 5 vértices, frente F2 = arista 1 (10.5 m). Niveles humanos [0,3,6].
Estilo global: republicano (sí hay ornato: reja con volutas, contraventanas,
tejadillo y alero de teja).

## Lo observado → theta (`request.json`)
- Componente `principal`, región `front_edge 1, u [0,1], depth_m [1.5,12]`
  (jardín/seto de 1.5 m al frente).
- Frente explícito: puerta oscura de reja (construction grille, rings,
  1 hoja) + ventana baja con reja vertical y alféizar; 2 ventanas altas
  1.7×1.6 con reja + 4 contraventanas verdes (`shutter`); ventanita alta
  con reja en retícula (la de lamas exige legacy+perfil: el estilo global
  fuerza perfil vinculado en toda window, hallazgo reutilizable).
- Banda inferior blanca como `material_regions` (slot accent), superior
  amarilla (primary/plaster). Marcos verdes, metal negro, madera verde.
- Techo plano (el `tile_shed` cubría toda la huella y levantaba un prisma
  rojo inexistente) + franja de teja como `canopy` corrido al frente
  (`alero`, shed de teja curva) + tejadillo sobre la puerta.
- Cerco `reja` h 1.1 con base blanca + puerta peatonal frente a la puerta;
  zona `garden` [0,1.5]. Portón verde de la derecha = vecino, excluido.
- Sin balcones/miembros/frontones/entablamentos; trim off (muros en lindero).

## Resultado (`run02/` — corrige techo)
- `building.glb` (11698 vértices, 21796 triángulos), envolvente passed.
- Base del cerco en piedra (el plaster amarillo la teñía).
- 4 violaciones benignas de rejas (barras desconectadas, 0 bordes abiertos,
  0 non-manifold) — misma clase que la demo.
- `comparisons/`: contorno calza con la casa amarilla en las 3 cámaras;
  verde/blanco/beige vecinos excluidos.

## Corrección run03 (dos fachadas, cerco parcial, dos aguas)
- Dos componentes: `ala` (u [0,0.3], retiro 4 m, techo `gable` teja 25°,
  1 ventanita alta, bajos ciegos) + `principal` (u [0.3,1], retiro 1.5 m,
  plano + franja de teja como canopy corrido).
- Cerco `reja` SOLO en el paño izquierdo (u 0–3.6, portón 0.3–2.3);
  el frente principal lleva solo seto (zona garden, sin run).
- Gable básico = 2 sheds (cumbrera paralela a calle); va en
  `component.roof`, no en `theta.roof`.
- Ojo: `material_regions` con ancho mayor al muro real falla
  ("outside facade"): medir contra el `width` resuelto, no el estimado.

## run04 (descripción GPT + correcciones: 2 módulos, dos aguas derecha)
- `f1` u [0,0.32] retiro 1.0, plano + parapeto 0.3, puerta + ventanita;
  `f23` u [0.32,1] a filo de lote (depth 0), gable teja 22° + franja alero.
- Cerco solo paño izquierdo; paso `corridor` a puerta F1; sin jardín.
- Gable básico = 2 sheds con cumbrera paralela a calle.

## run05 (cubierta real del catálogo)
- `roof_assemblies`: gable teja curva 22° como en
  `catalogo_techos/04_dos_aguas_teja_plana` (cumbrera, faldones con teja,
  canecillos) en vez del shed básico + franja.
- `parcel_tolerance_m: 0.1` absorbe el clearance del alero en linderos;
  regiones en u de arista para huellas rectangulares limpias.
- Parapeto F1 en 0 para encuentro limpio con el hastial.

## run06 (migración al catálogo de cercos)
- `runs[0].kind`: `reja` -> `republicano` (el validador ya rechaza legacy).
- 67932 vértices, envolvente passed, 5 violaciones benignas de rejas.
