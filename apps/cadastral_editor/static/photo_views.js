'use strict';
// Clean images are cached; extrusion height only changes this vector overlay.
const photoViews = new Map();
let activePhotoId = null, lightboxPhoto = null, overlayFrame = null, saveViewsTimer = null;

function clearPhotoViews() {
    clearTimeout(saveViewsTimer);
    photoViews.clear();
    activePhotoId = null;
    lightboxPhoto = null;
    if ($('lightbox').open) $('lightbox').close();
    $('photos').replaceChildren();
}

function updateHeight() {
    const height=Number($('height').value);
    if (!Number.isFinite(height) || height<1 || height>150) return;
    if (overlayFrame !== null) cancelAnimationFrame(overlayFrame);
    overlayFrame=requestAnimationFrame(()=>{
        overlayFrame=null;
        for (const v of photoViews.values()) paintPrism(v.overlay,v.photo.projection,height);
        if (lightboxPhoto && $('lightbox').open) paintPrism($('lightboxOverlay'),lightboxPhoto.projection,height);
    });
    scheduleSaveViews();
}

function scheduleSaveViews() {
    clearTimeout(saveViewsTimer);
    if (!detail) return;
    const height=Number($('height').value);
    if (!Number.isFinite(height) || height<1 || height>150) return;
    const id=detail.lot_id, revision=detail.geometry_revision;
    const body={geometry_revision:revision,photo_ids:[...photoViews.keys()],reference_height_m:height};
    saveViewsTimer=setTimeout(async()=>{
        try { await api('/api/lots/'+encodeURIComponent(id)+'/view-settings',body); }
        catch(e) { if(detail?.lot_id===id) message('No se guardaron las vistas: '+e.message,true); }
    },700);
}

function focusPhoto(pid) {
    const v=photoViews.get(pid);
    if (!v) return;
    activePhotoId=pid;
    for (const other of photoViews.values()) other.card.classList.toggle('active-photo',other===v);
    v.card.scrollIntoView({behavior:'smooth',block:'nearest'});
    draw();
}

function photoCard(p) {
    if (photoViews.has(p.id)) return;
    const number=photoViews.size+1;
    const card=document.createElement('div');card.className='photo';card.dataset.camera=p.id;
    const frame=document.createElement('div');frame.className='photo-frame';
    const img=document.createElement('img');img.alt='Foto '+number+' · '+p.id;
    // Eager fetch for explicitly selected views, even if controls push them below the fold.
    img.decoding='async';
    img.src=`/api/photos/${encodeURIComponent(p.id)}?lot_id=${encodeURIComponent(detail.lot_id)}&revision=${detail.revision}&clean=true&projection=${p.projection.version}`;
    const overlay=document.createElement('canvas');overlay.width=p.projection.width;overlay.height=p.projection.height;
    const status=document.createElement('p');status.className='muted';status.textContent='Cargando foto…';
    img.onload=()=>{status.textContent='Foto cargada · altura interactiva';};
    img.onerror=()=>{status.textContent='No se pudo cargar. Pulsa Actualizar para reintentar.';};
    frame.append(img,overlay);
    frame.onclick=()=>{
        activePhotoId=p.id;lightboxPhoto=p;
        $('lightbox').querySelector('img').src=img.src;
        const large=$('lightboxOverlay');large.width=p.projection.width;large.height=p.projection.height;
        paintPrism(large,p.projection,Number($('height').value));$('lightbox').showModal();draw();
    };
    const text=document.createElement('p');text.textContent=`● ${number} · ${p.id} · ${p.date||'fecha desconocida'} · ${p.distance_m??'?'} m`;
    text.title=`Cámara: ${p.camera_lonlat.join(', ')} (lon, lat)`;
    text.style.color='#ffda55';text.onclick=()=>focusPhoto(p.id);
    card.append(text,frame,status);$('photos').append(card);
    photoViews.set(p.id,{photo:p,number,card,image:img,overlay});
    paintPrism(overlay,p.projection,Number($('height').value));
}

function drawCameraMarkers() {
    for (const [pid,v] of photoViews) {
        const [x,y]=screen(v.photo.camera_lonlat), active=pid===activePhotoId;
        ctx.beginPath();ctx.arc(x,y,active?10:7,0,2*Math.PI);
        ctx.fillStyle='#ffdc45';ctx.fill();ctx.strokeStyle=active?'#fff':'#493a04';ctx.lineWidth=2;ctx.stroke();
        ctx.font='bold 12px system-ui';ctx.lineWidth=3;ctx.strokeStyle='#17232c';ctx.fillStyle='#ffed9f';
        ctx.strokeText(v.number,x+11,y+4);ctx.fillText(v.number,x+11,y+4);
    }
}

function hitCamera(x,y) {
    return [...photoViews].find(([,v])=>{const p=screen(v.photo.camera_lonlat);return Math.hypot(p[0]-x,p[1]-y)<11;})?.[0];
}

function fitPhotoCameras() {
    if (!detail) return;
    const features=state.features.filter(f=>f.id===detail.lot_id);
    for (const v of photoViews.values()) features.push({geometry:{type:'Polygon',coordinates:[[v.photo.camera_lonlat]]}});
    fit(features);
}
