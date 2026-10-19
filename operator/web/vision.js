(() => {
  const byId=id=>document.getElementById(id);
  if(!byId('detection-history')) return;
  let reports=[],lastVersion='',busy=false;
  function renderReport(){
    const row=reports.find(r=>r.id===byId('inspection-select').value);
    byId('inspection-result').hidden=!row;
    if(!row) return;
    byId('inspection-meta').textContent=`Sektor ${row.sector} · ${row.panel} · ${new Date(row.created_at).toLocaleString('pl-PL')} · wykrycia: ${row.total} · ${row.model}`;
    byId('inspection-image').src=row.image_url;
    const list=byId('inspection-objects');list.replaceChildren();
    for(const d of row.detections){const li=document.createElement('li');li.textContent=`${d.label} ${d.instance} · pewność ${(100*d.confidence).toFixed(1)}%`;list.append(li);}
    if(!row.total){const li=document.createElement('li');li.textContent='Brak wykryć powyżej progu 30%.';list.append(li);}
  }
  byId('inspection-select').addEventListener('change',renderReport);
  async function refresh(){
    if(document.hidden||busy)return;
    busy=true;
    try{
      const response=await fetch('/api/vision',{signal:AbortSignal.timeout(2500)});
      if(!response.ok)throw new Error('Oczekiwanie na detektor YOLO11s');
      const s=await response.json();
      const badge=document.querySelector('[data-badge="fpv"]');
      if(badge)badge.dataset.detectorReady=String(Boolean(s.ready && Date.now()/1000-(s.at||0)<4));
      byId('vision-status').textContent=`${s.model} · ${s.device} · ${s.ready?'kamera aktywna':s.message}`;
      const r=await fetch('/api/inspections',{signal:AbortSignal.timeout(2500)});if(!r.ok)return;
      const rows=await r.json();const version=rows.map(x=>x.id).join(',');
      if(version!==lastVersion){lastVersion=version;reports=rows;const select=byId('inspection-select');const previous=select.value;select.replaceChildren();for(const row of reports){const option=document.createElement('option');option.value=row.id;option.textContent=`${row.sector} / ${row.panel} · ${new Date(row.created_at).toLocaleString('pl-PL')} · wykrycia: ${row.total}`;select.append(option);}if(reports.some(r=>r.id===previous))select.value=previous;renderReport();}
    }catch(e){const badge=document.querySelector('[data-badge="fpv"]');if(badge)badge.dataset.detectorReady='false';byId('vision-status').textContent=e.message;}finally{busy=false;}
  }
  setInterval(refresh,1800);refresh();
})();
