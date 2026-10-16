# Catálogo único de techos

**Mantener esta guía y sus pruebas al cambiar formas, coberturas, aleros o validación.**
Muestras: `house_grammar/steps/step23_fresh_theta/catalogo_techos/` (20 casos).

## Contrato de autoría

- `roof`, `component.roof`, `roofs` y `roof_bodies[].roof`: solo `kind: flat`
  (o `null`), parapeto 0–2 m; `slope_deg` debe ser `null`.
- La base plana es una losa estructural válida, sin ornamentación inventada.
- Toda cubierta diseñada, incluso corrugada, usa `roof_assemblies` o `canopies`.
  Un assembly sustituye la superficie y parapeto básicos de su masa; no los apila.
- `RoofBody` se convierte en componente; su assembly usa `mass_ref: <id>:0`.
- Los motores históricos solo generan bases planas. No hay banda aleatoria de
  teja, prisma `tile_roof`, lámina básica de 5 cm ni `pitched_roof` histórico.
- Un valor básico antiguo falla; el resolver no lo convierte silenciosamente.

## Ejemplo: dos aguas de teja

Fragmento de theta, para una masa `casa:0` con espacio suficiente alrededor:

```json
{
  "roof": {"kind": "flat", "parapet_m": 0, "props": []},
  "roof_assemblies": [{
    "id": "cubierta", "mass_ref": "casa:0", "props_mode": "off",
    "design": {
      "form": "gable", "covering": "curved_tile", "detail": "full",
      "slope_deg": 22, "rotation_deg": 0, "ridge_fraction": 0.5,
      "eave": {"kind": "profiled", "overhang_m": 0.35}
    }
  }]
}
```

`rotation_deg` mide el vector ascendente del primer faldón desde +X local,
antihorario. A 0°, asciende en X y la cumbrera gable corre en Y; a 90°, al revés.
`ridge_fraction` (0.1–0.9) coloca la cumbrera entre extremos proyectados: el segundo
faldón ajusta su pendiente para encontrarse con el primero. No es el norte de mapa
ni el ángulo de fachada. Los recortes no cambian la cumbrera ni el datum del techo.

## Vocabulario

| Control | Valores |
|---|---|
| `form` | `flat`, `shed`, `gable`, `hip`, `pavilion`, `band`, `compound` |
| `covering` | `none`, `curved_tile`, `flat_tile`, `corrugated`, `panel`, `slats` |
| `construction` | `solid` (sustrato), `frame` (abierta; no admite tejas) |
| `eave.kind` | `auto`, `clean`, `closed`, `exposed`, `profiled`, `braces`, `curved`, `cornice` |
| `detail` | `full` por defecto; `medium` y `light` son simplificaciones explícitas del catálogo |
| `cap` | `none`, `flat`, `bevel`, `pitched`, `moulded`, `metal` |
| `props_mode` | `preserve`, `auto` (solo plano), `off` |

No todas las combinaciones son válidas. Hip/pavilion requieren huella convexa y
comparten algoritmo; compound requiere lóbulos rectangulares que cubran el soporte.
Band debe dejar un resto plano. Parapeto solo en flat; goterón de tapa solo en metal.
Tejas requieren sustrato continuo. Slats admite sol y sombra abierto.

Pendiente de diseño: 1–45°; espesor: 0.025–0.5 m; alero: 0–1.5 m.
Dimensiones de teja, solape, separación de canes, materiales y finitud se validan.
`enabled: false` desactiva el assembly y deja la base plana.

## Aleros, medianeras y encuentros

El vuelo debe caber en la envolvente; fascia, cornisa y canaleta necesitan margen
adicional. Para una cubierta al ras sin accesorios exteriores:

```json
"eave": {"kind": "clean", "overhang_m": 0, "fascia": false}
```

La tolerancia numérica del borde es 0.1 mm, no un permiso de vuelo. No aumentar
`parcel_tolerance_m` automáticamente para ocultar un error; autorizarla solo si
corresponde al levantamiento. Si se necesitan vuelos diferentes por lado, dividir
la composición o usar canopies explícitos: el alero de assembly es uniforme.

`junction: behind/gable` exige `crown_ref`; gable exige frontón triangular de todo
el ancho y revalida la pendiente derivada. `join_group` une soportes contiguos a la
misma cota con acabados compatibles. `canopies` comparte RoofDesign, admite
flat/shed y puede añadir postes. Props de azotea no se conservan en inclinados.

## Migración y verificación

Herramienta **offline**, no parte del resolver:

```bash
python3 house_grammar/docs/guia_theta/migrar_techos.py request.json --output migrated.json
```

Migra techos locales de componentes/cuerpos: tile_shed→shed con teja,
gable→gable con teja, corrugated→flat con cobertura corrugada. Conserva assemblies
ya declarados y orientación del marco canónico. Usa detalle full y borde al ras;
no inventa vuelos ni permisos. Globales/overrides requieren selección explícita de
masas; el resolver detecta los casos pendientes. Revisar visualmente la salida.

Los requests activos migrados deben regenerarse: sus GLB/manifiestos antiguos no
describen la geometría nueva. Runs anteriores y solicitudes históricas conservan
su autoría original; no se promete que resuelvan con la gramática actual.

Pruebas: `test_roof_catalog_only.py`, `test_roof_assemblies.py`,
`test_roofscape.py`, `test_top_composition.py`, tests theta/composición y goldens V4.
