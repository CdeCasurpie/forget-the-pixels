'use strict';
const $=id=>document.getElementById(id), map=$('map'), ctx=map.getContext('2d');
const COS=Math.cos(-12.14*Math.PI/180), storagePrefix='theta-fast-v2:', PHOTO_PAGE_SIZE=2;
let features=[], featureById=new Map(), detail=null, cameras=[], chosen=new Set(), selectedStyle='republicano';
let center=[0,0], scale=1, width=1,height=1,dpr=1, progress={}, pageIndex=0, candidateOffset=3;
let generation=0, lotController=null, photoController=null, currentRun=null, currentStep=1, overlayFrame=null;
let photoCanvases=[], lightboxPhoto=null, mapFrame=null, messageTimer=null;
const pending=new Map(), syncing=new Set(), cache=new Map(), imageCache=new Map(), jobs=new Map();
function message(text,error=false){$('message').textContent=text;$('message').classList.toggle('error',error);clearTimeout(messageTimer);if(text&&!error)messageTimer=setTimeout(()=>{$('message').textContent='';},4500);}
async function api(url,body,signal){const r=await fetch(url,{...(body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}),signal});const data=await r.json();if(!r.ok)throw Error(typeof data.detail==='string'?data.detail:JSON.stringify(data.detail));return data;}
function action(id,fn){$(id).onclick=()=>Promise.resolve().then(fn).catch(e=>{if(e.name!=='AbortError')message(e.message,true);});}
function xy(p){return [p[0],-p[1]/COS];}
function point(p){const q=xy(p);return [(q[0]-center[0])*scale+width/2,(q[1]-center[1])*scale+height/2];}
function world(p){return [(p[0]-width/2)/scale+center[0],(p[1]-height/2)/scale+center[1]];}
function resize(){width=innerWidth;height=innerHeight;dpr=Math.min(devicePixelRatio||1,1.5);map.width=width*dpr;map.height=height*dpr;draw();}
function draw(){if(mapFrame!==null)return;mapFrame=requestAnimationFrame(()=>{mapFrame=null;ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,width,height);ctx.setTransform(scale*dpr,0,0,scale*dpr,(width/2-center[0]*scale)*dpr,(height/2-center[1]*scale)*dpr);
 const left=center[0]-width/2/scale,right=center[0]+width/2/scale,top=center[1]-height/2/scale,bottom=center[1]+height/2/scale;
 for(const f of features){if(f.bounds[2]<left||f.bounds[0]>right||f.bounds[3]<top||f.bounds[1]>bottom)continue;const status=progress[f.id],selected=f.id===detail?.snapshot.lot.lot_id;ctx.fillStyle=selected?'#406a79':status?.stage==='generated'?'#305c4b':status?.stage==='prepared'?'#2c4c6c':status?.stage==='preparing'?'#4b4d48':'#203744';ctx.strokeStyle=selected?'#b1eee0':'#526978';ctx.lineWidth=(selected?2.5:.8)/scale;ctx.fill(f.path);ctx.stroke(f.path);if(status?.changed){ctx.fillStyle='#e8bf75';ctx.beginPath();ctx.arc(f.mid[0],f.mid[1],2.5/scale,0,Math.PI*2);ctx.fill();}}
 ctx.setTransform(dpr,0,0,dpr,0,0);cameras.forEach((p,i)=>{if(!chosen.has(p.id))return;const [x,y]=point(p.camera_lonlat);ctx.fillStyle='#f2d36c';ctx.beginPath();ctx.arc(x,y,6,0,Math.PI*2);ctx.fill();ctx.strokeStyle='#443b20';ctx.lineWidth=1.5;ctx.stroke();ctx.font='bold 12px system-ui';ctx.fillStyle='#ffecac';ctx.fillText(i+1,x+9,y+4);});});}
