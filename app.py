from pathlib import Path
from dataclasses import fields
import io, json, os, subprocess, sys, zipfile
import pandas as pd
import streamlit as st
from traffic.models import Config, Approach, DIRECTIONS, LABELS
from traffic.validation import validate
from traffic.analytic import calculate, candidates
from traffic.charts import comparison_chart, sumo_chart, intersection
from traffic.experiment import new_folder
from traffic.io import write_json
from traffic.scenarios import library
from traffic.ui_research import dashboard,search_panel,replay_panel
from traffic.ui_advanced import advanced_panel
from traffic import theme
from traffic.ui_city import city_panel

ROOT=Path(__file__).resolve().parent
EXPERIMENTS=ROOT/"experiments"
st.set_page_config(page_title="교통영향 분석 | Traffic Workspace",layout="wide")
theme.install()
view=theme.navigation()

def apply_config(defaults):
    st.session_state['scenario_config']=defaults.to_dict()
    st.session_state['profile_text']=', '.join(map(str,defaults.demand_profile))
    for kind,share in defaults.vehicle_mix.items():st.session_state['w_mix_'+kind]=float(share)
    for field in fields(defaults):
        if field.name=="approaches": continue
        value=getattr(defaults,field.name)
        if isinstance(value,(dict,list)):continue
        if isinstance(value,bool):
            st.session_state["w_"+field.name]=value
            continue
        if field.name not in ("warmup","duration","drain","seed","stochastic"):
            value=float(value)
        st.session_state["w_"+field.name]=value
    for d,a in defaults.approaches.items():
        st.session_state["w_lanes_"+d]=a.lanes
        st.session_state["w_base_"+d]=float(a.base)
        st.session_state["w_extra_"+d]=float(a.extra)

def reset():
    apply_config(Config())

def apply_scenario():
    apply_config(library()[st.session_state['preset']].config)
def quick():
    st.session_state["w_warmup"]=0
    st.session_state["w_duration"]=180
    st.session_state["w_drain"]=120
def full():
    st.session_state["w_warmup"]=900
    st.session_state["w_duration"]=3600
    st.session_state["w_drain"]=900

defaults=Config.from_dict(st.session_state.get("scenario_config",Config().to_dict()))
def number(label,key,value,step=1.0,integer=False,help=None):
    value=getattr(defaults,key,value)
    value=int(value) if integer else float(value)
    step=int(step) if integer else float(step)
    x=st.number_input(label,value=value,step=step,key="w_"+key,help=help)
    return x if x is not None else float("nan")

