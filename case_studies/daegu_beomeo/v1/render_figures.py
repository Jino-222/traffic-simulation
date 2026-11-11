"""Scientific figures and video, rendered only from recorded SUMO outputs."""
from pathlib import Path
import json,math,os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager,colors,cm
from matplotlib.collections import LineCollection,PatchCollection
from matplotlib.patches import Polygon,Rectangle,Circle
from mpl_toolkits.mplot3d.art3d import Poly3DCollection,Line3DCollection

ROOT=Path(__file__).resolve().parent
FONT=Path('C:/Windows/Fonts/malgun.ttf')
if FONT.exists(): font_manager.fontManager.addfont(str(FONT)); plt.rcParams['font.family']='Malgun Gothic'
plt.rcParams.update({'axes.unicode_minus':False,'font.size':10,'axes.titleweight':'bold','axes.labelcolor':'#516376','text.color':'#142d42','axes.spines.top':False,'axes.spines.right':False,'axes.edgecolor':'#c7d2dc','figure.facecolor':'#f7f9fb','axes.facecolor':'#f7f9fb','savefig.facecolor':'#f7f9fb','grid.color':'#dfe5eb'})
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
G=read(ROOT/'web/geometry.json'); D=read(ROOT/'web/results.json'); R=D['results']; META=D['experiment']
SC=['before','after','adjusted']; LABEL=['입주 전','입주 후','신호 조정안']; COL=['#537caa','#ed8258','#16a394']
REPLAY={s:read(ROOT/f'web/{s}.json') for s in SC}
CM=colors.LinearSegmentedColormap.from_list('speed',['#e14b51','#f2a259','#e6cd6f','#65baa2','#147c85'])
NORM=colors.Normalize(0,60)

def save(fig,name):
    fig.savefig(ROOT/f'figures/{name}.png',dpi=190,bbox_inches='tight')
    fig.savefig(ROOT/f'figures/{name}.pdf',bbox_inches='tight')
    plt.close(fig); print(name,flush=True)
def foot(fig,text='OSM 실제 도로 형태 · 교통량/신호는 가정 · 현장 적용/공식 LOS 평가 불가'):
    fig.text(.035,.025,text+'   |   © OpenStreetMap contributors · ODbL 1.0',fontsize=8,color='#687b8c')
def header(fig,n,title,sub):
    fig.text(.035,.965,f'{n}  /  DAEGU TRAFFIC LAB',color='#168d83',fontsize=11,fontweight='bold',va='top')
    fig.text(.035,.92,title,fontsize=23,fontweight='bold',va='top')
    fig.text(.035,.864,sub,fontsize=10,color='#596f82',va='top')
def within(shape,bounds,pad=40):
    a=np.asarray(shape)
    return len(a)>1 and a[:,0].max()>bounds[0]-pad and a[:,0].min()<bounds[1]+pad and a[:,1].max()>bounds[2]-pad and a[:,1].min()<bounds[3]+pad
def base(ax,bounds=(-850,850,-850,850),detail=False):
    ax.set(xlim=bounds[:2],ylim=bounds[2:],aspect='equal');ax.set_axis_off()
    ax.add_patch(Rectangle((bounds[0],bounds[2]),bounds[1]-bounds[0],bounds[3]-bounds[2],color='#edf1f3',zorder=-4))
    parks=[Polygon(p) for p in G['parks'] if within(p,bounds)]
    if parks: ax.add_collection(PatchCollection(parks,facecolor='#cde2c9',edgecolor='none',zorder=-3))
    buildings=[Polygon(b['shape']) for b in G['buildings'] if within(b['shape'],bounds)]
    ax.add_collection(PatchCollection(buildings,facecolor='#d3dde3',edgecolor='#b7c8d2',linewidth=.3,zorder=-2))
    # Convert widths in metres to points after the figure's axes placement is set.
    scale=ax.get_position().width*ax.figure.get_figwidth()*72/(bounds[1]-bounds[0])
    rs=[r for r in G['roads'] if within(r['shape'],bounds) and not r['internal']]
    ax.add_collection(LineCollection([r['shape'] for r in rs],linewidths=[max(.5,r['width']*scale) for r in rs],colors='#6d7a84' if detail else '#a6b5be',zorder=-1,capstyle='round'))
    if detail:
        ax.add_collection(PatchCollection([Polygon(p) for p in G['junctions'] if within(p,bounds)],facecolor='#6d7a84',edgecolor='none',zorder=-.5))
        lanes=[l for l in G['lanes'] if within(l['shape'],bounds)]
        # Lane edge offsets, using local normals; a rendering aid, not surveyed road markings.
        outlines=[]
        for l in lanes:
            a=np.asarray(l['shape']); delta=np.gradient(a,axis=0); lens=np.linalg.norm(delta,axis=1); lens[lens==0]=1
            normal=np.column_stack((-delta[:,1],delta[:,0]))/lens[:,None]
            outlines.append(a+normal*l['width']/2)
        ax.add_collection(LineCollection(outlines,linewidths=.45,colors='#e6ecef',linestyles=(0,(4,4)),zorder=0))
    return scale