function fit(all=false){let coords=features.filter(f=>all||f.id===detail?.snapshot.lot.lot_id).flatMap(f=>f.coordinates);if(!all)coords.push(...cameras.filter(p=>chosen.has(p.id)).map(p=>xy(p.camera_lonlat)));if(!coords.length)return;let minX=Infinity,minY=Infinity,maxX=-Infinity,maxY=-Infinity;for(const [x,y] of coords){minX=Math.min(minX,x);maxX=Math.max(maxX,x);minY=Math.min(minY,y);maxY=Math.max(maxY,y);}center=[(minX+maxX)/2,(minY+maxY)/2];const available=all?width-80:Math.max(180,width-$('photoPanel').offsetWidth-$('controlPanel').offsetWidth-100);scale=Math.min(available/Math.max(maxX-minX,.00025),(height-180)/Math.max(maxY-minY,.00025))*.8;draw();}
let drag=null;
map.onpointerdown=e=>{map.setPointerCapture(e.pointerId);drag={p:[e.clientX,e.clientY],center:[...center],moved:false};};
map.onpointermove=e=>{if(!drag)return;const dx=e.clientX-drag.p[0],dy=e.clientY-drag.p[1];if(Math.hypot(dx,dy)>4)drag.moved=true;center=[drag.center[0]-dx/scale,drag.center[1]-dy/scale];draw();};
map.onpointerup=e=>{if(!drag)return;const moved=drag.moved;drag=null;if(moved)return;const p=[e.clientX,e.clientY];const camera=cameras.find(c=>chosen.has(c.id)&&Math.hypot(...point(c.camera_lonlat).map((x,i)=>x-p[i]))<12);if(camera){pageIndex=Math.floor(cameras.indexOf(camera)/PHOTO_PAGE_SIZE);paintPhotos();return;}const [x,y]=world(p);ctx.setTransform(1,0,0,1,0,0);const f=features.find(f=>x>=f.bounds[0]&&x<=f.bounds[2]&&y>=f.bounds[1]&&y<=f.bounds[3]&&ctx.isPointInPath(f.path,x,y));if(f)loadLot(f.id);};
map.onpointercancel=()=>{drag=null;};
map.addEventListener('wheel',e=>{e.preventDefault();const p=[e.clientX,e.clientY],before=world(p);scale*=Math.exp(-Math.max(-.2,Math.min(.2,e.deltaY*.001)));const after=world(p);center=[center[0]+before[0]-after[0],center[1]+before[1]-after[1]];draw();},{passive:false});
addEventListener('resize',resize);

// Local write happens on every input; server writes are coalesced and serialized PER LOT.
function readLocal(id){try{return JSON.parse(localStorage.getItem(storagePrefix+id));}catch{return null;}}
function remember(id,value){try{localStorage.setItem(storagePrefix+id,JSON.stringify(value));}catch{message('No hay espacio local; mantén la pestaña abierta hasta sincronizar.',true);}}
function formValue(){const floors=+$('floors').value,regular=+$('floorHeight').value,first=$('firstDifferent').checked?+$('firstHeight').value:regular;return {geometry_revision:detail.snapshot.lot.geometry_revision,height:{mode:'suggested',value:+(first+(floors-1)*regular).toFixed(4)},floors:{mode:'suggested',value:floors},style:{mode:'suggested',value:selectedStyle},height_reference:'main_body',massing:{corner:false,delegate_complex:false,cuts:[]},massing_mode:'suggested',photo_ids:[...chosen],notes:$('notes').value,floor_height_m:regular,first_floor_different:$('firstDifferent').checked,first_floor_height_m:$('firstDifferent').checked?+$('firstHeight').value:null};}
function saveInput(){if(!detail)return;const id=detail.snapshot.lot.lot_id,entry={form:formValue(),dirty:true,stamp:Date.now()};remember(id,entry);pending.set(id,entry);$('saveStatus').textContent='Guardado local · sincronizando…';if(progress[id])progress[id].changed=true;draw();scheduleSync(id);}
const syncTimers=new Map();
function scheduleSync(id,delay=140){clearTimeout(syncTimers.get(id));syncTimers.set(id,setTimeout(()=>syncLot(id),delay));}
async function syncLot(id){if(syncing.has(id)||!pending.has(id))return;syncing.add(id);const entry=pending.get(id);try{await api('/api/lots/'+encodeURIComponent(id)+'/autosave',entry.form);if(pending.get(id)===entry){pending.delete(id);remember(id,{...entry,dirty:false});if(detail?.snapshot.lot.lot_id===id)$('saveStatus').textContent='✓ Guardado';}}catch(e){if(detail?.snapshot.lot.lot_id===id)$('saveStatus').textContent='Guardado local · '+e.message;if(!e.message.includes('cambió'))scheduleSync(id,2500);}finally{syncing.delete(id);if(pending.has(id)&&pending.get(id)!==entry)syncLot(id);}}
addEventListener('pagehide',()=>{for(const [id,entry] of pending){navigator.sendBeacon('/api/lots/'+encodeURIComponent(id)+'/autosave',new Blob([JSON.stringify(entry.form)],{type:'application/json'}));}});
addEventListener('online',()=>{for(const id of pending.keys())syncLot(id);});

