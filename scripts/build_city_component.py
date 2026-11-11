"""Adapt the frozen renderer to a same-origin, lifecycle-safe Streamlit component."""
from pathlib import Path
import re
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'case_studies/daegu_beomeo/v1/web'
target=ROOT/'frontend'
html=(SOURCE/'index.html').read_text(encoding='utf-8')
html=html[html.index('<div class="workspace">'):html.index('<p class="replay-note">')]
html=html.replace('<button id="snapshot">화면 PNG 저장 ↓</button>','')
html='<div class="city-root"><div class="city-toolbar"><strong>범어네거리 · 궤적 탐색</strong><span id="status" role="status">실행 기록을 불러오고 있습니다.</span></div>'+html+'</div>'
(target/'city.html').write_text(html,encoding='utf-8')
js=(SOURCE/'app.js').read_text(encoding='utf-8')
js=js[:js.index('function tick(')]
js=js.replace("'use strict';",'export default function({data: config,parentElement}) {\nlet alive=true,raf=0;const abort=new AbortController();')
js=js.replace('document.getElementById(id)',"parentElement.querySelector('#'+id)")
js=js.replace('Math.max(1,...Object.values(r.edges).map(e=>e.waiting/60))','Math.max(1,...Object.values(data.results).flatMap(x=>Object.values(x.edges).map(e=>e.waiting/60)))')
js=js.replace('Math.sqrt(e.waiting/60/maxWait)','(e.waiting/60/maxWait)')
js=js.replace('linear-gradient(90deg,#fff4bf,#e84b37)','linear-gradient(90deg,hsl(45,82%,82%),hsl(3,82%,48%))')
js=js.replace('배경색: 전체 관측 구간 집계 · 차량: 슬라이더 시각의 순간값','도로색: 관측 구간 집계 · 차량색: 순간 속도 0–60km/h')
js=js.replace('"Malgun Gothic",sans-serif','"Pretendard Variable","Malgun Gothic",sans-serif')
js=js.replace("function render(){if(!geo", "function render(){if(!alive||!geo")
js+='''
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
'''
(target/'city.js').write_text(js,encoding='utf-8')
