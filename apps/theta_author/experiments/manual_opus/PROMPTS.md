# Autoría manual de theta con Claude (2 IAs + reparación) — réplica del flujo manual

Objetivo: que el modelo haga exactamente lo que se hizo a mano en
`data/barranco/theta_experiments/1134706_manual_v1/`: mirar las fotos,
escribir un `ReconstructionRequest` completo desde cero y refinarlo contra
renders alineados a las cámaras reales. Sin Haiku, sin etapas: 1 prompt crea,
1 repara, 1 refina. Modelo sugerido: Opus.

## Preparar insumos (una vez por lote)

Desde la raíz del repo, con el `package.json` ya preparado por B:

```bash
RUN=data/barranco/theta_author/runs/<RUN_ID>
LOTE=<ID_LOTE>
OUT=data/barranco/theta_experiments/${LOTE}_manual_v1
mkdir -p $OUT
python3 - <<EOF
import json
p = json.load(open('$RUN/package.json'))
snap = p['snapshot']; lot = snap['lot']
hp = p['human_parameters']
def dv(k):
    v = hp.get(k, {})
    return v.get('value') if isinstance(v, dict) else v
def md(k):
    v = hp.get(k, {})
    return v.get('mode') if isinstance(v, dict) else None
floors = int(dv('floors'))
fh = hp.get('floor_height_m')
ff = hp.get('first_floor_height_m') if hp.get('first_floor_different') else None
levels = [0.0]
for i in range(floors):
    h = ff if (i == 0 and ff) else fh
    levels.append(round(levels[-1] + float(h), 3))
coords = lot['geometry']['coordinates'][0]
edges = [(a, b) for a, b in zip(coords, coords[1:])]
import math
lengths = [round(math.dist(a, b), 3) for a, b in edges]
front_ids = [f['id'] for f in lot['fronts'] if f['is_front']]
json.dump({
    "parcel_xy_epsg32718": coords,
    "front_lengths_m": lengths,
    "front_ids": front_ids,
    "floors": floors,
    "levels_m": levels,
    "style_suggestion": dv('style'),
    "style_mode": md('style'),
    "notes": hp.get('notes', ''),
}, open('$OUT/parcel.json', 'w'), indent=1, ensure_ascii=False)
print('levels:', levels, '| frentes:', front_ids, '| longitudes:', lengths)
EOF
```

Adjuntar al prompt 1: `parcel.json`, las fotos de `$RUN/evidence/`,
y como ejemplo de sintaxis válida
`data/barranco/theta_experiments/1134706_manual_v1/run05/request.json`
(marcarlo explícitamente como OTRA casa, solo sintaxis).

Materializar y comparar (fuera del modelo):

```bash
python3 house_grammar/docs/guia_theta/revisar_theta.py $OUT/request.json \
  --output $OUT/run01 --preview
python3 -m apps.theta_author.experiments.manual_opus.render_comparisons \
  --request $OUT/request.json --package $RUN/package.json \
  --output $OUT/run01/comparisons
```

## Prompt 1 — IA-1 describe (módulos, sin JSON)

```text
Describe esta casa para una gramática procedural. NO generes JSON.
Divide el frente en MÓDULOS verticales donde cambie alineación, cubierta
o composición, y responde por cada uno:
1. % del frente, retiro respecto al plano principal (m, estimado),
   ¿a filo de lote o retranqueado?
2. Techo/coronación: plano+parapeto, 1 agua, 2 aguas (¿dónde va la
   cumbrera?), alero de teja (¿cuánto vuela?), marquesinas.
3. Vanos por piso: tipo, ancho×alto aprox, posición relativa, reja,
   contraventanas, puerta (material, hojas, portal).
4. Cerco: ¿existe? ¿en qué tramo del frente? ¿portón dónde y de qué ancho?
5. Colores por piso/banda, zócalos, bandas de material.
6. Vecinos a cada lado (qué NO es el lote) y oclusiones (qué no se ve y no
   debe inventarse: azotea, laterales, fondo).
Cierra con tabla módulo | %frente | retiro | techo | vanos, y con las
medidas en que confías (porcentajes > metros absolutos).
```

## Prompt 2 — IA-2 construye el theta desde la descripción

