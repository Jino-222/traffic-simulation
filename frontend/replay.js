export default function({data,parentElement}) {
 const q=s=>parentElement.querySelector(s);
 const ui=q('.replay-root'), canvases=[q('#left-canvas'),q('#right-canvas')];
 const contexts=canvases.map(c=>c.getContext('2d'));
 let alive=true,playing=false,now=data.start||0,last=0,raf=0,views=[],selected=null,busy=false,revision=0;
 const cache=[new Map(),new Map()], lastPoints=[[],[]];
 const names={N:'북',S:'남',E:'동',W:'서'};
 const setText=(s,v)=>{q(s).textContent=v};
 async function getJSON(url){const r=await fetch(url);if(!r.ok)throw Error('기록을 불러오지 못했습니다: '+r.status);return r.json()}
 function phase(v,t){let p=v.phases[0];for(const x of v.phases){if(x.time>t)break;p=x}return p}
 async function frames(i,t){
   const v=views[i], ci=v.chunks.findIndex((c,j)=>t>=c.start&&(j===v.chunks.length-1||t<v.chunks[j+1].start));
   const chunk=v.chunks[Math.max(0,ci<0?v.chunks.length-1:ci)];
   if(!cache[i].has(chunk.file)){
     cache[i].set(chunk.file,await getJSON(data.views[i].base+chunk.file));
     if(cache[i].size>4)cache[i].delete(cache[i].keys().next().value);
   }
   return cache[i].get(chunk.file);
 }
 function position(view,px,py,w,h){const zoom=Number(q('#zoom').value);return [w/2+(px-view.center[0])*w/zoom,h/2-(py-view.center[1])*w/zoom]}
 function paint(i,frame,next,t){
   const view=views[i],canvas=canvases[i],ctx=contexts[i];
   const rect=canvas.getBoundingClientRect(),w=Math.max(250,rect.width),h=350,dpr=window.devicePixelRatio||1;
   if(canvas.width!==Math.round(w*dpr)||canvas.height!==h*dpr){canvas.width=Math.round(w*dpr);canvas.height=h*dpr}
   ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,w,h);ctx.fillStyle='#edf2ed';ctx.fillRect(0,0,w,h);
   const scale=w/Number(q('#zoom').value),xy=(x,y)=>position(view,x,y,w,h);
   for(const lane of view.geometry.lanes){
     if(!lane.shape.length)continue;
     ctx.beginPath();lane.shape.forEach((pt,j)=>{const p=xy(...pt);j?ctx.lineTo(...p):ctx.moveTo(...p)});
     ctx.lineWidth=Math.max(1,lane.width*scale);
     ctx.strokeStyle=lane.kind==='crossing'?'#fafaf4':lane.pedestrian?'#d1d8c9':'#53635f';ctx.stroke();
     if(!lane.pedestrian && lane.kind!=='internal'){
       ctx.setLineDash([6,8]);ctx.strokeStyle='#b8c7bd';ctx.lineWidth=.5;ctx.stroke();ctx.setLineDash([]);
       if(lane.edge?.endsWith('_in')&&lane.shape.length>1){
         const end=lane.shape.at(-1),prev=lane.shape.at(-2),dx=end[0]-prev[0],dy=end[1]-prev[1],norm=Math.hypot(dx,dy)||1;
         const cx=end[0]-dx/norm,cy=end[1]-dy/norm,half=lane.width*.45;
         ctx.beginPath();ctx.moveTo(...xy(cx-dy/norm*half,cy+dx/norm*half));ctx.lineTo(...xy(cx+dy/norm*half,cy-dx/norm*half));
         ctx.strokeStyle='#fff';ctx.lineWidth=2;ctx.stroke();
       }
     }
   }
   const ph=phase(view,t), signalColors={r:'#b7424a',y:'#d8a92f',Y:'#d8a92f',g:'#21b18d',G:'#21b18d'};
   for(const [link,d] of Object.entries(view.signals.vehicle_links)){
     const lane=view.geometry.lanes.find(l=>l.id===(view.signals.lane_ids[d]||[])[0]);if(!lane)continue;
     const p=xy(...lane.shape[lane.shape.length-1]);ctx.fillStyle=signalColors[ph.state[Number(link)]]||'#555';
     ctx.beginPath();ctx.arc(p[0],p[1],5,0,Math.PI*2);ctx.fill();ctx.strokeStyle='#fff';ctx.lineWidth=1;ctx.stroke();
   }
   for(const [link,d] of Object.entries(view.signals.ped_links||{})){
     const lane=view.geometry.lanes.find(l=>l.kind==='crossing'&&view.signals.crossing_sides[l.edge]===d);if(!lane)continue;
     const p=xy(...lane.shape[0]);ctx.fillStyle=signalColors[ph.state[Number(link)]]||'#555';
     ctx.fillRect(p[0]-3,p[1]-3,6,6);ctx.strokeStyle='#fff';ctx.lineWidth=1;ctx.strokeRect(p[0]-3,p[1]-3,6,6);
   }
   const nextById=new Map((next?.[1]||[]).map(p=>[p[0],p])), ratio=next?Math.max(0,Math.min(1,(t-frame[0])/(next[0]-frame[0]))):0;
   const hits=[];
   for(const p of frame[1]){
     const agent=view.agents[p[0]],n=nextById.get(p[0]);
     const x=p[1]+(n?n[1]-p[1]:0)*ratio,y=p[2]+(n?n[2]-p[2]:0)*ratio;
     const pos=xy(x,y);const active=selected===agent.id;
     ctx.save();ctx.translate(...pos);
     if(agent.kind==='person'){ctx.fillStyle='#7b4b9e';ctx.beginPath();ctx.arc(0,0,Math.max(2.5,scale*.4),0,Math.PI*2);ctx.fill()}
     else{
       ctx.rotate((p[3]-90)*Math.PI/180);
       ctx.fillStyle=active?'#fff55d':agent.source==='extra'?'#eead54':'#69c6ba';
       const length=(agent.type==='car'?5:12)*scale;
       ctx.fillRect(-length,-Math.max(1,scale),length,Math.max(2,2*scale));
       if(agent.source==='extra'){ctx.strokeStyle='#5b3a12';ctx.lineWidth=1;ctx.strokeRect(-length,-Math.max(1,scale),length,Math.max(2,2*scale))}
       if(active){ctx.strokeStyle='#17342e';ctx.lineWidth=2;ctx.strokeRect(-length,-scale,length,2*scale)}
     }
     ctx.restore();hits.push({x:pos[0],y:pos[1],agent,p});
   }
   lastPoints[i]=hits;
   ctx.fillStyle='#243c35';ctx.font='12px sans-serif';
   ctx.fillText('북 ↑',10,20);ctx.fillText('실제 신호: '+Object.entries(view.signals.vehicle_links).map(([k,d])=>names[d]+ph.state[k]).join(' · '),10,h-12);
   setText(i===0?'#left-stats':'#right-stats','기록 시각 '+frame[0].toFixed(1)+'초 · 차량 '+frame[1].filter(p=>view.agents[p[0]].kind==='vehicle').length+'대 · 보행 '+frame[1].filter(p=>view.agents[p[0]].kind==='person').length+'명');
   if(selected){
     const point=hits.find(h=>h.agent.id===selected);
     setText(i===0?'#left-selected':'#right-selected',point?selected+' · '+(point.agent.source==='extra'?'입주 추가':'기존')+' · '+(names[point.agent.direction]||'보행')+' · '+(point.p[4]*3.6).toFixed(1)+'km/h · 예정 '+point.agent.scheduled+'초':'선택 차량: 이 시각 기록에 없음');
   }else setText(i===0?'#left-selected':'#right-selected','차량을 클릭하거나 아래 목록에서 선택하세요.');
 }
 function spark(){
   const c=q('#spark'),rect=c.getBoundingClientRect(),w=Math.max(250,rect.width),h=105,dpr=window.devicePixelRatio||1;
   c.width=Math.round(w*dpr);c.height=h*dpr;const ctx=c.getContext('2d');ctx.scale(dpr,dpr);ctx.clearRect(0,0,w,h);
   const max=Math.max(1,...data.series.flatMap(s=>s.map(p=>p[1]))),end=Number(q('#scrub').max);
   data.series.forEach((series,i)=>{ctx.beginPath();ctx.strokeStyle=i===0?'#c57930':'#087f79';ctx.lineWidth=1.5;
     series.forEach((p,j)=>{const x=30+p[0]/end*(w-40),y=80-p[1]/max*65;j?ctx.lineTo(x,y):ctx.moveTo(x,y)});ctx.stroke()});
   ctx.strokeStyle='#183b35';ctx.beginPath();const x=30+now/end*(w-40);ctx.moveTo(x,5);ctx.lineTo(x,85);ctx.stroke();
   ctx.fillStyle='#334e45';ctx.font='11px sans-serif';ctx.fillText('정지 차량 합계 · 최대 '+max+'대',30,12);ctx.fillText('0초',30,101);ctx.fillText(end.toFixed(0)+'초',w-60,101);
 }
 async function render(){
   if(!views.length||busy||!alive)return;busy=true;const t=now,rev=++revision;
   try{
     const records=await Promise.all([frames(0,t),frames(1,t)]);
     if(!alive)return;
     records.forEach((fs,i)=>{let n=fs.findIndex(f=>f[0]>t);if(n<0)n=fs.length;paint(i,fs[Math.max(0,n-1)],fs[n],t)});
     q('#scrub').value=t;setText('#time-label',t.toFixed(1)+'초');spark();
     setText('#replay-status','실제 SUMO 궤적 · 같은 시각 비교 · 중간 위치는 화면 보간');
   }catch(e){playing=false;setText('#replay-status',e.message)}
   finally{busy=false;if(alive&&now!==t)render()}
 }
 function loop(ms){if(!alive)return;if(playing&&!busy&&last){now=Math.min(Number(q('#scrub').max),now+(ms-last)/1000*Number(q('#speed').value));render();if(now>=Number(q('#scrub').max)){playing=false;setText('#play','재생')}}last=ms;raf=requestAnimationFrame(loop)}
 q('#play').onclick=()=>{playing=!playing;setText('#play',playing?'일시정지':'재생')};
 q('#scrub').oninput=()=>{playing=false;setText('#play','재생');now=Number(q('#scrub').value);render()};
 q('#zoom').onchange=()=>render();
 q('#jump-button').onclick=()=>{const target=Number(q('#jump').value);if(!Number.isFinite(target))return;playing=false;setText('#play','재생');now=Math.max(0,Math.min(Number(q('#scrub').max),target));render()};
 q('#vehicle').onchange=()=>{selected=q('#vehicle').value||null;render()};
 function jumpTo(t){playing=false;setText('#play','재생');now=Math.max(0,Math.min(Number(q('#scrub').max),t));q('#jump').value=now;render()}
 q('#begin').onclick=()=>jumpTo(0);
 q('#peak').onclick=()=>{
   const points=data.series.flatMap(s=>s.filter(p=>p[0]>=data.observation_start&&p[0]<data.observation_end));
   points.sort((a,b)=>b[1]-a[1]||a[0]-b[0]);if(points.length)jumpTo(points[0][0]);
 };
 q('#next-phase').onclick=()=>{
   const times=views.flatMap(v=>v.phases.map(p=>p.time)).filter(t=>t>now+.001);if(times.length)jumpTo(Math.min(...times));
 };
 canvases.forEach((canvas,i)=>canvas.onclick=e=>{
   const r=canvas.getBoundingClientRect(),x=e.clientX-r.left,y=e.clientY-r.top;
   const hit=lastPoints[i].map(h=>({...h,d:Math.hypot(h.x-x,h.y-y)})).sort((a,b)=>a.d-b.d)[0];
   if(hit&&hit.d<18){selected=hit.agent.id;q('#vehicle').value=selected;render()}
 });
 const resize=()=>render();window.addEventListener('resize',resize);
 Promise.all(data.views.map(v=>getJSON(v.base+'index.json'))).then(values=>{
   if(!alive)return;views=values;
   views.forEach(v=>{const c=v.geometry.junctions.find(j=>j.id==='C');v.center=c?[c.x,c.y]:[300,300]});
   const end=Math.min(...views.map(v=>v.chunks.at(-1).end));q('#scrub').max=end;q('#jump').max=end;now=Math.min(now,end);q('#jump').value=now;
   const vehicle=q('#vehicle');
   [...new Set(views.flatMap(v=>v.agents.filter(a=>a.kind==='vehicle'&&a.measured).map(a=>a.id)))].sort().forEach(id=>{const o=document.createElement('option');o.value=id;o.textContent=id;vehicle.appendChild(o)});
   setText('#left-title',data.views[0].title);setText('#right-title',data.views[1].title);
   render();raf=requestAnimationFrame(loop);
 }).catch(e=>setText('#replay-status',e.message));
 return ()=>{alive=false;cancelAnimationFrame(raf);window.removeEventListener('resize',resize)};
}

