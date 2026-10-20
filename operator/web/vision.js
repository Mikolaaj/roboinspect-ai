(() => {
  const byId=id=>document.getElementById(id);
  if(!byId('detection-history')) return;
  let reports=[],lastVersion='',busy=false;
  function renderReport(){
    const row=reports.find(r=>r.id===byId('inspection-select').value);
    byId('inspection-result').hidden=!row;
    if(!row) return;
    byId('inspection-meta').textContent=`Sektor ${row.sector} · ${row.panel} · ${new Date(row.created_at).toLocaleString('pl-PL')} · wykrycia: ${row.total} · ${row.model}`;
    const seg=row.segmentation;
    const samAvailable=Boolean(seg?.image_url);
    if(byId('inspection-view-controls'))byId('inspection-view-controls').hidden=!samAvailable;
    const showSam=samAvailable && byId('inspection-view')?.value==='sam';
    byId('inspection-image').src=showSam?seg.image_url:row.image_url;
    byId('inspection-image').alt=showSam?'Zapisana klatka z ramkami YOLO i maskami SAM':'Zapisana klatka z ramkami YOLO';
    if(byId('inspection-mask-download') && samAvailable)byId('inspection-mask-download').href=seg.data_url;
    const status={complete:'ukończona',partial:'częściowa',no_detections:'brak ramek YOLO',unavailable:'niedostępna',error:'błąd'};
    if(byId('inspection-segmentation'))byId('inspection-segmentation').textContent=seg?`${seg.model} · segmentacja: ${status[seg.status]||seg.status} · maski: ${seg.masks.length}/${row.total} · czas: ${seg.seconds.toFixed(2)} s`:'Starsza obserwacja bez segmentacji SAM.';
    if(row.dataset?.status==='collected')byId('inspection-meta').textContent+=` · etykieta symulacji: ${row.dataset.condition} · ${row.dataset.split} · wymaga przeglądu`;
    const list=byId('inspection-objects');list.replaceChildren();
    for(const [index,d] of row.detections.entries()){const li=document.createElement('li');const mask=seg?.masks.find(m=>m.detection_index===index+1);li.textContent=`${d.label} ${d.instance} · pewność YOLO ${(100*d.confidence).toFixed(1)}%`+(mask?` · maska ${mask.pixels.toLocaleString('pl-PL')} px (${(mask.image_fraction*100).toFixed(1)}% obrazu)`:'');if(mask && showSam)li.style.borderLeft=`3px solid rgb(${mask.color.join(',')})`;list.append(li);}
    if(!row.total){const li=document.createElement('li');li.textContent='Brak wykryć powyżej progu 30%.';list.append(li);}
  }
  byId('inspection-select').addEventListener('change',renderReport);
  byId('inspection-view')?.addEventListener('change',renderReport);
  async function refresh(){
    if(document.hidden||busy)return;
    busy=true;
    try{
      const response=await fetch('/api/vision',{signal:AbortSignal.timeout(2500)});
      if(!response.ok)throw new Error('Oczekiwanie na detektor YOLO11s');
      const s=await response.json();
      const badge=document.querySelector('[data-badge="fpv"]');
      if(badge)badge.dataset.detectorReady=String(Boolean(s.ready && Date.now()/1000-(s.at||0)<4));
      byId('vision-status').textContent=`${s.model} · ${s.device} · ${s.ready?'kamera aktywna':s.message} · ${s.sam?.available?'SAM przy inspekcji':'SAM niedostępny'}`;
      const r=await fetch('/api/inspections',{signal:AbortSignal.timeout(2500)});if(!r.ok)return;
      const rows=await r.json();const version=rows.map(x=>x.id).join(',');
      if(version!==lastVersion){lastVersion=version;reports=rows;const select=byId('inspection-select');const previous=select.value;select.replaceChildren();for(const row of reports){const option=document.createElement('option');option.value=row.id;option.textContent=`${row.sector} / ${row.panel} · ${new Date(row.created_at).toLocaleString('pl-PL')} · wykrycia: ${row.total}`;select.append(option);}if(reports.some(r=>r.id===previous))select.value=previous;renderReport();}
    }catch(e){const badge=document.querySelector('[data-badge="fpv"]');if(badge)badge.dataset.detectorReady='false';byId('vision-status').textContent=e.message;}finally{busy=false;}
  }
  setInterval(refresh,1800);refresh();
})();
