# Cubiertas, aleros y encuentros con frontones

## Revisar los resultados

```bash
python3 steps/step23_fresh_theta/generar_techos.py
# Regenerar solo casos de un catálogo ya existente:
python3 steps/step23_fresh_theta/generar_techos.py --only 12 19
```

`steps/step23_fresh_theta/catalogo_techos/` contiene 20 casos. Cada carpeta
incluye `building.glb`, `request.json`, `resolved_theta.json`,
`resolved_roofs.json`, `validation.json` y `manifest.json`. No se generan renders.

Para empezar: `05_cuatro_aguas`, `08_compuesto_L`, `11_tornapuntas`,
`12_mensulas_curvas`, `14_sol_sombra`, `15_fronton_hastial` y
`19_casona_compuesta`.

## Contratos y archivos

- `domain/roof_details.py`: forma, revestimiento, bordes, cubiertas por masa y marquesinas.
- `modeling/roof_planes.py`: partición en faldones afines y envolvente superior
  de cuerpos rectangulares superpuestos.
- `modeling/roof_detail_resolver.py`: herencia, anclajes, encuentros, recortes,
  validaciones, sustitución y agrupación.
- `modeling/roof_assembly.py`: soporte, tejas, chapas, listones, piezas de
  cumbrera, limahoyas, estructura visible, aleros y tapas.
- Integración en `resolve_theta` / `generate_resolved`; clasificación de
  bordes a partir de caras compartidas, no por identificadores de edificios.

## Sustitución por masa

```json
{
  "architectural_style": "republicano",
  "roof_assemblies": [{
    "id": "cubierta_principal",
    "mass_ref": "house:0",
    "design": {
      "form": "hip",
      "covering": "curved_tile",
      "slope_deg": 22,
      "detail": "full",
      "substrate_material": "wood",
      "material": "roof_tile",
      "eave": {
        "kind": "profiled",
        "overhang_m": 0.4,
        "spacing_m": 0.55,
        "beam_width_m": 0.08,
        "beam_height_m": 0.14,
        "fascia": true,
        "gutter": false
      }
    }
  }]
}
```

Una entrada activa reemplaza las superficies y el parapeto antiguos de esa
masa. No superpone una segunda losa. Los props existentes se conservan solo
si la nueva cubierta es plana. `enabled: false` desactiva la sustitución y
deja vigente el techo base; no elimina el techo de la casa.

`props_mode: preserve` conserva los props explícitos; `off` los desactiva;
`auto` propone hasta seis objetos sobre cubierta plana con semilla estable y
pesos por estilo. La selección incluye macetas, tanques, tragaluces, tendederos
y equipos según la familia. No altera la forma de un tanque por estilo.

Los requests antiguos que no seleccionan `roof_assemblies` conservan el motor
de roofscape existente. Esta entrega no modifica silenciosamente todas las
reconstrucciones guardadas. El prefab legacy `eave` sí delega en el ensamblador
común mediante un adaptador de colocación y nombres semánticos.

## Formas

| Forma | Regla |
|---|---|
| `flat` | Superficie horizontal; admite parapeto y tapa independientes. |
| `shed` | Un plano; asciende en la dirección `rotation_deg`. |
| `gable` | Dos planos; `rotation_deg` es la dirección transversal a la cumbrera. |
| `hip` | Envolvente inferior de planos ascendentes desde cada borde convexo. |
| `pavilion` | Mismo algoritmo sobre un perímetro convexo poligonal. |
| `band` | Faldón delantero de profundidad `band_depth_m` y resto plano sin tejas. |
| `compound` | Unión de lóbulos rectangulares mediante su envolvente superior. |

En `gable`, `ridge_fraction` mueve la cumbrera: la pendiente de la segunda
agua se deriva para mantener la misma altura y ambos arranques a igual cota.
`slope_deg` corresponde a la primera agua. No son dos pendientes independientes.

Para `compound`, `regions` contiene polígonos XY que deben cubrir exactamente
la planta de soporte. Cada lóbulo dispone la cumbrera en su eje largo. Se
eliminan las partes inferiores en las intersecciones y aparecen limahoyas reales.
Las plantas L/T ortogonales se construyen con estos lóbulos; no se promete
resolver cualquier polígono cóncavo sin descomposición.

Varias masas pueden compartir `join_group`. Deben estar conectadas, a igual
cota base y tener construcción/acabados compatibles. Las superficies se
resuelven juntas para evitar fascias interiores. Cubiertas a distintas alturas
se mantienen independientes: los muros más altos recortan la cubierta adosada;
si sus sólidos de cubierta chocan se exige corregir el encuentro.

## Revestimientos y detalle

`construction: solid` emite el soporte continuo; `frame` lo omite para una
cubierta ligera. Por ejemplo, `frame` + `panel` + `material: glass` permite
una cubierta transparente sobre viguetas, sin un tablero opaco debajo.
Las tejas exigen soporte continuo. La estructura visible se configura en `eave`.

- `curved_tile`: canales y cobijas alternados, sección curva con espesor.
- `flat_tile`: hiladas de piezas planas, juntas alternadas y solape.
- `corrugated`: ondulaciones volumétricas a lo largo del faldón.
- `panel`: lámina base y paños/juntas modulares.
- `slats`: listones separados; no se emite tablero continuo por debajo.
- `none`: soporte sin revestimiento añadido.

