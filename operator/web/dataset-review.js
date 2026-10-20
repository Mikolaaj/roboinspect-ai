'use strict';
const el=id=>document.getElementById(id);
const titles={clean:'Poprawny obraz',cracked:'Pęknięcia',dirty:'Zabrudzenie',occluded:'Zasłonięcie',missing:'Brak obrazu'};
const states={approved:'Zatwierdzona',rejected:'Odrzucona',pending_review:'Do przeglądu',needs_retake:'Wymaga powtórzenia'};
const parts={train:'Treningowa',validation:'Walidacyjna',test:'Testowa'};
let page=1,index=0,result={items:[],total:0,limit:20,page:1},busy=false,requestNumber=0;
function controls(){
  for(const id of ['review-prev','review-next','review-approve','review-reject','review-reset','filter-status','filter-split','filter-condition','review-condition','review-note'])el(id).disabled=busy;
  el('review-prev').disabled=busy||!result.total||(page===1&&index===0);
  el('review-next').disabled=busy||!result.total||(page-1)*result.limit+index+1>=result.total;
  el('review-approve').disabled=busy||!result.items[index]?.crop_sha256;
}
function render(){
 const row=result.items[index];el('review-card').hidden=!row;el('review-empty').hidden=!!row;
 el('review-progress').textContent=row?`Próbka ${(page-1)*result.limit+index+1} z ${result.total}`:'Brak próbek';
 if(row){
  el('review-title').textContent=`Sektor ${row.sector} · ${row.panel}`;
  el('review-status').textContent=states[row.review_status]||row.review_status;
  el('review-meta').textContent=`${new Date(row.created_at).toLocaleString('pl-PL')} · ${parts[row.split]} · ${row.collection_mode==='staged_static_robot_camera'?'Kontrolowana pozycja w symulatorze':'Inspekcja Nav2'} · ID: ${row.id.slice(0,8)}`;
  el('review-frame').src=`/api/dataset/${row.id}/frame.jpg`;
  el('review-crop').hidden=!row.crop_sha256;el('review-no-crop').hidden=!!row.crop_sha256;
  if(row.crop_sha256)el('review-crop').src=`/api/dataset/${row.id}/crop.jpg`;else el('review-crop').removeAttribute('src');
  el('review-condition').value=row.condition;el('review-note').value='';
  el('review-original').textContent=`Etykieta z symulacji: ${titles[row.original_condition||row.condition]}. Aktualna: ${titles[row.condition]}.`;
  const history=el('review-history');history.replaceChildren();
  for(const event of [...(row.review_history||[])].reverse()){
   const item=document.createElement('li');item.textContent=`${new Date(event.at).toLocaleString('pl-PL')} · ${states[event.decision]} · ${titles[event.condition]}${event.note?' · '+event.note:''}`;history.append(item);
  }
  if(!history.childNodes.length){const item=document.createElement('li');item.textContent='Brak zapisanych decyzji.';history.append(item);}
 }
 controls();
}
async function load(){
 const number=++requestNumber;busy=true;controls();el('review-error').textContent='';
 const query=new URLSearchParams({status:el('filter-status').value,split:el('filter-split').value,condition:el('filter-condition').value,page:String(page)});
 try{const response=await fetch('/api/dataset/samples?'+query,{cache:'no-store',signal:AbortSignal.timeout(10000)});if(!response.ok)throw Error('Nie udało się pobrać próbek.');const data=await response.json();if(number!==requestNumber)return;result=data;page=data.page;index=Math.min(index,Math.max(0,data.items.length-1));render();}
 catch(error){result={items:[],total:0,limit:20,page:1};index=0;render();el('review-error').textContent=error.message+' Odśwież stronę, aby spróbować ponownie.';}
 finally{if(number===requestNumber){busy=false;controls();}}
}
async function decide(decision){
 const row=result.items[index];if(!row||busy)return;busy=true;controls();el('review-error').textContent='';el('review-feedback').textContent='Zapisuję decyzję…';
 try{
  const response=await fetch(`/api/dataset/samples/${row.id}/review`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({decision,condition:el('review-condition').value,note:el('review-note').value,expected_revision:row.revision}),signal:AbortSignal.timeout(15000)});
  const data=await response.json();if(!response.ok)throw Error(typeof data.detail==='string'?data.detail:typeof data.error==='string'?data.error:'Nie zapisano decyzji. Odśwież próbki i spróbuj ponownie.');
  el('review-feedback').textContent=`${states[decision]} · ${row.panel}. Decyzja zapisana.`;
  // Stay at the same filtered position when the reviewed sample leaves the list.
  const leaves=(el('filter-status').value!=='all' && (el('filter-status').value==='pending'?decision!=='pending_review':decision!==el('filter-status').value))||(el('filter-condition').value!=='all'&&data.condition!==el('filter-condition').value);
  if(!leaves && index<result.items.length-1)index++;else if(!leaves && (page-1)*result.limit+index+1<result.total){page++;index=0;}
  await load();
 }catch(error){el('review-error').textContent=error.message;el('review-feedback').textContent='Decyzja nie została potwierdzona. Sprawdź widok przed ponowieniem.';}
 finally{busy=false;controls();}
}
for(const id of ['filter-status','filter-split','filter-condition'])el(id).addEventListener('change',()=>{page=1;index=0;el('review-feedback').textContent='';load();});
el('review-next').addEventListener('click',()=>{if(index<result.items.length-1){index++;render();}else{page++;index=0;load();}});
el('review-prev').addEventListener('click',()=>{if(index>0){index--;render();}else{page--;index=result.limit-1;load();}});
el('review-approve').addEventListener('click',()=>decide('approved'));
el('review-reject').addEventListener('click',()=>decide('rejected'));
el('review-reset').addEventListener('click',()=>decide('pending_review'));
load();
