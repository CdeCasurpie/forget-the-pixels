# Auditoría visual de las comparativas foto | malla — Step 22

## Alcance y criterio

Revisé las comparativas `before/compare_<camera>.jpg` (todas las cámaras
`present` por lote), las planchas de fotografías **enmascaradas** para
identificar la construcción correcta y las solicitudes/resueltos de θ. Son
19 lotes con comparativas; `1138310` carece ahora de carpeta y antes tenía
cinco vistas marcadas `absent`: **no hay comparación válida** para ese ID.

Una diferencia en la comparativa no demuestra por sí sola una carencia de
gramática: muchos θ fueron primeras hipótesis con `single_block`, vanos
repetidos y altura estimada. Indico **[AJUSTE]** cuando ya existe un control
en `src/domain/theta.py` y **[GRAMÁTICA]** cuando hace falta nueva
representación/generación. **[DATOS]** designa algo que las vistas no fijan
sin medición adicional. Un GLB que pasa la envolvente catastral no equivale
a parecerse al edificio de Street View.

Además, la imagen derecha se renderiza **sola sobre fondo blanco** con
cámara equivalente; no es un fotomontaje con oclusiones, árboles y sombras
de la escena real. Comparar silueta y fachada del edificio objetivo, no
interpretar la ausencia del entorno como fallo de gramática. La máscara
sirve para identificar el objetivo; algunos contornos incluyen cerco,
árbol o edificio vecino y requieren revisión humana.

## Diagnóstico por lote

### 1134299 — casa salmón republicana (4 vistas)

Foto: casa salmón de dos niveles, dos arcos bajos (ventana y acceso),
ventanas superiores blancas con rejas, pequeño balcón lateral; ocupa parte
del solar y detrás del muro/reja hay jardín/estacionamiento. Render: prisma
salmonado del lindero a cubierta, vanos rectangulares sobre superficie plana
y sin cerco ni jardín visible. **[AJUSTE]** Familias/materiales y posiciones
de vanos sí se ajustaron; aún comparar alturas y el saliente del balcón.
**[GRAMÁTICA]** Retiro frontal de este polígono falla por muros parcialmente
expuestos; separar huella/catastro, jardín y estacionamiento, muro por tramos,
arcos con reja y cuerpo lateral escalonado. **[DATOS]** Jardín oculto por
árbol y cerco: superficie exacta no inferible de esta foto.

### 1134486 — restaurante con terraza (4 vistas)

Foto: local blanco de alta con pocas ventanas verdes, planta baja abierta al
comedor exterior bajo toldos/sombrillas; otra cara muestra un comercio
magenta con gráfica propia. La máscara marca un sector de esa composición:
**verificar alcance del lote y de la etiqueta antes de copiar ambos locales
como uno solo**. Render: bloque bicolor, vanos repetidos y marquesina
genérica que ocupa la esquina. **[AJUSTE]** Suprimir vanos en muros ciegos,
materiales por fachada y programa comercial bajo separado del residencial
alto. **[GRAMÁTICA]** Terraza abierta con mesas, carpinterías plegables,
toldo/sombrillas y rótulos/grafismo propios; frentes múltiples con usos
independientes. El retiro probado colapsa la huella irregular.

### 1135369 — casona esquinera en demolición (5 vistas)

Foto: cascarón de esquina con sectores aún de dos niveles, grandes arcos de
planta baja, ventanas superiores desiguales y terraza abierta; valla de obra
y escombros son estado temporal. Render mejorado: dos niveles pero masa
íntegra opaca, accesos rectangulares y vanos que no reproducen el patrón de
daños. **[AJUSTE]** Abrir/suprimir vanos por cara y corregir altura
observada según ángulo; ya se usan fachadas explícitas. **[GRAMÁTICA]**
Arcos, cuerpos faltantes y superficies de ruina/estado de obra, si el
objetivo es clonar **esa fecha** de Street View. Modelar un edificio intacto
es otra hipótesis, no igualdad visual con las fotos.

### 1135370 — edificio crema con cerco bajo (3 vistas)

Foto enmascarada: casa crema de **aprox. dos plantas** con torreón/nicho
vertical a un lado, balconcito o ventana retranqueada, arcos en baja,
parapetos escalonados y reja/muro bajo con palmeras. Render: tres plantas
uniformes, balcones repetidos, muro bajo simétrico. **[AJUSTE]** Reducir
pisos/altura, suprimir balcones inventados, ubicar aberturas por cara;
`front_setback_m=0.5` + `concreto_bajo` ya fue validado pero solo abre una
franja pequeña. **[GRAMÁTICA]** Alturas diferentes por sector/torreón,
retranqueos y jambas ornamentales, cerco en tramos y jardín proporcional.
No confundir el volumen vecino demolido con parte del lote.