def scalebar(ax,bounds,length):
    x=bounds[0]+(bounds[1]-bounds[0])*.07; y=bounds[2]+(bounds[3]-bounds[2])*.07
    ax.plot([x,x+length],[y,y],color='#243f51',lw=2,zorder=10); ax.text(x,y+(bounds[3]-bounds[2])*.018,f'{length} m',fontsize=8)
    ax.annotate('N',xy=(bounds[1]-(bounds[1]-bounds[0])*.07,bounds[3]-(bounds[3]-bounds[2])*.08),xytext=(bounds[1]-(bounds[1]-bounds[0])*.07,bounds[3]-(bounds[3]-bounds[2])*.18),arrowprops={'arrowstyle':'-|>','color':'#314c61'},ha='center',fontsize=9)
def vehicles(ax,scenario,frame,bounds):
    f=REPLAY[scenario]['frames'][frame]; patches=[]; fc=[]
    for ident,x,y,speed,angle in f['v']:
        if not bounds[0]-15<x<bounds[1]+15 or not bounds[2]-15<y<bounds[3]+15: continue
        typ=REPLAY[scenario]['vehicles'][ident]['type']; ln,wd={'car':(4.6,1.8),'bus':(11.5,2.5),'truck':(7.5,2.4)}[typ]
        theta=math.radians(angle); d=np.array([math.sin(theta),math.cos(theta)]); side=np.array([-d[1],d[0]])*wd/2; front=np.array([x,y]); back=front-ln*d
        patches.append(Polygon([front+side,front-side,back-side,back+side]));fc.append(CM(NORM(speed*3.6)))
    artist=PatchCollection(patches,facecolors=fc,edgecolors='#223e4c',linewidths=.3,zorder=5);ax.add_collection(artist)
    return artist
def signal(ax,scenario,frame,bounds):
    state=REPLAY[scenario]['frames'][frame]['tls']; lines=[]; cols=[]
    for sig in G['signals']:
        if sig['tls'] not in state or not within(sig['shape'],bounds):continue
        char=state[sig['tls']][1][sig['index']].lower(); lines.append(sig['shape']);cols.append({'g':'#58ce96','r':'#ed7378','y':'#f8ce56'}.get(char,'#999'))
    art=LineCollection(lines,colors=cols,linewidths=.6,alpha=.65,zorder=3);ax.add_collection(art);return art

def atlas():
    fig=plt.figure(figsize=(14,10));header(fig,'01','범어네거리, 도로망을 실험 공간으로','OSM 도로·건물 형상에 합성 교통량을 주입한 재현 가능한 시나리오')
    ax=fig.add_axes([.035,.1,.61,.72]);b=(-850,850,-850,850);base(ax,b)
    for a,p in G['entries'].items():
        ax.scatter(*p,s=80,c='#ed8258' if a=='S' else '#168d83',edgecolors='white',zorder=7)
        ax.annotate(f'{a} 유입',p,xytext=(9,8),textcoords='offset points',fontsize=10,fontweight='bold')
    ax.scatter(0,0,s=140,facecolors='none',edgecolors='#168d83',linewidths=2,zorder=7);ax.annotate('범어네거리',(0,0),xytext=(15,25),textcoords='offset points',weight='bold')
    ax.text(240,-70,'달구벌대로',fontsize=10);ax.text(95,350,'동대구로',rotation=85,fontsize=10);scalebar(ax,b,200)
    x=.69
    blocks=[('01  실제 형상','대구 수성구 범어네거리 주변\n중심 35.85914°N, 128.62622°E\n약 1.7 km × 1.7 km 지도 범위'),('02  가상 수요','기본 2,650대/시\n남측 유입 +600대/시 가정\n실제 아파트 개발·실측 교통량 아님'),('03  비교 실험','입주 전 → 입주 후 → 신호 조정안\n동일 입주 후 차량·경로를 재사용\n중앙 신호 주기 90초 유지'),('04  근거의 경계','차로·연결·신호는 현장 미검증\n건물 높이 일부는 12 m 가정\n보행자·실제 버스 노선 미구현')]
    for y,(title,text) in zip([.77,.59,.41,.23],blocks):
        fig.text(x,y,title,fontsize=13,weight='bold');fig.text(x,y-.04,text,fontsize=11,color='#526b80',va='top',linespacing=1.8)
    foot(fig);save(fig,'01_network_atlas')

