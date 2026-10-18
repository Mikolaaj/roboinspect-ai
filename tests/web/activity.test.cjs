const {test}=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
function activity(){
  const box={hidden:false,attributes:{},setAttribute(name,value){this.attributes[name]=value;}};
  const label={textContent:''};const events=new EventTarget();
  events.getElementById=id=>id==='chat-activity'?box:id==='chat-activity-label'?label:null;
  vm.runInNewContext(fs.readFileSync('operator/web/activity.js','utf8'),{document:events});
  function send(name,busy){const event=new Event('roboinspect-'+name+'-busy');event.detail={busy};events.dispatchEvent(event);}
  return {box,label,send};
}
test('spinner starts for speech and stops after transcript or cancellation',()=>{
  const a=activity();assert(a.box.hidden);
  a.send('speech',true);assert(!a.box.hidden);assert.match(a.label.textContent,/Whisper/);
  a.send('speech',false);assert(a.box.hidden);assert.equal(a.box.attributes['aria-busy'],'false');
});
test('model response keeps spinner active until completion',()=>{
  const a=activity();a.send('model',true);assert(!a.box.hidden);assert.match(a.label.textContent,/Bielik/);
  a.send('model',false);assert(a.box.hidden);assert.equal(a.label.textContent,'');
});
test('overlapping speech and model operations cannot hide each other spinner',()=>{
  const a=activity();a.send('model',true);a.send('speech',true);
  a.send('model',false);assert(!a.box.hidden);assert.match(a.label.textContent,/Whisper/);
  a.send('model',true);a.send('speech',false);assert(!a.box.hidden);assert.match(a.label.textContent,/Bielik/);
  a.send('model',false);assert(a.box.hidden);
});