### 1135382 — casa verde-agua de esquina (5 vistas)

Foto: vivienda predominantemente **de una planta**, puerta central en arco,
ventanas con reja, garaje blanco lateral y pequeño volumen retirado sobre
una parte. Render: dos plantas completas con ventanas y puerta ajenas;
discrepancia de silueta dominante. **[AJUSTE]** Modelo de una planta si el
volumen alto no pertenece a esta construcción; `bay_count`, grilles y
posición de portón. **[GRAMÁTICA]** Volumen alto parcial *sin masa explícita*,
arco y reja, garaje junto a jardín/retiro lateral. El retiro probado falla
por exposición parcial de muros.

### 1135384 — comercio de zócalo ladrillo y planta blanca (2 vistas)

Foto: bajo rojo de portones/paneles casi ciegos y entrada peatonal arqueada;
alto blanco con **dos ventanas separadas**; cubierta del garaje a una agua
con tejas. Render: escaparate comercial abierto, tres ventanas genéricas
arriba y barra de rótulo ajena. **[AJUSTE]** Evitar `mixed_use` repetido:
fachada explícita por piso, portones (`roller`/`metal_gate`), dos ventanas,
quitar toldo/rotulación y separar pintura de ladrillo. **[GRAMÁTICA]** Arco
peatonal, reja y cubierta inclinada parcial sobre garaje sin definir masas a
mano. La gran torre a la izquierda pertenece al vecino.

### 1135572 — vivienda terracota estrecha con patio (3 vistas)

Foto: volumen angosto de ladrillo/terracota con una ventana enrejada saliente
y remate de cornisa; patio/corredor lateral cerrado por reja. Render: dos
fachadas enteras rosa y gris, balcón que no coincide y huecos estándar.
**[AJUSTE]** Suprimir balcón automático, pocos vanos con `facades` y colores
por slot. **[GRAMÁTICA]** Patio lateral entre volumen y lindero, reja/portón
por tramo, ventanal saliente/volado y huella que no llene el polígono.

### 1135847 — local estrecho con pantalla (3 vistas)

Foto: escaparate de cafetería en baja, alta como **celosía perforada** de
pantalla completa, letras y grafismo propio, paleta crema/oscura. Render
mejorado: dos paños vidriados, panel liso, persiana de lamas horizontales
opacas, laterales ciegos. **[AJUSTE]** Escala del letrero, altura y ancho de
paños. **[GRAMÁTICA]** Celosía paramétrica perforada (módulo, espesor,
transparencia y patrón), rótulo de texto arbitrario/material real. El prefab
`louver` no equivale a esa trama; el catálogo de glifos rechazó el nombre.

### 1137173 — grifo / marquesina exenta (3 vistas)

Foto: casi todo es **espacio abierto pavimentado**; cubierta ancha y delgada
sostenida por postes sobre surtidores, caseta lateral baja y publicidad.
Render: prisma cerrado con puerta, ventanas y señal genérica en esquinas.
**[GRAMÁTICA, BLOQUEANTE]** Programa `fuel_station`/marquesina exenta con
planta de postes, altura libre, canto/cubierta, surtidores, caseta y área de
circulación pavimentada. No se soluciona con cambiar `family` o cerco; θ
actual no tiene primitivas para construir este tipo sin masas explícitas.

### 1137568 — comercio blanco con terraza ligera (2 vistas)

Foto: local blanco estrecho con acceso arqueado y escaparates/cierre en
baja, **cubierta ligera abierta** a un costado/arriba. Render: dos plantas
cerradas con ventanas genéricas y rótulo automático. **[AJUSTE]** Diferenciar
paños de escaparate y suprimir ventanas altas inventadas; revisar si el
volumen alto pertenece al lote. **[GRAMÁTICA]** Terraza y marquesina con
estructura abierta, arcada real, rótulo de tienda no limitado a presets.

### 1137619 — banco / gran fachada esquinera (5 vistas)

Fotos: dos caras muy distintas: una sede amarilla de esquina con **lamas
verticales altas** y zócalo azul; ala gris larga con gran portón, pilastras,
cornisa y ventanas altas con rejas. Render: prisma gris de una altura, una
cara ciega y la otra con ventanas estrechas repetidas y puerta minúscula.
**[AJUSTE]** `facades` explícitas por cara, vanos y material_regions/slots,
puerta y portón diferenciados; la cara gris no debe repetir el patrón de la
amarilla. **[GRAMÁTICA]** Dos lenguajes arquitectónicos unidos en el mismo
solar, alturas/remates distintos por ala, lamas de escala arquitectónica,
portón monumental y cornisa/pilastras continuas por frente.