if view!="대구 범어네거리":
    with st.sidebar:
        st.markdown("### 실험 조건")
        st.caption("01 수요 → 02 신호 → 03 SUMO 실행")
        scenarios=library()
        st.selectbox('시나리오 예제',list(scenarios),format_func=lambda k:scenarios[k].title,key='preset')
        st.caption(scenarios[st.session_state['preset']].question)
        st.button('시나리오 적용',on_click=apply_scenario,width='stretch')
        st.button("↺ 기본값 복원",on_click=reset,width="stretch")
        with st.expander("교통량과 직진 차로"):
            st.caption("진입하는 쪽 기준 · 교통량 단위: 대/시간")
            approaches={}
            for d in DIRECTIONS:
                st.markdown(f"**{LABELS[d]}**")
                a,b,e=st.columns([1,1.4,1.4])
                with a:n=number("차로",f"lanes_{d}",defaults.approaches[d].lanes,integer=True)
                with b:q=number("기존",f"base_{d}",defaults.approaches[d].base,step=50)
                with e:extra=number("추가",f"extra_{d}",defaults.approaches[d].extra,step=50)
                approaches[d]=Approach(n,q,extra)
        vals=st.session_state.get('scenario_config',Config().to_dict()).copy()
        vals.pop('approaches',None)
        with st.expander("차량 신호시간"):
            vals["cycle"]=number("신호 주기 (초)","cycle",90)
            a,b=st.columns(2)
            with a:vals["yellow"]=number("현시별 황색 (초)","yellow",3,step=.5)
            with b:vals["all_red"]=number("현시별 전적색 (초)","all_red",2,step=.5)
            st.markdown("**입주 전·후 공통 녹색**")
            a,b=st.columns(2)
            with a:vals["before_ns"]=number("남북 (초)","before_ns",40)
            with b:vals["before_ew"]=number("동서 (초)","before_ew",40)
            st.markdown("**신호 개선 후보 녹색**")
            a,b=st.columns(2)
            with a:vals["improved_ns"]=number("후보 남북 (초)","improved_ns",50)
            with b:vals["improved_ew"]=number("후보 동서 (초)","improved_ew",30)
            def transfer(delta):
                for key,v in [("improved_ns",delta),("improved_ew",-delta)]:
                    st.session_state["w_"+key]+=v
            a,b=st.columns(2)
            a.button("← 동서에 1초",on_click=transfer,args=(-1,),width="stretch")
            b.button("남북에 1초 →",on_click=transfer,args=(1,),width="stretch")
            st.caption("배분 버튼은 녹색 합계를 유지합니다. 숫자를 직접 바꾸면 합계를 다시 검사합니다.")
        with st.expander("보행 조건"):
            st.caption("남북 보행은 동·서측 도로를, 동서 보행은 남·북측 도로를 횡단합니다.")
            for key,label,value,step in [
                ("crossing_length_ns","남북 보행 가정 길이 (m)",20,1),("crossing_length_ew","동서 보행 가정 길이 (m)",20,1),
                ("pedestrian_speed","보행속도 (m/s)",1,.1),("pedestrian_walk","보행 진입 허용시간 (초)",3,.5),
                ("pedestrian_margin","보행 소거 여유 (초)",2,.5),("pedestrian_budget_ns","남북 보행 배정 (초)",25,1),
                ("pedestrian_budget_ew","동서 보행 배정 (초)",25,1),("pedestrian_rate","횡단보도당 보행 수요 (명/시간)",60,10)]:
                vals[key]=number(label,key,value,step)
            st.caption("필요시간 = 진입 허용 + 길이/속도 + 소거 여유. SUMO 실행 전 입력 길이와 생성 길이 중 긴 값으로 재검사합니다.")
        with st.expander("계산·도로 가정"):
            for key,label,value,step in [
                ("saturation","차로당 포화교통류율 (대/시간/차로)",1800,50),
                ("start_loss","출발 손실시간 (초)",2,.5),
                ("road_length","접근로 길이 (m)",300,50),("speed_kmh","제한속도 (km/h)",50,5)]:
                vals[key]=number(label,key,value,step)
            st.caption("포화교통류율·출발 손실시간은 공식 계산의 가정입니다. SUMO의 차량 동작 매개변수와 별개입니다.")
        with st.expander("SUMO 실험 시간·재현성"):
            a,b=st.columns(2)
            a.button("빠른 확인",on_click=quick,width="stretch")
            b.button("1시간 관측",on_click=full,width="stretch")
            for key,label,value in [("warmup","준비시간 (초)",900),("duration","관측시간 (초)",3600),("drain","추가 종료시간 (초)",900),("seed","난수 시드",42)]:
                vals[key]=number(label,key,value,integer=True)
            vals["stochastic"]=st.checkbox("출발 시각에 무작위 변동 적용",value=defaults.stochastic,key="w_stochastic")
            vals['record_trajectories']=st.checkbox('SUMO 궤적 저장 (재생·대기행렬)',value=defaults.record_trajectories,key='w_record_trajectories')
            st.caption("방향별 차량 수는 고정하고 출발 시각만 변화시킵니다. 입주 후와 후보는 같은 차량 파일을 사용합니다.")
        with st.expander('시간대·차종 고급 조건'):
            profile=st.text_input('동일 길이 구간별 수요 배율',value=', '.join(map(str,vals['demand_profile'])),key='profile_text')
            try:vals['demand_profile']=[float(v.strip()) for v in profile.split(',')]
            except ValueError:vals['demand_profile']=[]
            st.caption('배율의 평균이 1이어야 총수요가 보존됩니다. 예: 0.8, 1, 1.4, 0.8')
            vals['vehicle_mix']={kind:st.number_input(label,min_value=0.0,max_value=1.0,value=float(vals['vehicle_mix'][kind]),step=.05,key='w_mix_'+kind)
                for kind,label in [('car','승용차 비율'),('bus','버스 비율'),('truck','트럭 비율')]}
    
    c=Config(approaches=approaches,**vals)
    st.session_state["scenario_config"]=c.to_dict()
