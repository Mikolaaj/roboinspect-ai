'use strict';
const $ = id => document.getElementById(id);
const labels = {inspecting:'Analiza obrazu',idle:'Gotowy',dispatching:'Wysyłanie celu',navigating:'W drodze',canceling:'Anulowanie',succeeded:'Dotarł do celu',canceled:'Anulowano',failed:'Błąd przejazdu',queued:'Przyjęto',running:'W drodze',uncertain:'Sprawdzanie zatrzymania',interrupted:'Przerwano po utracie kontaktu'};
let submitting = false;
let current = null;
let historyFingerprint = null;
function text(id,value){if($(id)) $(id).textContent = value;}
function buttons(){
  document.querySelectorAll('[data-goal],[data-inspect]').forEach(button=>{
    button.disabled = submitting || !current?.ready || current?.busy;
    button.classList.toggle('active', Boolean(current?.busy && current?.goal === button.dataset.goal));
  });
  const op = current?.operation_busy ? current.operation : null;
  const missionBusy = current?.busy && !op;
  document.querySelectorAll('[data-mapping]').forEach(button=>{
    const kind = button.dataset.mapping;
    const mayInterrupt = op?.kind === 'start' && !op.cancel_requested && ['reset','finish'].includes(kind);
    button.disabled = submitting || !current?.mapping_controls || current?.scenario !== 'normal' || missionBusy ||
      (op ? !mayInterrupt : (['save','finish'].includes(kind) && !current?.mapping_ready));
  });
  document.querySelectorAll('[data-warehouse]').forEach(button=>{
    button.disabled=submitting || !current?.mapping_controls || current?.scenario!=='normal' || current?.mode!=='navigation' || !current?.ready || current?.busy || Boolean(op);
    button.classList.toggle('selected',current?.warehouse?.mode===button.dataset.warehouse);
  });
  if($('cancel')) $('cancel').disabled = submitting || !current?.busy || current?.state === 'canceling' ||
      (op && (op.kind !== 'start' || op.cancel_requested));
}
function error(message){if($('error')){$('error').hidden = !message; $('error').textContent = message;}}
async function command(path,data){
  if(submitting) return;
  submitting = true;buttons();error('');
  try{
    const body = JSON.stringify(data);
    const saved = JSON.parse(sessionStorage.getItem('pending-command') || 'null');
    if(saved && (saved.path !== path || saved.body !== body) && path !== '/api/cancel')
      throw new Error('Poprzednie żądanie ma niepewny wynik. Ponów to samo polecenie lub anuluj aktywną misję.');
    const key = saved && saved.path === path && saved.body === body ? saved.key : crypto.randomUUID();
    if(path !== '/api/cancel') sessionStorage.setItem('pending-command',JSON.stringify({path,body,key}));
    const response = await fetch(path,{method:'POST',headers:{'Content-Type':'application/json','Idempotency-Key':key},body,signal:AbortSignal.timeout(7000)});
    sessionStorage.removeItem('pending-command');
    const result = await response.json();
    if(!response.ok) throw new Error(result.error || 'Polecenie nie powiodło się');
  }catch(exc){error(exc.message);}
  finally{submitting = false; await poll();}
}
document.querySelectorAll('[data-goal]').forEach(button=>button.addEventListener('click',()=>command('/api/goal',{goal:button.dataset.goal})));
document.querySelectorAll('[data-mapping]').forEach(button=>button.addEventListener('click',()=>command('/api/mapping/'+button.dataset.mapping,{})));
document.querySelectorAll('[data-warehouse]').forEach(button=>button.addEventListener('click',()=>command('/api/warehouse/'+button.dataset.warehouse,{})));
document.querySelectorAll('[data-inspect]').forEach(button=>button.addEventListener('click',()=>command('/api/inspect/'+button.dataset.inspect,{})));
if($('cancel')) $('cancel').addEventListener('click',()=>command('/api/cancel',{}));
async function poll(){
  try{
    const response = await fetch('/api/status',{cache:'no-store',signal:AbortSignal.timeout(2500)});
    if(!response.ok) throw new Error('Brak odpowiedzi');
    current = await response.json();
    document.dispatchEvent(new CustomEvent("roboinspect-status",{detail:current}));
    text('connection',current.transitioning ? 'Przełączanie trybu…' : current.mode === 'mapping' ? (current.mapping_ready ? 'SLAM · mapowanie aktywne' : 'SLAM · oczekiwanie na lidar') : current.ready ? 'Połączono · Nav2 gotowe' : 'Oczekiwanie na symulację / Nav2');
    $('connection-dot').classList.toggle('ready',current.ready || current.mapping_ready);
    text('rendering',current.rendering ? `Renderowanie: ${current.rendering.device} · fizyka i ROS: CPU` : 'Renderowanie: Brak danych');
    text('scenario',({normal:'HALA STANDARDOWA',blocked:'HALA Z BLOKADĄ',unreachable:'TEST: CEL B NIEDOSTĘPNY'})[current.scenario]);
    text('mission-state',current.mode === 'mapping' ? (current.mapping_ready ? 'Mapowanie SLAM' : 'Start SLAM') : current.busy || current.ready ? labels[current.state] || current.state : 'Oczekiwanie');
    text('goal',current.mode === 'mapping' ? 'Brak danych' : current.goal || 'Brak danych');
    text('distance',current.distance_m == null ? 'Brak danych' : `${current.distance_m.toFixed(1)} m`);
    text('speed',current.velocity ? `${current.velocity.linear.toFixed(2)} m/s` : 'Brak danych');
    text('position',current.map_position ? `${current.map_position.x.toFixed(1)}, ${current.map_position.y.toFixed(1)} m` : 'Brak danych');
    const op = current.operation;
    const opShown = op && (current.operation_busy || !current.mission || new Date(op.created_at) > new Date(current.mission.created_at));
    if(opShown) text('mission-state',current.operation_busy ? 'Operacja w toku' : ({succeeded:'Operacja zakończona',failed:'Błąd operacji',canceled:'Operacja anulowana',interrupted:'Operacja przerwana'}[op.status] || labels[op.status] || op.status));
    const warehouseOp=op?.kind?.startsWith('warehouse_');
    text('mapping-progress',op && !warehouseOp ? `${op.name} · ${op.message}` : 'Mapowaniem sterujesz przyciskami powyżej.');
    const warehouseLabel=({standard:'standardowe',clear:'bez przeszkód',random:'losowe'})[current.warehouse?.mode || 'standard'];
    text('warehouse-progress',warehouseOp ? `${op.name} · ${op.message}` : `Aktualne ustawienie: ${warehouseLabel}.`);
    text('message',opShown ? op.message : current.mode === 'mapping' ? 'SLAM aktywny. Użyj przycisków mapowania w panelu sterowania.' : current.message);
    if($('map-section')) {
      $('map-section').hidden = !current.map;
      if(current.map) {
        const m = current.map;
        const view = $('slam-map').parentElement;
        const mapZones=[...(current.inspection_zones || []),...(current.observation_zones || []).map(z=>({...z,observation:true}))];
        for(const zone of mapZones){
          let overlay = view.querySelector('[data-zone="'+zone.name+'"]');
          if(!overlay){overlay=document.createElement('span');overlay.className='inspection-zone'+(zone.observation?' observation-zone':'');overlay.dataset.zone=zone.name;overlay.setAttribute('aria-hidden','true');view.append(overlay);}
          overlay.textContent=zone.name;
          overlay.style.left=zone.x+'%';overlay.style.top=zone.y+'%';
          overlay.style.width=zone.width+'%';overlay.style.height=zone.height+'%';
          overlay.style.transform='translate(-50%,-50%) rotate('+zone.rotation+'rad)';
        }
        for(const overlay of view.querySelectorAll('[data-zone]')){
          if(!mapZones.some(zone=>zone.name===overlay.dataset.zone)) overlay.remove();
        }
        const marker = $('robot-marker');
        const point = current.robot_marker;
        marker.hidden = !point;
        if(point) {
          marker.style.left = `${100*point.x/m.width}%`;
          marker.style.top = `${100*point.y/m.height}%`;
          marker.style.transform = `translate(-50%,-50%) rotate(${-point.heading}rad)`;
          marker.title = `Robot: ${current.map_position.x.toFixed(2)}, ${current.map_position.y.toFixed(2)} m`;
        }
        text('map-status',`${current.mode === 'mapping' ? 'Tworzenie mapy' : 'Mapa nawigacyjna'} · ${m.width}×${m.height} · ${m.resolution.toFixed(2)} m/komórkę · znane: ${m.known_cells} · przeszkody: ${m.occupied_cells}`);
        if($('slam-map').dataset.version !== String(m.updates)) {
          $('slam-map').src = '/api/map.png?version='+m.updates;
          $('slam-map').dataset.version = String(m.updates);
        }
      }
    }
    const mission = current.mission;
    for(const name of ['fpv','follow','overhead']){
      const badge = document.querySelector(`[data-badge="${name}"]`);
      const wait = document.querySelector(`[data-wait="${name}"]`);
      if(!badge) continue;
      const frame = current.cameras[name];
      const live = frame && frame.age_s < 4 && (name!=='fpv' || badge.dataset.detectorReady==='true');
      badge.textContent = live ? 'NA ŻYWO' : frame ? 'OBRAZ NIEAKTUALNY' : 'OCZEKIWANIE';
      badge.classList.toggle('live',Boolean(live));
      badge.title = frame ? `Ostatnia odebrana klatka: ${frame.age_s.toFixed(1)} s temu` : 'Brak obrazu';
      wait.hidden = Boolean(live);
      wait.textContent = name==='fpv' && badge.dataset.detectorReady!=='true' ? 'Oczekiwanie na detekcję YOLO…' : frame ? 'Brak nowych klatek z kamery' : 'Oczekiwanie na obraz…';
    }
    if($('events')){
      $('events').replaceChildren();
      for(const event of [...current.events].reverse()){
        const li = document.createElement('li');const time = document.createElement('time');
        time.textContent = event.time;li.append(time,document.createTextNode(event.message));$('events').append(li);
      }
      if(!current.events.length){const li = document.createElement('li');li.textContent = 'Brak poleceń w tej sesji.';$('events').append(li);}
    }
  }catch(exc){
    if($('robot-marker')) $('robot-marker').hidden=true;
    current = null;document.dispatchEvent(new CustomEvent('roboinspect-status',{detail:null}));text('connection','Brak połączenia z kokpitem');$('connection-dot').classList.remove('ready');
    text('message','Uruchom kokpit lub sprawdź jego terminal.');
    document.querySelectorAll('[data-wait]').forEach(el=>{el.hidden=false;el.textContent='Brak połączenia';});
    document.querySelectorAll('[data-badge]').forEach(el=>{el.classList.remove('live');el.textContent='BRAK POŁĄCZENIA';});
  }
  buttons();
}
async function refresh(){if(!document.hidden) await poll(); setTimeout(refresh,1000);}
refresh();
// Reload disconnected MJPEG streams after a backend restart.
for(const image of document.querySelectorAll('.viewport img')){
  image.addEventListener('error',()=>setTimeout(()=>{if(!document.hidden && visibleStreams.has(image)) image.src=image.dataset.stream+'?retry='+Date.now();},2500));
}

