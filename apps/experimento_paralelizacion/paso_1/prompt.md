# Lectura arquitectónica detallada en español

Describe exclusivamente el inmueble de la parcela suministrada, usando todas las fotos. Devuelve TEXTO ESPAÑOL organizado por las preguntas siguientes, sin JSON ni código. Tu lector traducirá esta especificación a una gramática geométrica en otra solicitud independiente.

## Autoridad y coordenadas
La parcela, frentes, cantidad de pisos y cotas del registro son restricciones impuestas por el usuario, incluso si el formulario original dice suggested. No las reestimes. Puedes indicar qué cuerpos terminan en cada nivel conocido. Señala contradicciones sin alterar el registro. El estilo humano es la preferencia dominante, NO una obligación de inventar ornamentos. Otros estilos son hipótesis locales secundarias basadas en señales visibles.
El prisma catastral es una referencia, no la huella observada del edificio. Distingue vecinos y oclusores. No supongas ocupado todo el fondo del lote. Usa IDs M1 para masas, F1 para fachadas, V1 para ventanas, P1 para puertas, B1 para balcones, C1 para cercos. Identifica cada fachada por frente/arista y foto, y define izquierda/derecha mirando desde la calle. No confundas esa izquierda con la dirección de la arista.
Todo porcentaje debe indicar denominador: ancho de F1, profundidad del lote, altura del piso o superficie del lote. Da intervalos de ubicación y tamaño; no confundas 40% del ancho con 40% del área. Las proporciones proyectadas no son medidas rectificadas. Usa rangos métricos estimados solo cuando exista escala suficiente. No inventes precisión para el fondo invisible.
Por elemento indica: ID, cuerpo/fachada/nivel, ubicación, dimensiones, forma, material/color, relación con otros elementos, fotos de evidencia y confianza alta/media/baja por atributo. Estados: presente, ausente observable, no visible, inferido. No visible no significa ausente. No describas detalles típicos de un estilo como si estuvieran en las imágenes.

## Cuestionario obligatorio
### Diagnóstico visual antes de asignar nombres
El catálogo es una lista de candidatos que debes buscar, NO una lista de elementos que deban existir. Para cada región metálica, abertura o saliente compara estas alternativas y decide usando señales visibles:

| Candidato | Señales necesarias / discriminantes |
|---|---|
| Ventana con reja | Hueco delimitado por pared con jambas y dintel; barras cubren ese hueco. Buscar vidrio/marco detrás. No implica balcón. |
| Puerta peatonal | Hueco que llega a suelo/umbral, marco y posible hoja, bisagras/tirador. Si el pie está oculto, no confirmar uso. |
| Portón vehicular | Hueco ancho que llega a suelo y posible acceso/rampa; hojas, carril o enrollado si visibles. Ancho por sí solo no demuestra cochera. |
| Cerco de barrotes | Cerramiento delante de la fachada o en límite del lote, anclado al suelo/base, con continuidad entre postes. Buscar separación respecto a pared y accesos. |
| Baranda sobre terraza | Protección de borde de superficie transitable existente; demostrar borde/solado y cota. No añadir una losa saliente nueva. |
| Balcón saliente | Plataforma/losa que sale del muro y protección en su borde; buscar lateral, intradós y vano de acceso. Barras solas NO prueban plataforma. |
| Protección de vano sin balcón | Barras delante de un hueco alto sin plataforma demostrable. No atribuir vuelo de 1 m por apariencia típica. |
| Galería | Circulación/plataforma continua, cubierta y apoyos identificables; no basta una reja larga. |
| Balcón cajón | Volumen cerrado saliente, caras laterales y frontal, paneles/vidrio/celosía; no confundir una ventana de madera con cajón. |
| Seto / vegetación urbana | Follaje y tierra; comprobar si está dentro del lote o entre acera/calzada. No convertirlo en cerco metálico ni zona privada sin evidencia. |
| Volumen retranqueado | Dos planos de pared unidos por un retorno lateral visible o evidencia multivista; cambio de color/sombra no basta. |
| Cornisa / banda | Relieve horizontal limitado; no es por sí solo borde de piso ni cubierta. |
| Frontón | Silueta ornamental sobre vano o muro; distinguir del faldón real detrás. |
| Cubierta inclinada | Superficie y dirección de pendiente identificables; una franja de teja no prueba cubierta completa. |