def speeds():
    fig=plt.figure(figsize=(17,8));header(fig,'02','신호를 바꾸면, 어디가 달라지는가','300–1,500초 관측 구간 · 도로별 차량 체류시간으로 가중한 평균속도 · 동일 색상 범위')
    bounds=(-800,800,-800,800)
    for i,s in enumerate(SC):
        ax=fig.add_axes([.035+i*.32,.16,.30,.62]);scale=base(ax,bounds)
        roads=[r for r in G['roads'] if not r['internal'] and r['id'] in R[s]['edges'] and within(r['shape'],bounds)]
        ax.add_collection(LineCollection([r['shape'] for r in roads],linewidths=[max(2,r['width']*scale) for r in roads],colors=[CM(NORM(R[s]['edges'][r['id']]['speed_kmh'])) for r in roads],zorder=3))
        ax.set_title(LABEL[i],fontsize=15,color=COL[i],pad=8);scalebar(ax,bounds,200)
    cax=fig.add_axes([.32,.09,.37,.022]);fig.colorbar(cm.ScalarMappable(norm=NORM,cmap=CM),cax=cax,orientation='horizontal',label='평균속도 (km/h) · 회색: 관측 차량 없음')
    foot(fig);save(fig,'02_speed_comparison')

def queue_map():
    fig=plt.figure(figsize=(15,8.5));header(fig,'03','정체는 줄었지만, 모든 도로가 좋아진 것은 아니다','왼쪽: 입주 후 도로별 누적 정지 시간 / 오른쪽: 조정안 - 입주 후 평균속도')
    bounds=(-800,800,-800,800);ax=fig.add_axes([.04,.13,.44,.65]);base(ax,bounds)
    roads=[r for r in G['roads'] if not r['internal'] and r['id'] in R['after']['edges'] and within(r['shape'],bounds)]
    vals=[R['after']['edges'][r['id']]['waiting']/60 for r in roads];norm=colors.Normalize(0,max(vals));cmap=plt.get_cmap('YlOrRd')
    ax.add_collection(LineCollection([r['shape'] for r in roads],linewidths=3,colors=[cmap(norm(v)) for v in vals],zorder=4));ax.set_title('누적 정지 시간 (차량·분)',pad=12)
    fig.colorbar(cm.ScalarMappable(norm=norm,cmap=cmap),ax=ax,shrink=.65,pad=.01)
    ax2=fig.add_axes([.54,.13,.43,.65]);base(ax2,bounds)
    roads=[r for r in roads if r['id'] in R['adjusted']['edges']];vals=[R['adjusted']['edges'][r['id']]['speed_kmh']-R['after']['edges'][r['id']]['speed_kmh'] for r in roads]
    norm=colors.TwoSlopeNorm(vmin=-20,vcenter=0,vmax=20);cmap=plt.get_cmap('RdYlGn')
    ax2.add_collection(LineCollection([r['shape'] for r in roads],linewidths=3,colors=[cmap(norm(v)) for v in vals],zorder=4));ax2.set_title('속도 변화: 빨강 악화 / 초록 개선',pad=12)
    fig.colorbar(cm.ScalarMappable(norm=norm,cmap=cmap),ax=ax2,shrink=.65,pad=.01,label='km/h, ±20 범위')
    foot(fig);save(fig,'03_congestion_and_tradeoff')