async function history(){
  if(!$('missions')) return;
  if(document.hidden){setTimeout(history,3000);return;}
  try {
    const response = await fetch('/api/history?limit=30');
    if(!response.ok) throw new Error('history');
    const records = await response.json();
    const fingerprint = JSON.stringify(records);
    if(fingerprint !== historyFingerprint){
    const opened = new Set([...$('missions').querySelectorAll('details[open]')].map(el=>el.dataset.operation));
    historyFingerprint = fingerprint;
    $('missions').replaceChildren();
    for(const record of records){
      const li = document.createElement('li');
      const status = record.kind !== 'mission' ? ({running:'W toku',succeeded:'Zakończono',queued:'Przyjęto'}[record.status] || labels[record.status] || record.status) : labels[record.status] || record.status;
      const title = document.createElement('strong');
      title.textContent = `${new Date(record.created_at).toLocaleString('pl-PL')} · ${record.name} · ${status}`;
      li.append(title);
      if(record.kind !== 'mission') {
        const details = document.createElement('details');
        details.dataset.operation = record.id;
        details.open = opened.has(record.id);
        const summary = document.createElement('summary');
        summary.textContent = `Przebieg operacji (${record.details.length} zdarzeń)`;
        details.append(summary);
        for(const event of record.events || []){const line=document.createElement('div');line.textContent=`${new Date(event.time).toLocaleTimeString('pl-PL')} · ${event.message}`;details.append(line);}
        li.append(details);
      } else {const line=document.createElement('div');line.textContent=record.details.join(' → ');li.append(line);}
      if(record.saved_map){const saved=document.createElement('div'); saved.textContent='Zapisana wersja: '+record.saved_map.split('/').pop();li.append(saved);}
      $('missions').append(li);
    }
    if(!records.length) $('missions').textContent = 'Brak zapisanych przejazdów i operacji.';
    }
  } catch { historyFingerprint = null; $('missions').textContent = 'Nie udało się pobrać historii.'; }
  setTimeout(history,2000);
}
history();

