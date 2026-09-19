# Plan maestro de generación procedural urbana

## 1. Estado real del proyecto

El sistema actual ya resuelve la cadena geométrica básica:

```text
panoramas + poses + catastro
        │
        ├─ selección de cámaras y reproyección (Steps 1–7)
        ├─ observación de borde de techo (Step 8)
        ├─ altura multivista regularizada a pisos (Step 9)
        ▼
BuildingSpecification
        │
        ├─ propuesta de distribución arquitectónica
        ├─ gramática geométrica
        ├─ validación dentro del lote
        ▼
MeshData ──► OBJ/MTL + GLB + render diagnóstico (Step 10)
        │
        └─ generación por conjunto de lotes medidos (Step 11)
```

No se reconstruye todavía la casa exacta de una fotografía. El catastro y la
altura son evidencia geométrica; las ventanas, balcones, acabados, retiro y
elementos de azotea son actualmente hipótesis procedurales reproducibles.

## 2. Contrato actual: entrada y salida

La función geométrica estable es:

```python
generate_mesh(specification: BuildingSpecification) -> MeshData
```

`BuildingSpecification` recibe:

| Campo | Significado | Procedencia actual |
| --- | --- | --- |
| `parcel_xy` | límite legal completo del lote | catastro |
| `footprint_xy` | huella construida, independiente del lote legal | explícita o heurística de `layout.py` |
| `height` | altura continua, regularizada, pisos y calidad | Step 9 |
| `facade_edges` | una especificación por cara exterior | gramática o metadata futura |
| `Opening` | ventana, puerta, portón o ventana de balcón en coordenadas `(u,v)` | heurística actual |
| `material_regions` | zonas cromáticas/materiales por fachada en `(u,v)` | metadata o hipótesis |
| `projections` | paneles, marcos, aleros y marquesinas rectas/curvas | metadata o hipótesis |
| `exterior_stairs` | tramos, descanso y barandas fuera de la huella pero dentro del lote | metadata o hipótesis |
| `appearance` | catálogo PBR por slots semánticos | prior visual o familia |
| `setback` | profundidad, superficie, cerco y lados afectados | argumento o heurística |
| `roof` | techo plano/inclinado, parapeto y accesorios | argumento o default |
| `seed` | variación determinista | `objectid`/configuración |

`MeshData` retorna:

- vértices y triángulos;
- material PBR por cara (color, roughness, metallic, opacity y escala física);
- grupos semánticos (`wall`, `window_frame`, `glass`, `balcony_slab`, etc.);
- UV opcionales —el campo existe, pero la gramática aún no los genera—;
- partes exportables como nodos OBJ/GLB.

La malla usa XY en metros y Z vertical. Es un ensamblaje de sólidos cerrados
que pueden intersectarse entre sí; no es una unión booleana global para
impresión 3D. Los lotes se modelan en coordenadas locales y conservan
`local_origin_utm` para recuperar su posición EPSG:32718.

## 3. Cómo funciona la gramática actual

### 3.1 Selección de tipología

`layout.py` solo conoce tres perfiles:

| Perfil | Regla de uso en batch | Composición |
| --- | --- | --- |
| `narrow` | dimensión mínima del lote menor a 6 m | puerta + ventana ancha en planta baja, ventanas con reja arriba |
| `corner` | más de un frente candidato | ventanas repetidas, balcones periódicos, revestimiento horizontal |
| `courtyard` | caso restante | vanos más anchos y posible portón en planta baja |

Esto no constituye todavía tres familias arquitectónicas completas: son tres
presets de una misma gramática. El estilo no se detecta en la fotografía.

### 3.2 Derivación paso a paso

1. Normalizar la parcela en sentido antihorario.
2. Aplicar separación lateral de 0.20 m y retiro en las aristas de frente.
3. Rechazar la propuesta si el retiro rompe la huella en varios cuerpos o la
   reduce a menos de 1 m².
4. Dividir la altura en pisos uniformes.
5. Para cada fachada frontal, calcular bahías de aproximadamente 2.8–3.4 m.
6. Reservar puerta/portón en planta baja y repetir ventanas en pisos superiores.
7. En el perfil `corner`, convertir una de cada tres bahías superiores en
   ventana de balcón.