def closeup():
    fig=plt.figure(figsize=(16,8.4));header(fig,'04','차량 단위로 보는 같은 시각의 교차로','t = 900초 · FCD 차량 위치/각도/속도 + 해당 시각 SUMO 신호 상태 · 도로 표시는 렌더링 보조선')
    bounds=(-135,135,-135,135);idx=150
    for i,s in enumerate(SC):
        ax=fig.add_axes([.03+i*.325,.15,.30,.62]);base(ax,bounds,True);signal(ax,s,idx,bounds);vehicles(ax,s,idx,bounds)
        ax.set_title(LABEL[i],color=COL[i],fontsize=14,pad=9);scalebar(ax,bounds,25)
    cax=fig.add_axes([.34,.085,.33,.02]);fig.colorbar(cm.ScalarMappable(norm=NORM,cmap=CM),cax=cax,orientation='horizontal',label='차량 속도 (km/h) · 연결선: 기록된 신호색')
    foot(fig);save(fig,'04_junction_closeup')

def isometric_mplot3d_unused():
    fig=plt.figure(figsize=(15,10));header(fig,'05','실제 도로 형상 위에서 재생하는 도시 모형','입주 후 t = 900초 · SUMO 궤적을 별도 3D 렌더러로 표현 · 건물 높이 미측량, 기본 12 m')
    ax=fig.add_axes([.015,.07,.97,.76],projection='3d');bounds=(-350,350,-350,350)
    faces=[];fc=[]
    for b in G['buildings']:
        pts=np.array(b['shape']);mid=pts.mean(axis=0)
        if not (-345<mid[0]<345 and -345<mid[1]<345):continue
        h=b['height'];faces.append([(x,y,h) for x,y in pts]);fc.append('#b8ced9')
        for p,q in zip(pts, np.roll(pts,-1,axis=0)):
            faces.append([(p[0],p[1],0),(q[0],q[1],0),(q[0],q[1],h),(p[0],p[1],h)]);fc.append('#d0dce2' if p[0]<q[0] else '#9fb9c7')
    ax.add_collection3d(Poly3DCollection(faces,facecolors=fc,edgecolors='#8da9b8',linewidths=.15,alpha=.94))
    roadfaces=[]
    for r in G['roads']:
        if r['internal'] or not within(r['shape'],bounds):continue
        for p,q in zip(r['shape'],r['shape'][1:]):
            p=np.array(p);q=np.array(q);d=q-p;l=np.linalg.norm(d)
            if not l:continue
            off=np.array([-d[1],d[0]])/l*r['width']/2
            roadfaces.append([(x,y,.1) for x,y in [p+off,p-off,q-off,q+off]])
    for p in G['junctions']:
        if within(p,bounds):roadfaces.append([(x,y,.1) for x,y in p])
    ax.add_collection3d(Poly3DCollection(roadfaces,facecolors='#4b6070',edgecolors='none'))
    carfaces=[];carcols=[]
    for ident,x,y,speed,angle in REPLAY['after']['frames'][150]['v']:
        if not (-350<x<350 and -350<y<350):continue
        typ=REPLAY['after']['vehicles'][ident]['type'];ln,wd,h={'car':(4.6,1.8,1.6),'bus':(11.5,2.5,3.1),'truck':(7.5,2.4,3)}[typ]
        d=np.array([math.sin(math.radians(angle)),math.cos(math.radians(angle))]);n=np.array([-d[1],d[0]])*wd/2;p=np.array([x,y]);pts=[p+n,p-n,p-ln*d-n,p-ln*d+n]
        carfaces.append([(a,b,h+.3) for a,b in pts]);carcols.append(CM(NORM(speed*3.6)))
        for p,q in zip(pts,pts[1:]+pts[:1]):carfaces.append([(p[0],p[1],.2),(q[0],q[1],.2),(q[0],q[1],h+.3),(p[0],p[1],h+.3)]);carcols.append(CM(NORM(speed*3.6)))
    ax.add_collection3d(Poly3DCollection(carfaces,facecolors=carcols,edgecolors='#385663',linewidths=.1))
    ax.set(xlim=(-350,350),ylim=(-350,350),zlim=(0,170));ax.set_box_aspect((1,1,.28));ax.view_init(elev=43,azim=-59);ax.set_axis_off();ax.set_proj_type('ortho')
    fig.text(.06,.16,'범어네거리\n달구벌대로 × 동대구로',fontsize=14,weight='bold',linespacing=1.5)
    fig.text(.73,.17,'도시 모형: OSM 평면 + 가정 높이\n차량 움직임: SUMO 실제 실행 기록\n실사·현장 검증 모델이 아닙니다',fontsize=10,linespacing=1.7,color='#5d7386')
    foot(fig);save(fig,'05_isometric_city')