Ancho, longitud y solape son métricos. Al cambiar el techo aumenta el número
de piezas. Las tejas curvas se recortan con tapas cerradas conservando su
sección; las cumbreras tienen piezas curvas independientes. Las limahoyas
utilizan un perfil metálico en V. No se han modelado fijaciones ni selladores.

`full` usa nueve muestras transversales de teja; `medium`, cinco. `light`
utiliza una capa lisa y remates de aristas: es una reducción geométrica, no un
atlas de tejas generado automáticamente. Máximo de 18 000 módulos por faldón.

## Aleros y marquesinas

`eave.kind` admite `clean`, `closed`, `exposed`, `profiled`, `braces`, `curved`
y `cornice`. `auto` hereda:

| Estilo | Alero inicial |
|---|---|
| republicano | Canes perfilados |
| barroco / clasico | Cornisa con el perfil del estilo |
| madera | Canes rectos visibles |
| moderno | Canto limpio |

Material, forma y revestimiento siguen siendo independientes de esta elección.
Los canes y diagonales tienen sección rectangular; las ménsulas curvas son
extrusiones continuas. Fascia, sofito y canalón son controles independientes.
El canalón se coloca en bordes bajos horizontales; no añade bajantes automáticas.

`theta.canopies` especifica `mass_ref`, `edge`, `u_m`, `width_m`, `depth_m` y
`height_m`, más `design`. La altura es la del extremo exterior bajo respecto
a la base del muro. Si se indica `opening_index`, la marquesina se centra
sobre el vano y se sitúa 0.25 m sobre su dintel. `posts: true` reutiliza miembros
verticales de madera. Las marquesinas de madera cerradas incluyen tablazón
inferior con juntas; `slats` deja huecos reales.

## Encuentros con frontones

```json
{
  "id": "cubierta",
  "mass_ref": "house:0",
  "crown_ref": "fronton",
  "junction": "gable",
  "design": { "form": "gable", "covering": "flat_tile" }
}
```

- `gable`: necesita frontón triangular de ancho completo sobre la misma masa.
  El frontón determina dirección, pendiente y altura. Se elimina el vuelo
  del conjunto en esta modalidad para mantener el hastial coincidente.
- `behind`: permite cubierta detrás de un coronamiento curvo/escalonado/etc.
  Se reserva el espesor del frontón más 35 mm de junta. La cubierta y las tejas
  terminan allí; se sustituye el alero de ese borde por un remate metálico.
- `none`: independencia, sin relación implícita.

Los vanos explícitos del coronamiento se comprueban frente a la sección de
cubierta detrás del hueco completo. El sistema rechaza un hueco respaldado por
el cierre bajo cubierta; no es una simulación de iluminación.

Los frontones decorativos sobre puertas siguen siendo piezas de fachada.
No se transforma automáticamente una moldura curva en una cubierta curva.
No hay unión booleana global: tejas, soporte, muro y molduras conservan sus
componentes, con recortes y cierres controlados. Los cierres bajo cubierta
(`roof_gable_closure`) continúan el acabado superior del muro que prolongan,
incluidas sus regiones de material; no usan un enlucido fijo. El cierre solo
traslapa 20 mm con la coronación del muro y vuela 10 mm sobre su cara, y se
recorta 5 mm antes de cualquier masa vecina para no tocarla directamente.

## Parapetos y off

`parapet_m: 0` desactiva el parapeto. `cap` puede ser `none`, `flat`, `bevel`,
`pitched`, `moulded` o `metal`. `cap_drip` añade un borde plegado y solo es
compatible con tapa metálica. La tapa detallada toma precedencia sobre la
cornisa de trim anclada al mismo parapeto.

Para un borde limpio: `eave.kind: clean`, `fascia: false`, `soffit: false`,
`gutter: false`, `overhang_m: 0`. Ninguna opción off añade una pieza decorativa
oculta. `covering: none` conserva la estructura portante elegida.

## Límites explícitos

- Patios interiores: usar masas separadas; la cubierta detallada rechaza una
  planta de soporte con agujeros.
- No hay cubiertas curvas, mansardas, buhardillas ni reconocimiento automático
  de techo desde fotos.
- Los once props de azotea se reutilizan en superficies planas. No se agregan
  chimeneas/tragaluces apoyados en pendientes.
- Cubiertas legacy de galerías mantienen su contrato; una marquesina nueva se
  controla con `canopies` y requiere desactivar la cubierta anterior si coincide.
- La agrupación de tejas conserva componentes individuales dentro de las
  primitivas exportadas; los catálogos de detalle completo son más pesados.

## Comprobaciones

Pruebas de partición sin solapes, continuidad de aristas, limahoyas, sólidos
cerrados con volumen positivo, variantes de canes/ménsulas, tapas/off,
recorte detrás de frontón, cubiertas compartidas y roundtrip JSON. Validación
de envolvente en cada GLB. Una validación geométrica aprobada no sustituye
la revisión visual ni representa verificación estructural.