8. Cortar el muro alrededor de los vanos sin booleanas 3D frágiles.
9. Añadir marcos, dinteles, alféizares, parteluces, rejas, hojas abatidas,
   zócalos, pilastras, bandas entre pisos, balcones y servicios.
10. Construir techo plano, a una agua o a dos aguas. En techo plano buscar una
    plataforma completamente interior para cuarto, calamina y tanque.
11. Crear cerco/portón solo en los lados declarados y reservar corredores ante
    puertas para no bloquearlos con plantas.
12. Recortar cada sólido contra la parcela, triangular concavidades/patios y
    validar caras y aristas contra el límite catastral.

### 3.3 Variación

La variación actual modifica paleta, modulación y pequeños detalles mediante
una semilla. La misma especificación y semilla produce exactamente la misma
malla. No deben sortearse decisiones independientes por triángulo: la unidad
de coherencia es edificio → fachada → piso → bahía → componente.

## 4. Archivos y responsabilidades

| Archivo | Responsabilidad actual |
| --- | --- |
| `src/domain/models.py` | contratos neutrales del lote, cámara, altura, fachada, vanos y malla |
| `src/procedural_modeling/specification.py` | convierte evidencia estructural en especificación base |
| `src/procedural_modeling/layout.py` | produce una hipótesis arquitectónica determinista |
| `src/procedural_modeling/grammar.py` | deriva fachadas, vanos, detalles, techo, cercos y jardín |
| `src/procedural_modeling/mesh_builder.py` | crea sólidos, vigas, follaje y triangulación restringida |
| `src/procedural_modeling/validation.py` | valida índices, degeneración, materiales y contención |
| `src/procedural_modeling/io.py` | serialización de especificaciones JSON |
| `src/procedural_modeling/block.py` | une lotes, frentes y alturas disponibles para batch |
| `src/cadastral_geometry/street_fronts.py` | clasifica aristas por espacio exterior libre frente a otros lotes |
| `src/exporters/obj_exporter.py` | OBJ/MTL Z-up y grupos semánticos |
| `src/exporters/glb_exporter.py` | GLB Y-up y materiales de color plano |
| `steps/step10_procedural_generation_test/` | casos de aceptación y renders de geometría |
| `steps/step11_block_generation/` | manifiesto y generación de varios lotes medidos |
| `src/texturing/contracts.py` | contrato inicial; no implementa aún materiales PBR |

## 5. Problemas que debemos corregir antes de escalar

1. **Familias insuficientes.** `narrow/courtyard/corner` mezclan forma del lote
   con lenguaje arquitectónico. Un lote de esquina puede ser vivienda popular,
   edificio moderno, almacén o casona.
2. **Planta baja rígida.** La primera bahía siempre tiende a convertirse en
   puerta y el resto sigue pocos patrones.
3. **Masa única.** No hay podio + torre, volúmenes escalonados, patios múltiples,
   ampliaciones informales ni cuerpos separados.
4. **Poca evidencia visual.** Color, material, rejas, balcones y techo no se
   infieren aún de las fotos.
5. **Materialización incompleta.** GLB ya transporta color, metallic, roughness y
   transparencia por slot; aún faltan UV métricas y mapas de textura/normal/AO.
6. **Costo geométrico.** Las rejas y ventanas se duplican como geometría. Un
   lote bajo toma ~0.11 s, pero uno de 12 pisos y 116 864 triángulos toma ~8.72 s.
7. **Frentes por separación, no por vía legal.** Un borde libre puede ser patio,
   parque, vacío catastral o calle. Debe auditarse y luego cruzarse con una capa vial.

## 6. Arquitectura objetivo

La gramática ampliada tendrá cuatro capas independientes:

```text
BuildingEvidence
  │ lote, altura, frentes, observaciones y confianza
  ▼
BuildingProgram
  │ familia, masa, pisos, planta baja, patrón de fachada, techo
  ▼
BuildingSpecification
  │ reglas totalmente resueltas y serializables
  ▼
GeometryGrammar ──► MeshData semántico + UV
  │
  ▼
MaterializationGrammar ──► TexturedMesh/GLB PBR
```