def isometric():
    # Explicit painter order avoids mplot3d collection-level road/building occlusion.
    fig=plt.figure(figsize=(15,10));header(fig,'05','도시 모형에서 살펴보는 차량의 움직임','입주 후 t = 900초 · SUMO 궤적의 별도 2.5D 표현 · 건물 높이: OSM 태그 또는 12 m 가정')
    ax=fig.add_axes([.035,.08,.93,.74]);ax.set_aspect('equal');ax.set_axis_off();ax.set(xlim=(-390,390),ylim=(-300,350))
    def project(pts,z=0):return np.array([[x*.84-y*.54,x*.34+y*.5+(zz if len(p)>2 else z)*.9] for p in pts for x,y,*zs in [p] for zz in [zs[0] if zs else z]])
    def poly(pts,c,edge='none',z=0,lw=.2):ax.add_patch(Polygon(project(pts,z),facecolor=c,edgecolor=edge,linewidth=lw))
    def clipped(p,q,r=300):
        # Liang-Barsky segment clipping in world space.
        p=np.array(p);q=np.array(q);d=q-p;t0,t1=0.,1.
        for a,b in [(-d[0],p[0]+r),(d[0],r-p[0]),(-d[1],p[1]+r),(d[1],r-p[1])]:
            if abs(a)<1e-12:
                if b<0:return None
            elif a<0:t0=max(t0,b/a)
            else:t1=min(t1,b/a)
        if t0>t1:return None
        return p+t0*d,p+t1*d
    poly([[-300,-300],[300,-300],[300,300],[-300,300]],'#e4ebed')
    for r in G['roads']:
        if r['internal']:continue
        for p,q in zip(r['shape'],r['shape'][1:]):
            clippedpair=clipped(p,q)
            if clippedpair is None:continue
            p,q=clippedpair;d=q-p;l=np.linalg.norm(d)
            if l<.01:continue
            off=np.array([-d[1],d[0]])/l*r['width']/2;poly([p+off,p-off,q-off,q+off],'#597481')
    for pts in G['junctions']:
        if all(abs(x)<300 and abs(y)<300 for x,y in pts):poly(pts,'#597481')
    objects=[]
    for b in G['buildings']:
        pts=np.array(b['shape']);mid=pts.mean(axis=0)
        if not all(abs(x)<300 and abs(y)<300 for x,y in pts):continue
        objects.append((mid[0]*.34+mid[1]*.5,'building',b))
    for v in REPLAY['after']['frames'][150]['v']:
        if abs(v[1])<300 and abs(v[2])<300:objects.append((v[1]*.34+v[2]*.5,'car',v))
    for _,kind,o in sorted(objects,key=lambda a:a[0],reverse=True):
        if kind=='building':
            pts=o['shape'];h=o['height']
            for p,q in zip(pts,pts[1:]+pts[:1]):poly([[*p,0],[*q,0],[*q,h],[*p,h]],'#b9ced9' if p[0]<q[0] else '#99b6c7','#a0bbc8')
            poly(pts,'#dce8ed','#9cb6c5',h)
        else:
            ident,x,y,speed,angle=o;typ=REPLAY['after']['vehicles'][ident]['type'];ln,wd,h={'car':(4.6,1.8,1.6),'bus':(11.5,2.5,3.1),'truck':(7.5,2.4,3)}[typ]
            d=np.array([math.sin(math.radians(angle)),math.cos(math.radians(angle))]);n=np.array([-d[1],d[0]])*wd/2;p=np.array([x,y]);pts=[p+n,p-n,p-ln*d-n,p-ln*d+n];col=CM(NORM(speed*3.6))
            for p,q in zip(pts,pts[1:]+pts[:1]):poly([[*p,0],[*q,0],[*q,h],[*p,h]],col,'#385968')
            poly(pts,col,'#385968',h)
    fig.text(.06,.16,'범어네거리 주변 600 m × 600 m\n별도 렌더러로 생성한 조감도',fontsize=12,weight='bold',linespacing=1.7)
    fig.text(.70,.16,'차량 위치·속도: 실제 SUMO 실행 기록\n건물 높이: 현장 미검증\n실사 또는 측량 3D 모형이 아닙니다',fontsize=10,linespacing=1.7,color='#5d7386')
    foot(fig);save(fig,'05_isometric_city')