### 1138183 — bloque moderno de balcones corridos (5 vistas)

Foto: bloque de 4–5 pisos con bandas **continuas** de balcones/retranqueos,
núcleo vertical oscuro y paños vidriados amplios; el volumen se interrumpe
y cambia orientación cerca de esquina. Render: bloque macizo muy profundo
con balcones pequeños alternos y muchas ventanas/puertas repetidas incluso
en costados. **[AJUSTE]** Orientar frentes reales, limitar override a caras
expuestas, reducir repeticiones falsas, altura y materiales por nivel.
**[GRAMÁTICA]** Balcón lineal corrido por tramos, pórticos de pilares,
entrepiso abierto, varios cuerpos en un lote con unión y retiro procedimental,
circulación comercial baja y gran área libre. El patio/retiro no se obtiene
con el setback actual de esta parcela irregular.

### 1138209 — casona crema con galería (2 vistas)

Foto: dos plantas principales con hastial/mansarda y buhardillas sobre parte
del frente, gran galería lateral porticada y **cerco blanco** con accesos;
ventanas de carpintería blanca subdividida. Render: volumen bajo uniforme
con galería corrida por todo el frente, baja marrón, cubierta genérica y
sin cerco. **[AJUSTE]** `gallery_depth_m`, vanos/carpintería y materiales de
galería; probar cercos solo tras liberar lindero. **[GRAMÁTICA]** Cubierta
compuesta con buhardillas y frontones, volúmenes de dos alturas, galería
**parcial** y patio/cerco blanco por tramos. El setback actual falla.

### 1138261 — edificio de fachada azul gris vertical (3 vistas)

Foto: tres pisos, pilastras/bandas verticales continuas de arriba abajo,
vanos **estrechos y altos** repetidos, acceso de vidrio y garaje de mayor
ancho en baja. Render: ventanas pequeñas casi cuadradas por nivel, puerta
simple, paños laterales marrones, línea horizontal por piso y protuberancias
laterales. **[AJUSTE]** Más vanos esbeltos mediante ejes/medidas individuales,
`materials` por slot y puerta/garaje distintos. **[GRAMÁTICA]** Retícula
vertical continua de pilastras y paneles a toda altura, carpintería apilada
por eje, entradas comerciales/vehiculares bajo un mismo frente; evitar que
un lote catastral grande genere masa lateral gigantesca.

### 1138283 — vivienda verde tras muro (2 vistas)

Foto: volumen verde de tres pisos **retirado** tras muro de ladrillo con
portones/rejas; balcones y un tramo superior más estrecho. Render: edificio
completo en el lindero con puerta y ventana abajo, balcones en niveles
superiores; el `fence=ladrillos` pedido no aparece porque no queda arista
libre. **[AJUSTE]** Vanos y color por piso, no atribuir el muro al edificio.
**[GRAMÁTICA]** Huella retraída independiente del solar, cerco frontal con
portón y jardín/patio/estacionamiento detrás, volumen superior escalonado.
El setback actual colapsa este lote al considerar varios frentes.

### 1138316 — muro y local bajo, evidencia fragmentaria (4 vistas)

Fotos y máscaras muestran por turnos un comercio en esquina, un paño largo
de muro ciego y partes del vecino; no hay una envolvente completa y segura
del mismo edificio en todas las vistas. Render: tira larga con **ventanas
repetidas que no existen en el muro**. **[AJUSTE]** Antes de optimizar θ,
revisar correspondencia cámara→segmento/lote, etiquetar qué tramo es muro,
puerta y comercio; suprimir vanos en caras ciegas con `facades`. **[GRAMÁTICA]**
Muros perimetrales por tramos y patio libre, edificio de baja ocupación sin
forzar un prisma continuo. **[DATOS]** No inferir una fachada posterior desde
segmentos mezclados.

### 1138323 — casona amarilla monumental de esquina (5 vistas)

Foto: edificio de una planta con dos fachadas a calle, **portales arqueados
altos**, vanos de reja entre pilastras, cornisa blanca pesada y frontones
escalonados en los ejes de acceso; zócalo oscuro. Render: prisma monótono
de una planta, ventanas estrechas/puertas de madera genéricas, sin frontón
ni contraste amarillo-blanco-negro. **[AJUSTE]** Materias por zona, puerta
central y ventanas por cara, ritmos de vanos particulares. **[GRAMÁTICA]**
Sistema de arcos de altura variable, pilastras y cornisa en relieve con
frontón por eje; ornamentación simétrica en **dos fachadas** unidas en
esquina. `republicano` como etiqueta sola no genera esa arquitectura.

