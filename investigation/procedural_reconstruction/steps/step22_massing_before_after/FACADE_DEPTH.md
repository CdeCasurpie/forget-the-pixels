# Profundidad local por FacadeZone

API: `FacadeZone('front', controls, u=(.2,.8), z_m=(0.,3.5), offset_m=-.8)`.
El signo positivo desplaza hacia fuera según la normal de la pared; negativo
retrae. Rango v1: -2 a +1 metros. Se usan los charts y el schema 0.3 existentes.

La resolución conserva el chart original, las entidades y la máscara visible;
registra `ResolvedWall.plane_offset_m`. La materialización desplaza el origen
de toda la fachada, incluidos pared perforada, openings y proyecciones. No
deja una pared original tapando el nuevo plano. Los retornos de perímetro
conectan ambos planos con shells cerrados de 20 mm. La unión de dominios
visibles evita retornos espurios entre bandas del mismo patch.

Los paños desplazados se recortan contra la envolvente permitida. Los planos
base, masas, cubiertas y niveles no se modifican. `offset_m=0` conserva la ruta
anterior y no añade campos a la serialización canónica legacy.

Permite nichos de entrada, paños retraídos, cuerpos locales salientes y fondos
de pórticos bajo una planta superior. Las zonas adyacentes se componen por
separado. No realiza una unión booleana entre sus retornos, ni recorta losas
o cubiertas para vacíos de doble altura; tampoco resuelve automáticamente
colisiones de un retranqueo con otra masa interior. Una galería abierta sigue
necesitando sus apoyos/primitivas existentes: el desplazamiento no los infiere.
Los retornos no son un sistema de muros estructurales o espesores constructivos.

Reproducción: `python steps/step22_massing_before_after/build_facade_depth.py`.
Los dos demos son pruebas de geometría, no mediciones de profundidad deducidas
de las fotos. Comparan oracle anterior con planta baja a -0.65 m (salmón) y
-0.95 m (crema), manteniendo la planta alta en el plano anterior.

Validación: 79 tests relacionados; suite 387 passed, 129 subtests passed en
116.78 s; 21/21 fingerprints y planes resueltos legacy idénticos.

## Sección cubierta opt-in (v2)

```python
FacadeZone('front', controls, u=(.2,.8), z_m=(0.,3.5), offset_m=-1.2,
           section=FacadeSection(back_wall=True,
                                 column_axes_u=(.08,.92),
                                 column_width_m=.25, slab_m=.20))
```

La sección sustituye los retornos finos de v1 por suelo, losa superior
(con cara inferior/soffit) y columnas cuadradas. Los ejes de columna son
normalizados al chart original de la zona; la visibilidad recorta sin
reubicar apoyos. `column_axes_u=()` permite una sección sin columnas.
`back_wall=False` elimina la pared de fondo y exige controles explícitos
vacíos: no se silencian openings que quedarían flotando. La planta superior
se conserva como otra zona y puede mantener su programa completo.

La sección debe ocupar un solo intervalo entre pisos: se rechazan zonas que
cruzan una losa intermedia. No se altera MassComponent, el roof ni la malla
global de losas; las secciones son ensamblajes locales, no operaciones CSG.
No hay inferencia estructural: el usuario declara apoyos. No se resuelven
encuentros booleanos de secciones vecinas ni colisiones con otras masas.
No equivale todavía a un sistema completo de LocalVolumes ni permite vacíos
arbitrarios de doble altura. Los extremos laterales del pórtico quedan abiertos.

Demo: `python steps/step22_massing_before_after/build_facade_depth.py --section`.
Genera `after_facade_section` para salmón (fondo retranqueado) y crema (fondo
abierto), con suelo, soffit y dos apoyos. Son demostraciones de capacidad,
no una afirmación de que esos apoyos estén presentes en Street View.

Validación v2: 40 tests profundidad/zonas; suite completa **390 passed,
129 subtests passed in 121.86s**; **21/21 fingerprints y planes legacy**.