def metrics():
    fig=plt.figure(figsize=(16,10));header(fig,'06','통행 완료는 늘고, 완료 차량 시간손실은 증가했다','동일한 입주 후 요청 차량 1,355대 비교 · 불리한 결과와 미진입 차량을 함께 공개')
    ax=fig.add_axes([.07,.52,.39,.27]);ys=np.arange(3);left=np.zeros(3)
    for k,c,label in [('completed','#168d83','완료'),('running','#e3b752','미완료'),('waiting','#d86564','미진입')]:
        vals=[R[s]['counts'][k] for s in SC];ax.barh(ys,vals,left=left,color=c,label=label,height=.48)
        for y,l,v in zip(ys,left,vals):
            if v:ax.text(l+v/2,y,str(v),ha='center',va='center',fontsize=10,color='white' if k=='completed' else '#24394b')
        left+=vals
    ax.set_yticks(ys,LABEL);ax.invert_yaxis();ax.set_xlabel('시뮬레이션 종료 t = 2,100초 기준 차량 수');ax.legend(loc='lower left',bbox_to_anchor=(0,1.02),ncol=3,frameon=False);ax.set_xlim(0,1460)
    ax=fig.add_axes([.57,.52,.37,.27]);
    for i,s in enumerate(SC):
        ser=np.array(R[s]['series']);ax.plot(ser[:,0],ser[:,2],label=LABEL[i],color=COL[i],lw=1.7)
    ax.set(xlabel='시뮬레이션 시간 (초)',ylabel='네트워크 내 정지 차량 수');ax.grid(alpha=.5);ax.legend(frameon=False,fontsize=9)
    ax=fig.add_axes([.07,.13,.39,.27]);vals=[R[s]['mean_stopped_vehicles'] for s in SC];ax.bar(LABEL,vals,color=COL,width=.5)
    for i,v in enumerate(vals):ax.text(i,v+3,f'{v:.1f}대',ha='center',weight='bold')
    ax.set_ylim(0,165);ax.set_ylabel('평균 정지 차량 (300–1,500초)');ax.grid(axis='y',alpha=.5);ax.set_axisbelow(True)
    ax=fig.add_axes([.57,.13,.37,.27]);
    for i,s in enumerate(SC):
        v=np.sort(R[s]['completed_time_loss_s']);ax.plot(v,np.arange(1,len(v)+1)/len(v),color=COL[i],label=f'{LABEL[i]} {v.mean():.1f}초')
    ax.set(xlabel='완료 차량의 SUMO timeLoss (초)',ylabel='누적 비율');ax.legend(frameon=False,fontsize=9);ax.grid(alpha=.5)
    foot(fig,'정지 기준 < 0.1 m/s · timeLoss는 완료 차량만: 미완료/미진입 제외에 따른 선택 편향 있음');save(fig,'06_metrics_and_completion')

def trajectories():
    fig=plt.figure(figsize=(16,9));header(fig,'07','궤적이 수평으로 눕는 구간이, 멈춰 있는 시간이다','동→서 경로 차량 · 기록 간격 4초 · x축 시간 / y축 동서 위치 · 각 선은 한 차량')
    demand={v['id']:v['route'] for v in read(ROOT/'data/vehicles.json')};segs=[]
    for j,s in enumerate(SC):
        ax=fig.add_axes([.07,.62-j*.225,.86,.18]);traces={}
        for f in REPLAY[s]['frames']:
            if not 600<=f['t']<=1080:continue
            for i,x,y,speed,a in f['v']:
                if demand.get(REPLAY[s]['vehicles'][i]['id'])=='EW':traces.setdefault(i,[]).append([f['t'],x,speed])
        lines=[];cols=[]
        for points in traces.values():
            for p,q in zip(points,points[1:]):
                if q[0]-p[0]>4:continue
                lines.append([p[:2],q[:2]]);cols.append(CM(NORM((p[2]+q[2])*1.8)))
        ax.add_collection(LineCollection(lines,colors=cols,linewidths=1.1));ax.set(xlim=(600,1080),ylim=(-800,800),ylabel='동서 위치 (m)');ax.axhline(0,color='#8297a5',ls='--',lw=.6);ax.set_title(LABEL[j],loc='left',fontsize=11,color=COL[j]);ax.grid(alpha=.4)
        if j==2:ax.set_xlabel('시뮬레이션 시간 (초)')
    cax=fig.add_axes([.36,.075,.30,.015]);fig.colorbar(cm.ScalarMappable(norm=NORM,cmap=CM),cax=cax,orientation='horizontal',label='차량 속도 (km/h)')
    foot(fig);save(fig,'07_time_space_trajectories')