### 1138401 — comercio rojo y rejas (2 vistas)

Foto: tramo bajo de locales/muros rojos con rejas, portones grandes y
cubierta ligera; las vistas largas muestran muros de predios contiguos.
Render: bloque cerrado gris-marrón con ventanas rítmicas, letreros de
taller y portón repetido en cara errónea. **[AJUSTE]** Quitar carteles
genéricos y ventanas sin evidencia, ubicar portones/rejas en la cara real.
**[GRAMÁTICA]** Secuencia de unidades comerciales independientes con
portones de distintos anchos, patio/muro ciego intercalado y cubierta
ligera parcial.

### 1138477 — edificio blanco con garaje (2 vistas)

Foto: **dos niveles principales** con paños de vidrio y balcones estrechos,
alta parcial en terraza; baja en gran parte abierta para autos, rampa y
portón amplio, retranqueada respecto a plantas altas. Render: tres pisos
cerrados de ventanas y balcones pequeños repetidos, acceso estrecho.
**[AJUSTE]** Recontar niveles y abrir portón con vanos explícitos.
**[GRAMÁTICA]** Planta baja libre con pilares, rampa/estacionamiento y
volumen superior sostenido (voladizo/soporte), combinación de cubiertas y
retiro por piso; el setback frontal actual colapsa la huella irregular.

### 1138310 — sin comparación actual

Los cinco recortes estaban etiquetados `absent` y su carpeta ya no está;
no hay evidencia para atribuir rasgos a ese lote. Una propuesta anterior
fue solo hipotética: **no** debe entrar en métricas foto–render ni en una
lista de limitaciones arquitectónicas observadas. Preservar este estado
explícito; conseguir una vista válida si se quiere evaluar el lote.

## Capacidades presentes que deben aprovecharse ANTES de cambiar src

`src/domain/theta.py` ofrece `facades` por arista y `FacadeControls` en modo
`repeat` o `explicit`: ejes/ancho/alto de vanos, `opening_edits`, puertas,
portones, `prefab` (storefront, louver, roller), material_regions,
projections, `balconies=false`; `materials` cambia slots, `roof` cubierta y
parapeto, `site.runs` cercos por tramos libres. Muchas imágenes mejorarían
enormemente con **clasificación correcta, ejes de vanos y planta baja por
cara**, sin tocar la gramática. El generador masivo actual todavía usa θ
repetitivo y no realizó una búsqueda completa; documentar ese error por
separado del límite estructural.

## Prioridades para ampliar la gramática sin masas explícitas

1. **Implantación y espacio libre (bloqueante para muchos lotes):** huella
   procedimental desacoplada de parcela, retiros por arista/piso, soporte
   de exposición parcial de muros y recortes no convexos. Tipar jardín,
   estacionamiento, terraza, paso peatonal y patio; cerco/portón por tramos
   alineado al acceso. Referencia: `AREA_LIBRE_AUDIT.md` (solo un retiro
   de 0.5 m resolvió entre 20 solicitudes).
2. **Sistema de cuerpos por reglas, no huellas a mano:** ala frontal/trasera,
   torreón, anexo, franja de balcón y plantas sobre pórtico con alturas
   independientes, soporte y conexiones; fachadas diferentes por cuerpo
   y por planta. 1135382, 1138209, 1138183, 1138477.
3. **Composición semántica de fachadas:** programa de baja independiente de
   alta, caras de esquina distintas, huecos de puerta/portón/escaparate en
   ejes irregulares; líneas verticales/horizontales continuas y balcones
   corridos parciales. 1134486, 1137619, 1138261, 1138183.
4. **Prefabs arquitectónicos faltantes:** arco con geometría de intradós,
   pilastra, frontón, cornisa escalonada, buhardilla, marquesina exenta,
   pantalla de celosía perforada y cubierta ligera. 1138323, 1138209,
   1137173, 1135847.
5. **Aspecto y representación visual:** texturas/fotografía de materiales
   reales, tipografías libres, rejas según dibujo, color por región y
   material de puertas. Calibrar cámaras/altura con máscaras multivista;
   renders comparativos sobre el fondo real con **oclusión separada** para
   evaluar la misma silueta, pero no incorporar árbol/coche al modelo.

Para buscar una coincidencia casi exacta harán falta anotaciones de alturas,
profundidades visibles/ocultas y estado temporal. Incluso con gramática más
rica, cinco fotos de calle pueden no observar azotea, patio y parte posterior:
**igualdad exacta en 3D no es verificable** sin evidencia adicional. El
objetivo medible es coincidencia de silueta, posición, semántica de fachada y
apariencia **en las vistas disponibles**, con incertidumbre explícita fuera
de ellas.
