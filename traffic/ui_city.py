"""City case workspace. Frozen outputs, explicit cohorts, no basic-model coupling."""
from pathlib import Path
import hashlib,json
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from .city import CASE,NAMES,SCOPES,load_case
from .theme import COLORS
from .dashboard import finish

ASSETS=Path(__file__).resolve().parents[1]/'frontend'
FIGURES=[
 ('01_network_atlas','도로망과 수요 유입 위치'),('02_speed_comparison','시나리오별 도로 평균속도'),
 ('03_congestion_and_tradeoff','누적 정지와 방향별 상충 관계'),('04_junction_closeup','같은 시각의 차량·신호'),
 ('05_isometric_city','OSM 건물 평면 기반 입체 모형'),('06_metrics_and_completion','성과와 미완료 차량'),
 ('07_time_space_trajectories','시간–공간 궤적'),('08_signal_plan','신호 현시 배분'),
 ('09_native_sumo_overview','SUMO GUI 원본 · 도로망'),('10_native_sumo_closeup','SUMO GUI 원본 · 교차로 확대')]

@st.cache_data(show_spinner=False)
def cached_case(version):return load_case()

@st.cache_resource
def renderer(version):
    tag=hashlib.sha256(str(version).encode()).hexdigest()[:10]
    return st.components.v2.component('daegu_workspace_'+tag,
        html=(ASSETS/'city.html').read_text(encoding='utf-8'),
        css=(ASSETS/'city.css').read_text(encoding='utf-8'),js=(ASSETS/'city.js').read_text(encoding='utf-8'))

def table_for(data,scope):
    return pd.DataFrame([{'시나리오':NAMES[s],'출발 요청 (대)':r['counts']['requested'],
        '완료 (대)':r['counts']['completed'],'도로 안 미완료 (대)':r['counts']['running'],
        '도로 밖 미진입 (대)':r['counts']['waiting'],'완료율 (%)':round(100*r['completion_rate'],2),
        '완료 차량 평균 timeLoss (초)':round(r['mean_time_loss_s'],2),
        '완료 차량 평균 정지시간 (초)':round(r['mean_waiting_time_s'],2)}
        for s,r in data['metrics']['scopes'][scope].items()])

def result_charts(data,scope):
    runs=data['metrics']['scopes'][scope];figs={}
    f=go.Figure()
    for k,title,col in [('completed','완료','#3267c8'),('running','도로 안 미완료','#c58a3b'),('waiting','도로 밖 미진입','#a55c65')]:
        f.add_bar(x=list(NAMES.values()),y=[runs[s]['counts'][k] for s in NAMES],name=title,marker_color=col,
                  text=[runs[s]['counts'][k] for s in NAMES],textposition='auto')
    f.update_layout(barmode='stack');figs['종료 시 차량 상태']=finish(f,'대 · 선택한 출발 예정 집단')
    f=go.Figure()
    for s in NAMES:
        vals=sorted(runs[s]['completed_time_loss_s'])
        f.add_scatter(x=vals,y=[100*(i+1)/len(vals) for i in range(len(vals))],mode='lines',name=NAMES[s],line_color=COLORS[s])
    f.update_xaxes(title='완료 차량 timeLoss (초)');figs['완료 차량 시간 손실 분포']=finish(f,'누적 비율 (%)')
    f=go.Figure()
    for s in NAMES:
        f.add_bar(x=['북측','남측','동측','서측'],y=[runs[s]['directions'][d]['mean_time_loss_s'] for d in 'NSEW'],
                  name=NAMES[s],marker_color=COLORS[s])
    f.update_layout(barmode='group');figs['진입 방향별 시간 손실']=finish(f,'완료 차량 평균 timeLoss (초)')
    return figs

def city_panel():
    data=cached_case((CASE/'derived_metrics.json').stat().st_mtime_ns)
    st.html('<div class="case-badges"><span>OSM 도로 형상</span><span>합성 수요</span><span>1개 시드 · 단일 조정안</span><span>현장·보행 미검증</span></div>')
    page=st.radio('범어네거리 작업', ['지도·궤적','실험 결과','계산 기준·검증','시각화 자료'],horizontal=True,key='city_page',label_visibility='collapsed')
    if page=='지도·궤적':
        st.caption('저장된 실행 기록 · 기본 2,650대/시간 + 남측 추가 600대/시간 · 실제 입주 사업이나 현장 수요 자료가 아닙니다.')
        version=tuple((ASSETS/name).stat().st_mtime_ns for name in ['city.html','city.css','city.js'])
        renderer(version)(data={'base':'/app/static/daegu/'},key='daegu_actual_replay')
        st.caption('차량 위치·속도·신호: 저장된 SUMO 기록, 4초 간격, 위치 보간 없음. 입체 모형: 별도 2.5D 렌더러이며 898개 건물 중 699개 높이는 12m 가정입니다.')
        st.html('<div class="case-note"><strong>해석 기준</strong> 지도 색상은 세 상황에 공통 범위를 사용합니다. 평균속도·누적 정지 지도는 300–1,500초 집계이며, 차량과 하단 대수는 선택 시각의 순간값입니다. 신호 조정안을 최적안 또는 실제 운영안으로 판단하지 않습니다.</div>')
    elif page=='실험 결과':results_panel(data)
    elif page=='계산 기준·검증':method_panel(data)
    else:gallery_panel()