Antes de llamar balcón, cerco o portón a algo, registra dos señales observadas que apoyen esa clase y una alternativa descartada con motivo. Si no hay señales suficientes, conserva ID neutral R1 (región con barras), H1 (hueco), S1 (saliente) con candidatos y geometría observable. La incertidumbre de clase NO obliga a omitir ubicación/color/extensión visibles. No marques candidato como presente por cumplir una sola señal genérica.

Busca también, sin asumir presencia: ventanas rectangulares/arco/óculo; puertas paneladas/tablas/vidriadas/reja/lamas; barandas verticales/aros/volutas/balaustres/cruces/vidrio; columnas circulares y pilastras rectangulares; frontones triangulares/curvos/escalonados; techo plano/una/dos/cuatro aguas, teja/chapa/listones; cercos macizos/barrotes/lamas/tablas. Describe rasgos observados antes de escoger la etiqueta de catálogo. Si la forma real no encaja, déjala sin equivalente exacto.

1. Identificación: ¿qué inmueble es el objetivo en cada foto? ¿Qué caras se ven y cuáles están ocultas? ¿Hay contradicciones entre vistas?
2. Masas: ¿cuántos cuerpos cerrados y abiertos hay? Para cada uno: intervalo del ancho del frente, profundidad conocida/estimada/desconocida, niveles ocupados, relación frente/fondo y apoyos. ¿Patios, pasos laterales, recortes, cuerpos sobre azotea, frente bajo/fondo alto, escalonamientos? Distingue masa de cambio de material.
3. Planos: ¿qué sectores sobresalen o se retranquean y respecto a qué plano? ¿Desde qué nivel? ¿Cuánto aproximadamente? ¿Es volumen habitable, balcón, marquesina o moldura? ¿Gira por esquina? ¿Se ven columnas o ménsulas?
4. Puertas del edificio: inventario con posición horizontal, borde inferior, ancho/alto, rectángulo/arco, uso peatonal/vehicular/comercial, hojas, cuarterones/tablas/vidrio/reja/lamas, marco, sobreluz, retranqueo, portal, escalones/rampa. No confundir con puertas del cerco.
5. Ventanas: inventario por piso y fachada. Cantidad, intervalos, antepecho, ancho/alto, rectángulo/arco/círculo/óvalo, divisiones, marco y relieve, profundidad, alféizar, reja vertical/retícula/rombos, contraventanas. Para repetidas especifica cantidad, separación y excepciones. Explica alineación entre pisos.
6. Balcones: plataforma saliente, protección sin plataforma, terraza sobre otro cuerpo, galería con postes o cajón cerrado. Posición, nivel, ancho, vuelo, vanos conectados, baranda (barras/aros/volutas/balaustres/madera/vidrio/lamas/macizo), lados, ménsulas, borde, cubierta, curvatura, vuelta de esquina, jardineras.
7. Soportes: columnas/pilastras/postes, ejes, altura y sección, adosados/separados, base/capitel, liso/acanalado/torneado/panel/torsionado, material y función observable.
8. Remates: frontones sobre vano o muro, ancho/altura, triangular/curvo/semicircular/escalonado/partido/hombros cóncavos, óculos, cartelas, volutas, dentículos. Cornisas, frisos, bandas y zócalos: intervalos, cotas, vuelo y continuidad. No confundir frontón con cubierta inclinada.
9. Cubiertas por masa: forma plana/una/dos/cuatro aguas/compuesta/banda; recubrimiento teja curva/plana/chapa ondulada/panel/listones; dirección de pendiente/cumbrera si visible; alero y vuelo, vigas/ménsulas/tornapuntas, fascia/canaleta, parapeto. ¿Solo se ve una franja? No extrapolarla al techo entero. Marquesinas y objetos de azotea solo observados.
10. Cercos: presencia y tramos, posición respecto al edificio, altura/base, macizo/barrotes/lamas/tablas, material/color, aros/volutas/puntas, pilares. Puerta peatonal y portón: intervalos, anchos, hojas, patrón y paso abierto/cerrado. Correspondencias orientativas: republicano=barrotes/aros; barroco=volutas; clasico=macizo; madera=tablas; moderno=lamas horizontales. Si no encaja, describe fielmente sin forzar etiqueta.
11. Suelo: retiro, patio, jardín, estacionamiento dentro del lote (observado o inferido), cubierto/descubierto/bajo piso, acceso vehicular, rampa, corredor, pavimento y desniveles. Un portón no demuestra la geometría interior; un auto en calle no demuestra estacionamiento privado.
12. Acabados: material/color por plano y franja. Distingue pintura de relieve. Toldos, letreros con texto realmente legible, bajantes, aletas y paneles: ubicación y tamaño. No completar letras ocultas.
13. Cierre: cinco rasgos prioritarios para reconocer el edificio; inventario consolidado de IDs; incógnitas; contradicciones; aproximaciones necesarias. Revisa que cada pieza pueda ubicarse sin releer toda la narración.

