'use strict';
(() => {
  const svg=document.getElementById('hangar-map');
  if(!svg) return;
  const status=document.getElementById('route-status');
  const namespace='http://www.w3.org/2000/svg';
  let layout=null, latest=null, obstacleFingerprint='', loading=false;
  function element(tag,attrs={},content){
    const node=document.createElementNS(namespace,tag);
    for(const [name,value] of Object.entries(attrs)) node.setAttribute(name,String(value));
    if(content!==undefined) node.textContent=content;
    return node;
  }
  function rectangle(box,attrs={}){
    const [x1,x2,y1,y2]=box;
    return element('rect',{x:x1,y:-y2,width:x2-x1,height:y2-y1,...attrs});
  }
  const observed=element('g',{'class':'observed-obstacles'});
  const routeLine=element('polyline',{'class':'route-line',fill:'none'});
  const goal=element('circle',{'class':'route-goal',r:.26});
  const robot=element('circle',{'class':'overview-robot',r:.28});
  const direction=element('path',{'class':'overview-direction',d:'M .25 -.14 L .55 0 L .25 .14 Z'});
  function build(data){
    svg.replaceChildren();
    svg.append(rectangle(data.bounds,{'class':'overview-floor',rx:.4}));
    const colors={A:'#9ac8e6',B:'#8bdebd',C:'#e6c68b'};
    for(const [name,sector] of Object.entries(data.sectors)){
      svg.append(rectangle(sector.bounds,{fill:colors[name],'fill-opacity':.1,rx:.2}));
      const [x1,x2]=sector.bounds;
      svg.append(element('text',{x:(x1+x2)/2,y:-2.8,'text-anchor':'middle','class':'overview-label',fill:colors[name]},name));
    }
    const [bx,by]=data.base;
    svg.append(rectangle([bx-2.5,bx+2.5,by-2,by+2],{'class':'overview-base',rx:.2}));
    svg.append(element('text',{x:bx,y:-by+.2,'text-anchor':'middle','class':'overview-label'},'BASE'));
    for(const box of data.obstacles) svg.append(rectangle(box,{'class':'overview-obstacle'}));
    for(const [name,zone] of Object.entries(data.zones)){
      const [x,y]=zone.pose,[w,h]=zone.size;
      svg.append(rectangle([x-w/2,x+w/2,y-h/2,y+h/2],{'class':'overview-zone',rx:.12}));
    }
    for(const [name,zone] of Object.entries(data.observation_zones || {})){
      const [x,y]=zone.pose,[w,h]=zone.size;
      svg.append(rectangle([x-w/2,x+w/2,y-h/2,y+h/2],{'class':'overview-observation',rx:.08}));
      svg.append(element('text',{x,y:-y+.12,'text-anchor':'middle','class':'observation-label'},name));
    }
    svg.append(observed,routeLine,goal,robot,direction);
  }
  function update(state){
    latest=state;
    if(state?.warehouse?.layout_id && layout?.layout_id!==state.warehouse.layout_id){if(!loading) load();}
    if(!layout) return;
    const route=state?.route;
    const points=route?.status==='live' ? route.points : [];
    routeLine.setAttribute('points',points.map(([x,y])=>`${x},${-y}`).join(' '));
    routeLine.style.display=points.length>1?'':'none';
    goal.style.display=route?.goal?'':'none';
    if(route?.goal){goal.setAttribute('cx',route.goal[0]);goal.setAttribute('cy',-route.goal[1]);}
    const position=state?.map_position;
    robot.style.display=position?'':'none';direction.style.display=position?'':'none';
    if(position){
      robot.setAttribute('cx',position.x);robot.setAttribute('cy',-position.y);
      direction.setAttribute('transform',`translate(${position.x} ${-position.y}) rotate(${-((state.robot_marker?.heading || 0)+(state.map?.origin?.[2] || 0))*180/Math.PI})`);
    }
    const boxes=state?.observed_obstacles || [];
    const fingerprint=JSON.stringify(boxes);
    if(fingerprint!==obstacleFingerprint){
      obstacleFingerprint=fingerprint;
      observed.replaceChildren(...boxes.map(box=>rectangle(box)));
    }
    const visual=state?.route_visual;
    status.textContent=!state ? 'Brak połączenia. Trasa i pozycja zostały ukryte.' :
      route?.status==='live' ? `Plan Nav2 · aktualizacja ${route.age_s.toFixed(1)} s temu · cel ${state.goal || ''}`+
        (visual?.ready && visual?.fresh ? ' · widoczny w kamerach' : ' · oczekiwanie na wizualizację kamer') :
      route?.goal ? 'Nav2 wyznacza lub odświeża trasę. Żółty punkt wskazuje cel.' :
      state.mode==='mapping' ? 'Mapowanie SLAM. Robot widoczny na planie, bez trasy Nav2.' : 'Robot gotowy. Wybierz cel w panelu sterowania.';
  }
  document.addEventListener('roboinspect-status',event=>update(event.detail));
  async function load(){
    loading=true;
    try{
      const response=await fetch('/api/hangar',{signal:AbortSignal.timeout(5000)});
      if(!response.ok) throw new Error();
      layout=await response.json();build(layout);update(latest);
    }catch{status.textContent='Nie udało się pobrać planu hangaru.';setTimeout(load,3000);}
    finally{loading=false;}
  }
  load();
})();