function defaultForm(d){const v=d.snapshot.view_settings,reference=v&&!d.snapshot.view_settings_stale?v.reference_height_m:9;const floors=Math.max(1,Math.min(20,Math.round(reference/3)));return {floors:{value:floors},height:{value:reference},style:{value:'republicano'},photo_ids:d.photos.map(p=>p.id),notes:'',floor_height_m:Math.max(2,Math.min(6,Math.round(reference/floors*10)/10)),first_floor_different:false,first_floor_height_m:4};}
function applyForm(f){const floors=Math.max(1,Math.min(50,f.floors?.value||3));$('floors').max=Math.max(20,floors);$('floorsNumber').max=Math.max(20,floors);$('floors').value=floors;$('floorHeight').value=f.floor_height_m||Math.max(2,Math.min(6,(f.height?.value||floors*3)/floors));$('firstDifferent').checked=!!f.first_floor_different;$('firstHeight').value=f.first_floor_height_m||4;$('notes').value=f.notes||'';selectedStyle=f.style?.value||'republicano';chosen=new Set(f.photo_ids||[]);renderStyles();updateHeight();}
async function loadLot(id){
 if(detail?.snapshot.lot.lot_id===id)return;
 const old=detail?.snapshot.lot.lot_id;if(old)syncLot(old);
 const token=++generation;lotController?.abort();photoController?.abort();lotController=new AbortController();detail=null;cameras=[];photoCanvases=[];currentRun=null;pageIndex=0;candidateOffset=3;
 $('photoPanel').hidden=true;$('controlPanel').hidden=true;$('welcome').hidden=true;draw();message('');
 const render=d=>{if(token!==generation)return;detail=d;cameras=[...d.photos];$('photoPanel').hidden=false;$('controlPanel').hidden=false;$('lotTitle').textContent='Lote '+id;$('search').value=id;const local=readLocal(id);const saved=local?.form.geometry_revision===d.snapshot.lot.geometry_revision?local.form:d.form?.geometry_revision===d.snapshot.lot.geometry_revision?d.form:null;applyForm(saved||defaultForm(d));currentRun=d.latest_run;setStep(1);paintPhotos();draw();$('saveStatus').textContent=local?.dirty?'Guardado local · sincronizando…':'Guardado automático';if(local?.dirty&&saved===local.form){pending.set(id,local);syncLot(id);} };
 // Cached geometry lets repeat selections open immediately; refresh remains abortable.
 if(cache.has(id))render(cache.get(id));
 try{const d=await api('/api/lots/'+encodeURIComponent(id)+'/editor',undefined,lotController.signal);if(token!==generation)return;cache.set(id,d);if(!detail)render(d);else if(detail.snapshot.lot.geometry_revision!==d.snapshot.lot.geometry_revision){render(d);message('El catastro cambió; revisa los parámetros.');}else if(JSON.stringify(detail.snapshot.lot.geometry)!==JSON.stringify(d.snapshot.lot.geometry)){render(d);message('La manzana se movió; se conserva tu trabajo.');}else{detail.latest_run=d.latest_run;if(!currentRun)currentRun=d.latest_run;}}catch(e){if(e.name!=='AbortError')message(e.message,true);}
}
function closeLot(){if(detail)syncLot(detail.snapshot.lot.lot_id);++generation;lotController?.abort();photoController?.abort();detail=null;cameras=[];photoCanvases=[];currentRun=null;$('photoPanel').hidden=true;$('controlPanel').hidden=true;$('welcome').hidden=false;draw();}
function styleLabel(style){return style==='clasico'?'Clásico':style[0].toUpperCase()+style.slice(1);}
function pickStyle(style){if(!detail)return;if(currentStep!==1)setStep(1);selectedStyle=style;renderStyles();saveInput();}
function renderStyles(){for(const button of $('styles').children)button.setAttribute('aria-checked',button.dataset.style===selectedStyle?'true':'false');}
for(const [key,style] of Object.entries(STYLE_KEYS)){const b=document.createElement('button');b.className='styleCard';b.dataset.style=style;b.setAttribute('role','radio');b.setAttribute('aria-label',styleLabel(style)+' (tecla '+key.toUpperCase()+', sugerido)');const kbd=document.createElement('kbd');kbd.className='key';kbd.textContent=key.toUpperCase();const img=document.createElement('img');img.src='/static/styles/'+style+'.svg';img.alt='Ilustración orientativa '+style;const label=document.createElement('span');label.textContent=styleLabel(style);b.append(kbd,img,label);b.onclick=()=>pickStyle(style);$('styles').append(b);}
function setNum(id,v){const el=$(id);if(document.activeElement!==el)el.value=v;}
function updateHeight(){const n=+$('floors').value,h=+$('floorHeight').value,first=$('firstDifferent').checked?+$('firstHeight').value:h,total=first+(n-1)*h;setNum('floorsNumber',n);setNum('floorHeightNumber',h);setNum('firstHeightNumber',+$('firstHeight').value);$('totalHeight').textContent=total.toFixed(1)+' m';$('firstControl').hidden=!$('firstDifferent').checked;
 if(overlayFrame!==null)cancelAnimationFrame(overlayFrame);overlayFrame=requestAnimationFrame(()=>{overlayFrame=null;const cut=$('firstDifferent').checked?first:null;for(const v of photoCanvases)paintPrism(v.canvas,v.photo.projection,total,cut);if(lightboxPhoto&&$('lightbox').open)paintPrism($('lightbox').querySelector('canvas'),lightboxPhoto.projection,total,cut);});}
