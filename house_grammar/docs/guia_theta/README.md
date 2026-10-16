# Cómo escribir un theta para esta gramática

Esta guía describe **la implementación del repositorio**, no una gramática arquitectónica universal. Revisión de `src/` y de la casa de demostración; versión del materializador: `grammar-v1.1-dev`. Las rutas de código de esta carpeta son relativas a `house_grammar`.

## Mapa de lectura

1. **Este archivo:** qué es theta, cómo construirlo y cómo se transforma en geometría.
2. [Catálogos y apariencia](CATALOGOS.md): palabras admitidas, aspecto y compatibilidades.
3. [Referencia completa de campos](REFERENCIA_CAMPOS.md): todos los contratos alcanzables desde `ReconstructionRequest`, tipos y valores predeterminados extraídos del código.
4. [Recorrido archivo por archivo](MODULOS.md): responsabilidad y entradas/salidas de los 100 archivos Python de `src/`.
5. [Casa de demostración](DEMOSTRACION.md): desglose concreto, ejecución y hallazgos.
6. [Prompt y flujo de autoría](PROMPT.md): texto reutilizable para producir solicitudes.
7. [Catálogo único de techos](../../../CATALOGO_TECHOS.md): losa plana, cubiertas, orientación, cuerpos de azotea y migración.

Los campos estructurales están en las dataclasses; las opciones de texto y las incompatibilidades están repartidas entre los resolvers y los constructores. **Aceptar un JSON por tipos no equivale a poder generar su geometría.** Existe también un [inventario previo de Step23](../../steps/step23_fresh_theta/GRAMATICA_CAPACIDADES_Y_USO.md), con rutas y números de línea antiguos; esta guía contrasta los contratos y constructores actuales.

## 1. Qué es theta

Theta es una **descripción declarativa de decisiones arquitectónicas**. No es código Python, una malla, una imagen ni el formulario reducido de B. El motor interpreta esas decisiones y produce piezas geométricas.

La solicitud completa tiene esta estructura:

```text
ReconstructionRequest
├── context       parcela métrica, frentes, origen y altura bloqueada
├── theta         arquitectura que se solicita
├── nuisance      semilla y cortinas
├── config        implementación, política de completado y detalle
├── observations  referencias a imágenes/cámaras
└── evidence      procedencia y confianza por parámetro
```

Distinciones fundamentales:

| Concepto | Control | Significado |
|---|---|---|
| Composición de fachada | `theta.family` | Ritmo, proporciones y programa predeterminado: vivienda, comercio, galería, etc. |
| Lenguaje de piezas | `theta.architectural_style` | `republicano`, `barroco`, `clasico`, `madera`, `moderno`. Perfiles y variantes compatibles. |
| Forma construida | `massing`, `masses`, `roof_bodies` | Volúmenes, niveles, vacíos y cuerpos sobre azotea. |
| Distribución en pared | `facade`, `facades`, `faces`, `zones` | Vanos, materiales y relieve de cada superficie. |
| Ensambles | `balconies`, `vertical_members`, `crowns`, etc. | Objetos paramétricos anclados a entidades existentes. |
| Apariencia física | `materials`, `primary_color`, `side_material` | Materiales y color; no sustituyen la forma. |
| Azar secundario | `nuisance` | Variación de cortinas/vegetación y detalles; no decide pisos ni masas. |

**No existe `theta.style`, ni `floor_height_m`, ni `first_floor_different` en este contrato.** Esos últimos pertenecen al formulario del estimador/autor. Para un primer piso de 3.1 m y dos superiores de 2.3 m, escribir niveles `[0, 3.1, 5.4, 7.7]` en una masa o componente.

## 2. Coordenadas: dónde queda cada cosa

