"""Plots are computed only from saved raw SUMO/analytic outputs."""
from pathlib import Path
import json
import pandas as pd
import plotly.graph_objects as go
from .theme import FONT
from .models import LABELS,DIRECTIONS
from .results import summary
NAMES={"before":"입주 전","after":"입주 후","improved":"신호 조정 후보"}
COLORS={"before":"#8190a5","after":"#c58a3b","improved":"#3267c8"}

def finish(fig,ylabel=None,height=350):
    fig.update_layout(height=height,margin=dict(l=15,r=15,t=50,b=105),
        paper_bgcolor="#ffffff",plot_bgcolor="#ffffff",
        font=dict(family=FONT,color="#23334c"),
        legend=dict(orientation="h",y=-.26,yanchor="top",x=0,xanchor="left"),hovermode="closest")
    if ylabel:fig.update_yaxes(title=ylabel)
    return fig

def load(folder):
    folder=Path(folder)
    data=json.loads((folder/"comparison.json").read_text(encoding="utf-8"))
    data["vehicle_links"]=json.loads((folder/"network"/"network_info.json").read_text(encoding="utf-8"))["vehicle_links"]
    tables={}
    for run in data["sumo"]:
        sid=run["scenario"];sub=folder/sid
        tables[sid]={}
        for name in ("telemetry","vehicles","geometric_queue"):
            path=sub/(name+".csv")
            if path.exists():tables[sid][name]=pd.read_csv(path)
    return data,tables

def insight(data):
    by={r["scenario"]:summary(r) for r in data["sumo"]}
    a,b=by["after"],by["improved"]
    if a["time_loss"] is None or b["time_loss"] is None:
        return "완료 차량이 없어 시간 손실 변화율을 계산하지 않습니다."
    delta=b["time_loss"]-a["time_loss"]
    runs={r["scenario"]:r for r in data["sumo"]}
    old={r["direction"]:r for r in runs["after"]["rows"]}
    worse=[LABELS[r["direction"]] for r in runs["improved"]["rows"]
           if r["time_loss"] is not None and old[r["direction"]]["time_loss"] is not None
           and r["time_loss"]>old[r["direction"]]["time_loss"]]
    text=f"완료 차량 평균 시간 손실: {a['time_loss']:.2f} → {b['time_loss']:.2f}초 ({delta:+.2f}초). "
    text+=("증가한 방향: "+", ".join(worse)+". ") if worse else "시간 손실이 증가한 방향은 없습니다. "
    pending=a["pending"]+a["unfinished"];remaining=b["pending"]+b["unfinished"]
    text+=f"미진입·미완료: {pending:,} → {remaining:,}대."
    if pending or remaining:text+=" 완료 차량만의 평균이므로 전반적 개선으로 판정하지 않습니다."
    return text

def overview(data):
    figs={}
    f=go.Figure()
    runs={r["scenario"]:r for r in data["sumo"]}
    by={s:{r["direction"]:r for r in run["rows"]} for s,run in runs.items()}
    for d in DIRECTIONS:
        f.add_scatter(x=[by["after"][d]["time_loss"],by["improved"][d]["time_loss"]],
            y=[LABELS[d]]*2,mode="lines",line=dict(color="#c4d1cc"),showlegend=False,hoverinfo="skip")
    for sid in ("after","improved"):
        f.add_scatter(x=[by[sid][d]["time_loss"] for d in DIRECTIONS],y=[LABELS[d] for d in DIRECTIONS],
            mode="markers",marker=dict(size=13,color=COLORS[sid],symbol="circle" if sid=="after" else "diamond"),
            name=NAMES[sid],hovertemplate="%{y}: %{x:.2f}초<extra>%{fullData.name}</extra>")
    f.update_xaxes(title="완료 차량 평균 시간 손실 (초)")
    figs["방향별 이익과 불이익"]=finish(f)
    f=go.Figure()
    for key,label,color in [("completed","완료","#3267c8"),("unfinished","도로 안 미완료","#c58a3b"),("pending","도로 밖 미진입","#b34d52")]:
        f.add_bar(name=label,x=[NAMES[r["scenario"]] for r in data["sumo"]],
            y=[sum(v[key] for v in r["rows"]) for r in data["sumo"]],marker_color=color,
            text=[sum(v[key] for v in r["rows"]) for r in data["sumo"]],textposition="auto")
    f.update_layout(barmode="stack")
    figs["출발 예정 차량의 최종 상태"]=finish(f,"대 · 관측기간 출발 예정 집단")
    f=go.Figure()
    for sid in ("before","after","improved"):
        sc=next(x for x in data["analytic"] if x["id"]==sid)
        f.add_bar(name=NAMES[sid]+" 수요",x=[r["label"] for r in sc["rows"]],
            y=[r["volume"] for r in sc["rows"]],marker_color=COLORS[sid],legendgroup=sid)
        f.add_scatter(name=NAMES[sid]+" 계산 용량",x=[r["label"] for r in sc["rows"]],
            y=[r["capacity"] for r in sc["rows"]],mode="markers",marker=dict(size=13,symbol="line-ew",color=COLORS[sid]),legendgroup=sid)
    f.update_layout(barmode="group",legend=dict(y=1.28))
    figs["수요와 공식 기반 처리능력"]=finish(f,"대/시간",410)
    return figs

