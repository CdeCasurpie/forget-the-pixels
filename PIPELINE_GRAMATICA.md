# Índice vivo: de theta al edificio 3D

> **Primera lectura al retomar el proyecto.** Rutas relativas a la raíz del repositorio. Estado documentado: 15-10-2026, tras el commit `6a1e996`. Este índice describe la **ruta theta vigente**; que un módulo histórico siga en el árbol no significa que forme parte de ella. Actualizar este archivo al cambiar contratos, catálogos, etapas o comandos.

## 1. Resumen operativo

```text
ReconstructionRequest (JSON)
  └─ domain.theta.from_json / decode (tipos, claves y defaults)
      └─ pipeline.theta.reconstruct (observaciones y evidencia)
          ├─ modeling.theta.resolve_theta (decisiones → ResolvedArchitecture)
          └─ modeling.theta.generate_resolved (arquitectura → MeshData)
              └─ modeling.exporters.glb_exporter.export_glb (malla → building.glb)
```

La entrada real no es un `theta` aislado: es un `ReconstructionRequest` con `context` y `theta`; lo demás tiene defaults. `reconstruct()` devuelve `ReconstructionResult(requested, resolved, mesh)`: **no escribe archivos**. El runner de Step18 sí valida, exporta y guarda diagnósticos. La evidencia fotográfica no genera geometría implícitamente.

## 2. Árbol orientado a la ruta activa

```text
forget-the-pixels/
├── PIPELINE_GRAMATICA.md                 ← este índice
├── CATALOGO_VANOS.md                     ← catálogo vigente de vanos
├── CATALOGO_TECHOS.md                    ← catálogo vigente de techos
├── README.md, Makefile                   ← contexto y arranque de A/B
├── apps/
│   ├── cadastral_editor/                 ← A: geometría catastral y frentes
│   ├── theta_author/                     ← B: autoría/evidencia; proveedor mock
│   └── theta_estimator/                  ← estimaciones parciales, no solicitud completa
├── packages/                             ← código compartido por aplicaciones
├── data/barranco/                        ← fuentes y estado local; no es catálogo de gramática
└── house_grammar/
    ├── requirements.txt, README.md, ARCHITECTURE.md
    ├── assets/pbr/catalog.json           ← catálogo de texturas PBR
    ├── docs/guia_theta/
    │   ├── README.md                     ← tutorial, coordenadas y advertencias
    │   ├── REFERENCIA_CAMPOS.md          ← esquema completo y defaults
    │   ├── CATALOGOS.md                  ← vocabulario arquitectónico
    │   ├── MODULOS.md                    ← inventario de módulos de src/
    │   ├── DEMOSTRACION.md, PROMPT.md    ← caso explicado y autoría
    │   ├── revisar_theta.py              ← diagnóstico ampliado
    │   └── ejemplos/                     ← solicitudes completas
    ├── src/
    │   ├── domain/                       ← contratos de entrada y piezas
    │   ├── pipeline/                     ← orquestación pública theta
    │   ├── modeling/                     ← resolución y construcción geométrica
    │   │   ├── exporters/                ← GLB/OBJ
    │   │   └── texturing/                ← catálogo/carga PBR
    │   ├── spatial/                      ← utilidades geoespaciales
    │   └── vision/                       ← adquisición/proyección/estimación, separadas
    ├── steps/
    │   ├── step18_theta_interface/       ← runner JSON → GLB + diagnósticos
    │   │   ├── run.py, README.md
    │   │   └── examples/01_simple.json
    │   ├── step22_massing_before_after/  ← comparaciones de volumetría
    │   └── step23_fresh_theta/           ← solicitudes por lote y catálogos visuales
    └── tests/                            ← pruebas y fixtures de regresión
```

El árbol omite deliberadamente outputs, autosaves, renders, GLB y archivos auxiliares. `house_grammar/data` enlaza a `../data/barranco`. **No existe** `house_grammar/src/data/` con catálogos JSON arquitectónicos: las reglas están principalmente en módulos Python; `assets/pbr/catalog.json` trata de texturas.

