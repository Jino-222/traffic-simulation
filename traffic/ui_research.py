from pathlib import Path
import json,os,subprocess,sys
import pandas as pd
import streamlit as st
from . import dashboard as charts
from .models import Config,LABELS
from .results import summary
from .experiment import new_folder
from .io import write_json
ROOT=Path(__file__).resolve().parents[1]
EXPERIMENTS=ROOT/"experiments"

@st.cache_data(show_spinner=False)
def load_saved(folder,modified,derived_version=None):
    return charts.load(folder)

def choose_experiment(key):
    folders=sorted([p.parent for p in EXPERIMENTS.rglob("comparison.json")],key=lambda p:p.stat().st_mtime,reverse=True)
    if not folders:st.info("먼저 세 상황 SUMO 실험을 실행하세요.");return None
    default=EXPERIMENTS/"baseline_v2"
    index=folders.index(default) if default in folders else 0
    return st.selectbox("표시할 저장 실험",folders,index=index,format_func=lambda p:str(p.relative_to(EXPERIMENTS)),key=key)

def draw(figures,prefix):
    for i,(name,fig) in enumerate(figures.items()):
        st.subheader(name)
        st.plotly_chart(fig,width="stretch",key=prefix+str(i),
            config={"displaylogo":False,"toImageButtonOptions":{"format":"png","filename":prefix+str(i),"scale":2}})

def dashboard(config):
    folder=choose_experiment("detail_experiment")
    if folder is None:return
    data,tables=load_saved(str(folder),(folder/"comparison.json").stat().st_mtime_ns,
        tuple(p.stat().st_mtime_ns for p in sorted(folder.glob('*/geometric_queue.csv'))))
    stored=Config.from_dict(data["config"])
    # Recording switches do not change physical input; still display exact provenance below.
    a=config.to_dict();b=stored.to_dict()
    for v in (a,b):v.pop("record_trajectories",None)
    if a!=b:st.warning("저장된 실험의 결과입니다. 현재 왼쪽 입력과 다릅니다.")
    st.caption(f"{folder.name} · 관측 {stored.duration}초 · 시드 {stored.seed} · 수요와 관측기간이 같은 실험끼리 비교하세요.")
    st.info(charts.insight(data))
    cols=st.columns(3)
    for col,run in zip(cols,data["sumo"]):
        s=summary(run)
        with col,st.container(border=True):
            st.markdown("**"+charts.NAMES[run["scenario"]]+"**")
            st.metric("완료 차량 평균 시간 손실",f"{s['time_loss']:.2f}초" if s["time_loss"] is not None else "해당 없음")
            st.caption(f"완료 {s['completed']:,}/{s['requested']:,}대 · 미진입 {s['pending']:,} · 미완료 {s['unfinished']:,}")
    mode=st.radio("그래프 묶음",["핵심 비교","시간·분포 분석"],horizontal=True,key="graph_group")
    if mode=="핵심 비교":draw(charts.overview(data),"overview")
    else:
        left,right=st.columns(2)
        direction=left.selectbox("분석 방향",list(LABELS),format_func=lambda d:LABELS[d])
        sid=right.selectbox("시간 상세 상황",list(charts.NAMES),index=1,format_func=lambda s:charts.NAMES[s])
        draw(charts.detail(data,tables,direction,sid),"detail")
        if 'geometric_queue' not in tables[sid]:
            st.info('이 기록에는 위치 기반 대기행렬 자료가 없습니다. 왼쪽 SUMO 실험 설정에서 궤적 저장을 켜고 실행하면 길이 그래프가 함께 생성됩니다.')
        st.caption("시간 손실 분포는 관측기간 출발 예정 차량 중 완료 차량만 포함합니다. 정지 차량 수의 단위는 대이며, 대기행렬 길이(m)가 아닙니다.")
        st.caption('정지 차량군 길이는 저장된 위치·속도로 재구성한 연구 지표입니다. 속도 0.1m/s 미만, 정지 1초 초과, 차량 사이 간격 10m 이하인 그룹의 최장 길이를 기본으로 사용합니다. 실제 사용 조건은 실험 설정에 따릅니다. E2 원자료의 길이 값과 구분합니다.')
    a,b,c=st.columns(3)
    a.download_button("비교 CSV", (folder/"comparison.csv").read_bytes(),file_name=folder.name+"_comparison.csv",mime="text/csv")
    b.download_button("실험 설정 JSON",(folder/"inputs.json").read_bytes(),file_name=folder.name+"_inputs.json",mime="application/json")
    c.download_button("결과 해석 저장",charts.insight(data),file_name=folder.name+"_interpretation.txt",mime="text/plain")
    st.caption("각 그래프의 카메라 버튼으로 이미지를 저장할 수 있습니다.")

def start_search(folder,config,seeds,resume=False):
    folder.mkdir(parents=True,exist_ok=True)
    if not resume:write_json(folder/"request_config.json",config.to_dict())
    log=(folder/"worker.log").open("a",encoding="utf-8")
    command=[sys.executable,"-X","utf8","-m","traffic.search","--config",str(folder/"request_config.json"),
             "--output",str(folder),"--seeds",seeds,"--workers","2"]
    if resume:command.append("--resume")
    proc=subprocess.Popen(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,
        env=dict(os.environ,PYTHONUTF8="1"),creationflags=subprocess.CREATE_NO_WINDOW if os.name=="nt" else 0)
    log.close();st.session_state["search_job"]=proc;st.session_state["search_folder"]=str(folder)