for(const id of ['floors','floorHeight','firstHeight','firstDifferent'])$(id).oninput=()=>{updateHeight();saveInput();};$('notes').oninput=saveInput;

async function imageURL(photo,revision,id,signal){const key=revision+':'+id+':'+photo.id;if(imageCache.has(key))return imageCache.get(key);const r=await fetch(`/api/photos/${encodeURIComponent(photo.id)}?lot_id=${encodeURIComponent(id)}&revision=${revision}`,{signal});if(!r.ok)throw Error('No se pudo proyectar la foto');const blob=await r.blob();if(signal.aborted)throw new DOMException('Aborted','AbortError');const url=URL.createObjectURL(blob);imageCache.set(key,url);if(imageCache.size>24){const oldest=imageCache.keys().next().value;URL.revokeObjectURL(imageCache.get(oldest));imageCache.delete(oldest);}return url;}
function paintPhotos(){photoController?.abort();photoController=new AbortController();const signal=photoController.signal,token=generation;$('photos').replaceChildren();photoCanvases=[];const pages=Math.max(1,Math.ceil(cameras.length/PHOTO_PAGE_SIZE));pageIndex=Math.min(pageIndex,pages-1);$('photoPage').textContent=(pageIndex+1)+' / '+pages;$('prevPhotos').disabled=pageIndex===0;$('nextPhotos').disabled=pageIndex===pages-1;$('photoCount').textContent=chosen.size+' seleccionadas · 2 por página';
 cameras.slice(pageIndex*PHOTO_PAGE_SIZE,(pageIndex+1)*PHOTO_PAGE_SIZE).forEach((p,index)=>{const number=pageIndex*PHOTO_PAGE_SIZE+index+1,card=document.createElement('article');card.className='photo';card.classList.toggle('selected',chosen.has(p.id));const label=document.createElement('label'),check=document.createElement('input');check.type='checkbox';check.checked=chosen.has(p.id);const caption=document.createElement('span');caption.textContent=`${number} · ${p.distance_m!=null?p.distance_m+' m · ':''}${p.date||'fecha desconocida'}`;check.onchange=()=>{card.classList.toggle('selected',check.checked);applyPhotoChoice(p.id,check.checked);};label.append(check,caption);const frame=document.createElement('div');frame.className='frame';const img=document.createElement('img');img.alt='Cargando foto '+number;const canvas=document.createElement('canvas');canvas.width=p.projection.width;canvas.height=p.projection.height;frame.append(img,canvas);card.append(label,frame);$('photos').append(card);photoCanvases.push({photo:p,canvas});
 imageURL(p,detail.snapshot.revision,detail.snapshot.lot.lot_id,signal).then(url=>{if(token===generation&&!signal.aborted){img.src=url;img.alt='Foto '+number;}}).catch(e=>{if(e.name!=='AbortError'&&token===generation)img.alt='No se pudo cargar; cambia de página para reintentar';});
 frame.onclick=()=>{if(!img.src)return;lightboxPhoto=p;const c=$('lightbox').querySelector('canvas');c.width=p.projection.width;c.height=p.projection.height;$('lightbox').querySelector('img').src=img.src;$('lightbox').showModal();updateHeight();};});updateHeight();}
