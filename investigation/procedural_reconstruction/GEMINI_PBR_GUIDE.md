# Implementación PBR: instrucciones para Gemini

## Estado y alcance

Trabajar en `investigation/procedural_reconstruction`. La gramática genera geometría
real; los materiales deben ajustarse a esa geometría. Las fotos pueden aportar
color/familia/confianza, sin necesidad de proyectarlas sobre fachadas distintas.

Ya existe `BuildingAppearance` con `MaterialSpecification`, slots por fachada,
regiones de material y salientes. `materials.py` resuelve el catálogo y
`MeshData.face_materials` asigna materiales. GLB exporta factores PBR constantes.
`texture_set`, `real_scale_m`, `normal_strength` y `weathering` son metadata: todavía
no producen mapas. `MeshData.uv` existe pero el constructor no genera UV.

`layout.py` activa `detail_level="composed"` por defecto. `composition.py` añade
acentos alineados con vanos, marcos de varios pisos, marquesinas y aleros cuando
caben en el lote. `detail_level="basic"` permite comparar con la variante anterior.
Los diseños explícitos se generan con `generate_mesh(spec)` sin recomposición.
Escaleras explícitas son prototipos geométricos: revisar accesos, colisiones y
descansos antes de usarlas como circulación; no están certificadas para construcción.

## Resultado esperado

Conservar `generate_mesh(BuildingSpecification) -> MeshData`. Añadir una etapa
`materialize_mesh(mesh, specification, asset_library) -> MeshData` con UV, imágenes
y materiales resueltos. Exportar un GLB portable con texturas embebidas. Mantener
colores de respaldo si falta un recurso y registrar el recurso faltante.

## Recursos a descargar

Empezar con 1K/2K tileables: estuco neutro, concreto fino, ladrillo, madera,
metal galvanizado y pavimento. Un HDRI exterior para revisar reflejos e iluminación.
Vidrio y metal pintado pueden empezar con parámetros, sin texturas pesadas.
Guardar bajo `assets/pbr/<asset_id>/` y un catálogo con id, URL original, licencia,
fecha, SHA256, archivos, resolución, tamaño físico del mosaico y convención normal.
No descargar durante `generate_mesh`; descargar una vez y reutilizar localmente.

Fuentes verificadas: [Poly Haven CC0](https://polyhaven.com/license) y
[ambientCG CC0](https://docs.ambientcg.com/license/). Si se usa la API de Poly Haven,
revisar sus [condiciones de API](https://github.com/Poly-Haven/Public-API/blob/master/ToS.md),
que son distintas de la licencia del asset. No inventar URLs de archivos.

## Mapas y convenciones

Usar metallic-roughness. Albedo/base color es sRGB; normales, AO, roughness y metallic
son datos lineales. En glTF, metallic-roughness usa G=roughness y B=metallic; se puede
compartir imagen ORM con R=AO. AO se conecta además en `occlusionTexture`.
Normal tangent-space OpenGL (+Y), con escala y tangentes coherentes. Specular no
es necesario para el flujo básico. Emissive es opcional. Height/displacement no
tiene un canal básico equivalente en glTF; dejarlo fuera de la primera versión.
Referencia normativa: [glTF 2.0 materiales](https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html#materials).

No hornear sombras direccionales dentro del albedo. La madera/ladrillo no deben
teñirse indiscriminadamente con la paleta: usar tintes sobre estuco neutro y
reservar materiales naturales con su color original. Convertir colores sRGB
observados a lineal antes de usarlos como factores glTF. Documentar y versionar
esa convención para los valores heredados de `base_color_rgb`.

## Orden de implementación por archivo

1. `domain/models.py`: agregar contrato TextureSet con rutas/mapas, escala U/V,
   normal convention y provenance. Mantener lectura de JSON anteriores.
2. Nuevo `texturing/library.py`: cargar catálogo, validar rutas/hash/dimensiones;
   caché de imágenes por recurso. Separar descarga de carga y generación.
3. `mesh_builder.py`: conservar origen y ejes de cada cara al crearla. Fachadas:
   UV=(u/scale_u, z/scale_v); cubiertas XY; laterales de marcos con sus propios
   ejes. Usar el mismo origen de fachada entre celdas para continuidad del ladrillo.
   Duplicar vértices en costuras UV y bordes duros. No compartir una normal suavizada
   entre dos caras ortogonales. Transformar normales/tangentes junto con Z-up/Y-up.
4. Nuevo `texturing/pbr.py`: resolver texture_set, tintes, normal_strength y mapas
   ORM. Respetar regiones de material. No cambiar aberturas/huella. Reservar
   weathering para una máscara posterior controlada, no ruido independiente por cara.
5. `exporters/glb_exporter.py`: preservar UV al separar grupos/materiales; añadir
   texturas baseColor, normal, metallicRoughness y occlusion. Evitar duplicar imágenes
   por componente. Comprobar soporte real de Trimesh; si falta, usar exportador
   explícito glTF o Blender, sin declarar soporte que no se exporta.
6. Vidrio: metallic=0, roughness baja. BLEND permite ver a través pero no equivale
   a transmisión física. Evaluar KHR_materials_transmission/ior con un visor que
   las soporte; agregar interiores simples/cortinas para evitar el edificio vacío.
   Metal pintado se comporta como pintura dieléctrica: metallic=0 en la superficie;
   metal desnudo puede usar metallic=1. Ajustar defaults actuales de frame/metal.
7. Render de revisión en Blender o visor PBR con HDRI, sol, exposición consistente
   y sombras. El render de diagnóstico actual no demuestra normal maps ni PBR.

## Aceptación

- Render antes/después con misma cámara, geometría y luz; revisar realmente imágenes.
- Checker métrico de 1 m mantiene tamaño al cambiar ancho/altura del edificio.
- Ladrillos continuos entre celdas y sin estiramiento en caras laterales.
- Prueba de normal map con luz lateral: canales y relieve correctos.
- GLB reabierto offline conserva imágenes, UV, slots y factores.
- Ventanas no parecen espejos metálicos; paredes no reflejan como plástico.
- Validación geométrica sigue pasando para lotes cóncavos y patios.
- Reportar tiempo, tamaño GLB y memoria de texturas; reutilizar assets por cuadra.

Entregar primero una vivienda con estuco, ladrillo, madera, vidrio y reja; revisar
visualmente y después extender al batch. No prometer fotorealismo únicamente por
haber conectado mapas: geometría, escala, iluminación y contexto son necesarios.