La precedencia será:

```text
valor observado y revisado
    > valor inferido con confianza
    > regla contextual del barrio
    > default determinista de la familia
```

Cada atributo importante debe conservar `value`, `source`, `confidence` y
`view_ids`. Así una puerta detectada nunca es reemplazada por una tirada aleatoria.

## 7. Familias propuestas

Separaremos dos conceptos:

- **implantación:** entre medianeras, aislada, esquina, retiro frontal,
  patio delantero, podio, varios cuerpos;
- **lenguaje:** vivienda popular incremental, vivienda Barranco tradicional,
  multifamiliar moderno, comercial de planta baja, industrial/almacén.

Cada familia define rangos y reglas, no una malla fija:

| Dimensión | Opciones iniciales |
| --- | --- |
| Masa | bloque completo, bloque con retiro, L/U, podio + volumen, escalonada |
| Planta baja | residencial, cochera, comercio, muro/portón, jardín/reja |
| Pisos altos | repetitivo, alternado, balcones continuos, balcones puntuales |
| Vano | corredizo, batiente, paño completo, ventana enrejada, puerta/portón |
| Composición | ejes alineados, bandas horizontales, módulos irregulares controlados |
| Techo | plano, terraza, calamina ligera, una/dos aguas, ampliación informal |
| Borde | abierto, muro, reja, muro bajo + reja, portón vehicular |

La selección de familia debe ser una entrada explícita o una distribución de
probabilidades trazable; nunca una consecuencia accidental del ancho del lote.

## 8. Materiales procedurales PBR

No proyectaremos una foto sobre una geometría que no coincide. Extraeremos de
las fotos **priors de apariencia**: tipo de material, color dominante, color de
acento, marco, vidrio, techo y nivel de desgaste.

Contrato propuesto:

```python
@dataclass(frozen=True)
class MaterialSpecification:
    family: str                 # stucco, brick, concrete, wood, glass, metal
    texture_set: str
    base_color_rgb: tuple[float, float, float]
    real_scale_m: float
    roughness: float
    metallic: float
    opacity: float = 1.0
    normal_strength: float = 1.0
    weathering: float = 0.0
    seed: int = 0

@dataclass(frozen=True)
class BuildingAppearance:
    wall: MaterialSpecification
    ground_floor: MaterialSpecification
    accent: MaterialSpecification
    frame: MaterialSpecification
    glass: MaterialSpecification
    door: MaterialSpecification
    roof: MaterialSpecification
```

La biblioteca tendrá `basecolor`, `normal`, `roughness`, `ao` y opcionalmente
`height`. Las UV se calculan en metros en el sistema local de cada fachada:
`U=u/real_scale_m`, `V=v/real_scale_m`. El patrón se repite, no se estira.

Las ventanas tendrán marco, vidrio PBR, plano interior oscuro/cortina y, para
LOD alto, interior mapping. Esto evita vidrio transparente que parece un hueco
negro. La suciedad y variación se aplican de forma continua por fachada, no por
triángulo.

API objetivo:

```python
materialize_building(
    mesh: MeshData,
    specification: BuildingSpecification,
    appearance: BuildingAppearance,
    library: MaterialLibrary,
) -> TexturedMesh
```

## 9. Frentes de lote: validación y precálculo

El clasificador actual ya aplica la lógica de proximidad exterior: orienta el
lote, toma cinco muestras interiores de cada arista, avanza 5 cm hacia afuera
y calcula distancia al lote vecino. Con `neighbour_clearance_m=1.25`, una
arista pasa si al menos 2/3 de sus muestras están libres.

La validación debe realizarse en tres escalas antes de usarlo para todo Barranco:

1. Un lote aleatorio: verde si no encuentra otro lote a 0.5–1.0 m hacia afuera,
   rojo/gris si choca o queda cerca; mostrar índice y distancia mínima.
2. Diez lotes aleatorios: comparar visualmente medianeras, esquinas y formas
   cóncavas; ajustar umbral y muestras.
3. Todo Barranco: guardar JSON versionado por `objectid`, CRS, orientación de
   anillo, endpoints, normal exterior, longitud, distancias por muestra,
   clasificación, parámetros y versión del algoritmo.