- Geometría en **metros**, plano XY y Z hacia arriba. `crs` predeterminado: `EPSG:32718`.
- Entregar geometría local; `metric_origin` registra el origen, pero `reconstruct()` no resta automáticamente grandes coordenadas UTM ni coloca la malla exportada sobre un mapa.
- `context.parcel`: anillo sin huecos, válido; el motor lo orienta antihorario y lo comienza en el vértice lexicográficamente menor.
- `context.fronts`: índices de aristas del anillo recibido; se remapean al normalizar. Los índices de `PlanRegion.front_edge`, `FenceRun.edge` y de las masas se interpretan sobre sus anillos canónicos.
- En fachada, `u_m` recorre la arista **desde `vertex_a` hacia `vertex_b`**, y `v_m` sube desde la base de la pared/banda. No es izquierda en la pantalla de una foto arbitraria.
- Profundidad positiva = hacia afuera. `FacadeZone.offset_m < 0` retranquea la pared.
- `PlanRegion.u` y `FacadeZone.u` son fracciones de 0 a 1; no metros. `depth_m` es métrico; `depth` es fracción de profundidad.
- `levels_m` contiene cotas absolutas locales: primera = base, última = coronación de la masa. `floor_m` de un balcón y `bottom_m` de un miembro son relativos a la base de su masa.
- Los índices `floor`, `bay`, `group`, `opening_index`, `edge` empiezan en **0**. `opening_index` refiere al orden resuelto, no a un identificador de ventana.

Ejemplo de parcela `[[0,0],[12,0],[12,16],[0,16]]`: frente 0 va de `(0,0)` a `(12,0)`, interior hacia +Y y calle hacia −Y. En esa fachada `u_m=2` está a 2 m de `(0,0)`.

Las masas obtienen IDs como `principal:0`. En `masses`, el orden canónico usa rol, centroide, base y geometría; no asumir que el primer objeto del JSON recibe el índice 0 global. En componentes, el ID proviene de `component.id` y del fragmento resultante. Usar las referencias del resultado de `resolve_theta()`.

## 3. Elegir una de tres formas de volumetría

### A. Patrón compacto

Se suministran `height_m`, `floors` y un patrón. Sirve para edificios sencillos con pisos uniformes.

```json
{
  "context": {"parcel": [[0,0],[12,0],[12,16],[0,16]], "fronts": [0]},
  "theta": {
    "schema_version": "0.3",
    "height_m": 6.4,
    "floors": 2,
    "family": "quiet_house",
    "architectural_style": "moderno",
    "massing": {"pattern": "single_block"},
    "facade": {"bay_count": 3, "balconies": false, "projections": [], "material_regions": []},
    "roof": {"kind": "flat", "parapet_m": 0.4, "props": []}
  },
  "nuisance": {"seed": 23, "curtains": false}
}
```

Otros patrones: `stepped_back`, `podium_tower`, `front_tall_rear_low`, `front_low_rear_tall`, `corner_accent`. Sus parámetros activos se describen en el catálogo.

### B. Masas explícitas

Se escriben huellas XY y niveles. Adecuado cuando ya se conoce la geometría, como la casa de demostración.

```json
{
  "schema_version": "0.3",
  "massing": {"pattern": "explicit"},
  "masses": [{
    "role": "principal",
    "footprint": [[0,0],[12,0],[12,12],[0,12]],
    "levels_m": [0,3.1,5.4,7.7]
  }]
}
```

Este fragmento va en `theta`. **Omitir `height_m` y `floors`**: se derivan de los niveles. No añadir retiros a `massing`; en esta modalidad debe ser exactamente `pattern="explicit"` con los otros campos en sus defaults. Las masas no pueden interpenetrarse y las elevadas deben estar apoyadas. Aquí las alturas entre niveles deben estar entre 2.2 y 6 m.

### C. Composición relativa al catastro

Usa `schema_version="0.3"` y `massing.components`. Describe franjas/rectángulos en el marco de un frente, que se intersectan con la parcela. Es útil para inferir una organización sin inventar cada vértice XY.

```json
{
  "schema_version": "0.3",
  "family": "quiet_house",
  "massing": {
    "components": [{
      "id": "principal",
      "region": {"front_edge": 0, "u": [0,1], "depth_m": [3,13]},
      "levels_m": [0,3.1,5.8],
      "faces": [{"face": "front", "controls": {"bay_count": 3, "balconies": false}}]
    }]
  }
}
```