else:
    c=defaults
    with st.sidebar:
        st.caption("도시 사례 · 고정 실행 기록")
        st.markdown("**대구 범어네거리**")
        st.caption("SUMO 1.28 · seed 2026\n\n실제 도로 형상 / 합성 수요\n\n기본 모델의 입력값과 독립된 사례입니다.")

analysis=calculate(c)
errors=validate(c)
valid=not any(errors.values())
theme.heading(view)
if view=='대구 범어네거리':city_panel()
if view=='전후 비교':
    cols=st.columns(3)
    for col,sc in zip(cols,analysis):
        with col:
            if sc["rows"]:
                worst=max(sc["rows"],key=lambda x:x["vc"])
                st.metric(f"{sc['title']} · 최대 v/c",f"{worst['vc']:.3f}")
                st.caption(f"{worst['label']} · 총 유입 {sum(r['volume'] for r in sc['rows']):,.0f}대/시간")
            else:
                st.metric(f"{sc['title']} · 최대 v/c","—")
                for message in sc["errors"]:st.error(message)
    left,right=st.columns([1,1.4])
    with left:
        choice=st.radio("교차로에 표시할 상황",range(3),format_func=lambda i:analysis[i]["title"],index=2,horizontal=True,key="diagram_scenario")
        st.image(intersection(c,analysis[choice]),width="stretch")
    with right:
        st.subheader("방향별 수요 / 처리능력")
        st.plotly_chart(comparison_chart(analysis),width="stretch",key="vc_chart")
        st.caption("v/c > 1은 가정상 처리능력 초과입니다. 지체시간·혼잡등급·LOS가 아닙니다.")
    if analysis[1]["rows"] and analysis[2]["rows"]:
        delta=[dict(진입=LABELS[a["direction"]],처리능력변화=round(b["capacity"]-a["capacity"],2),
                    입주후_vc=round(a["vc"],3),후보_vc=round(b["vc"],3))
               for a,b in zip(analysis[1]["rows"],analysis[2]["rows"])]
        st.subheader("한 방향의 변화, 다른 방향의 영향")
        st.dataframe(pd.DataFrame(delta),hide_index=True,width="stretch")
        st.caption("같은 입주 후 수요에서 신호만 바꾼 결과입니다. 후보안의 개선을 보장하지 않습니다.")
    flat=[dict(상황=sc["title"],방향=r["label"],교통량=r["volume"],처리능력=round(r["capacity"],2),
               vc=round(r["vc"],4)) for sc in analysis for r in sc["rows"]]
    st.subheader("세 상황 상세 비교")
    st.dataframe(pd.DataFrame(flat),hide_index=True,width="stretch")
    if valid:
        st.download_button("입력·공식 계산 JSON 저장",json.dumps(dict(config=c.to_dict(),analytic=analysis),ensure_ascii=False,indent=2),
                           file_name="traffic_analytic.json",mime="application/json")
    with st.expander("조건을 만족하는 신호 후보 찾기"):
        st.write("1초 간격의 후보 중 최대 v/c가 작은 순서입니다. 수학적 탐색이며 학습형 AI가 아닙니다.")
        suggestions=candidates(c) if valid else []
        st.dataframe(pd.DataFrame(suggestions),hide_index=True,width="stretch")
        st.caption("원하는 후보의 남북·동서 시간을 왼쪽에 입력한 뒤 SUMO에서 다시 검증하세요.")