## 3. Contrato JSON y semántica

Fuente de verdad: [`house_grammar/src/domain/theta.py`](house_grammar/src/domain/theta.py); campos exhaustivos en [`REFERENCIA_CAMPOS.md`](house_grammar/docs/guia_theta/REFERENCIA_CAMPOS.md). `decode()` rechaza campos no admitidos, tipos incorrectos y números no finitos; `from_json()` decodifica la solicitud; `canonical()` produce serialización determinista. Pasar el esquema sintáctico no garantiza que la geometría sea realizable.

| Campo superior | Contrato y finalidad |
|---|---|
| `context` **obligatorio** | `parcel` (anillo XY métrico sin agujeros), `fronts` (índices de aristas), `crs` default `EPSG:32718`, `metric_origin`, `locked_height_m`. Se exige al menos un frente. El origen se conserva como metadato: `reconstruct()` no traslada automáticamente coordenadas UTM a locales. |
| `theta` **obligatorio** | `ThetaCandidate`: `height_m`, `floors`, `family`, `architectural_style`, `massing`, `masses`, `roof_bodies`, `facade`, `facades`, `roof`, `roofs`, `site`, `materials`, color/acabado y ensambles anclados (`balconies`, `vertical_members`, `crowns`, `entablatures`, `entrances`, `roof_assemblies`, `canopies`, `trim`). `schema_version` tiene default `0.2`; declarar `0.3` al usar composición. |
| `nuisance` | `seed=0`, `curtains=true`: azar secundario, no decide el volumen principal. |
| `config` | `GrammarConfig`: `implementation="theta-candidate-v0"`, `grammar_reference="grammar-v1.0"`, `completion_policy="conservative-0.2"`, `detail=2`. Esas etiquetas no son equivalentes a la versión efectiva del materializador en `modeling/version.py`. |
| `observations` | Referencias a vistas (`view_id`, `image_path`, pose y fecha opcionales). IDs únicos; no se leen/procesan las imágenes durante `reconstruct()`. |
| `evidence` | Mapa de selectores de campos theta a `Evidence(state, confidence, view_ids)`. Se validan estados (`observed`, `inferred`, `prior`, `unknown`, `externally_known`), confianza 0–1 y vistas existentes. `unknown` exige valor `null`; `observed`/`externally_known`, valor no nulo. Selectores de colecciones usan IDs/rol/arista, no posiciones arbitrarias. No modifica el theta. |

Coordenadas: XY en metros, Z hacia arriba; la parcela se orienta y rota a anillo canónico. Los frentes se remapean desde índices del anillo recibido. `levels_m` son cotas absolutas locales (base a techo); `u_m` avanza por la arista dirigida `vertex_a → vertex_b`, `v_m` sube desde la base local. `PlanRegion.u` y `FacadeZone.u` son fracciones 0–1; `depth_m` son metros; offset positivo sale de la pared y negativo retranquea. Índices `edge`, `floor`, `bay`, `group` y `opening_index` son base cero. No asumir que el orden de `masses` en JSON coincide con sus IDs resueltos.

`null` solo es válido en campos opcionales y puede pedir completado; campo omitido usa su default de dataclass; `[]` indica ausencia explícita, no necesariamente herencia. Ejemplo: `facade.projections=null` permite relieve por familia en modo repetitivo, mientras `[]` lo desactiva. `theta.balconies=[]` no elimina balcones creados por la fachada. No existen las claves `theta.style`, `floor_height_m` ni `first_floor_different` en este contrato.

### Formas de definir el volumen