def phases():
    fig=plt.figure(figsize=(15,7));header(fig,'08','90초를 유지하고, 녹색 배분만 바꾼 후보','신호현시의 순서·연결 상태·황색 6초는 보존 · 보행자 횡단시간 검증을 거치지 않은 연구용 후보')
    ax=fig.add_axes([.1,.39,.82,.36]);colors4=['#338ca3','#6aa9bd','#168d83','#8cbfa7']
    for row,s in enumerate(['after','adjusted']):
        start=0
        for j,d in enumerate(R[s]['green_seconds']):
            ax.barh(row,d,left=start,color=colors4[j],height=.5);ax.text(start+d/2,row,f'G{j+1}\n{d:g}초',ha='center',va='center',color='white',fontsize=12,weight='bold');start+=d
            ax.barh(row,6,left=start,color='#e4b956',height=.5);ax.text(start+3,row,'6',ha='center',va='center',fontsize=10);start+=6
    ax.set(xlim=(0,90),xlabel='한 주기 내 시간 (초)');ax.set_yticks([0,1],['기본 자동 생성 신호','수요 가중 조정안']);ax.invert_yaxis();ax.grid(axis='x',alpha=.4)
    fig.text(.1,.24,'15 / 17 / 17 / 17초  →  16 / 12 / 21 / 17초',fontsize=21,weight='bold')
    fig.text(.1,.15,'최적화 결과가 아닌 단일 후보입니다. 현시별 진입 수요 가중치와 최소 녹색 10초를 사용했습니다.\n실제 신호 설계에는 현장 차로·보행·상충·연동 조건의 별도 확인이 필요합니다.',fontsize=11,linespacing=1.7,color='#5d7386')
    foot(fig);save(fig,'08_signal_plan')

def movie():
    import imageio_ffmpeg
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    fig=plt.figure(figsize=(16,7.4),dpi=100);canvas=FigureCanvasAgg(fig)
    header(fig,'REPLAY','같은 시간, 세 가지 교통 상황','SUMO FCD 기록 재생 · 4초 간격 원본 프레임 / 12 fps = 시뮬레이션 시간 48배속 · 중간 위치 보간 없음')
    bounds=(-270,270,-270,270);axes=[];artists=[]
    for j,s in enumerate(SC):
        ax=fig.add_axes([.025+j*.326,.13,.30,.63]);base(ax,bounds,True);ax.set_title(LABEL[j],color=COL[j],fontsize=14,pad=9);axes.append(ax);artists.append([])
    clock=fig.text(.80,.955,'',fontsize=13,weight='bold',va='top');foot(fig)
    path=ROOT/'output/daegu_comparison_replay.mp4'
    writer=imageio_ffmpeg.write_frames(str(path),(1600,740),fps=12,codec='libx264',quality=8,pix_fmt_in='rgb24',pix_fmt_out='yuv420p',macro_block_size=2);writer.send(None)
    for frame in range(300):
        for j,s in enumerate(SC):
            for art in artists[j]:art.remove()
            artists[j]=[signal(axes[j],s,frame,bounds),vehicles(axes[j],s,frame,bounds)]
        clock.set_text(f"t = {REPLAY['after']['frames'][frame]['t']:.0f} s")
        canvas.draw();rgba=np.asarray(canvas.buffer_rgba());writer.send(np.ascontiguousarray(rgba[:,:,:3]).tobytes())
    writer.close();plt.close(fig);print(path,flush=True)

if __name__=='__main__':
    import sys
    if '--movie-only' in sys.argv: movie()
    else:
        atlas();speeds();queue_map();closeup();isometric();metrics();trajectories();phases()
        if '--movie' in sys.argv: movie()