@st.cache_data(show_spinner=False)
def archive_bytes(folder,modified):
    data=io.BytesIO()
    with zipfile.ZipFile(data,"w",zipfile.ZIP_DEFLATED) as z:
        for f in Path(folder).rglob("*"):
            if f.is_file() and f.suffix in (".json",".xml",".csv",".log",".gz"):
                z.write(f,f.relative_to(folder))
    return data.getvalue()

@st.fragment(run_every="2s")
def sumo_panel(config,is_valid):
    job=st.session_state.get("job")
    running=job is not None and job.poll() is None
    a,b=st.columns([3,1])
    def request_run():
        st.session_state["job_requested"]=True
    def request_cancel():
        Path(st.session_state["job_folder"],"CANCEL").touch()
    a.button("세 시나리오 SUMO 실행",type="primary",disabled=not is_valid or running,width="stretch",on_click=request_run)
    # Consume an explicit click once, even across fragment/full reruns.
    if st.session_state.pop("job_requested",False) and is_valid and not running:
        folder=new_folder(EXPERIMENTS)
        folder.mkdir(parents=True)
        write_json(folder/"inputs.json",config.to_dict())
        log=(folder/"worker.log").open("w",encoding="utf-8")
        env=dict(os.environ,PYTHONUTF8="1",PYTHONIOENCODING="utf-8")
        proc=subprocess.Popen([sys.executable,"-X","utf8","-m","traffic.experiment","--config",str(folder/"inputs.json"),"--output",str(folder)],
                              cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,env=env,
                              creationflags=subprocess.CREATE_NO_WINDOW if os.name=="nt" else 0)
        log.close()
        st.session_state["job"]=proc;st.session_state["job_folder"]=str(folder)
        st.rerun()
    b.button("실행 중단",disabled=not running,width="stretch",on_click=request_cancel)
    if not is_valid: st.warning("왼쪽 입력 오류를 수정하면 SUMO를 실행할 수 있습니다.")
    folder=Path(st.session_state.get("job_folder",EXPERIMENTS/"baseline_v2"))
    statusfile=folder/"status.json"
    if statusfile.exists():
        status=json.loads(statusfile.read_text(encoding="utf-8"))
        st.caption(f"실행 상태: {status['message']} · {folder.name}")
        if running:
            st.progress(min(status.get("completed",0)/3,.99))
        elif status["state"]=="running":
            st.warning("완료 기록이 없는 실행입니다. 브라우저를 새로 열었거나 작업이 종료되었을 수 있습니다. 실행 로그와 프로세스를 확인하세요.")
        elif status["state"] in ("failed","cancelled","needs_review"):
            st.warning(status["message"])
            if (folder/"error.log").exists():st.code((folder/"error.log").read_text(encoding="utf-8"))
    history=sorted([f.parent for f in EXPERIMENTS.glob("*/comparison.json") if f.parent.name!="smoke_run"],key=lambda p:p.stat().st_mtime,reverse=True)
    if history:
        selected=st.selectbox("저장된 실험",history,format_func=lambda p:p.name,key="history_select")
        def show_record():
            st.session_state["job_folder"]=str(selected)
        st.button("선택한 기록 보기",disabled=running,on_click=show_record)
    datafile=folder/"comparison.json"
    if not datafile.exists():
        st.info("실행 후 실제 SUMO 결과가 여기에 나타납니다. 처음에는 왼쪽의 ‘빠른 확인’으로 연결을 확인할 수 있습니다.")
        return
    data=json.loads(datafile.read_text(encoding="utf-8"))
    if not is_valid or Config.from_dict(data["config"]).fingerprint()!=config.fingerprint():
        st.warning("현재 입력과 다른 이전 실행 결과입니다. 현재 조건의 결과를 보려면 다시 실행하세요.")
    st.caption(f"결과 입력: 시드 {data['config']['seed']} · 준비 {data['config']['warmup']}초 / 관측 {data['config']['duration']}초 / 추가 종료 {data['config']['drain']}초")
    r=data["sumo"]
    if any(x["anomaly_count"] or x["collisions"] or x["teleports"] for x in r):
        st.error("이 실행은 동작 이상이 발견돼 해석을 보류해야 합니다. 원시 기록을 확인하세요.")
    else:st.success("세 시나리오 완료 · 신호·보행 동작 검사 이상 0건")
    st.caption("동작 검사 통과는 현장 안전 검증을 의미하지 않습니다.")
    m=st.selectbox("비교 지표",["time_loss","waiting_time","mean_halting","crossed_in_window"],
                   format_func=lambda x:{"time_loss":"완료 차량 평균 시간 손실 (초)","waiting_time":"완료 차량 평균 정차대기시간 (초)",
                                         "mean_halting":"관측기간 평균 정지 차량 (대)","crossed_in_window":"관측기간 교차로 통과 차량 (대)"}[x],key="sumo_metric")
    metric_units={"time_loss":"시간 손실 (초/완료 차량)","waiting_time":"정차대기시간 (초/완료 차량)",
                  "mean_halting":"평균 정지 차량 (대)","crossed_in_window":"통과 차량 (대)"}
    st.plotly_chart(sumo_chart(r,m,metric_units[m]),width="stretch",key="sumo_chart")
    rows=[dict(상황=x["scenario"],방향=LABELS[row["direction"]],요청=row["requested"],진입=row["inserted"],
               완료=row["completed"],미진입=row["pending"],미완료=row["unfinished"],
               시간손실_초=round(row["time_loss"],2) if row["time_loss"] is not None else None,
               정차대기_초=round(row["waiting_time"],2) if row["waiting_time"] is not None else None,
               최대정지차량=row["max_halting"]) for x in r for row in x["rows"]]
    st.dataframe(pd.DataFrame(rows),hide_index=True,width="stretch")
    if any(row["pending"]+row["unfinished"] for x in r for row in x["rows"]):
        st.warning("미진입·미완료 차량이 있습니다. 완료 차량의 평균 시간만으로 개선 여부를 판단하지 마세요.")
    st.caption("차량 집계는 관측기간에 출발 예정인 차량 집단 기준입니다. 관측기간 통과량은 별도의 시간창 집계입니다. 최대 정지 차량 수는 대기행렬 길이(m)가 아닙니다.")
    ped=[dict(상황=x["scenario"],보행자등장=x["pedestrian_departed"],횡단진입관측=x["pedestrian_crossed"],
              보행이동완료=x["pedestrian_completed"],충돌=x["collisions"],텔레포트=x["teleports"]) for x in r]
    st.dataframe(pd.DataFrame(ped),hide_index=True,width="stretch")
    a,b=st.columns(2)
    a.download_button("실험 전체 ZIP 저장",archive_bytes(str(folder),datafile.stat().st_mtime_ns),file_name=folder.name+".zip",mime="application/zip")
    b.download_button("비교표 CSV 저장",(folder/"comparison.csv").read_bytes(),file_name="comparison.csv",mime="text/csv")
    st.caption("저장 위치: "+str(folder))