Cuando exista capa vial, se añadirá `road_confirmed` por distancia/intersección.
Hasta entonces se llamará `exposed_edge`, no `street_edge`, porque “vacío” no
demuestra legalmente que exista una pista.

## 10. Niveles de detalle y rendimiento

| LOD | Uso | Geometría |
| --- | --- | --- |
| LOD1 | mapa distante/cuadra | masa, techo, color/material general |
| LOD2 | navegación urbana | huecos, marcos, balcones y cercos simplificados |
| LOD3 | primer plano | rejas, molduras, servicios, vegetación, interiores falsos |

Las repeticiones deben convertirse en instancias: una geometría de ventana,
baranda o reja reutilizada con transformaciones. Para GLB se evaluará
`EXT_mesh_gpu_instancing`; para exportadores sin instancing habrá una opción de
materialización. Meta preliminar: menos de 1 s para LOD2 de 12 pisos y menos de
30 000 triángulos por edificio típico.

## 11. Plan de implementación

### Fase A — contratos y trazabilidad

1. Añadir `EvidenceValue`, `BuildingProgram`, `BuildingAppearance` y catálogo de
   familias sin romper `BuildingSpecification` v2.
2. Crear esquema JSON v3 con migración v2 → v3.
3. Separar selección de familia de la geometría del lote.
4. Registrar cada decisión en un `derivation_report.json`.

**Criterio:** misma entrada/semilla produce mismo spec; toda decisión indica su fuente.

### Fase B — gramática geométrica ampliada

1. Implementar masa por componentes y patios múltiples.
2. Crear gramáticas independientes de planta baja y pisos repetitivos.
3. Añadir balcones continuos, voladizos, cochera/comercio y más tipos de techo.
4. Resolver encuentros en esquinas, medianeras y fachadas muy cortas.
5. Introducir LOD1/LOD2/LOD3 e instancing.

**Criterio:** cero caras fuera del lote; 100 semillas por familia sin errores ni
vanos superpuestos; prueba específica de polígonos cóncavos y rotados.

### Fase C — apariencia PBR

1. Crear biblioteca pequeña y licenciada: estuco, concreto, ladrillo, madera,
   metal, vidrio y calamina.
2. Generar UV métricas por semántica y tangentes para normal maps.
3. Extender GLB con texturas PBR, transparencia y materiales por nodo.
4. Implementar variación de color/desgaste basada en `objectid`.
5. Añadir vidrio con interior simplificado.

**Criterio:** ausencia de estiramiento, escala material consistente y validación
visual en Blender/visor glTF bajo tres iluminaciones.

### Fase D — priors visuales

1. Empezar con un JSON manual por lote para validar el contrato.
2. Extraer color con máscaras robustas y balance entre cámaras.
3. Clasificar material, reja, balcón, retiro y tipo de techo con confianza.
4. Agregar revisión humana de atributos inciertos.
5. Pasar únicamente priors a la gramática; no proyectar píxeles sobre vanos que
   no corresponden geométricamente.

**Criterio:** comparación contra 30 fachadas anotadas y reporte por atributo,
no una sola puntuación agregada.

### Fase E — cuadra y distrito

1. Validar y precalcular aristas expuestas de todo Barranco.
2. Ejecutar alturas por lote y conservar faltantes como cola de adquisición.
3. Generar tiles georreferenciados por cuadra con presupuesto de LOD.
4. Añadir capa vial para confirmar frentes y agrupar cuadras reales.
5. Construir una galería de regresión visual y métricas de rendimiento.

## 12. Próximo incremento recomendado

El siguiente incremento debe ser **PBR antes que detección automática**:

1. implementar contratos `MaterialSpecification`/`BuildingAppearance`;
2. escoger manualmente apariencia para tres casas de referencia;
3. generar UV métricas y siete materiales PBR base;
4. exportar GLB texturizado y evaluar visualmente;
5. solo después automatizar los priors desde fotos.

Así podremos saber si la gramática y el materializador producen el nivel visual
deseado antes de invertir tiempo en un clasificador que quizá entregue datos
que el generador todavía no sabe representar.
