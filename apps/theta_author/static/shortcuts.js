'use strict';
/* Atajos de teclado de B · fuente única para la UI y el diálogo de ayuda.
   app.js consume STYLE_KEYS y SHORTCUT_GROUPS; el test de consistencia los
   evalúa con node y comprueba que cada tecla documentada existe en app.js. */
const STYLE_KEYS={'1':'republicano','2':'barroco','3':'clasico','4':'madera','5':'moderno'};
const SHORTCUT_GROUPS=[
 {title:'Alturas exactas',items:[
  {key:'Q',label:'Cantidad de pisos',hint:'Enfoca y selecciona; escribe el número y Tab'},
  {key:'A',label:'Altura por piso',hint:'Enfoca y selecciona; escribe el número y Tab'},
  {key:'S',label:'Primer piso diferente',hint:'Activa o desactiva; al activar salta a su altura'},
  {key:'W',label:'Altura del primer piso',hint:'Si está apagado lo enciende y enfoca'}]},
 {title:'Estilos',items:[
  {key:'1',label:'Republicano'},{key:'2',label:'Barroco'},{key:'3',label:'Clásico'},
  {key:'4',label:'Madera'},{key:'5',label:'Moderno'}]},
 {title:'Fotos',items:[
  {key:'D',label:'Página anterior de fotos'},{key:'F',label:'Página siguiente de fotos'},
  {key:'Z',label:'Marcar 1.ª foto visible'},{key:'X',label:'Marcar 2.ª foto visible'},
  {key:'C',label:'Más fotos cercanas'}]},
 {title:'Flujo',items:[
  {key:'V',label:'Notas opcionales',hint:'Enfoca el campo'},
  {key:'G',label:'Siguiente lote sin paquete',hint:'El más cercano al lote actual'},
  {key:'Enter',label:'Preparar / Generar',hint:'Paso 1 prepara · paso 2 genera'},
  {key:'/',label:'Buscar lote por ID'},{key:'H',label:'Esta ayuda'},
  {key:'Esc',label:'Cerrar lote o diálogo'},
  {key:'Retroceso',label:'Volver y ajustar',hint:'Del paso 2 al paso 1'}]}];
if(typeof module==='object'&&module.exports)module.exports={STYLE_KEYS,SHORTCUT_GROUPS};