@st.fragment(run_every="3s")
def search_panel(config,valid):
    st.write("주기와 보행 조건을 고정하고 1초 간격 녹색 배분을 SUMO로 비교합니다. 학습형 AI가 아닌 후보 열거 실험입니다.")
    proc=st.session_state.get("search_job");running=proc is not None and proc.poll() is None
    seeds=st.text_input("탐색 시드 (쉼표로 구분)","101,202,303",disabled=running)
    try:seed_values=[int(v.strip()) for v in seeds.split(",")];seed_ok=bool(seed_values) and len(seed_values)==len(set(seed_values)) and all(0<=s<=2147483647 for s in seed_values)
    except ValueError:seed_ok=False
    a,b=st.columns([3,1])
    if a.button("현재 조건으로 전체 후보 탐색",type="primary",disabled=running or not valid or not seed_ok):
        start_search(new_folder(EXPERIMENTS/"interactive_search"),config,seeds);st.rerun(scope="fragment")
    if b.button("탐색 중단",disabled=not running):
        (Path(st.session_state["search_folder"])/"CANCEL").touch()
    if running:
        active=Path(st.session_state["search_folder"])
        if (active/"status.json").exists():
            state=json.loads((active/"status.json").read_text(encoding="utf-8"))
            st.progress(min(1,state.get("completed",0)/max(1,state.get("total",1))),text=f"완료 {state.get('completed',0)} / {state.get('total',0)}")
    # Holdout runs are attached to their discovery below, never presented as a new search winner.
    manifests=sorted([p for p in EXPERIMENTS.rglob("search_manifest.json")
        if not (p.parent.parent/'frozen_selection.json').exists()],key=lambda p:p.stat().st_mtime,reverse=True)
    if not manifests:st.info("저장된 후보 탐색이 없습니다.");return
    default=EXPERIMENTS/'study_v2/discovery/search_manifest.json'
    chosen=st.selectbox("저장된 후보 탐색",manifests,index=manifests.index(default) if default in manifests else 0,
        format_func=lambda p:str(p.parent.relative_to(EXPERIMENTS)),key="search_history")
    folder=chosen.parent
    state={'state':'unknown'}
    if (folder/"status.json").exists():
        state=json.loads((folder/"status.json").read_text(encoding="utf-8"))
        st.caption(f"상태: {state['state']} · 완료 {state.get('completed',0)}/{state.get('total',0)}")
    manifest=json.loads(chosen.read_text(encoding="utf-8"))
    st.caption(f"저장 조건 · 관측 {manifest['config']['duration']}초 · 후보 {len(manifest['ns_values'])}개 · 시드 {manifest['seeds']}")
    if (folder/"request_config.json").exists() and not running and state.get("state") in ("cancelled","failed","needs_review"):
        if st.button("선택 탐색 이어 실행 / 실패 재시도"):
            start_search(folder,Config.from_dict(manifest["config"]),",".join(map(str,manifest["seeds"])),True);st.rerun(scope="fragment")
    result=folder/"search_summary.json"
    if not result.exists():
        st.info("이 탐색은 아직 최종 집계 전입니다. 실행 중에는 완료 수가 갱신됩니다.");return
    report=json.loads(result.read_text(encoding="utf-8"))
    if state["state"]!="completed":st.warning("완료되지 않은 탐색입니다. 아래 결과는 부분 결과입니다.")
    best,balance=st.columns(2)
    best.metric("전체 평균 우선 · 남북 녹색",str(report["overall_best"])+"초" if report["overall_best"] is not None else "적격 후보 없음")
    balance.metric("최악 방향 우선 · 남북 녹색",str(report["balanced_best"])+"초" if report["balanced_best"] is not None else "적격 후보 없음")
    st.caption("모든 시드에서 후보와 기준 실험이 정상 완료되고 미진입·미완료가 없는 경우에만 추천합니다.")
    limit=st.number_input("추가 필터: 방향별 악화 허용 상한 (초)",min_value=0.0,value=10.0,step=1.0,
        help="연구자가 정하는 비교 조건이며 공식 교통 기준이 아닙니다.")
    fair=[r for r in report["candidates"] if r["eligible"] and r["worst_paired_direction_delta"] is not None and r["worst_paired_direction_delta"]<=limit]
    if fair:st.success("악화 상한을 만족하는 배분: "+", ".join(f"{r['ns']} / {r['ew']:g}초" for r in fair))
    else:st.info("이 악화 상한까지 함께 만족하는 후보가 없습니다.")
    draw(charts.search_figures(report),"search_"+folder.name)
    columns=["ns","ew","eligible","mean_time_loss","worst_direction_time_loss","pending","unfinished","worst_paired_direction_delta","reason"]
    st.dataframe(pd.DataFrame(report["candidates"])[columns],hide_index=True,width="stretch")
    st.download_button("후보 비교 CSV",(folder/"candidate_comparison.csv").read_bytes(),file_name="candidate_comparison.csv",mime="text/csv")
    holdout=folder.parent/"holdout"/"holdout_summary.json"
    if holdout.exists():
        validation=json.loads(holdout.read_text(encoding="utf-8"))
        st.subheader("선택 후 별도 시드 재검증")
        st.write("탐색 시드:",validation["frozen"]["discovery_seeds"],"검증 시드:",validation["frozen"]["validation_seeds"])
        if "validation" in validation:
            st.dataframe(pd.DataFrame(validation["validation"]["candidates"])[columns],hide_index=True,width="stretch")
        st.caption("후보 선택을 먼저 고정한 뒤 검증했습니다. 검증 결과를 이용해 후보를 다시 선택하지 않습니다.")

def replay_panel():
    folder=choose_experiment("replay_experiment")
    if folder is None:return
    from .player import show
    a,b=st.columns(2)
    left=a.selectbox("왼쪽 상황",list(charts.NAMES),index=1,format_func=charts.NAMES.get)
    right=b.selectbox("오른쪽 상황",list(charts.NAMES),index=2,format_func=charts.NAMES.get)
    show(folder,left,right)