// Chat inference and robot STOP are separate actions; STOP never waits for the model.
if($('chat-form')) {
  let sending=0, canceling=false, chatFingerprint='', oldest=null, generation=0;
  let panelReady=false;
  let controlEpoch=0, epochReady=false, normalRequest=null, pendingId=null, emergencySending=false;
  const rowsById=new Map();
  const stopText=value=>/^(stop|sotp|zatrzymaj(?:\s+(robota|wszystko|misje|przejazd))?)\s*[.!]*$/i.test(value.trim().normalize('NFD').replace(/[\u0300-\u036f]/g,''));
  function chatButtons(){
    document.dispatchEvent(new CustomEvent('roboinspect-model-busy',{detail:{busy:sending>0 || pendingId!==null}}));
    const emergency=stopText($('chat-input').value);
    $('chat-send').disabled=(!emergency && (sending>0 || pendingId!==null || !epochReady || !panelReady));
    $('chat-stop').hidden=pendingId===null;
    $('chat-stop').disabled=canceling;
    $('chat-new').disabled=!panelReady || sending>0 || pendingId!==null;
  }
  function renderChat(){
    const rows=[...rowsById.values()].sort((a,b)=>a.sequence-b.sequence);
    pendingId=rows.find(row=>row.status==='pending')?.id || null;
    chatButtons();
    const fingerprint=JSON.stringify(rows);
    if(fingerprint===chatFingerprint) return;
    const box=$('chat-messages');
    const atBottom=box.scrollHeight-box.scrollTop-box.clientHeight<90;
    const initial=box.childElementCount===0;
    chatFingerprint=fingerprint;box.replaceChildren();
    const welcome=document.createElement('div');welcome.className='chat-bubble assistant';
    welcome.textContent='Cześć! Podaj mi misję do wykonania albo zapytaj, jak obsługiwać robota, mapowanie i kamery. Napisz STOP, aby zatrzymać bieżące zadania.';
    box.append(welcome);
    for(const row of rows){
      for(const [role,content] of [['user',row.text],['assistant',row.reply]]){
        const bubble=document.createElement('div');bubble.className='chat-bubble '+role;
        if(role==='assistant' && row.status==='pending'){
          const waiting=document.createElement('div');waiting.className='typing-indicator';waiting.setAttribute('role','status');waiting.setAttribute('aria-label','Bielik analizuje wiadomość');
          waiting.textContent='Przygotowuję odpowiedź…';
          bubble.append(waiting);
        } else {
          const body=document.createElement('div');body.className='chat-answer';body.textContent=content;bubble.append(body);
        }
        const meta=document.createElement('small');meta.textContent=(role==='user'?'Ty':'Bielik')+' · '+new Date(row.created_at).toLocaleTimeString('pl-PL');bubble.append(meta);
        if(role==='assistant' && row.mission){const result=document.createElement('small');result.textContent='Nav2: '+(labels[row.mission.status] || row.mission.status)+' · '+row.mission.message;bubble.append(result);}
        if(role==='assistant' && row.tracking_error){const warning=document.createElement('small');warning.textContent='Zapis pomiarów odpowiedzi nie powiódł się';bubble.append(warning);}
        box.append(bubble);
      }
    }
    if(atBottom || initial) box.scrollTop=box.scrollHeight;
  }
  async function loadChat(older=false){
    if(!panelReady) return;
    const requestGeneration=generation;
    try{
      const [response,control]=await Promise.all([
        fetch('/api/chat?limit=100'+(older && oldest?'&before='+oldest:''),{signal:AbortSignal.timeout(4000)}),
        fetch('/api/chat/control',{signal:AbortSignal.timeout(4000)})
      ]);
      if(!response.ok || !control.ok) throw new Error('Nie udało się odczytać rozmowy');
      const rows=await response.json(),state=await control.json();
      if(requestGeneration!==generation) return;
      controlEpoch=Math.max(controlEpoch,state.control_epoch);epochReady=true;
      rows.forEach(row=>{
        const previous=rowsById.get(row.id);
        if(previous && previous.status!=='pending' && row.status==='pending') return;
        rowsById.set(row.id,row);
      });
      if(rows.length) oldest=Math.min(oldest || Infinity,...rows.map(row=>row.sequence));
      if(older || rowsById.size<=100) $('chat-older').hidden=rows.length<100;
      renderChat();
    }catch(exc){text('chat-error',exc.message);}
  }
  $('chat-input').addEventListener('input',chatButtons);
  $('chat-input').addEventListener('keydown',event=>{
    if(event.key==='Enter' && !event.shiftKey && !event.isComposing){event.preventDefault();$('chat-form').requestSubmit();}
  });
  $('chat-stop').addEventListener('click',async()=>{
    if(!pendingId || canceling) return;
    const id=pendingId;canceling=true;chatButtons();text('chat-error','');
    try{
      const response=await fetch('/api/chat/'+id+'/cancel',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}',signal:AbortSignal.timeout(7000)});
      const result=await response.json();if(!response.ok) throw new Error(result.error || 'Nie udało się zatrzymać odpowiedzi');
      rowsById.set(id,{...rowsById.get(id),...result});renderChat();
    }catch(exc){text('chat-error',exc.message);}
    finally{canceling=false;await loadChat();chatButtons();}
  });
  $('chat-new').addEventListener('click',async()=>{
    if(sending || pendingId) return;
    sending++;chatButtons();
    try{
      if(localStorage.getItem('roboinspect-chat-pending')) throw new Error('Najpierw ponów wiadomość z niepewnym wynikiem lub wyślij STOP.');
      const response=await fetch('/api/chat/new',{method:'POST',headers:{'Content-Type':'application/json','Idempotency-Key':crypto.randomUUID()},body:'{}',signal:AbortSignal.timeout(7000)});
      const result=await response.json();if(!response.ok) throw new Error(result.error || 'Nie udało się rozpocząć rozmowy');
      generation++;rowsById.clear();oldest=null;chatFingerprint='';$('chat-input').value='';text('chat-error','');
    }catch(exc){text('chat-error',exc.message);}
    finally{sending--;await loadChat();chatButtons();}
  });
  $('chat-older').addEventListener('click',()=>loadChat(true));

  $('chat-form').addEventListener('submit',async event=>{
    event.preventDefault();
    const value=$('chat-input').value.trim(),emergency=stopText(value);
    if(!value || (emergency && emergencySending) || (!emergency && (sending || pendingId || !epochReady || !panelReady))) return;
    const beforeEpoch=controlEpoch;
    if(emergency) emergencySending=true;
    if(emergency && normalRequest) normalRequest.abort();
    sending++;chatButtons();text('chat-error','');
    const storage=emergency?'roboinspect-stop-pending':'roboinspect-chat-pending';
    const controller=new AbortController();if(!emergency) normalRequest=controller;
    const timer=setTimeout(()=>controller.abort(),7000);
    try{
      const previous=JSON.parse(localStorage.getItem(storage) || 'null');
      if(previous && previous.text!==value) throw new Error('Ponów poprzednią wiadomość albo wyślij STOP.');
      const item=previous || {text:value,key:crypto.randomUUID(),epoch:controlEpoch};
      localStorage.setItem(storage,JSON.stringify(item));
      const response=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json','Idempotency-Key':item.key},body:JSON.stringify({text:value,control_epoch:item.epoch ?? controlEpoch}),signal:controller.signal});
      const result=await response.json();
      if(response.status>=500) throw new Error(result.error || 'Błąd serwera. Ponów tę samą wiadomość.');
      localStorage.removeItem(storage);
      if(!response.ok) throw new Error(result.error || 'Nie udało się wysłać wiadomości');
      if(emergency){controlEpoch=Math.max(controlEpoch,result.control_epoch || 0);localStorage.removeItem('roboinspect-chat-pending');text('chat-error','');}
      if($('chat-input').value.trim()===value) $('chat-input').value='';
    }catch(exc){if(!controller.signal.aborted) text('chat-error',exc.message);else if(emergency || (!emergencySending && controlEpoch===beforeEpoch && normalRequest===controller)) text('chat-error','Sprawdź stan rozmowy; w razie potrzeby ponów wiadomość lub wyślij STOP.');}
    finally{clearTimeout(timer);if(emergency) emergencySending=false;if(normalRequest===controller) normalRequest=null;sending--;await loadChat();chatButtons();}
  });
  async function runtimeChat(){
    try{
      const response=await fetch('/api/chat/runtime',{signal:AbortSignal.timeout(4000)}),info=await response.json();
      text('chat-runtime',info.available ? (info.loaded ? `Model załadowany · GPU: ${(info.gpu_memory_bytes/1024**3).toFixed(1)} GiB` : 'Model gotowy · zostanie załadowany przy wiadomości') : 'Asystent chwilowo niedostępny');
    }catch{text('chat-runtime','Brak połączenia z asystentem');}
  }
  const panelKey=crypto.randomUUID();
  async function startPanel(){
    try{
      const response=await fetch('/api/chat/session',{method:'POST',headers:{'Content-Type':'application/json','Idempotency-Key':panelKey},body:'{}',signal:AbortSignal.timeout(7000)});
      const result=await response.json();if(!response.ok)throw new Error(result.error || 'Nie udało się rozpocząć nowej rozmowy');
      generation++;rowsById.clear();oldest=null;chatFingerprint='';pendingId=null;
      localStorage.removeItem('roboinspect-chat-pending');
      localStorage.removeItem('roboinspect-stop-pending');
      $('chat-input').value='';panelReady=true;text('chat-error','');await loadChat();chatButtons();
    }catch(e){text('chat-error',e.message);setTimeout(startPanel,2000);}
  }
  renderChat();startPanel();
  chatButtons();runtimeChat();setInterval(()=>{if(!document.hidden) runtimeChat();},10000);loadChat();setInterval(()=>{if(!document.hidden) loadChat();},1500);
}

// Release video connections in background tabs and outside the mobile viewport.
const streamImages = [...document.querySelectorAll('.viewport img')];
const visibleStreams = new Set(streamImages);
for (const image of streamImages) image.dataset.stream = image.getAttribute('src');
function syncStreams(){
  for(const image of streamImages){
    const active = !document.hidden && visibleStreams.has(image);
    if(active && !image.getAttribute('src')) image.src = image.dataset.stream;
    if(!active && image.getAttribute('src')) image.removeAttribute('src');
  }
}
if('IntersectionObserver' in window){
  const observer = new IntersectionObserver(entries=>{
    for(const entry of entries){if(entry.isIntersecting) visibleStreams.add(entry.target);else visibleStreams.delete(entry.target);}
    syncStreams();
  },{rootMargin:'150px'});
  streamImages.forEach(image=>observer.observe(image));
}
document.addEventListener('visibilitychange',syncStreams);
syncStreams();
