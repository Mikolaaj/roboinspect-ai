'use strict';
(() => {
  const box=document.getElementById('chat-activity');
  const label=document.getElementById('chat-activity-label');
  if(!box || !label) return;
  let speech=false, model=false;
  function render(){
    box.hidden=!speech && !model;
    label.textContent=speech ? 'Whisper rozpoznaje nagranie…' : model ? 'Bielik przygotowuje odpowiedź…' : '';
    box.setAttribute('aria-busy',String(speech || model));
  }
  document.addEventListener('roboinspect-speech-busy',event=>{speech=Boolean(event.detail.busy);render();});
  document.addEventListener('roboinspect-model-busy',event=>{model=Boolean(event.detail.busy);render();});
  render();
})();