- `kind="enclosed"`: volumen cerrado. `kind="open"`: losas y apoyos, sin fachadas cerradas.
- `cutouts`: regiones que se restan; permiten patios y fragmentar un componente.
- `support.kind`: `bearing`, `columns`, `cantilever`; comprueba apoyo geométrico, **no es cálculo estructural**.
- `region.fit="parcel"` recorta al catastro; `rectangle` conserva el rectángulo y exige caber dentro de la tolerancia.
- `parcel_tolerance_m`: 0–2 m, solo en composición. No aumentarlo como reparación automática de un theta erróneo.
- `depth_m` reemplaza a `depth`: dejar este último en su default `[0,1]`.
- Un componente con `facade=null` es **ciego**, incluso frente a calle. Dar `facade`, `faces` o `zones` explícitamente.
- `levels_m` admite incrementos ≥0.5 m en esta vía; no confundir esta flexibilidad con el límite 2.2–6 m de masas explícitas.
- `roof_bodies`: añade un cuerpo encima de un componente padre. Requiere composición 0.3 y un `parent` existente. Altura 2.2–6 m; su región tiene que estar sostenida por ese padre.

Existe además el adaptador Python `modeling.base_massing.with_base()`: transforma `BaseFloor`, `Setback` y `Bite` en componentes por piso. **No son claves JSON adicionales de theta.**

## 4. Construir las fachadas

### `repeat`: regla más correcciones

1. Elegir `family`.
2. Definir **una** distribución: `bay_count`, `bay_axes_m` o `bay_groups`.
3. Ajustar `window_ratio`, `window_height_m`, `sill_m`.
4. Ajustar balcones y profundidad si la familia lo permite.
5. Usar `opening_edits` (`suppress` / `replace`) para excepciones, o `added_openings` para vanos extra.
6. Para grupos, `opening_programs` cambia tipo, forma, dimensiones y reja por `group`/`floor`.

`bay` es una crujía/eje rítmico de fachada, no un piso ni un hueco físico obligatorio. Los grupos dejan espacios ciegos entre intervalos. `ground_role="inherit"` no inventa una puerta de entrada; `entrance` y `garage` requieren `count=1`.

El ritmo se compone sobre la pared completa **antes** de recortarla por exposición a otras masas: un vecino no debe desplazar puertas ni reiniciar la numeración.

**Detalle de implementación:** el compositor theta no usa automáticamente todos los atributos del compositor V4. En particular `arch_ground`, `arch_upper` y el `pitch` del catálogo de familias no hacen que `repeat` produzca arcos o ese paso exacto. Para arcos usar `OpeningProgram.shape`, una abertura explícita o una edición. El paso automático de theta parte de aproximadamente 3.1 m.

### `explicit`: escribir cada objeto

```json
{
  "mode": "explicit",
  "openings": [
    {"kind":"door", "u_m":1.0, "v_m":0.12, "width_m":1.2, "height_m":2.4,
     "door":{"model":"auto", "construction":"panelled"}},
    {"kind":"window", "u_m":4.0, "v_m":0.9, "width_m":1.5, "height_m":1.6,
     "prefab":"slim_window", "grille":true, "sill":true}
  ],
  "projections": [],
  "material_regions": []
}
```

Requiere `openings` (puede ser `[]`). No mezclar con `bay_count`, dimensiones repetitivas, `opening_edits` ni `added_openings`. `door.model="auto"` necesita estilo global. La variante explícita no hereda el programa repetitivo de la fachada global.

### Alcance y prioridad

- `theta.facade`: default de frentes de masas convencionales; laterales son ciegos por defecto.
- `theta.facades[]`: override por `mass_role` y `edge`. Puede activar una cara no orientada a calle.
- En componentes: `facade` base; `faces[]` modifica bandas verticales de una orientación (`front/back/left/right/all`); la última banda activa gana donde coinciden.
- `zones[]` delimita un rectángulo `u × z_m`, con composición propia; se sustrae del programa base y puede desplazar el plano. Sus interiores no deben solaparse.
- Coordenadas de aberturas dentro de una zona empiezan en la esquina inferior de esa zona. En correcciones repetidas de zonas, `floor` conserva el índice del piso del componente.
- `section` añade losa/columnas a un retranqueo de al menos 0.3 m; `back_wall=false` pide un espacio abierto con controles explícitos vacíos. No puede cruzar una losa intermedia.

En overrides repetitivos los campos no nulos se mezclan con el global. **Las tuplas vacías también son no nulas:** no asumir herencia profunda de listas. Es más seguro declarar los grupos/motivos/programas completos por superficie.

### `null`, omisión y `[]`

