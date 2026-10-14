# Gramática ampliada a partir de referencias de Barranco

## Observaciones de las siete imágenes

1. Vivienda alta: grandes paños, subdivisiones finas, rejas, acceso retirado,
   vegetación que oculta parcialmente la planta baja, ampliación ligera en azotea.
2. Vivienda compacta: superior sencillo, ventanas pequeñas, puerta central,
   tratamiento distinto de planta baja y escalera lateral independiente.
3. Departamentos: ritmo vertical, balcones concentrados, paños ciegos, remate
   curvo, estacionamiento y reja frontal con retiro profundo.
4. Uso mixto: comercio inferior, toldos, ventanas de tamaños distintos entre
   pisos, rejas y modificaciones acumuladas. El deterioro no es uniforme.
5. Taller: acceso vehicular dominante, portones metálicos, cartel superior,
   cerramiento alto y pocos vanos residenciales.
6. Esquina: cuerpos con distinta altura, escalera metálica exterior, balcones,
   marquesina curva ligera, terraza y color continuo entre componentes.
7. Lavandería/vivienda: cerco de ladrillo con acceso comercial y doméstico
   separados, cartel, coronación cerámica y celosías de ventilación.

Estas observaciones guían familias; no se extraen automáticamente de las fotos.

## Uso

```python
spec = propose_building(
    parcel, footprint=optional_footprint, front_edges=(0,), floors=3,
    architectural_family="mixed_use", seed=23,
)
mesh = generate_mesh(spec)
```

Omitir `footprint` si no se conoce. `architectural_family="auto"` elige una familia
reproducible; no infiere el uso real del inmueble. La API y CLI usan `auto` por
defecto; usar `legacy` explícitamente para reproducir la propuesta anterior.
La familia es independiente de `style`, que conserva la implantación heredada.

| Familia | Composición |
| --- | --- |
| quiet_house | Vanos superiores contenidos, rejas, acceso y marquesina |
| ribbon_windows | Paños anchos subdivididos, líneas horizontales de losa discretas |
| balcony_apartments | Balcones por columnas alternas, ritmo vertical y acento lateral |
| mixed_use | Escaparates inferiores, cartel TIENDA, alero y vivienda superior |
| workshop | Persianas inferiores y cartel TALLER; superiores según pisos pedidos |
| brick_courtyard | Base/coronación de ladrillo, acceso y posible cerco declarado |

`Opening.prefab`: slim_window, storefront, wood_panel, metal_gate, roller, louver.
Incluye marco delgado, revelado, vidrio con backing y cortinas con cobertura
paramétrica; rejas verticales, cuadrícula o rombos. Ventanas antiguas conservan
prefab=legacy. Louver está disponible para especificaciones explícitas.
`FacadeSpecification.ornamented=False` desactiva bandas y pilastras heredadas.
`FacadeProjection.label` produce letras geométricas de un alfabeto limitado para
TIENDA, TALLER y LOCAL; no es un motor tipográfico ni reproduce logotipos.

## Archivos

- `families.py`: decide uso, ritmo, vanos, acentos y accesorios de azotea.
- `prefabs.py`: convierte puertas, ventanas, cortinas, rejas y letras en geometría.
- `layout.py`: conserva la huella y aplica la familia solicitada.
- `grammar.py`: ensambla los componentes, con la envolvente del lote existente.
- `family_gallery.py`: seis JSON editables, GLB PBR, imágenes diagnósticas y validación.

## Límites explícitos

No se modelan todavía cuerpos con alturas distintas, remates curvos habitables,
estacionamientos funcionales, tejados cerámicos ni deterioro espacial. Las
escaleras existentes siguen siendo explícitas y necesitan resolver accesos y
colisiones antes de colocarlas automáticamente. La marquesina de comercio es
una lámina simple con material de techo, no una cubierta con todas sus fijaciones.
La generación de vegetación permanece simplificada. Cortinas e interiores son
aproximaciones, no habitaciones completas. La gramática puede conservarse dentro
del lote sin que eso garantice ausencia de toda intersección entre componentes.

Los renders de la galería muestran composición y geometría; evaluar materiales
e iluminación del GLB en Blender. No representan reconstrucciones exactas ni
demuestran fotorealismo. Los nuevos campos son opcionales en JSON v3 y conservan
defaults compatibles; un lector antiguo ignorante de ellos requiere actualización.
