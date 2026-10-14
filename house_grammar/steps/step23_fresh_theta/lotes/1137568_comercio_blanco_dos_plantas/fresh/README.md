# Tintoretto blanco — 1137568, Step23

**Edificio objetivo:** local blanco de planta baja con escaparate y acceso en arco bajo terraza abierta y techumbre oscura. En las dos fotos `_lot.jpg` aparece entre el minimarket amarillo «Plus» a la izquierda y un edificio crema de ventanas grandes a la derecha. Ambos son **vecinos**; el GLB solo contiene el volumen correspondiente al frente corto catastral del restaurante. `after/request.json` se usa para parcela/frente/cámaras, no como patrón de vanos o masa.

## Primero: masa, verificada antes de detallar

`../massing_preview/` contiene un theta de **solo masas** con dos comparativas (una por cámara) y dos renders. Desde el frente canónico corto de ~7.27 m: `shop` cerrado, una planta de 3.3 m de altura y profundidad de ~9 m; `terrace_roof` abierto desde z3.3 a 6 m y profundidad ~8.5 m, con soportes `columns` y cubierta `corrugated`. La terraza es espacio abierto bajo techo, **no** una segunda planta encerrada por una fachada ficticia. La cubierta usa material `roof` oscuro; el intradós estructural sigue claro porque `concrete` comparte usos en la base. La azotea del primer cuerpo lleva parapeto .36 m.

Comparación de masas: la tipología, el vacío superior y la altura general corresponden, pero la silueta renderizada queda algo **más estrecha y desplazada** que la fachada del restaurante de la foto. La catastral/cámara disponible no permite concluir todavía una anchura fotográfica exacta. No se escaló fuera de la parcela para disimularlo.

## Luego: detalles y profundidad

`fresh/request.json` añade una ventana comercial rectangular subdividida y hundida .19 m a la izquierda; letrero geométrico `sign_box` «TINTORETTO» sobre esa vidriera; plinto, faja de coronación y pilastras de piedra clara salientes. El acceso arqueado de la derecha es una **zona de fachada independiente** (`FacadeZone` de `u:[.53,1]`, `offset_m:-1.15`) con `FacadeSection`: suelo y sofito cubiertos, columnas laterales; vano de arco que se hunde otros .32 m y `segmental_surround` alrededor. En las dos oblicuas el retranqueo se aprecia, a diferencia de una moldura pegada al plano frontal. Materiales: revoque blanco roto, metal/vidrio oscuros, madera cálida, tejado gris oscuro. `family:quiet_house` no introduce letreros de otros negocios porque los frentes se programan explícitamente.

## Resultado y límites de semejanza

`manifest.json`: `envelope_test: passed`, 3176 triángulos, dos cámaras. `fresh/compare_*.jpg` muestra que la ventana y el acceso ahora son diferentes y que el arco tiene profundidad real. Aun quedan diferencias visibles: el acceso de la foto está enmarcado por una verja exterior negra ausente, el letrero tipográfico vectorial no reproduce el logotipo original, los apoyos/antepecho superiores son más regulares y la cubierta del render enseña un intradós claro, mientras el de la foto se percibe oscuro. Los árboles ocultan parte de la cubierta y no son masa del edificio. **No se afirma que el resultado sea perfecto** por pasar validación geométrica.

Reproducir desde `investigation/procedural_reconstruction`: `python3 steps/step23_fresh_theta/lotes/1137568_comercio_blanco_dos_plantas/build_fresh.py --massing-only` y luego el mismo comando sin flag para la etapa detallada.
