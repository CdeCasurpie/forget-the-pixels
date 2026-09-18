# Gramática arquitectónica — new-proposal

Genera **mallas reales**, no imágenes generativas: OBJ/MTL, GLB, especificación
JSON editable, render de arcilla/materiales y reporte de validación. Las tres
tipologías de referencia son vivienda estrecha, casa con retiro/cerco y edificio
de esquina; se añade una planta en L y tres lotes catastrales de Barranco.

## Ejecutar

Desde `investigation/`, con el entorno del proyecto:

```bash
make run-procedural-proposal
make test-procedural-proposal
```

La primera orden genera siete casos en `outputs/new_proposal/`. Incluye
`comparison.png` con sus renders, `validation.json`, y los archivos individuales.
Para los cuatro casos sintéticos, sin catastro ni metadata de cámaras:

```bash
python proy_geom/steps/step10_procedural_generation_test/run.py
```

Para regenerar una especificación editada (el JSON del modelo, no el reporte):

```bash
make run-procedural-proposal PROCEDURAL_SPEC=/ruta/casa.json
make run-procedural-proposal PROCEDURAL_SEED=19
```

También están disponibles `--output`, `--spec`, `--seed`, `--no-render` y
`--cadastre`. Requiere Shapely >= 2.1 con GEOS >= 3.10, NumPy, OpenCV y Trimesh;
GeoPandas/PyProj solo para los ejemplos catastrales. No necesita Blender ni GPU.

## API y responsabilidades

```python
from shapely.geometry import Polygon
from procedural_modeling import propose_building, generate_mesh, validate_mesh
from exporters.glb_exporter import export_glb

parcel = Polygon([(0, 0), (10, 0), (10, 16), (0, 16)])
spec = propose_building(
    parcel, front_edges=(0, 1), floors=3, height_m=8.4,
    style="corner", setback_m=1.5, boundary="fence", seed=42,
)
mesh = generate_mesh(spec)
report = validate_mesh(mesh, parcel)
export_glb(mesh, "casa.glb")
```

`propose_building` es una **hipótesis editable** de distribución arquitectónica.
`generate_mesh(BuildingSpecification) -> MeshData` respeta los vanos y frentes
explícitos; no lee fotos, catastro ni archivos de configuración. El futuro
extractor visual debe producir esas especificaciones, reemplazando hipótesis por
observaciones con `source`, `view_id`, `score` y `observed`.

| Módulo | Responsabilidad |
| --- | --- |
| `domain/models.py` | Contratos: parcela, huella edificada, fachadas, vanos, retiro, techo, semilla |
| `procedural_modeling/layout.py` | Retiro por frente y composición determinista de planta baja/pisos |
| `procedural_modeling/grammar.py` | Muros con vanos, marcos, rejas, balcones, cubierta y jardín |
| `procedural_modeling/mesh_builder.py` | Sólidos recortados y triangulación restringida |
| `procedural_modeling/io.py` | Lectura de especificaciones JSON v1/v2 |
| `procedural_modeling/validation.py` | Índices, áreas, coordenadas, materiales y contención |
| `exporters/` | OBJ/MTL Z-up y GLB Y-up con grupos semánticos/materiales |
| `render.py` | Cámara ortográfica, z-buffer y sombras de la malla, solo diagnóstico |

## Convenciones que no deben perderse

- XY en **metros**, Z hacia arriba. Para exportación usar coordenadas locales;
  los ejemplos catastrales guardan `metadata.local_origin_utm` para recuperar su
  ubicación en EPSG:32718. No tratar sus coordenadas locales como UTM absolutas.
- `parcel_xy` es el límite legal, `footprint_xy` la huella construida. No son
  intercambiables cuando existen retiros. Ambos pueden tener patios/huecos.
- Los frentes y los cercos usan índices del contorno de parcela **normalizado
  antihorario**. No se consideran fachadas todas las aristas largas.
- Cada vano usa `u_m` desde `vertex_a`, `v_m` desde el suelo. Las normales se
  recalculan a partir del contorno; también se admiten fachadas invertidas.
- La altura recibida define la parte superior de la losa principal. Parapetos,
  cuarto de azotea, tanque y cubierta ligera pueden superar esa cota: activar
  estos detalles solo si esa es la interpretación correcta de la altura medida.
  Para una silueta que termine exactamente en Z, desactivar los tres accesorios
  y usar `parapet_height_m=0`, techo plano.
- Misma especificación/semilla produce la misma malla. Cambiar la semilla cambia
  paleta, modulación y detalles secundarios; no cambia los vanos observados.

## Reglas implementadas

1. Reservar espacio de retiro únicamente en los frentes indicados, manteniendo
   separación lateral de 0.20 m para detalles en la propuesta automática.
2. Componer la planta baja con puerta/ventana o acceso amplio; repetir módulos
   superiores. Los contratos permiten reemplazar cualquier distribución.
3. Dividir el muro alrededor de los vanos, insertar marcos con profundidad,
   dinteles, alféizares, vidrio, parteluces y hojas abatidas opcionales.
4. Añadir rejas, relieves, zócalos, bandas entre pisos y balcones con frente,
   retornos laterales y ornamentos verticales/romboidales. Solo emitir un balcón
   completo si su envolvente cabe en el lote.
5. Crear cubierta plana con parapeto, o inclinada a una/dos aguas. En cubierta
   plana buscar una plataforma interior para cuarto, calamina nervada, postes y
   tanque. No colocar plataforma sobre patios o fuera de la huella.
6. Construir muro de ladrillo o reja y portón solo en los lados seleccionados.
   Ubicar jardineras y arbustos simplificados en el espacio libre del retiro.
7. Recortar sólidos contra la parcela y comprobar las **caras y aristas**, no
   solo sus vértices: una diagonal puede cruzar el vacío de un lote cóncavo.

## Calidad, límites y siguiente iteración

- La triangulación restringida respeta concavidades y agujeros, a diferencia de
  filtrar Delaunay únicamente por el centroide de cada triángulo.
- La propuesta automática rechaza retiros que destruyan/dividan la huella:
  devuelve un error explicativo; no inventa puentes entre volúmenes. Para varios
  cuerpos, autorizar especificaciones separadas dentro de la misma parcela.
- El resultado es un **ensamblaje de componentes**, no una unión booleana única:
  hay intersecciones intencionales entre molduras/muros. No está certificado como
  sólido global estanco para impresión 3D. Techos inclinados no añaden todavía
  cerramientos triangulares de hastial.
- Son hipótesis inspiradas en las referencias, **no reconstrucciones fieles de
  esas fotos**. No hay detección automática de puertas, balcones, retiros o
  colores, ni UV/texturas fotográficas. El render sencillo no sustituye una
  revisión de materiales/iluminación en Blender ni garantiza calidad AAA.
- El modo catastral elige un frente orientado hacia cámaras guardadas. Esa
  selección no certifica visibilidad y los pisos de demostración no son una
  nueva medición del paso 9. Para producción, pasar su altura y frentes revisados.
- Los laterales no observados quedan ciegos. Los arbustos son aproximaciones
  geométricas; no se generan personas, cables de la calle ni edificios vecinos.

Pruebas: triangulación con patios/concavidades, cierre y orientación por
componente, semilla, retiros inválidos, vanos inválidos, cercos selectivos,
alturas, tres cubiertas, round-trip JSON y ejes OBJ/GLB. Revisar también
`comparison.png` y los modelos GLB antes de aprobar una variante para producción.