def detail(data,tables,direction="N",sid="after"):
    figs={}
    f=go.Figure()
    for scenario,tab in tables.items():
        if "telemetry" not in tab:continue
        t=tab["telemetry"];t=t[(t.direction==direction)&t.observation].copy()
        t["minute"]=(t.time-data["config"]["warmup"])//30*.5
        agg=t.groupby("minute",as_index=False).halting.mean()
        f.add_scatter(x=agg.minute,y=agg.halting,name=NAMES[scenario],line=dict(color=COLORS[scenario]),
            hovertemplate="%{x:.1f}분: %{y:.2f}대<extra>%{fullData.name}</extra>")
    f.update_xaxes(title="관측 시작 후 분 · 30초 구간 평균")
    figs["정지 차량의 시간 변화"]=finish(f,"평균 정지 차량 (대)")
    if "telemetry" in tables.get(sid,{}):
        t=tables[sid]["telemetry"];td=t[t.direction==direction].copy()
        td["minute"]=td.time/60
        f=go.Figure()
        for k,label in [("scheduled","출발 예정"),("inserted","실제 진입"),("crossed","교차로 통과"),("completed","경로 완료")]:
            f.add_scatter(x=td.minute.iloc[::10],y=td[k].iloc[::10],name=label)
        f.update_xaxes(title="실험 시작 후 분 · 준비기간 포함 누적 · 10개 관측마다 표시")
        figs["누적 차량 흐름"]=finish(f,"대 · 전체 생성 수요")
        t=t[t.observation].copy();t["minute"]=(t.time-data["config"]["warmup"])//60
        pivot=t.pivot_table(index="direction",columns="minute",values="halting",aggfunc="mean").reindex(DIRECTIONS)
        # Fixed color scale across the three situations in this experiment.
        heat_max=1.0
        for tab in tables.values():
            if 'telemetry' not in tab:continue
            other=tab['telemetry'];other=other[other.observation].copy()
            other['minute']=(other.time-data['config']['warmup'])//60
            if len(other):heat_max=max(heat_max,float(other.groupby(['direction','minute']).halting.mean().max()))
        f=go.Figure(go.Heatmap(z=pivot.values,x=pivot.columns,y=[LABELS[d] for d in pivot.index],
            zmin=0,zmax=heat_max,colorscale="YlOrRd",colorbar=dict(title="대"),hovertemplate="%{y} · %{x}분: %{z:.2f}대<extra></extra>"))
        f.update_xaxes(title="관측 시작 후 분 · 1분 평균")
        figs["방향별 혼잡 집중 시간"]=finish(f,"방향")
        phase=tables[sid]["telemetry"].drop_duplicates("time")
        phase=phase[(phase.time>=data["config"]["warmup"])&(phase.time<data["config"]["warmup"]+180)]
        links={d:int(i) for i,d in data["vehicle_links"].items()}
        f=go.Figure()
        stateval={"r":0,"y":1,"Y":1,"g":2,"G":2}
        z=[[stateval.get(v[links[d]],0) for v in phase.signal] for d in DIRECTIONS]
        f.add_heatmap(z=z,x=(phase.time-data["config"]["warmup"]).tolist(),y=[LABELS[d] for d in DIRECTIONS],
            text=[[v[links[d]] for v in phase.signal] for d in DIRECTIONS],zmin=0,zmax=2,
            colorscale=[[0,"#b34d52"],[.25,"#b34d52"],[.25,"#d4a93d"],[.75,"#d4a93d"],[.75,"#3267c8"],[1,"#3267c8"]],
            colorbar=dict(tickvals=[0,1,2],ticktext=["적색","황색","녹색"]),
            hovertemplate="%{y} · %{x}초: %{text}<extra></extra>")
        f.update_xaxes(title="관측 시작 후 초 · 첫 180초의 실제 신호")
        figs["실제 신호 타임라인"]=finish(f)
    f=go.Figure()
    for scenario,tab in tables.items():
        if "vehicles" not in tab:continue
        v=tab["vehicles"];v=v[v.measured&(v.status=="completed")&(v.direction==direction)]
        f.add_box(y=v.time_loss,name=NAMES[scenario],marker_color=COLORS[scenario],boxpoints=False,
            hovertemplate="%{y:.2f}초<extra>%{fullData.name}</extra>")
    figs["완료 차량 시간 손실 분포"]=finish(f,"시간 손실 (초)")
    if any('geometric_queue' in tab for tab in tables.values()):
        f=go.Figure()
        for scenario,tab in tables.items():
            if 'geometric_queue' not in tab:continue
            q=tab['geometric_queue'];q=q[(q.direction==direction)&(q.time>=data['config']['warmup'])&(q.time<data['config']['warmup']+data['config']['duration'])].copy()
            q['minute']=(q.time-data['config']['warmup'])//30*.5
            q=q.groupby('minute',as_index=False).queue_m.max()
            f.add_scatter(x=q.minute,y=q.queue_m,name=NAMES[scenario],line=dict(color=COLORS[scenario]))
        f.update_xaxes(title='관측 시작 후 분 · 30초 구간 최댓값')
        figs['위치로 재구성한 최장 정지 차량군']=finish(f,'길이 (m) · 평행 차로 최댓값')
    return figs