## Protocolo de lectura multivista
Lee primero la leyenda del prisma y el registro. Identifica el objetivo por su parcela proyectada en cada imagen, no por el edificio más llamativo. Usa los identificadores de foto del paquete. Las líneas verdes NO prueban que haya una losa, ventana o cambio de fachada allí; son cotas humanas superpuestas. Las aristas traseras del prisma pueden atravesar visualmente vecinos, árboles y cielo: no son contornos del edificio. No atribuyas los colores de las líneas al inmueble.
Reúne las observaciones de todas las fotos antes de contar elementos. Una ventana vista en dos fotos es un único ID. Si no puedes asociar dos vistas con seguridad, declara la asociación incierta en lugar de duplicar piezas. Usa la vista menos ocluida para cada atributo, no necesariamente la imagen principal. Describe árboles, vehículos y cables únicamente como oclusores salvo vegetación inequívocamente dentro del lote.
Separa tres cosas: (a) niveles impuestos del proyecto, (b) niveles físicamente reconocibles en imágenes, (c) nivel donde asignas cada elemento. Si no ves el tercer piso impuesto, escribe eso: no inventes ventanas para rellenarlo ni cambies los tres pisos del registro.

## Ficha obligatoria por cuerpo y elemento
Usa español natural y listas breves con estas etiquetas. No es JSON:
- ID y clase; cuerpo y fachada de pertenencia; foto(s) que lo muestran.
- Presencia: observado / inferido / no visible / ausencia comprobable.
- Ubicación horizontal: borde inicial–final como porcentaje del ancho de SU fachada, indicando origen izquierda mirando desde calle. Para columnas indica eje. Asocia con arista catastral solo si puedes justificarlo; si no, deja correspondencia pendiente.
- Ubicación vertical: piso impuesto, borde inferior y superior respecto al suelo de ese piso; preferir metros estimados o porcentaje de la altura de ese piso. Di explícitamente qué unidad usas.
- Ancho, altura, profundidad o vuelo: valor/rango y referencia del plano desde el cual se mide. Si no se puede estimar, dilo.
- Forma, material y color aparentes; subdivisiones, relieve, adornos y estado abierto/cerrado cuando visibles.
- Relaciones: alineado con, encima de, apoyado en, retranqueado respecto a, conectado a otro ID. Distingue soporte observado de soporte hipotético.
- Confianza por atributo y motivo: por ejemplo, ancho medio por perspectiva; profundidad baja porque el lateral está oculto.
- Correspondencia de catálogo opcional, con nombre y motivo visual; si no existe equivalente, describe la diferencia sin deformar la observación para encajar.
Para grupos repetidos da número, límites de cada vano o separación entre ejes, dimensiones comunes y excepciones. Evita fórmulas vagas como 'varias ventanas uniformes'. Una lista de posiciones debe ser coherente con los anchos y la fachada disponible.

