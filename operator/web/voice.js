'use strict';
(() => {
  const button = document.getElementById('voice-record');
  if (!button) return;
  const cancel = document.getElementById('voice-cancel');
  const label = document.getElementById('voice-label');
  const status = document.getElementById('voice-status');
  const input = document.getElementById('chat-input');
  let phase = 'idle', stream = null, recorder = null, timer = null, request = null;
  let generation = 0, maxSeconds = 30, maxBytes = 2097152, ready = false;
  const supported = window.isSecureContext && navigator.mediaDevices?.getUserMedia && window.MediaRecorder;
  const types = ['audio/webm;codecs=opus','audio/ogg;codecs=opus','audio/mp4'];
  const mime = supported ? types.find(type=>MediaRecorder.isTypeSupported(type)) : null;
  function controls(){
    document.dispatchEvent(new CustomEvent('roboinspect-speech-busy',{detail:{busy:phase==='processing'}}));
    button.disabled = !ready || ['permission','processing'].includes(phase);
    button.classList.toggle('recording', phase === 'recording');
    button.setAttribute('aria-pressed', String(phase === 'recording'));
    label.textContent = phase === 'recording' ? 'Zakończ nagranie' : phase === 'processing' ? 'Whisper rozpoznaje…' : 'Mikrofon';
    button.setAttribute('aria-label',label.textContent);
    button.setAttribute('title',phase === 'idle' ? 'Nagraj wiadomość' : label.textContent);
    cancel.hidden = phase === 'idle';
    cancel.textContent = phase === 'processing' ? 'Anuluj rozpoznawanie' : 'Anuluj nagranie';
  }
  function release(){
    clearInterval(timer); timer = null;
    stream?.getTracks().forEach(track=>track.stop()); stream = null;
  }
  function discard(message='Nagranie anulowane. Możesz pisać w czacie.'){
    generation++;
    if(recorder && recorder.state !== 'inactive') recorder.stop();
    recorder = null; request?.abort(); request = null;
    release(); phase = 'idle'; status.textContent = message; controls();
  }
  async function transcribe(blob, version, original){
    if(version !== generation) return;
    release(); phase = 'processing'; controls();
    status.textContent = 'Lokalny Whisper rozpoznaje polską mowę. Nagranie pozostaje na tym komputerze.';
    const controller = new AbortController(); request = controller;
    const timeout = setTimeout(()=>controller.abort(),120000);
    try{
      const response = await fetch('/api/speech/transcribe', {method:'POST',headers:{'Content-Type':blob.type},body:blob,signal:controller.signal});
      const result = await response.json();
      if(version !== generation) return;
      if(!response.ok) throw new Error(result.error || 'Nie udało się rozpoznać mowy.');
      if(input.value !== original){
        status.textContent = 'Nie zmieniono wpisanego tekstu. Rozpoznano: '+result.text;
        return;
      }
      input.value = result.text;
      input.dispatchEvent(new Event('input',{bubbles:true}));
      input.focus();
      status.textContent = 'Rozpoznano mowę. Sprawdź tekst, potem naciśnij Enter lub Wyślij.'+(result.tracking_error?' Pomiary MLflow nie zostały zapisane.':'');
    }catch(error){
      if(version === generation) status.textContent = controller.signal.aborted ? 'Rozpoznawanie przerwane. Spróbuj krótszego nagrania.' : error.message;
    }finally{
      clearTimeout(timeout);
      if(version === generation){request=null;phase='idle';controls();}
    }
  }
  button.addEventListener('click',async()=>{
    if(phase === 'recording'){recorder?.stop();return;}
    if(phase !== 'idle' || !ready) return;
    const version = ++generation, original = input.value;
    phase='permission';status.textContent='Zezwól przeglądarce na użycie mikrofonu.';controls();
    try{
      const acquired = await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true},video:false});
      if(version !== generation){acquired.getTracks().forEach(track=>track.stop());return;}
      stream = acquired;
      const recording = new MediaRecorder(stream,{mimeType:mime});
      recorder = recording;
      const chunks = [];let bytes=0;
      recording.addEventListener('dataavailable',event=>{
        if(version !== generation || !event.data.size) return;
        bytes += event.data.size;
        if(bytes > maxBytes){discard('Nagranie jest za duże. Nagraj krótsze polecenie.');return;}
        chunks.push(event.data);
      });
      recording.addEventListener('error',()=>{if(version===generation) discard('Błąd mikrofonu. Spróbuj ponownie.');});
      recording.addEventListener('stop',()=>{
        if(version !== generation) return;
        recorder=null;
        transcribe(new Blob(chunks,{type:recording.mimeType}),version,original);
      });
      const started = performance.now();
      phase='recording';recording.start(250);controls();
      const tick=()=>{
        const seconds=Math.floor((performance.now()-started)/1000);
        status.textContent=`Nagrywanie ${seconds} / ${maxSeconds} s. Kliknij Zakończ nagranie.`;
        if(seconds>=maxSeconds-1 && recording.state==='recording') recording.stop();
      };
      tick();timer=setInterval(tick,250);
    }catch(error){
      if(version !== generation) return;
      release();phase='idle';controls();
      status.textContent=error.name === 'NotAllowedError' ? 'Brak zgody na mikrofon. Zezwól na niego w ustawieniach tej witryny lub użyj klawiatury.' : 'Mikrofon jest niedostępny. Sprawdź urządzenie i spróbuj ponownie.';
    }
  });
  cancel.addEventListener('click',()=>discard());
  // A typed command, including STOP, always takes precedence over unfinished speech.
  document.getElementById('chat-form').addEventListener('submit',()=>{if(phase!=='idle') discard('Użyto wiadomości tekstowej. Nagranie anulowane.');},{capture:true});
  document.getElementById('chat-new').addEventListener('click',()=>{if(phase!=='idle') discard();});
  document.addEventListener('visibilitychange',()=>{if(document.hidden && ['recording','permission'].includes(phase)) discard('Nagranie anulowane po opuszczeniu karty.');});
  window.addEventListener('pagehide',()=>discard());
  async function runtime(){
    if(!supported || !mime){status.textContent='Nagrywanie wymaga obsługiwanej przeglądarki oraz localhost lub HTTPS. Możesz użyć klawiatury.';controls();return;}
    try{
      const response=await fetch('/api/speech/runtime',{signal:AbortSignal.timeout(4000)});
      if(!response.ok) throw new Error();
      const info=await response.json();ready=info.available;maxSeconds=info.max_seconds;maxBytes=info.max_bytes;
      if(phase==='idle') status.textContent=ready ? 'Whisper lokalnie · polski · nagraj, sprawdź tekst i wyślij.' : 'Brak modelu Whisper. Uruchom bash scripts/setup_whisper.sh.';
    }catch{ready=false;if(phase==='idle') status.textContent='Brak połączenia z rozpoznawaniem mowy.';}
    controls();
  }
  runtime();setInterval(()=>{if(!document.hidden && !ready && phase==='idle') runtime();},10000);
})();
