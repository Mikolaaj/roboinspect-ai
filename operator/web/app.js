'use strict';
const $ = id => document.getElementById(id);
const labels = {idle:'Gotowy',dispatching:'Wysyłanie celu',navigating:'W drodze',canceling:'Anulowanie',succeeded:'Dotarł do celu',canceled:'Anulowano',failed:'Błąd przejazdu',queued:'Przyjęto',running:'W drodze',uncertain:'Sprawdzanie zatrzymania',interrupted:'Przerwano po utracie kontaktu'};
let submitting = false;
let current = null;
function text(id,value){if($(id)) $(id).textContent = value;}
function buttons(){
  document.querySelectorAll('[data-goal]').forEach(button=>{
    button.disabled = submitting || !current?.ready || current?.busy;
    button.classList.toggle('active', Boolean(current?.busy && current?.goal === button.dataset.goal));
  });
  if($('run-plan')) $('run-plan').disabled = submitting || !current?.ready || current?.busy;
  if($('cancel')) $('cancel').disabled = submitting || !current?.busy || current?.state === 'canceling';
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
if($('cancel')) $('cancel').addEventListener('click',()=>command('/api/cancel',{}));
async function poll(){
  try{
    const response = await fetch('/api/status',{cache:'no-store',signal:AbortSignal.timeout(2500)});
    if(!response.ok) throw new Error('Brak odpowiedzi');
    current = await response.json();
    text('connection',current.mode === 'mapping' ? (current.mapping_ready ? 'SLAM · mapowanie aktywne' : 'SLAM · oczekiwanie na lidar') : current.ready ? 'Połączono · Nav2 gotowe' : 'Oczekiwanie na symulację / Nav2');
    $('connection-dot').classList.toggle('ready',current.ready || current.mapping_ready);
    text('rendering',current.rendering ? `Renderowanie: ${current.rendering.device} · fizyka i ROS: CPU` : 'Renderowanie: —');
    text('scenario',({normal:'HALA STANDARDOWA',blocked:'HALA Z BLOKADĄ',unreachable:'TEST: CEL B NIEDOSTĘPNY'})[current.scenario]);
    text('mission-state',current.mode === 'mapping' ? (current.mapping_ready ? 'Mapowanie SLAM' : 'Start SLAM') : current.busy || current.ready ? labels[current.state] || current.state : 'Oczekiwanie');
    text('goal',current.mode === 'mapping' ? '—' : current.goal || '—');
    text('distance',current.distance_m == null ? '—' : `${current.distance_m.toFixed(1)} m`);
    text('speed',current.velocity ? `${current.velocity.linear.toFixed(2)} m/s` : '—');
    text('position',current.map_position ? `${current.map_position.x.toFixed(1)}, ${current.map_position.y.toFixed(1)} m` : '—');
    text('message',current.mode === 'mapping' ? 'Tryb SLAM: nawigacja sektorowa jest wyłączona. Uruchom przejazd mapujący w drugim terminalu.' : current.message);
    if($('map-section')) {
      $('map-section').hidden = !current.map;
      if(current.map) {
        const m = current.map;
        text('map-status',`${current.mode === 'mapping' ? 'Tworzenie mapy' : 'Mapa nawigacyjna'} · ${m.width}×${m.height} · ${m.resolution.toFixed(2)} m/komórkę · znane: ${m.known_cells} · przeszkody: ${m.occupied_cells}`);
        if($('slam-map').dataset.version !== String(m.updates)) {
          $('slam-map').src = '/api/map.png?version='+m.updates;
          $('slam-map').dataset.version = String(m.updates);
        }
      }
    }
    const mission = current.mission;
    text('plan-progress',mission ? `${mission.name} · krok ${mission.current_step == null ? '—' : mission.current_step+1}/${mission.steps.length} · ${labels[mission.status] || mission.status}` : '');
    for(const name of ['fpv','follow','overhead']){
      const badge = document.querySelector(`[data-badge="${name}"]`);
      const wait = document.querySelector(`[data-wait="${name}"]`);
      if(!badge) continue;
      const frame = current.cameras[name];
      const live = frame && frame.age_s < 4;
      badge.textContent = live ? '● NA ŻYWO' : frame ? 'OBRAZ NIEAKTUALNY' : 'OCZEKIWANIE';
      badge.classList.toggle('live',Boolean(live));
      badge.title = frame ? `Ostatnia odebrana klatka: ${frame.age_s.toFixed(1)} s temu` : 'Brak obrazu';
      wait.hidden = Boolean(live);
      wait.textContent = frame ? 'Brak nowych klatek z kamery' : 'Oczekiwanie na obraz…';
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
    current = null;text('connection','Brak połączenia z kokpitem');$('connection-dot').classList.remove('ready');
    text('message','Uruchom kokpit lub sprawdź jego terminal.');
    document.querySelectorAll('[data-wait]').forEach(el=>{el.hidden=false;el.textContent='Brak połączenia';});
    document.querySelectorAll('[data-badge]').forEach(el=>{el.classList.remove('live');el.textContent='BRAK POŁĄCZENIA';});
  }
  buttons();
}
async function refresh(){await poll(); setTimeout(refresh,700);}
refresh();
// Reload disconnected MJPEG streams after a backend restart.
for(const image of document.querySelectorAll('.viewport img')){
  image.addEventListener('error',()=>setTimeout(()=>{image.src=image.src.split('?')[0]+'?retry='+Date.now();},2500));
}

if($('run-plan')) $('run-plan').addEventListener('click',()=>{
  const targets = $('plan-targets').value.split(',').map(x=>x.trim().toUpperCase());
  if(!targets.length || targets.length > 20 || targets.some(t=>!['A','B','C','BASE','P1','P2','P3','P4','P5'].includes(t))) {
    error('Podaj 1–20 znanych celów oddzielonych przecinkami.'); return;
  }
  command('/api/missions',{name:$('plan-name').value,steps:targets.map(target=>({target}))});
});
async function history(){
  if(!$('missions')) return;
  try {
    const response = await fetch('/api/missions?limit=10');
    if(!response.ok) throw new Error('history');
    const records = await response.json();
    $('missions').replaceChildren();
    for(const record of records){
      const li = document.createElement('li');
      li.textContent = `${new Date(record.created_at).toLocaleString('pl-PL')} · ${record.name} · ${labels[record.status] || record.status} · ${record.steps.map(s=>s.target+' ('+s.status+')').join(' → ')}`;
      $('missions').append(li);
    }
    if(!records.length) $('missions').textContent = 'Brak zapisanych misji.';
  } catch { $('missions').textContent = 'Nie udało się pobrać historii.'; }
  setTimeout(history,2000);
}
history();