1. **Patrón compacto:** `height_m`, `floors` y `massing.pattern` (`single_block`, `stepped_back`, `podium_tower`, `front_tall_rear_low`, `front_low_rear_tall`, `corner_accent`). Se completan parámetros faltantes sujetos a restricciones.
2. **Masas explícitas:** `massing.pattern="explicit"`, `masses=[{role, footprint, levels_m}]`. No proporcionar `height_m` ni `floors` redundantes; derivan de niveles. Huellas válidas, sin interpenetración y masas elevadas apoyadas.
3. **Composición catastral 0.3:** `massing.components=[{id, region, levels_m, kind, cutouts, support, facade, faces, zones, roof, trim}]`; regiones relativas a frente se recortan contra parcela. `roof_bodies` agrega cuerpos sobre un componente padre. `kind="open"` genera losas/apoyos; `facade=null` es ciego aun frente a calle. `PlanRegion.fit="rectangle"` debe caber dentro de tolerancia. El soporte es comprobación geométrica, no ingeniería estructural.

`family` fija programa y ritmo de fachada (reglas en `modeling/facade_program.py:FAMILY_RULES`); `architectural_style` controla lenguaje de perfiles/piezas (`republicano`, `barroco`, `clasico`, `madera`, `moderno`). No son el mismo selector. `facade.mode="repeat"` compone crujías, grupos, programas y ediciones; `mode="explicit"` exige `openings` y define vanos individuales. `facades[]` ajusta una masa/arista; `faces[]` y `zones[]` actúan sobre componentes, con sus propias coordenadas y prioridad. Catálogos de palabras y compatibilidades: [`CATALOGOS.md`](house_grammar/docs/guia_theta/CATALOGOS.md), [`CATALOGO_VANOS.md`](CATALOGO_VANOS.md), [`CATALOGO_TECHOS.md`](CATALOGO_TECHOS.md).

## 4. Flujo de resolución y construcción, paso a paso

| Fase | Qué ocurre | Código principal |
|---|---|---|
| 1. Decodificar | JSON → dataclasses estrictas; defaults y rechazo de claves no reconocidas. | `domain/theta.py:from_json`, `decode` |
| 2. Verificar procedencia | Revalidar solicitud, IDs de vistas y rutas/estados de evidencia. No hace inferencia visual. | `pipeline/theta.py:reconstruct`, `_evidence_value` |
| 3. Resolver contexto y masa | Normalizar parcela/frentes, completar controles, expandir `roof_bodies`, materializar patrones/huellas/recortes y soportes, crear IDs estables. | `modeling/theta.py:resolve_theta`, `assembly.py`, `top_composition.py`, `geometry_constraints.py` |
| 4. Componer fachadas | Calcular exposición entre masas; componer programa sobre pared original antes de recortar visibilidad; distribuir vanos y relieve; resolver zonas, profundidad y remates. | `exposure.py`, `visibility.py`, `facade_composition.py`, `facade_program.py`, `facade_depth.py`, `facade_top.py` |
| 5. Resolver otras piezas | Techos básicos/detallados, cercos, sitio, trim, balcones, miembros, coronas, entablamentos y accesos; verificar anclajes y conflictos. | `roofscape.py`, `roof_detail_resolver.py`, `boundaries.py`, `fences.py`, `site.py` y resolvers especializados |
| 6. Resultado semántico | `ResolvedArchitecture`: `context`, `theta`, `masses`, `walls`, `roofs`, `boundaries`, `structures`, `site_zones`, ensambles, `completed` y `completion_details`. **No es una malla ni otro theta de entrada.** | `modeling/theta.py:ResolvedArchitecture` |
| 7. Materializar | Materiales/semilla y presupuesto de detalle; paredes perforadas, vanos, relieve, pisos, techos, cercos y ensambles → primitivas trianguladas. | `modeling/theta.py:generate_resolved`, `grammar.py:facade`, `opening_catalog.py`, `mesh_builder.py` |
| 8. Validar/exportar | Runner comprueba envolvente/malla, escribe solicitud, resuelto y manifiesto, exporta GLB y vistas ortográficas diagnósticas. | `modeling/validation.py`, `modeling/exporters/glb_exporter.py`, `steps/step18_theta_interface/run.py` |

La resolución valida varias combinaciones; otras comprobaciones (p. ej. ciertas puertas, ventanas y geometría final) ocurren **al materializar**. `completed` y `completion_details` permiten auditar decisiones derivadas. El compositor de fachadas theta **no** importa automáticamente todas las opciones del compositor histórico V4.