- `null` significa desconocido **solo si el tipo lo permite**; el resolver puede completarlo.
- Omitir un campo usa su default de dataclass, que no siempre es `null`.
- En `repeat`, `projections=null` deja producir el relieve de familia; `[]` lo desactiva.
- `material_regions=null` y `[]` no añaden pintura automática de familia. El acabado se declara con `wall_material`, `side_material` y regiones explícitas. Las regiones asignan materiales al muro existente, sin cáscaras superpuestas: [guía de materiales](../../../MATERIALES_MUROS.md).
- En `explicit`, `projections=null` acaba vacío; no produce el catálogo repetitivo.
- `balconies=[]` en theta significa no añadir ensambles independientes; **no cancela** los balcones producidos por `facade`/familia.
- `projections=[]` no anula piezas pedidas separadamente mediante `motifs`, `order` o `crowns` de fachada.

## 5. Añadir piezas por anclaje

Después de resolver masas y vanos, usar las referencias resultantes:

| Colección | Qué crea | Anclaje |
|---|---|---|
| `balconies` | Plataforma, baranda, galería o cajón | Masa, arista, nivel `floor_m`, tramo `u_m/width_m` |
| `vertical_members` | Pilastra, columna, poste | Masa, arista, eje `u_m`, base/altura y posición |
| `crowns` | Frontón volumétrico | Pared superior, sobrevano o cota de fachada |
| `entablatures` | Arquitrabe + friso + cornisa continuos | Conjunto de masas y cota superior |
| `entrances` | Escalones, rampa o paso | Abertura existente `door/gate` |
| `roof_assemblies` | Cubierta detallada que reemplaza superficies básicas | Masa con techo expuesto |
| `canopies` | Marquesina/cobertura adosada | Pared o abertura |

No duplicar una pieza de `projections` con un ensamble independiente en el mismo sitio. Los resolvers comprueban varias de estas colisiones y rechazan combinaciones incompatibles.

El estilo global comprueba compatibilidad de ventanas, puertas, balcones, miembros independientes, frontones y entablamentos. **No es un override universal:** las cubiertas permiten estilo local, los cercos lo declaran en `kind`, y diseños anidados de columnas/portales pueden seleccionar otro estilo. La galería de la demo usa columnas anidadas `madera` dentro de un edificio republicano.

## 6. Qué no debe confundirse arriba del edificio

| Necesidad | Control adecuado |
|---|---|
| Cambiar silueta continua de la pared con vanos atravesándola | `facade.top_profile` |
| Frontón sencillo adicional de fachada | `facade.crowns` (`triangular/stepped`) |
| Frontón volumétrico con moldura y óculo | `theta.crowns` |
| Habitación/torre con volumen y techo detrás | `roof_bodies` o una masa/componente |
| Forma real de cubierta | `roof_assemblies[].design.form` |
| Tanque, antena, cuarto de servicio decorativo de azotea | `roof.props` |

Un frontón no aumenta automáticamente los pisos. `height_m` de theta es coronación de masas: cubiertas inclinadas, parapetos y frontones pueden superar esa cota. Un `caseta` de props no tiene el mismo contrato arquitectónico que un `roof_body`.

## 7. Camino real hasta la malla

```text
JSON
  → domain.theta.from_json / decode
  → pipeline.theta.reconstruct
      valida observations y evidence
      → modeling.theta.resolve_theta
          expande roof_bodies
          normaliza parcela y completa defaults
          resuelve masas e IDs
          calcula exposición y compone fachadas
          resuelve techos básicos, cercos, apoyos y sitio
          resuelve trim, balcones, miembros, frontones,
                    entablamentos, entradas y cubiertas detalladas
          → ResolvedArchitecture
      → modeling.theta.generate_resolved
          resuelve materiales y semilla secundaria
          grammar.facade → pared perforada + abertura + relieve
          construye estructuras, suelo, techos y piezas ancladas
          → MeshBuilder.finish → MeshData
  → validate_mesh / analyze_topology
  → export_glb o export_obj
```

`ResolvedArchitecture` conserva `completed` y `completion_details`: valores completados, heredados o derivados. Es el lugar para auditar qué inventó/completó el motor. No enviar ese resultado completo como si fuera otro `ThetaCandidate`.

