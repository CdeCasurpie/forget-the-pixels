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