## 5. Mapa de archivos: dónde cambiar cada cosa

**Contratos y núcleo.** `src/domain/theta.py`: esquema theta y serialización; `src/domain/models.py`: `Opening`, materiales, fachadas y `MeshData`; `src/domain/architecture.py`: masas/planes reutilizados. `src/domain/{balconies,vertical_members,crowns,entrances,roof_details,fence_catalog}.py`: contratos y vocabularios de piezas. `src/pipeline/theta.py`: interfaz `reconstruct`. `src/modeling/theta.py`: resolver, arquitectura resuelta y materializador. `src/modeling/assembly.py`: composición de regiones/masas/apoyos; `base_massing.py`: adaptador Python de pisos y retiros (no claves JSON nuevas); `top_composition.py`: cuerpos de azotea; `exposure.py` y `visibility.py`: oclusión y recorte preservando coordenadas de pared.

**Fachadas y vanos.** `src/modeling/facade_composition.py` aplica repetición, grupos, correcciones y vanos explícitos; `facade_program.py` define familias y relieve (también tiene funciones usadas por V4). `facade_depth.py` resuelve planos retrasados y secciones; `facade_top.py` la silueta superior. `grammar.py` materializa pared perforada y delega el vano; `opening_catalog.py` normaliza/valida el despacho vigente; `window_assembly.py`, `door_assembly.py` y `apertures.py` construyen rellenos/contornos. `prefabs.py`, `prefabs_facade.py`, `ornaments.py` contienen piezas auxiliares y adaptadores: no elegirlos como nueva API de entrada de vanos sin revisar el despacho actual. El catálogo vigente y ejemplos están en [`CATALOGO_VANOS.md`](CATALOGO_VANOS.md).

**Techos, perímetro y piezas ancladas.** `roofscape.py` produce techos básicos; `roof_detail_resolver.py`, `roof_planes.py`, `roof_assembly.py` resuelven/arman cubiertas detalladas y encuentros; `prefabs_roof.py` aporta objetos de azotea. `boundaries.py` determina cercos libres y `fences.py` los modela; `site.py` maneja suelo/vegetación. `balcony_{catalog,resolver,assembly}.py`, `railing_assembly.py`, `vertical_member_{catalog,resolver,assembly,profiles,sweep}.py`, `crown_{catalog,resolver,paths,assembly}.py`, `trim_{profiles,resolver,sweep}.py`, `entablature_resolver.py` y `entrances.py` separan selección/validación de construcción. `src/modeling/materials.py` y `texturing/library.py` gobiernan slots/PBR.

**Geometría y entrega.** `mesh_builder.py` construye topología y atributos; `detail.py` controla presupuesto geométrico; `validation.py` revisa contención e índices y diagnostica topología por componente. `exporters/glb_exporter.py` empaqueta PBR y convierte Z-up a Y-up; `obj_exporter.py` ofrece OBJ/MTL alternativo. `src/modeling/version.py` identifica el materializador. En `MeshData`, `vertices` y `faces` comparten índices de posición **dentro de cada componente**; `corner_uv` va por esquina de triángulo; `face_materials`, `materials`, `parts` y `components` preservan apariencia y semántica. No es un sólido booleano único. GLB de autoría conserva identidad de componentes; exportación runtime puede agrupar por semántica.

**Catálogos y muestras.** Las familias están en `facade_program.py`, las variantes de piezas en módulos `*_catalog.py` y contratos `domain/`; texturas en `house_grammar/assets/pbr/catalog.json`. `steps/step22_massing_before_after/lotes/` y `steps/step23_fresh_theta/lotes/` contienen solicitudes comparativas por inmueble; usar `request.json` como entrada, no tomar GLB/render como fuente del esquema. `tests/fixtures/{golden_regression_hashes,facade_composition_hashes}.json` fija regresiones. Para detalle archivo por archivo: [`MODULOS.md`](house_grammar/docs/guia_theta/MODULOS.md) (puede quedarse atrás frente a nuevos módulos; contrastar con código).

