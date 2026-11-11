export default function({data: config,parentElement}) {
let alive=true,raf=0;const abort=new AbortController();
const $=id=>parentElement.querySelector('#'+id), canvas=$('canvas'),ctx=canvas.getContext('2d');
let geo,data,replays={},mode='map',scenario='after',frame=150,playing=false,lastTick=0,selected=null,W=900,H=590,DPR=1,screenCars=[];
const labels={before:'입주 전',after:'입주 후',adjusted:'신호 조정안'},modes={map:'SUMO FCD · 도로·차량',iso:'OSM + SUMO · 입체 모형',speed:'300–1,500초 · 도로 평균속도',wait:'300–1,500초 · 도로 누적 정지'};
const palette=['#e14b51','#f2a259','#e6cd6f','#65baa2','#147c85'];
function color(speed){let n=Math.max(0,Math.min(3.999,speed/60*4)),i=Math.floor(n),t=n-i;let a=palette[i].slice(1).match(/../g).map(x=>parseInt(x,16)),b=palette[i+1].slice(1).match(/../g).map(x=>parseInt(x,16));return `rgb(${a.map((v,j)=>Math.round(v+(b[j]-v)*t)).join(',')})`;}
const q=()=>+ $('zoom').value;
function project(x,y,z=0){let s=Math.min(W,H)/(q()*2)*.86;if(mode==='iso')return [W*.52+(x*.84-y*.54)*s,H*.57-(x*.34+y*.5+z*.9)*s];return [W*.52+x*s,H*.53-y*s];}
function path(points,fill,stroke,width=1,z=0){if(!points.length)return;ctx.beginPath();points.forEach((p,i)=>{let [x,y]=project(p[0],p[1],p[2]??z);i?ctx.lineTo(x,y):ctx.moveTo(x,y)});if(fill){ctx.closePath();ctx.fillStyle=fill;ctx.fill()}if(stroke){ctx.strokeStyle=stroke;ctx.lineWidth=width;ctx.stroke()}}
function visible(shape,pad=40){let r=q()*(mode==='iso'?1.5:1.4)+pad;return shape.some(p=>Math.abs(p[0])<r&&Math.abs(p[1])<r)}
function render(){if(!alive||!geo||!replays[scenario])return;let f=replays[scenario].frames[frame],r=data.results[scenario],s=Math.min(W,H)/(q()*2)*.86;
 ctx.clearRect(0,0,W,H);ctx.fillStyle=mode==='iso'?'#e9eff1':'#edf2f3';ctx.fillRect(0,0,W,H);ctx.lineCap='round';ctx.lineJoin='round';screenCars=[];
 // Floor grid makes the isometric camera readable without pretending to be satellite imagery.
 if(mode==='iso'){for(let x=-1000;x<=1000;x+=100){path([[x,-1000],[x,1000]],null,'#dce6e8',.6);path([[-1000,x],[1000,x]],null,'#dce6e8',.6)}}
 for(let p of geo.parks)if(visible(p))path(p,'#d0e4d1');
 if(mode!=='iso'&&$('buildings').checked)for(let b of geo.buildings)if(visible(b.shape))path(b.shape,'#d4dfe3','#bdcdd4',.5);
 const rs=geo.roads.filter(r=>!r.internal&&visible(r.shape));
 for(let r of rs)path(r.shape,null,mode==='map'||mode==='iso'?'#627987':'#bbc8cf',Math.max(.7,r.width*s));
 if(mode==='map'||mode==='iso')for(let p of geo.junctions)if(visible(p))path(p,'#627987');
 if((mode==='map'||mode==='iso')&&q()<420){ctx.setLineDash([4,5]);for(let l of geo.lanes)if(visible(l.shape)){let pts=l.shape.map((p,i,a)=>{let p0=a[Math.max(0,i-1)],p1=a[Math.min(a.length-1,i+1)],dx=p1[0]-p0[0],dy=p1[1]-p0[1],len=Math.hypot(dx,dy)||1;return[p[0]-dy/len*l.width/2,p[1]+dx/len*l.width/2]});path(pts,null,'#c9d6dc',.5)}ctx.setLineDash([])}
 if(mode==='speed'||mode==='wait'){let maxWait=Math.max(...Object.values(r.edges).map(e=>e.waiting/60));for(let road of rs){let e=r.edges[road.id];if(!e)continue;let col=mode==='speed'?color(e.speed_kmh):`hsl(${45-42*(e.waiting/60/maxWait)},82%,${82-34*(e.waiting/60/maxWait)}%)`;path(road.shape,null,col,Math.max(2.5,road.width*s))} $('legendMax').textContent=mode==='wait'?Math.round(maxWait):60;$('gradient').style.background=mode==='wait'?'linear-gradient(90deg,hsl(45,82%,82%),hsl(3,82%,48%))':'';}else{$('legendMax').textContent='60';$('gradient').style.background=''}
 if($('signals').checked&&q()<420&&(mode==='map'||mode==='iso'))for(let g of geo.signals){let st=f.tls[g.tls];if(!st||!visible(g.shape))continue;let c=st[1][g.index].toLowerCase();ctx.globalAlpha=.65;path(g.shape,null,({g:'#72e8b1',r:'#ff858d',y:'#f8df75'})[c]||'#aaa',.7);ctx.globalAlpha=1}
 if($('trails').checked){let traces=new Map;for(let j=Math.max(0,frame-(selected==null?5:25));j<=frame;j++)for(let v of replays[scenario].frames[j].v){if(selected!=null&&v[0]!==selected)continue;let ps=traces.get(v[0])||[];ps.push([v[1],v[2]]);traces.set(v[0],ps)}ctx.globalAlpha=.35;for(let ps of traces.values())path(ps,null,'#1a6f7c',selected==null?.7:2);ctx.globalAlpha=1}
 function drawCar(v){let [id,x,y,speed,angle]=v,typ=replays[scenario].vehicles[id].type,dim={car:[4.6,1.8,1.6],bus:[11.5,2.5,3.1],truck:[7.5,2.4,3]}[typ],ln=dim[0],wd=dim[1],a=angle*Math.PI/180,dx=Math.sin(a),dy=Math.cos(a),nx=-dy*wd/2,ny=dx*wd/2,ps=[[x+nx,y+ny],[x-nx,y-ny],[x-ln*dx-nx,y-ln*dy-ny],[x-ln*dx+nx,y-ln*dy+ny]],col=color(speed*3.6);
 if(!visible(ps))return;let h=mode==='iso'?dim[2]:0;if(h){for(let i=0;i<4;i++){let p=ps[i],q=ps[(i+1)%4];path([[...p,0],[...q,0],[...q,h],[...p,h]],col,'#365766',.3)}}path(ps,col,'#244c5c',.35,h);let pos=project(x-ln*dx/2,y-ln*dy/2,h);screenCars.push([id,...pos]);if(selected===id){ctx.strokeStyle='#0d524e';ctx.lineWidth=2;ctx.beginPath();ctx.arc(...pos,9,0,Math.PI*2);ctx.stroke()}}
 if(mode==='iso'){
 let objs=f.v.map(v=>({d:v[1]*.34+v[2]*.5,v}));if($('buildings').checked)for(let b of geo.buildings)if(visible(b.shape)){let p=b.shape.reduce((a,p)=>[a[0]+p[0]/b.shape.length,a[1]+p[1]/b.shape.length],[0,0]);objs.push({d:p[0]*.34+p[1]*.5,b})}objs.sort((a,b)=>b.d-a.d);
 for(let o of objs){if(o.v){drawCar(o.v);continue}let b=o.b,h=b.height,ps=b.shape;for(let i=0;i<ps.length-1;i++){let p=ps[i],q=ps[i+1];path([[...p,0],[...q,0],[...q,h],[...p,h]],p[0]<q[0]?'#bdcfd9':'#a5bfcd','#a2bac7',.35)}path(ps,'#dbe6eb','#a6bdc9',.4,h)}
 }else for(let v of f.v)drawCar(v);
 if(q()>450){ctx.font='bold 11px "Pretendard Variable","Malgun Gothic",sans-serif';for(let [name,p]of Object.entries(geo.entries)){let [x,y]=project(...p);ctx.fillStyle=name==='S'?'#e68156':'#168d83';ctx.beginPath();ctx.arc(x,y,5,0,Math.PI*2);ctx.fill();ctx.fillStyle='#365765';ctx.fillText(name==='S'?'S +600대/시 가정':name+' 유입',x+9,y-8)}}
 if(mode!=='iso'){let p=project(0,0);ctx.font='11px "Pretendard Variable","Malgun Gothic",sans-serif';ctx.fillStyle='#395768';ctx.fillText('범어네거리',p[0]+12,p[1]-14)}
 // Scale bar is valid only for the orthographic 2D map.
 if(mode!=='iso'){let len=q()<300?50:200;ctx.strokeStyle='#345967';ctx.lineWidth=2;ctx.beginPath();ctx.moveTo(24,H-112);ctx.lineTo(24+len*s,H-112);ctx.stroke();ctx.fillStyle='#476b79';ctx.font='10px sans-serif';ctx.fillText(len+' m',24,H-120);ctx.fillText('N ↑',W-44,36)}
 $('activeCount').textContent=f.v.length;$('stoppedCount').textContent=f.v.filter(v=>v[3]<.1).length;$('timeText').textContent=f.t+' s';$('time').value=frame;$('zoomValue').textContent=q()*2+' m';$('scenarioTag').textContent=labels[scenario];$('viewTag').textContent=modes[mode];$('legendTitle').textContent=mode==='wait'?'누적 정지 (차량·분)':mode==='speed'?'도로 평균속도 (km/h)':'차량 속도 (km/h)';$('mapCaption').textContent=mode==='iso'?'건물 높이: OSM 태그 또는 12 m 가정 · 별도 입체 렌더러':mode==='speed'||mode==='wait'?'도로색: 관측 구간 집계 · 차량색: 순간 속도 0–60km/h':'차량·연결선은 기록 시각의 상태입니다.';
 if(selected!=null){let v=f.v.find(v=>v[0]===selected),m=replays[scenario].vehicles[selected];$('selection').innerHTML=`<strong>${m.id}</strong><p>${{car:'승용차',bus:'버스 형상',truck:'트럭 형상'}[m.type]} · ${m.extra?'입주 추가 수요':'기존 수요'}<br>${v?(v[3]*3.6).toFixed(1)+' km/h':'현재 프레임에 없음'}</p>`;$('clearSelection').hidden=false}
}
function resize(){let r=canvas.getBoundingClientRect();W=r.width;H=r.height;DPR=Math.min(devicePixelRatio,2);canvas.width=Math.round(W*DPR);canvas.height=Math.round(H*DPR);ctx.setTransform(DPR,0,0,DPR,0,0);render()}
function clearSelection(){selected=null;$('selection').innerHTML='<strong>차량을 클릭해 보세요</strong><p>차량 ID, 현재 속도와 유입 종류를 확인합니다.</p>';$('clearSelection').hidden=true;render()}

function tick(now){
 if(!alive)return;
 if(playing&&now-lastTick>4000/(+$('rate').value)){
   frame=(frame+1)%replays[scenario].frames.length;lastTick=now;render();
 }
 raf=requestAnimationFrame(tick);
}
const modesButtons=()=>parentElement.querySelectorAll('[data-mode]');
const observer=new ResizeObserver(()=>{if(alive)resize()});
function setup(){
 modesButtons().forEach(b=>b.onclick=()=>{mode=b.dataset.mode;modesButtons().forEach(x=>x.classList.toggle('active',x===b));render()});
 $('scenario').onchange=()=>{scenario=$('scenario').value;clearSelection()};
 $('zoom').oninput=render;$('time').oninput=()=>{frame=+$('time').value;render()};
 for(let id of ['buildings','trails','signals'])$(id).onchange=render;
 $('overview').onclick=()=>{$('zoom').value=850;mode='map';modesButtons().forEach(x=>x.classList.toggle('active',x.dataset.mode==='map'));render()};
 $('play').onclick=()=>{playing=!playing;$('play').textContent=playing?'일시정지':'재생';lastTick=performance.now()};
 $('clearSelection').onclick=clearSelection;
 canvas.onclick=e=>{let b=canvas.getBoundingClientRect(),x=e.clientX-b.left,y=e.clientY-b.top;
 let v=screenCars.map(a=>[a[0],Math.hypot(a[1]-x,a[2]-y)]).sort((a,b)=>a[1]-b[1])[0];
 if(v&&v[1]<13){selected=v[0];$('trails').checked=true;render()}};
 observer.observe(canvas);resize();raf=requestAnimationFrame(tick);
 $('status').textContent='3개 시나리오 · 900프레임 · 저장 기록';$('play').disabled=false;
}
Promise.all(['geometry','results','before','after','adjusted'].map(async s=>{
 const r=await fetch(config.base+s+'.json',{signal:abort.signal});
 if(!r.ok)throw Error(s+' HTTP '+r.status);return r.json();
})).then(loaded=>{if(!alive)return;[geo,data,replays.before,replays.after,replays.adjusted]=loaded;setup()})
 .catch(e=>{if(alive&&e.name!=='AbortError'){$('status').textContent='기록을 불러올 수 없습니다: '+e.message;$('selection').textContent='앱의 static/daegu 자료와 정적 파일 설정을 확인하세요.'}});
return ()=>{alive=false;abort.abort();cancelAnimationFrame(raf);observer.disconnect()};
}