if view=='SUMO 실험':
    st.subheader("같은 차량으로, 신호만 바꿔 실험")
    st.write("입주 후와 신호 후보는 동일한 차량·보행자 파일을 사용합니다. 입력은 즉시 계산하고 SUMO는 실행 버튼으로 시작합니다.")
    sumo_panel(c,valid)

if view=='상세 그래프':
    dashboard(c)
if view=='후보 탐색':
    search_panel(c,valid)
if view=='궤적 재생':
    replay_panel()
if view=='심화 연구':
    advanced_panel()

if view=='계산 공식·가정':
    st.subheader("공식과 검증 조건")
    st.latex(r"c_i=n_i s\frac{G_i-L}{C},\qquad (v/c)_i=\frac{v_i}{c_i}")
    st.write("차로 수 × 차로당 포화교통류율 × 유효녹색 비율로 처리능력을 계산합니다. 유효녹색은 녹색에서 출발 손실을 뺀 근사이며 황색·전적색 중 통과를 제외합니다.")
    st.latex(r"C=G_{NS}+G_{EW}+2(Y+R)")
    st.latex(r"T_{need}=T_{walk}+D/u+M\leq T_{budget}\leq G")
    st.write("보행 필요시간은 진입 허용시간 + 횡단길이/속도 + 소거 여유입니다. SUMO에서 보행 진입을 일찍 닫고 평행 차량 녹색 안에서 횡단을 마칠 시간을 확보합니다.")
    st.write("횡단길이 D는 입력 가정과 생성된 횡단보도 길이 중 긴 값으로 검사합니다. 차로 수 변경 후 다시 확인합니다.")
    st.markdown("[처리능력 공식 참고 · FHWA](https://ops.fhwa.dot.gov/publications/fhwahop08024/chapter3.htm) · [SUMO 지표 정의](https://sumo.dlr.de/docs/Simulation/Output/TripInfo.html)")
    st.subheader("결과의 범위")
    st.write("기본 전후 비교는 가상의 단일 직진 교차로입니다. 회전·인접 교차로와 공개 자료 비교는 심화 연구 화면의 별도 실험입니다. 공식 계산의 포화교통류율은 SUMO 차량 동작에 자동 적용되지 않습니다.")
    st.write("SUMO 시간 손실·정차대기시간은 공식 교통영향평가의 제어지체나 LOS가 아닙니다. 시간 지표는 관측기간 출발 예정 차량 중 종료까지 완료한 차량만 집계합니다.")
    st.write("짧은 실험과 낮은 수요에서는 신호 변경의 효과가 다를 수 있습니다. 비교는 수요 파일·관측시간·시드·미완료 차량 수를 함께 확인해야 합니다.")