## Precisiones adicionales del inventario
- Puertas/portones: especifica hueco frente a hoja, sentido/apertura solo visible, sobreluz vidriada/abierta/con reja, pilastras/columnas del portal, cornisa, umbral, rellano, peldaños y rampa. Si parece enrollable, descríbelo así aunque el catálogo solo aproxime lamas; no inventes dos hojas.
- Ventanas: diferencia divisiones del vidrio de barras de seguridad, alféizar de banda continua y contraventana de reja. Indica espesor aparente del marco y hundimiento del relleno solo estimables.
- Balcones: distingue baranda sobre techo existente de losa propia; indica qué lados cierran, franja sólida inferior, postes, vidrio, celosías, cubierta y soportes. Un vano con reja no implica balcón.
- Cercos: describe cada tramo y cada interrupción por puerta/portón; indica la posición del acceso tanto respecto al frente como al tramo. Base maciza, altura total, apertura visual entre barras/lamas, coronación y materiales por parte. No inventes cercos laterales invisibles.
- Suelo: distingue estacionamiento de entrada vehicular, patio de terraza elevada y escalera exterior larga de peldaños de acceso. Describe recorrido, dirección, desnivel, ancho y barandas si visibles. Capacidad de autos solo si existe evidencia espacial suficiente.
- Cubiertas: distingue cubierta opaca de sol y sombra, fascia de cornisa, cierre inferior de vigas expuestas; anota pendiente en dirección hacia calle/fondo/lateral, no un giro XY inventado. Describe encuentro con frontón y si el techo queda detrás. Props de azotea: posición respecto al cuerpo y evidencia, sin rellenar los invisibles.
- Remates: distingue frontón sobre puerta, frontón que corona muro, parapeto y cuerpo habitable de azotea; describe continuidad por esquinas y patios solo visibles. Cornisa/zócalo/bandas deben tener cotas, extensión y proyección estimadas.
- Materiales: localiza regiones distintas, color base/acento, hoja/marco/reja y revestimiento. No deduzcas espesor estructural de un acabado de ladrillo. Estado de conservación no autoriza añadir geometría.
- Estilo: no produzcas porcentajes arbitrarios de mezcla estilística. Prioriza la sugerencia humana; señala excepciones locales claras, con rasgos observados. Los porcentajes pedidos son sobre todo geométricos y siempre llevan denominador.

## Cierre verificable para el traductor
Usa las imágenes MARCADAS para identificar parcela y cotas, y sus parejas LIMPIAS para reconocer detalles. Cada pareja muestra exactamente la misma foto: NO contar como evidencia independiente ni duplicar elementos. No deduzcas la altura física del edificio de una línea verde ni del extremo posterior del prisma. Para afirmar coronación observada exige borde real continuo identificable y correspondencia espacial; si la copa lo tapa, solo puedes declarar tercer nivel no reconocible, no coronación medida a 6 m.
No inventes orientaciones cardinales ni índices de aristas a partir de impresiones de la foto. Usa el contexto/cámara suministrados o deja correspondencia pendiente. No declares ausencia de portón/ventana en una zona tapada. No conviertas 'no observado' en 'ausente' en el resumen final.
No propongas puerta centrada, ventanas simétricas, repetición de barandas ni profundidad arbitraria para rellenar incertidumbre. En esta etapa las incógnitas quedan abiertas: el traductor recibirá por separado una política de completado. Da medidas aproximadas cuando la evidencia permita acotarlas, explicando referencia; no repitas 'no medible' seguido de un número sin fundamento.
Comprueba aritmética: 10–90% equivale a 80% del ancho; borde superior menos inferior debe coincidir con la altura indicada. Mantén el mismo denominador de F1 en todas las fichas: ancho total del frente catastral o ancho de fachada física, explícitamente elegido, nunca intercambiados. La tabla final no debe añadir medidas, clases ni certezas que no aparezcan justificadas en las fichas.
Incluye una tabla compacta final con ID, tipo, masa/fachada/piso, intervalo horizontal, vertical, profundidad y evidencia. Después lista las incógnitas que impiden ubicar geometría. Separa cualquier propuesta de completado de lo observado y justifica por qué sería mínima. No transformes una hipótesis del fondo en un dato medido.
Revisa consistencia: conteo sin duplicados entre fotos; piezas dentro del ancho descrito; niveles compatibles con las cotas humanas; aperturas sin solapes inventados; referencias a IDs existentes; ningún cerco, frontón o techo añadido solo por estilo. Señala cualquier conflicto que no puedas resolver.

Sé exhaustivo pero compacto: objetivo 2500–4000 palabras, sin rellenar por alcanzar una longitud. Prioriza medidas/intervalos y relaciones sobre adjetivos y repeticiones. El catálogo adjunto es vocabulario de representación, no evidencia de presencia. No omitas una sección: escribe no visible/ausente cuando corresponda, distinguiendo ambos estados.