def results_panel(data):
    scope=st.selectbox('차량 집계 기준',list(SCOPES),format_func=lambda s:SCOPES[s],key='city_cohort')
    runs=data['metrics']['scopes'][scope];a,b=runs['after'],runs['adjusted']
    st.html(f'<div class="data-scope"><strong>{SCOPES[scope]}</strong> · 예정 출발 시각으로 집단을 고정합니다. 최종 상태는 t=2,100초 기준입니다.</div>')
    cols=st.columns(3)
    cols[0].metric('조정안 완료 차량',f"{b['counts']['completed']:,}대",f"{b['counts']['completed']-a['counts']['completed']:+,}대 · 입주 후 대비",delta_color='off')
    cols[1].metric('조정안 미진입 차량',f"{b['counts']['waiting']:,}대",f"{b['counts']['waiting']-a['counts']['waiting']:+,}대 · 입주 후 대비",delta_color='off')
    cols[2].metric('조정안 완료 차량 timeLoss',f"{b['mean_time_loss_s']:.2f}초",f"{b['mean_time_loss_s']-a['mean_time_loss_s']:+.2f}초 · 입주 후 대비",delta_color='off')
    st.info('종료 시 미완료·미진입이 남아 있습니다. 완료 차량의 구성도 달라 평균 timeLoss만으로 전체 차량의 개선을 판정할 수 없습니다. 기본 모델의 후보 순위에 이 결과를 합산하지 않습니다.')
    frame=table_for(data,scope);st.dataframe(frame,hide_index=True,width='stretch')
    st.download_button('선택 기준 결과 CSV',frame.to_csv(index=False).encode('utf-8-sig'),file_name=f'daegu_{scope}_metrics.csv',mime='text/csv')
    figures=result_charts(data,scope)
    a,b=st.columns(2)
    for col,(title,f) in zip([a,b],list(figures.items())[:2]):
        with col:st.subheader(title);st.plotly_chart(f,width='stretch',key='city_'+title)
    st.caption('분포의 분모는 각 상황에서 완료한 차량 수입니다. 미완료·미진입을 0초로 처리하지 않습니다.')
    st.subheader('진입 방향별 시간 손실')
    st.plotly_chart(figures['진입 방향별 시간 손실'],width='stretch',key='city_direction')
    st.divider();st.subheader('네트워크 전체 · 관측 구간 정지 차량')
    st.caption('이하 지표는 위 차량 집계 선택과 독립적입니다. 300 ≤ t < 1,500초, 2초 간격의 네트워크 전체 차량 표본을 사용합니다.')
    f=go.Figure();rows=[]
    for s in NAMES:
        r=data['original']['results'][s]
        f.add_scatter(x=[v[0] for v in r['series']],y=[v[2] for v in r['series']],name=NAMES[s],mode='lines',line_color=COLORS[s])
        rows.append({'상황':NAMES[s],'평균 정지 차량 (대)':round(r['mean_stopped_vehicles'],2)})
    f.update_xaxes(title='시뮬레이션 시각 (초)');st.plotly_chart(finish(f,'속도 < 0.1m/s 차량 수'),width='stretch',key='city_stop_series')
    st.dataframe(pd.DataFrame(rows),hide_index=True,width='stretch')
    st.caption('평균 정지 차량 = 각 표본 시각의 정지 차량 수 합 / 표본 수. 대기행렬 길이 또는 교차로 공식 지체시간이 아닙니다.')