action('morePhotos',async()=>{if(!detail)return;const token=generation,id=detail.snapshot.lot.lot_id;$('morePhotos').disabled=true;try{let added=[];while(!added.length){const result=await api(`/api/lots/${encodeURIComponent(id)}/candidates?offset=${candidateOffset}&limit=3`);if(token!==generation)return;candidateOffset+=result.length;added=result.filter(p=>!cameras.some(c=>c.id===p.id));if(!result.length){message('No hay más fotos cercanas.');return;}}cameras.push(...added);pageIndex=Math.floor((cameras.length-1)/PHOTO_PAGE_SIZE);paintPhotos();draw();}finally{$('morePhotos').disabled=false;}});
$('prevPhotos').onclick=()=>{pageIndex--;paintPhotos();};$('nextPhotos').onclick=()=>{pageIndex++;paintPhotos();};$('closeImage').onclick=()=>$('lightbox').close();

function setStep(step){currentStep=step;$('editStep').hidden=step!==1;$('sendStep').hidden=step!==2;$('stepLabel').textContent=step===1?'1 / 2 · Información sugerida':'2 / 2 · Preparar y enviar';if(step===2)renderRun();}
function renderRun(){const r=currentRun;if(!r)return;const busy=['preparing','queued','running'].includes(r.status),done=r.status==='succeeded'&&r.validation_status==='valid';$('stepIcon').textContent=done?'✓':busy?'◌':'→';$('runTitle').textContent=done?'Theta generado':r.status==='failed'?'No se pudo completar':'Información preparada';$('runSummary').textContent=`${$('floors').value} pisos · ${$('totalHeight').textContent} · ${selectedStyle} · ${chosen.size} fotos`;
 const labels={preparing:r.send_when_ready?'Envío solicitado. Terminando imágenes en segundo plano…':'Procesando adjuntos en segundo plano. Puedes enviar ahora o continuar con otro lote.',prepared:'Paquete listo para enviar.',queued:'Generación en cola…',running:'Generando theta…',succeeded:done?'Resultado guardado y validado por el adaptador mínimo.':'Respuesta guardada, pero no pasó la validación.',failed:r.error||'Error al preparar o generar',interrupted:'Trabajo interrumpido; prepara una nueva versión.',cancelled:'Trabajo cancelado.'};$('runStatus').textContent=labels[r.status]||r.status;$('resultInfo').textContent=done?'El lote aparece verde en el mapa. Sigue siendo un resultado MOCK.':'';$('generate').hidden=done;$('generate').disabled=!!r.send_when_ready||!['preparing','prepared'].includes(r.status)||r.stale;$('generate').textContent=r.send_when_ready?'Envío solicitado ✓':'Generar theta · MOCK →';$('nextLot').hidden=!done;}