if view=='연구 기록':
    st.subheader("연구·검증 기록")
    reports={"범어네거리 통합":"daegu_integration.txt","전체 연구":"research_report.md","회전·인접 교차로":"network_research.md",
             "공개 자료·보행 형상":"advanced_research.md","시간 수요·차종":"profile_mix_research.md",
             "개발 도구·검토 범위":"contributions.md"}
    report_name=st.selectbox("연구 문서",list(reports),key="report_document")
    report=ROOT/"docs"/reports[report_name]
    if report.exists():
        st.download_button("선택 보고서 저장",report.read_bytes(),file_name=report.name,mime="text/markdown")
        st.markdown(report.read_text(encoding="utf-8"))
    else:st.info("연구 실험과 검증 결과를 정리하고 있습니다.")
    movie=ROOT/"docs/demo/traffic_comparison.mp4"
    if movie.exists():
        with st.expander("실제 SUMO 기록 시연 영상",expanded=False):
            st.video(str(movie))
            st.caption("30초 영상 · 실제 180초를 6배속 재생 · 별도 검증 시드 701 · 선택 후보 49/31초. 누적 통과량은 준비기간 900초를 포함한 실험 시작부터 집계합니다.")
            st.download_button("시연 영상 MP4 저장",movie.read_bytes(),file_name=movie.name,mime="video/mp4")
    st.caption("기본 교차로는 합성 실험이며 공개 궤적 비교는 별도 연구입니다. 현장 성능은 검증하지 않았습니다.")