`observations` y `evidence` **no disparan visión ni inferencia de fotografías** dentro de `reconstruct()`. El futuro flujo IA tiene que observar y construir theta antes de llamar al motor.

La ruta `from modeling import generate_mesh` exporta actualmente **`generate_v4_mesh`**, no el generador theta. Para esta guía usar `pipeline.theta.reconstruct` o `modeling.theta.generate_from_theta`.

## 8. Comprobar y exportar

Desde la raíz del repositorio:

```bash
python3 house_grammar/docs/guia_theta/revisar_theta.py \
  house_grammar/steps/step23_fresh_theta/casa_demostracion_barranco/request.json \
  --output /tmp/opencode/mi-theta
```

Se guarda solicitud, resultado resuelto, validación geométrica, resumen topológico, perfil de llamadas y GLB. El script exige una carpeta de salida nueva para conservar ejecuciones anteriores. La comprobación topológica puede reportar diferencias de identidad de componente aun cuando el límite geométrico pasa; leer el diagnóstico.

Añadir `--preview` genera una vista frontal y oblicua con color base (requiere Matplotlib). Ejemplos completos comprobados con el mismo script:

| Solicitud | Qué muestra | Triángulos | Envolvente | Violaciones topológicas |
|---|---|---:|---|---:|
| [Mínimo](ejemplos/minimo.json) | Patrón compacto de dos pisos | 1 640 | Pasa | 0 |
| [Primer piso diferente](ejemplos/primer_piso_diferente.json) | Componente con niveles `[0,3.1,5.8]` y vanos explícitos | 3 572 | Pasa | 1 |
| [Casa con balcón republicano](ejemplos/casa_balcon_republicano.json) | Dos masas, balcón con aros, pilastras, frontón con óculo, entablamentos, cerco y patio | 52 448 | Pasa | 2 |

La violación del segundo ejemplo es una `window_grille` con nueve componentes desconectados dentro del mismo registro, sin bordes abiertos, aristas no-manifold, caras duplicadas ni degeneradas. Es el mismo tipo de diagnóstico que aparece en la [demostración](DEMOSTRACION.md).

Para regenerar el diccionario estructural después de cambiar contratos:

```bash
python3 house_grammar/docs/guia_theta/generar_referencia.py
```

## 9. Hallazgos que afectan a un prompt

1. **Dos pipelines conviven.** Documentación/nombres de V4 no son automáticamente claves de theta.
2. **Familia no equivale a estilo.** `family="madera"`, `family="moderno"` o `family="clasico"` no están en `FAMILY_RULES`; usar las familias del catálogo.
3. **El esquema 0.3 hay que pedirlo:** el default del contrato aún es `0.2`.
4. **`auto` depende del contexto:** sin estilo global, muchos ensambles necesitan estilo explícito. No usar `auto` en cualquier string.
5. **`RoofBody.trim` se declara pero no se copia** al `MassComponent` en `expand_roof_bodies()` actual. No prometer que ese override funcione.
6. **No todos los controles de ventana llegan al mismo constructor.** `architectural_style` fuerza perfiles vinculados en `kind="window"`; estos aceptan relleno `legacy/slim_window/storefront/open`, no `wood_panel/screen/louver`. `family="quinta"` + estilo global puede producir esta incompatibilidad en repetición.
7. **Cortinas:** `nuisance.curtains` asigna cobertura a ciertos vanos, pero el constructor de ventana vinculada no la dibuja; el constructor prefab tradicional sí. No prometer cortinas visibles en todos los estilos.
8. **La declaración de estilo no convierte puertas simples en ensambles completos.** Hace falta `Opening.door`; además evitar `frame_profile` en una puerta sin ese bloque, pues el despacho intenta el constructor de ventanas.
9. **Los rótulos tienen alfabeto limitado.** Los caracteres no soportados hacen que no se genere el texto, aunque el docstring diga “rejected”.
10. **Validación por fases:** varias comprobaciones (puertas, ventanas, geometría final) ocurren al materializar, no solo al resolver.
11. **`trim` y `top_profile` no combinan actualmente** en una masa con remates perimetrales: el resolver exige coronaciones horizontales.
12. **No es un sólido booleano único ni un plano estructural.** Es un ensamble de componentes; validar sus identidades y topología por separado.

Los hallazgos describen el código revisado; no cambian el comportamiento de la gramática.