def method_panel(data):
    st.subheader('지표의 분모와 시간 범위')
    definitions=[
      ['출발 요청·완료·미완료·미진입','전체 [0,1500) 또는 관측 예정 [300,1500)','예정 출발 시각으로 집단 선택 → 종료 2100초 상태 집계. 요청 = 완료 + 미완료 + 미진입.'],
      ['완료율','선택 집단의 출발 요청','완료 차량 수 / 출발 요청 수.'],
      ['평균 timeLoss·정지시간','선택 집단 중 종료 시 완료 차량만','tripinfo의 timeLoss 또는 waitingTime 합 / 완료 수. 미완료·미진입은 평균에서 제외.'],
      ['평균 정지 차량','관측 [300,1500), 2초 간격 · 네트워크 전체','순간 속도 <0.1m/s 차량 수의 산술 평균. 준비시간 출발 차량도 관측 시 도로 안에 있으면 포함.'],
      ['도로 평균속도 지도','관측 [300,1500)의 edgeData','Σ(speed × sampledSeconds) / Σ sampledSeconds × 3.6. 관측 없는 도로는 회색.'],
      ['도로 누적 정지 지도','관측 [300,1500)의 edgeData','도로별 waitingTime 합 / 60 (차량·분). 차량당 평균이 아님. 세 시나리오 공통 색 범위.'],
      ['궤적 화면의 차량·정지 대수','선택 프레임 300..1496초 · 4초 간격','프레임 내 차량 수와 속도 <0.1m/s 차량 수. 결과 그래프의 시간 평균과 다름.']]
    st.dataframe(pd.DataFrame(definitions,columns=['지표','계산 대상·구간','계산 방법']),hide_index=True,width='stretch')
    with st.expander('지표별 계산식과 집계 설명 전체 보기'):
        for title,population,method in definitions:
            st.markdown(f'**{title}**  \n대상: {population}  \n{method}')
    st.subheader('기본 모델과 도시 사례의 검증 범위')
    st.dataframe(pd.DataFrame([
        ['도로·수요','합성 단일 직진 교차로','OSM 자동 변환 도로망 + 합성 수요'],
        ['공식 v/c','가정상 용량 공식·입력 신호 합계 검사','동일 공식을 범어 도로망에 적용하지 않음'],
        ['보행','기본 모델의 입력·생성 형상·실행 검사','보행 미모사, 보행 횡단시간 미검증'],
        ['후보 비교','기본 실험의 완료 상태·별도 시드 검증 확인','시드 2026 한 번, 녹색 배분 단일 후보'],
        ['실행·자료 무결성','각 실험에 저장된 검증 기록','원본 구조 검사 23개 + 통합 원본 해시·집계 대조'],
        ['현장 적용·LOS','현장 보정·공식 LOS 미검증','차로·회전 연결·신호·수요 현장 미검증']],columns=['항목','기본 교차로','대구 범어네거리']),hide_index=True,width='stretch')
    st.info('범어네거리의 충돌·순간이동 기록이 0인 것은 이번 실행의 사건 집계입니다. 교통안전성 또는 실제 도로 운영 가능성을 입증하지 않습니다. 모든 시나리오에 미완료 차량이 있어 최적안으로 선정하지 않습니다.')
    st.subheader('실험 조건')
    st.write('신호 주기 90초. 기존 녹색 15 / 17 / 17 / 17초 → 후보 16 / 12 / 21 / 17초. 황색 6초 × 4, 현시 상태·순서 유지. 입주 후·조정안은 동일 차량 파일을 사용합니다.')
    st.write('수요 생성 0–1,500초 · 준비 300초 · 관측 300–1,500초 · 종료 2,100초. 버스·트럭은 형상·길이를 구분한 합성 차종이며 실제 노선·운행 자료가 아닙니다.')
    with st.expander('원본 구조 검사 23개 · 현장 검증과 구분'):
        st.dataframe(pd.DataFrame(data['audit']['checks']),hide_index=True,width='stretch')
    with st.expander('원본 설정 및 재현 자료'):
        display={**data['experiment'],'scenarios':{s:{**r,'label':NAMES[s]} for s,r in data['experiment']['scenarios'].items()}}
        st.json(display)
        for rel,title in [('derived_metrics.json','통합 집계 JSON'),('import_manifest.json','원본 가져오기 해시 목록'),('output/audit.json','원본 구조 검사 JSON')]:
            st.download_button(title,(CASE/rel).read_bytes(),file_name=Path(rel).name,mime='application/json',key='download_'+rel)
    st.markdown('출처: [OpenStreetMap 및 ODbL](https://www.openstreetmap.org/copyright) · [SUMO tripinfo](https://sumo.dlr.de/docs/Simulation/Output/TripInfo.html) · [SUMO edgeData](https://sumo.dlr.de/docs/Simulation/Output/Lane-_or_Edge-based_Traffic_Measures.html)')

def gallery_panel():
    st.caption('기존 원본 시각화 10종을 보존했습니다. 원본 수치 비교 도표는 전체 출발 요청 기준이며, 관측기간 출발 예정 집계는 실험 결과 화면에서 확인하세요.')
    name=st.selectbox('자료 선택',[x[0] for x in FIGURES],format_func=lambda n:dict(FIGURES)[n],key='city_figure')
    path=CASE/'figures'/f'{name}.png'
    st.image(str(path),caption=dict(FIGURES)[name],width='stretch')
    a,b=st.columns(2)
    a.download_button('PNG 원본 다운로드',path.read_bytes(),file_name=path.name,mime='image/png')
    pdf=path.with_suffix('.pdf')
    if pdf.exists():b.download_button('PDF 원본 다운로드',pdf.read_bytes(),file_name=pdf.name,mime='application/pdf')
    st.caption('입체 모형은 별도 렌더러입니다. 09·10번은 실제 SUMO GUI 캡처이며 차량 색은 해당 GUI의 기본 표시 설정입니다.')
    st.subheader('세 상황 동기화 재생')
    video=CASE/'output/daegu_comparison_replay.mp4';st.video(str(video))
    st.download_button('비교 영상 MP4 다운로드',video.read_bytes(),file_name=video.name,mime='video/mp4')
