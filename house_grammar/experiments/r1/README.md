# R1 — Integración de las masas nuevas con el materializador de catálogo

**Estado:** completada. Cambios en `src/`: nuevo contrato `domain/surfaces.py`;
`modeling/crown_resolver.py` y `modeling/balcony_resolver.py` consumen el
contrato en vez de un candidato theta; `modeling/theta.py` pasa a construir el
chart en su frontera; nuevo `planning/chart.py` (chart desde las masas nuevas) y
`planning/catalogue.py` (resolución y materialización con los ensambladores del
catálogo). **No** se tocó ningún constructor de piezas, ni los JSON históricos de
`steps/`, ni la geometría de masas.

**Objetivo de la fase:** dejar de dibujar piezas dos veces. El lado nuevo
(`planning/`) ya no implementa carpintería propia para coronación y balcones: los
resolvers del catálogo colocan, y los ensambladores del catálogo materializan,
sobre un contrato de superficies común.

---

## 1. Cómo ejecutar

```bash
# Pruebas de capacidad R1 (rápidas, no leen JSON histórico)
PYTHONPATH=house_grammar/src python3 -m pytest house_grammar/tests/test_intent_catalogue.py -q

# Banco R1: 4 masas nuevas vestidas con frontón y balcón reales
PYTHONPATH=house_grammar/src python3 house_grammar/experiments/r1/run.py \
  --output apps/experimento_paralelizacion/gramatica_adaptable/r1 --sheet
```

`run.py` escribe por caso `preview.png` (perspectiva) y `front.png` (elevación
ortográfica real), más `manifest.json` con la semántica emitida, las
colocaciones resueltas y el **desvío de silueta** de cada piso. El directorio de
salida **no debe existir**.

---

## 2. El problema que resuelve R1

Antes de R1 había dos mitades que no se hablaban:

- `planning/` no importaba nada de `modeling/` salvo `randomness` y el render de
  R0, y dibujaba su propia carpintería en `planning/envelope._joinery`.
- Los catálogos (`modeling/`) resolvían y construían, pero sus resolvers tomaban
  `(theta, masses, walls, envelope, materials)` y solo podían ser disparados por
  un candidato theta.

La buena noticia: los resolvers ya consumían **geometría** (`masses` + `walls`),
y theta solo aportaba *qué piezas colocar y con qué estilo*. R1 separa esas dos
cosas: la geometría pasa a ser un contrato explícito y las piezas un parámetro.

---

## 3. El contrato de superficies (`src/domain/surfaces.py`)

| Tipo | Campos que importan para colocar piezas |
|---|---|
| `WallSurface` | `mass_role`, `edge`, `base_z`, `height_m`, `axes_m`, `facade: FacadeSpecification`, `visible_domains` (regiones expuestas `u0,z0,u1,z1` en local), `plane_offset_m`, `section` |
| `SurfaceChart` | `bodies: tuple[MassSpec,...]`, `surfaces: tuple[WallSurface,...]` + `body()`, `surfaces_of()`, `surface()`, `candidates()` |

`WallSurface` conserva la forma del antiguo `ResolvedWall` de `theta.py` (que
ahora es un alias del nuevo tipo), por lo que la frontera theta no cambió de
contrato. Añade dos ayudas que los resolvers no tenían:

- `frame()` → `(origin, tangent, normal)` con el origen desplazado al plano
  construido (`plane_offset_m`).
- `local_point(u, z, offset)` → coordenada de mundo de un punto local; es la
  misma aritmética que usan `crown_resolver` y `balcony_resolver`.

**Decisión:** un cuerpo por **piso** (no por edificio). Un retiro deja de
aplanarse a una huella única; el cuerpo del piso conserva su silueta y su
`roof_z` real, que es lo que exige el anclaje `wall_top` de un frontón.

---

## 4. La ruta

```
request (intent-v1)
  → planning.envelope.plan_envelope      masas + plantas + envolvente constructiva
  → planning.chart.surface_chart         SurfaceChart (cuerpo por piso + una
                                         superficie por arista expuesta, con
                                         los vanos ya reservados)
  → planning.catalogue.resolve_pieces    crown_resolver / balcony_resolver
                                         (consumen el chart, no theta)
  → planning.catalogue.build_pieces      crown_assembly.build_crown /
                                         balcony_assembly.build_balcony
  → MeshBuilder.finish()                 MeshData con semántica de catálogo
```

`planning/chart.permitted_envelope` reconstruye la envolvente de proyección
(parcela + vuelo sobre las frentes declaradas) reutilizando
`modeling/geometry_constraints.projection_envelope`; es la misma cota que valida
un balcón o un frontón.

Los vanos del chart se mapean desde los que la envolvente ya reservó
(por el `surface` de cada vano), de modo que un frontón no pisa una ventana y un
balcón no choca con una puerta.

---

## 5. Evidencia

- **4/4** casos emiten `crown_body`/`crown_moulding` y `balcony_platform`/
  `balcony_handrail` (más barras, postes, cornisas y fascia del catálogo).
- **Silueta intacta:** `silhouette_drift_m2` es `0.0` para cada piso en cada caso
  (el materializador no mueve las masas).
- Frontón triangular con molduras y balcón con balaustres torneados (clásico,
  barroco) o barrotes metálicos (moderno, republicano) según el estilo resuelto
  por el catálogo.
- `tests/test_intent_catalogue.py` prueba el contrato, el mapeo de vanos, la
  coincidencia arista↔huella, que un anclaje sobre un cuerpo inexistente se
  rechaza, y que sin colocación no hay piezas.

---

## 6. Límites (lo que R1 no hace)

- **No** migra los resolvers de pilastras, entablamentos, entradas y cubiertas
  (siguen sobre theta; migran en R4/R5).
- **No** toca los vanos: la carpintería propia `_joinery` se sustituye por
  `opening_catalog` en **R3**.
- **No** introduce uso, tipología ni pisos tipo (**R2**).
- **No** elige ornamento por estilo ni cercos (**R4**).

## 7. Huecos que R1 deja abiertos

- Los controles siguen direccionando por `mass_ref` + `edge` + `u_m`. El chart
  garantiza una superficie por arista, pero un control no puede nombrar una
  superficie por su `edge_id` directamente; conviene añadirlo cuando un piso
  genere varias superficies sobre la misma arista (p. ej. con retranqueos
  verticales, R2).
- `visible_domains` es un intervalo vertical completo por arista: un piso con un
  vano de esquina raro aún no parte la exposición en varios ejes.
- La materialización y las masas se renderizan juntas pero como mallas
  separadas; R7 unificará el export.