action('prepare',async()=>{if(!detail||$('prepare').disabled)return;const token=generation,id=detail.snapshot.lot.lot_id,body=formValue();saveInput();syncLot(id);$('prepare').disabled=true;setStep(2);$('runTitle').textContent='Registrando información…';$('runStatus').textContent='';$('generate').disabled=true;try{const r=await api('/api/lots/'+encodeURIComponent(id)+'/prepare-quick',body);jobs.set(r.run_id,r);progress[id]={stage:r.status==='succeeded'?'generated':r.status==='preparing'?'preparing':'prepared',run_id:r.run_id,changed:false};draw();if(token===generation){currentRun=r;renderRun();}watchRun(r.run_id);}catch(e){if(token===generation){setStep(1);message(e.message,true);}}finally{$('prepare').disabled=false;}});
async function watchRun(id){const old=jobs.get(id);try{const r=await api('/api/runs/'+id+'/status');jobs.set(id,r);if(detail?.snapshot.lot.lot_id===r.lot_id&&currentRun?.run_id===id){currentRun=r;if(currentStep===2)renderRun();}if(['preparing','prepared','queued','running','succeeded'].includes(r.status)){progress[r.lot_id]={...progress[r.lot_id],stage:r.status==='succeeded'&&r.validation_status==='valid'?'generated':r.status==='preparing'?'preparing':'prepared',run_id:id};draw();}if(['preparing','queued','running'].includes(r.status))setTimeout(()=>watchRun(id),500);else refreshProgress();}catch(e){if(old)message('No se pudo consultar el estado: '+e.message,true);}}
action('generate',async()=>{if(!currentRun)return;const id=currentRun.run_id;$('generate').disabled=true;const r=await api('/api/runs/'+id+'/start',{});jobs.set(id,r);if(currentRun?.run_id===id){currentRun=r;renderRun();}watchRun(id);});
$('back').onclick=()=>setStep(1);$('nextLot').onclick=closeLot;$('closeLot').onclick=closeLot;

