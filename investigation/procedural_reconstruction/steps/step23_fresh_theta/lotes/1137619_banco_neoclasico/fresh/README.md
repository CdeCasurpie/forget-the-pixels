# 1137619 — banco gris BCP

Objetivo en las **cinco** `_lot.jpg`: edificio BCP gris de una planta alta, con portada blanca en el chaflán, zócalo pétreo, cornisa clásica y ventanas protegidas por rejas. El BanBif amarillo alto y las iglesias blancas visibles en distintos ángulos son vecinos, no componentes del banco. El recuadro amarillo de Street View no determina la altura de la masa.

## Etapa 1: masas

`../massing_preview/` contiene request, theta resuelto, GLB, cinco renders y sus comparativas. Masa cerrada de una planta con altura 5,25 m sobre la huella del predio original y cubierta plana con remate bajo. Las dos vistas cercanas del chaflán (`AeUUE…`, `qFcE…`) sirven para comparar altura, esquina y longitud del costado; `Uzf1…` y `HRx6…` muestran el frente longitudinal; `4zrQ…` está dominada por BanBif y solo deja ver parcialmente el banco. En los renders aparece una discrepancia de escala/proyección respecto de las fotos: el banco proyectado ocupa menos pantalla, especialmente en las vistas desde BanBif. No se aumentó su tamaño extendiéndolo fuera de la parcela.

## Etapa 2: detalles

`fresh/` contiene el request reconstruido a partir del `after/` original, GLB y cinco pares de render/comparativa. Los paños catastrales que dan a calle reciben zócalo, pilastras estrechas, cornisa con dentículos, vanos hundidos y rejas de rombos. El frente largo hacia BanBif tiene portón metálico gris a un extremo y dos ventanas enrejadas; el costado restante recibe dos ventanas visibles. El chaflán corto incorpora la portada clara saliente con entablamento/pedimento y acceso acristalado. Los letreros BCP son aproximaciones geométricas; las letras y el logotipo reales no se reproducen fielmente.

**Diferencias observables:** el chaflán del render se percibe demasiado estrecho y su portada no tiene las ménsulas ni el dintel horizontal grueso de la foto; las ventanas y pilastras son más regulares que las reales; el portón de servicio carece de los paneles rectangulares grandes. La proyección respecto de la fotografía sigue siendo menor; los renders no incluyen vecinos, árboles, postes ni autos. `manifest.json` registra 30316 triángulos, cinco vistas y validación geométrica aprobada; eso no certifica parecido visual.

Desde `investigation/procedural_reconstruction`, ejecutar `python3 steps/step23_fresh_theta/lotes/1137619_banco_neoclasico/build_fresh.py --massing-only` y luego el mismo comando sin flag para regenerar ambas etapas.