## 6. Ejecutar una solicitud real

Desde la raíz, instalar primero `house_grammar/requirements.txt` y ejecutar:

```bash
python3 -m pip install -r house_grammar/requirements.txt
python3 house_grammar/steps/step18_theta_interface/run.py \
  --theta house_grammar/steps/step18_theta_interface/examples/01_simple.json \
  --output /tmp/opencode/theta-ejemplo --no-render
```

Ejemplo de contrato completo equivalente (los campos opcionales pueden omitirse):

```json
{
  "context": {"parcel": [[0, 0], [10, 0], [10, 16], [0, 16]], "fronts": [0]},
  "theta": {"height_m": 5.6, "floors": 2, "family": "quiet_house", "facade": {"bay_count": 3, "balconies": false}},
  "nuisance": {"seed": 18}
}
```

El runner produce `input_theta.json` (original), `canonical_request.json`, `resolved_theta.json`, `building.glb` y `manifest.json` (hashes, versiones, completados y validación). Sin `--no-render` agrega `iso.png` y `street.png`; son vistas de diagnóstico, no comparación PBR con fotos. Para validación y perfil topológico más amplios: `python3 house_grammar/docs/guia_theta/revisar_theta.py <request.json> --output /tmp/opencode/otro-theta` (carpeta nueva). Pruebas: desde `house_grammar/`, `PYTHONPATH=src python3 -m pytest -q`; focalizar `tests/test_theta.py`, `test_opening_catalog_only.py`, `test_roof_catalog_only.py`, `test_topology.py` y `test_golden_regression.py` según el cambio.

## 7. Fronteras importantes y deuda

- **A/B no son el materializador.** A corrige parcela y frentes; B prepara evidencia, sugerencias y paquetes con proveedor mock/provisional. El estimador devuelve parámetros parciales. Ni B ni el estimador deben asumirse como productor listo de este `ReconstructionRequest` completo, ni B exporta la malla por este flujo. Véanse [`apps/theta_author/README.md`](apps/theta_author/README.md) y [`README.md`](README.md).
- **Ruta antigua aún presente:** `from modeling import generate_mesh` apunta a `generate_v4_mesh`; `modeling/layout.py`, `massing.py`, partes de `grammar.py`/`facade_program.py`, `pipeline/contracts.py` y pasos previos contienen propuesta/V4 o adaptadores. **No** usar `generate_batch.py` como prueba de JSON theta: genera edificios V4 aleatorios. La intención de quedarse solo con la ruta actual **no equivale** a que ya se haya eliminado físicamente todo legacy; antes de borrarlo, identificar consumidores y migrar pruebas/scripts por separado.
- **Limitaciones:** el estilo no convierte por sí solo todas las aberturas en ensambles; no confundir coronación de fachada, frontón volumétrico, cuerpo sobre azotea y prop decorativo. La validez de JSON no asegura ausencia de colisiones, topología perfecta ni fidelidad fotográfica. Consultar los hallazgos actualizados de [`guia_theta/README.md`](house_grammar/docs/guia_theta/README.md) antes de prometer un comportamiento.
- **Estado local:** `data/barranco/`, autosaves y ejecuciones pueden no estar en Git; el repositorio por sí solo no reproduce todo el workspace. No confirmar outputs binarios por accidente al cambiar catálogos.

## 8. Regla de mantenimiento de este índice

En cada cambio a la gramática: (1) corregir aquí la etapa afectada y su contrato, rutas y comando; (2) ajustar guía/catálogos específicos y ejemplos JSON si cambian opciones; (3) ampliar pruebas y revisar hashes solo si el cambio geométrico es intencional; (4) ejecutar pruebas relevantes y un ejemplo Step18; (5) registrar incompatibilidades/migraciones entre versiones sin llamar «vigente» a una ruta antigua. Usar este archivo para **encontrar** el código; para valores exactos de todos los campos manda `domain/theta.py` y [`REFERENCIA_CAMPOS.md`](house_grammar/docs/guia_theta/REFERENCIA_CAMPOS.md).