// Entrada exacta: cada número refleja su deslizador y viceversa. Programar
// .value no dispara 'input', así que no hay bucles; updateHeight() respeta el
// campo que estás editando para no mover el cursor mientras escribes.
for(const [numId,rangeId] of [['floorsNumber','floors'],['floorHeightNumber','floorHeight'],['firstHeightNumber','firstHeight']]){
 const num=$(numId),range=$(rangeId);
 num.oninput=()=>{if(num.value==='')return;const v=+num.value;if(!Number.isFinite(v))return;range.value=v;updateHeight();saveInput();};
 num.onchange=()=>{const v=+num.value;if(num.value===''||!Number.isFinite(v)){updateHeight();return;}const c=Math.min(+range.max,Math.max(+range.min,v));num.value=c;range.value=c;updateHeight();saveInput();};
 num.onblur=updateHeight;
 num.onkeydown=e=>{if(e.key==='Enter'){e.preventDefault();e.stopPropagation();focusNext(numId);}};
}
const TAB_CHAIN=['floorsNumber','floorHeightNumber','firstDifferent','firstHeightNumber','styleGroup','notes','prepare'];
function focusNumber(id){const el=$(id);if(!el||el.closest('[hidden]'))return;el.focus();el.select();}
function focusNext(fromId){
 const visible=TAB_CHAIN.filter(id=>id==='styleGroup'||($(id)&&!$(id).closest('[hidden]')));
 const next=visible[visible.indexOf(fromId)+1];
 if(next==='styleGroup'){($('styles').querySelector('[aria-checked=true]')||$('styles').firstElementChild)?.focus();return;}
 if(!next){$('prepare').focus();return;}
 const el=$(next);el.focus();if(el.select)el.select();
}
// Atajos de teclado v2: bloque compacto QWERTY para evaluar sin mouse.
function ensureEditStep(){if(currentStep!==1&&detail)setStep(1);}
function isTyping(t){return !!t&&(t.tagName==='INPUT'||t.tagName==='TEXTAREA'||t.isContentEditable);}
function applyPhotoChoice(id,on){on?chosen.add(id):chosen.delete(id);$('photoCount').textContent=chosen.size+' seleccionadas · 2 por página';saveInput();draw();}
function toggleVisiblePhoto(index){
 if(!detail)return;
 const p=cameras[pageIndex*PHOTO_PAGE_SIZE+index];
 if(!p){message('No hay foto en esa posición; usa F para avanzar.');return;}
 applyPhotoChoice(p.id,!chosen.has(p.id));paintPhotos();
}
function pagePhotos(dir){
 if(!detail)return;
 const pages=Math.max(1,Math.ceil(cameras.length/PHOTO_PAGE_SIZE)),next=pageIndex+dir;
 if(next<0||next>=pages){message(dir>0?'Ya estás en la última página.':'Ya estás en la primera página.');return;}
 pageIndex=next;paintPhotos();
}
function nextUnevaluatedLot(){
 if(!features.length){message('El mapa todavía se está cargando.');return;}
 const currentId=detail?.snapshot.lot.lot_id,here=currentId&&featureById.has(currentId)?featureById.get(currentId).mid:xy(center);
 const fresh=features.filter(f=>!progress[f.id]?.stage);
 const pool=(fresh.length?fresh:features.filter(f=>progress[f.id]?.stage==='prepared')).filter(f=>f.id!==currentId);
 const target=(pool.length?pool:features.filter(f=>f.id!==currentId)).map(f=>[f,Math.hypot(f.mid[0]-here[0],f.mid[1]-here[1])]).sort((a,b)=>a[1]-b[1])[0]?.[0];
 if(!target){message('No quedan lotes sin paquete.');return;}
 if(!fresh.length)message('Sin lotes nuevos; retomando uno preparado sin generar.');
 if(!detail)message('Lote '+target.id);
 loadLot(target.id).then(()=>fit()).catch(e=>message(e.message,true));
}
function primaryAction(){
 if(!detail)return;
 if(currentStep===1){if(!$('prepare').disabled)$('prepare').click();}
 else if(!$('generate').hidden&&!$('generate').disabled)$('generate').click();
 else if(!$('nextLot').hidden)closeLot();
 else message('Espera a que el paquete esté listo.');
}
function shortcutToAction(k){
 if(STYLE_KEYS[k])return()=>pickStyle(STYLE_KEYS[k]);
 if({q:'floorsNumber',a:'floorHeightNumber',w:'firstHeightNumber'}[k])return()=>{ensureEditStep();const id={q:'floorsNumber',a:'floorHeightNumber',w:'firstHeightNumber'}[k];if(id==='firstHeightNumber'&&!$('firstDifferent').checked){$('firstDifferent').checked=true;updateHeight();saveInput();}focusNumber(id);};
 switch(k){
  case 's':return()=>{ensureEditStep();const c=$('firstDifferent');c.checked=!c.checked;updateHeight();saveInput();message(c.checked?'Primer piso diferente activado.':'Primer piso diferente desactivado.');};
  case 'd':return()=>pagePhotos(-1);
  case 'f':return()=>pagePhotos(1);
  case 'z':return()=>toggleVisiblePhoto(0);
  case 'x':return()=>toggleVisiblePhoto(1);
  case 'c':return()=>{if(detail&&!$('morePhotos').disabled)$('morePhotos').click();};
  case 'v':return()=>{ensureEditStep();$('notes').focus();};
  case 'g':
  case 'n':return nextUnevaluatedLot;
  case 'e':return()=>fit();
  case 'm':return()=>fit(true);
 }
 return null;
}
addEventListener('keydown',e=>{
 if(e.metaKey||e.ctrlKey||e.altKey)return;
 if($('lightbox').open||$('detailsDialog').open||$('keysDialog').open)return;
 if(isTyping(e.target))return;
 const raw=e.key;
 if(raw==='?'){e.preventDefault();$('keysDialog').showModal();return;}
 if(raw==='/'){e.preventDefault();$('search').focus();$('search').select();return;}
 if(raw==='Escape'){if(detail&&$('controlPanel')&&!$('controlPanel').hidden)closeLot();return;}
 if(raw==='Enter'){e.preventDefault();primaryAction();return;}
 if(raw==='Backspace'){if(detail&&currentStep===2){e.preventDefault();setStep(1);}return;}
 const k=raw.length===1?raw.toLowerCase():raw;
 const run=shortcutToAction(k);
 if(run){e.preventDefault();run();}
});
function renderKeysHelp(){
 const box=$('keysList');if(!box)return;box.replaceChildren();
 for(const group of SHORTCUT_GROUPS){
  const h=document.createElement('h3');h.textContent=group.title;box.append(h);
  const table=document.createElement('table');table.className='keysTable';
  for(const item of group.items){
   const row=document.createElement('tr'),key=document.createElement('td'),label=document.createElement('td');
   const kbd=document.createElement('kbd');kbd.className='key';kbd.textContent=item.key;key.append(kbd);
   label.textContent=item.label+(item.hint?' · '+item.hint:'');row.append(key,label);table.append(row);
  }
  box.append(table);
 }
}
renderKeysHelp();
for(const el of document.querySelectorAll('[data-key]'))el.addEventListener('click',()=>shortcutToAction(el.dataset.key)?.());
$('keysHelp').onclick=()=>$('keysDialog').showModal();
$('closeKeys').onclick=()=>$('keysDialog').close();
$('nextUnevaluated').onclick=nextUnevaluatedLot;
async function showRun(id){const r=await api('/api/runs/'+id);$('detailText').textContent=JSON.stringify({status:r.status,validation:r.validation,proposal:r.proposal,request:r.request,prompt:r.package?.prompt},null,2);$('export').hidden=!r.package||['preparing','queued','running'].includes(r.status);$('export').href='/api/runs/'+id+'/export';}
action('details',async()=>{if(!detail)return;$('detailsDialog').showModal();$('detailText').textContent='Cargando…';const d=await api('/api/lots/'+encodeURIComponent(detail.snapshot.lot.lot_id));$('history').replaceChildren();for(const r of d.runs){const b=document.createElement('button');b.textContent=r.created_at.slice(0,16)+' · '+r.status;b.onclick=()=>showRun(r.run_id).catch(e=>message(e.message,true));$('history').append(b);}if(currentRun)await showRun(currentRun.run_id);});$('closeDetails').onclick=()=>$('detailsDialog').close();
let featuresRevision=null;function buildFeatures(list){features=list.map(f=>{const coordinates=f.geometry.coordinates[0].map(xy),path=new Path2D();coordinates.forEach((p,i)=>i?path.lineTo(...p):path.moveTo(...p));path.closePath();const xs=coordinates.map(p=>p[0]),ys=coordinates.map(p=>p[1]),bounds=[Math.min(...xs),Math.min(...ys),Math.max(...xs),Math.max(...ys)];return {...f,coordinates,path,bounds,mid:[(bounds[0]+bounds[2])/2,(bounds[1]+bounds[3])/2]};});featureById=new Map(features.map(f=>[f.id,f]));}
async function refreshProgress(){try{progress=await api('/api/progress');for(const id of pending.keys())if(progress[id])progress[id].changed=true;try{const lots=await api('/api/lots');if(lots.revision!==featuresRevision){featuresRevision=lots.revision;buildFeatures(lots.features);}}catch{}draw();}catch{}}
$('searchForm').onsubmit=async e=>{e.preventDefault();await loadLot($('search').value.trim());fit();};$('all').onclick=()=>fit(true);$('fit').onclick=()=>fit();
resize();api('/api/lots').then(async data=>{featuresRevision=data.revision;buildFeatures(data.features);fit(true);await refreshProgress();const id=new URLSearchParams(location.search).get('lot');if(id){await loadLot(id);fit();}}).catch(e=>message(e.message,true));
setInterval(refreshProgress,5000);