```text
Eres autor de solicitudes theta para la gramática de este repositorio.
Tu única salida es un JSON ReconstructionRequest válido, sin comentarios.

Adjuntos: parcel.json (parcela, frentes, pisos, niveles, estilo sugerido),
fotos de evidencia del lote, y request_ejemplo.json de OTRA casa (solo
para copiar sintaxis exacta de componentes, caras, vanos, cerco y zonas).

Reglas de observación:
1. Identifica la casa objetivo y sepárala de vecinos (suelen aparecer
   edificios distintos a los lados). Nombra qué es vecino.
2. Registra oclusiones (planta baja tras cerco/plantas, azotea no visible,
   laterales tapados). Lo ocluido NO se inventa: se omite o se deja ciego.
3. La sugerencia de estilo humano no es vinculante: si la fachada es
   austera, usa architectural_style=null con valores explícitos por pieza.
4. Una colección vacía [] es una decisión válida (sin balcones, sin
   pilastras, sin frontones si no se ven). No poblar catálogos por poblar.

Reglas theta (schema_version="0.3"):
- context.parcel: copiar vértices tal cual de parcel.json; fronts: índices
  de aristas del anillo recibido (empezando en 0). metric_origin tal cual.
- UNA vía de volumetría: massing.components con un componente "principal"
  (region front_edge + u [0,1] + depth_m con retiro de jardín si se ve
  jardín/cerco; levels_m = niveles de parcel.json). Sin height_m ni floors.
- family="quiet_house" salvo evidencia clara de otra (ver ejemplo).
- Caras: facade=null (ciega) + faces solo para el frente visible, mode
  explicit con openings. Laterales ciegos si los tapan vecinos.
- Vanos: kind window/door/gate, shape rectangle salvo arco visible,
  prefab legacy + style sliding, grille vertical + sill en ventanas con reja.
  Puerta detallada exige bloque door con model/construction/materiales
  explícitos (nunca model auto si style es null). curtain siempre 0.
- Coordenadas de arista: u_m desde vertex_a, v_m desde base del muro.
  Todo vano debe caber en el largo del muro con margen.
- Techo: kind flat + parapet_m 0–0.5 si hay parapeto; props [] si la
  azotea no se ve. Sin roof_assemblies salvo cubierta claramente visible.
  Cualquier pendiente o cobertura corrugada se escribe en roof_assemblies:
  form shed/gable/etc., covering, detail full y alero explícito según evidencia.
  roof/component.roof/roofs/roof_bodies[].roof solo admiten flat; slope_deg null.
  rotation_deg es dirección ascendente desde +X local, no el norte ni la fachada;
  en gable la cumbrera es perpendicular. No ampliar tolerancias para forzar vuelos.
- Sitio: runs explícitos (edge, start_m/end_m dentro del largo de arista,
  kind republicano|barroco|clasico|madera|moderno según lo visto,
  gate_u/garage_u en METROS desde start_m, openness 0.1–0.7, planters solo
  moderno, plinth null salvo estilo vinculado). site.fence="none" con runs.
  zones garden/patio solo sobre suelo libre visible.
- Trim: cornice/plinth enabled=false por defecto (los muros sobre lindero
  no admiten relieve: vuela fuera de la envolvente). Base de piedra como
  material_regions, no como geometría.
- Materiales: solo slots existentes (plaster, stone, wood, metal, frame,
  glass…), template existente + color RGB 0–1. primary_color = revoque.
- nuisance {"seed":23,"curtains":false}, config {"detail":2}.
- No inventes claves. Si falta un dato indispensable, elígelo conservador
  y anótalo en una línea final fuera del JSON empezando con NOTA:.
```

## Prompt 3 — reparar error del resolver

```text
El motor rechazó el request con este error exacto:
<PEGAR TRACEBACK>

Reglas: haz el parche mínimo que lo supere SIN cambiar valores observados
(posiciones, tamaños, colores). Errores conocidos y su arreglo:
- "Cornice auto requires..." → profile explícito (moderno = rectangular
  simple) o cornice enabled=false si no hay moldura visible.
- "projection outside permitted envelope" en trim → trim off en ese bloque
  (los relieves sobre linderos siempre fallan; usa material_regions).
- "Mass outside parcel" → recorta la región al catastro (fit parcel ya lo
  hace; revisa depth_m/u fuera de rango).
- "Interpenetrating..." → un solo componente, sin cutouts salvo patio visto.
- "Fence overlaps building / Invalid fence gate" → revisa métricas del run
  contra el largo de arista (gate dentro de [start_m,end_m]).
- "needs architectural_style" (door auto, frame auto) → escribe el estilo
  local explícito en esa pieza.
Devuelve el JSON completo corregido + una línea CAMBIO: qué tocaste y por qué.
```

## Prompt 4 — refinar contra comparaciones

```text
Adjunto comparaciones foto/render/superposición de las cámaras reales y el
request.json actual. Ajusta SOLO: posiciones u_m, anchos, altos, v_m,
colores y regiones de material para calzar con la foto. No añadas piezas
no visibles ni cambies la masa salvo que la silueta lo exija (la
superposición amarilla manda). Devuelve el JSON completo + viñetas
CAMBIO: valor antes → después + en qué foto se ve.
```