def search_figures(report):
    df=pd.DataFrame(report["candidates"]);figs={}
    if df.empty:return figs
    df=df.sort_values("ns")
    f=go.Figure()
    for key,label in [("mean_time_loss","전체 평균"),("worst_direction_time_loss","시드별 최악 방향 평균의 평균")]:
        f.add_scatter(x=df.ns,y=df[key],mode="lines+markers",name=label)
    bad=df[~df.eligible]
    if len(bad):f.add_scatter(x=bad.ns,y=bad.mean_time_loss,mode="markers",name="추천 제외",marker=dict(symbol="x",size=12,color="#b34d52"))
    f.update_xaxes(title="남북 녹색시간 (초) · 동서는 나머지 녹색")
    figs["후보 배분과 성능"]=finish(f,"시간 손실 (초)")
    f=go.Figure()
    for eligible,label,color in [(True,"적격","#3267c8"),(False,"제외","#b34d52")]:
        part=df[df.eligible==eligible]
        f.add_scatter(x=part.mean_time_loss,y=part.worst_direction_time_loss,mode="markers+text",
            text=[str(r.ns) if r.ns in (report['overall_best'],report['balanced_best']) else '' for r in part.itertuples()],
            customdata=part.ns,textposition=['top right' if r.ns==report['overall_best'] else 'bottom right' for r in part.itertuples()],
            name=label,marker=dict(color=color,size=11,symbol='circle' if eligible else 'x'),
            hovertemplate="남북 %{customdata}초 · 전체 %{x:.2f}초 · 최악방향 %{y:.2f}초<extra></extra>")
    frontier=df[df.pareto].sort_values("mean_time_loss")
    f.add_scatter(x=frontier.mean_time_loss,y=frontier.worst_direction_time_loss,mode="lines",name="상호 절충 후보",line=dict(dash="dot",color="#3267c8"))
    f.update_xaxes(title="전체 평균 시간 손실 (초)")
    figs["전체 효율과 방향 균형"]=finish(f,"시드별 최악 방향 평균의 평균 (초)")
    f=go.Figure()
    refs={r["seed"]:r for r in report["records"] if r["reference"]}
    for ns in sorted({report["overall_best"],report["balanced_best"]}-{None}):
        rows=[r for r in report["records"] if r["ns"]==ns and r["seed"] in refs]
        paired=[(r["seed"],r["metrics"]["time_loss"]-refs[r["seed"]]["metrics"]["time_loss"]) for r in rows
                if r["metrics"]["time_loss"] is not None and refs[r["seed"]]["metrics"]["time_loss"] is not None]
        f.add_scatter(x=[str(s) for s,v in paired],y=[v for s,v in paired],mode="lines+markers",name=f"남북 {ns}초")
    f.add_hline(y=0,line_dash="dot");f.update_xaxes(title="같은 수요로 비교한 시드")
    figs["시드별 기준 대비 차이"]=finish(f,"후보 − 기준 시간 손실 (초)")
    return figs

