const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');

function harness({permission}={}){
  const elements=new Map();
  class Element {
    constructor(){this.value='';this.handlers={};this.classList={toggle(){}};this.hidden=false;this.disabled=false;}
    addEventListener(name,fn){(this.handlers[name]??=[]).push(fn);}
    setAttribute(){}
    dispatchEvent(event){for(const fn of this.handlers[event.type]||[]) fn(event);}
    focus(){}
    async click(){for(const fn of this.handlers.click||[]) await fn({type:'click'});}
  }
  for(const id of ['voice-record','voice-cancel','voice-label','voice-status','chat-input','chat-form','chat-new']) elements.set(id,new Element());
  const tracks=[{stopped:false,stop(){this.stopped=true;}}];
  const stream={getTracks:()=>tracks};
  const doc=new Element();doc.hidden=false;doc.getElementById=id=>elements.get(id);
  const window=new Element();window.isSecureContext=true;window.MediaRecorder=true;
  const pending=[];
  class Recorder extends Element{
    static isTypeSupported(){return true;}
    constructor(_,options){super();this.mimeType=options.mimeType;this.state='inactive';Recorder.last=this;}
    start(){this.state='recording';}
    stop(){this.state='inactive';this.dispatchEvent({type:'dataavailable',data:new Blob(['sound'])});this.dispatchEvent({type:'stop'});}
  }
  const context={document:doc,window,navigator:{mediaDevices:{getUserMedia:()=>permission||Promise.resolve(stream)}},
    CustomEvent:class extends Event{constructor(type,options){super(type);this.detail=options.detail;}},
    MediaRecorder:Recorder,Blob,AbortController,Event,performance:{now:()=>0},setInterval:()=>1,
    clearInterval(){},setTimeout:()=>1,clearTimeout(){},AbortSignal,
    fetch:async (path,options)=>{
      if(path.endsWith('/runtime')) return {ok:true,json:async()=>({available:true,max_seconds:30,max_bytes:2097152})};
      return new Promise(resolve=>pending.push({resolve,options}));
    }};
  vm.runInNewContext(fs.readFileSync('operator/web/voice.js','utf8'),context);
  return {el:id=>elements.get(id),tracks,doc,Recorder,pending,stream};
}
const flush=()=>new Promise(resolve=>setImmediate(resolve));
const result=(text='Jedź do B')=>({ok:true,json:async()=>({text})});

test('recording becomes an editable draft and never submits a command',async()=>{
  const h=harness();await flush();
  assert.equal(h.el('voice-record').disabled,false);
  let sent=0;h.el('chat-form').addEventListener('submit',()=>sent++);
  await h.el('voice-record').click();await h.el('voice-record').click();
  await flush();assert.equal(h.pending.length,1);assert(h.tracks[0].stopped);
  h.pending[0].resolve(result());await flush();
  assert.equal(h.el('chat-input').value,'Jedź do B');assert.equal(sent,0);
});

test('cancel discards a late result and releases microphone',async()=>{
  const h=harness();await flush();
  await h.el('voice-record').click();await h.el('voice-record').click();await flush();
  await h.el('voice-cancel').click();h.pending[0].resolve(result());await flush();
  assert.equal(h.el('chat-input').value,'');assert(h.tracks[0].stopped);
  assert(h.pending[0].options.signal.aborted);
});

test('typing during recognition preserves user text',async()=>{
  const h=harness();await flush();
  await h.el('voice-record').click();await h.el('voice-record').click();await flush();
  h.el('chat-input').value='STOP';h.pending[0].resolve(result());await flush();
  assert.equal(h.el('chat-input').value,'STOP');
  assert.match(h.el('voice-status').textContent,/Rozpoznano: Jedź do B/);
});

test('typed STOP cancels unfinished recognition without submitting its draft later',async()=>{
  const h=harness();await flush();
  await h.el('voice-record').click();await h.el('voice-record').click();await flush();
  h.el('chat-input').value='STOP';h.el('chat-form').dispatchEvent({type:'submit'});
  h.pending[0].resolve(result());await flush();
  assert.equal(h.el('chat-input').value,'STOP');assert(h.pending[0].options.signal.aborted);
});

test('leaving a tab before microphone permission returns releases the late stream',async()=>{
  let grant;const h=harness({permission:new Promise(resolve=>grant=resolve)});await flush();
  const opening=h.el('voice-record').click();await flush();
  h.doc.hidden=true;h.doc.dispatchEvent({type:'visibilitychange'});
  grant(h.stream);await opening;await flush();
  assert(h.tracks[0].stopped);assert.equal(h.pending.length,0);
});
