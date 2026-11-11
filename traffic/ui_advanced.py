"""Saved advanced research evidence, explicitly separated from the synthetic app."""
from pathlib import Path
import json
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from .dashboard import finish

ROOT=Path(__file__).resolve().parents[1]

def read(path):return json.loads(path.read_text(encoding='utf-8'))

def public_panel():
    folder=ROOT/'experiments/public_calibration_v2'
    if not (folder/'summary.json').exists():st.info('공개 자료 보정 실험을 집계하고 있습니다.');return
    s=read(folder/'summary.json');protocol=s['protocol'];validation=s['validation']
    st.subheader('공개 실측 자료로 차량 추종을 비교')
    st.write('NGSIM Lankershim 공개 표본에서 앞차의 관측 이동을 재생하고, 뒤차는 처음 상태만 맞춘 뒤 SUMO가 스스로 주행하게 했습니다. 왼쪽의 가상 교차로 입력과 독립된 저장 실험입니다.')
    st.caption('보정 차량 11대 · 별도 검증 차량 10대 · 매개변수 조합 24개 · 시간 간격 0.1초 · 차량별 오차에 같은 가중치')
    params=s['frozen']['parameters'];same=params==protocol['baseline']
    if same:st.info('이 표본과 탐색 범위에서는 기준 매개변수가 선택됐습니다. 추가 성능 개선은 확인되지 않았습니다.')
    else:st.info('보정 자료에서 선택을 고정한 뒤 별도 차량에서 오차를 비교했습니다.')
    st.write(f"선택값: 시간 간격 tau {params['tau']:g}초 · 최소 간격 {params['minGap']:g}m · 가속도 {params['accel']:g}m/s²")
    a,b=st.columns(2)
    a.metric('별도 검증 · 차량별 속도 RMSE 평균',f"{validation['calibrated']['mean_speed_rmse_mps']:.3f}m/s")
    b.metric('별도 검증 · 차량별 차간격 RMSE 평균',f"{validation['calibrated']['mean_gap_rmse_m']:.3f}m")
    st.caption('RMSE는 관측값과 예측값 차이의 제곱평균제곱근이며 작을수록 일치도가 높습니다. 차량 전체 프레임을 합친 RMSE와 구분합니다.')
    grid=pd.read_csv(folder/'calibration.csv')
    fig=go.Figure()
    for accel in sorted(grid.accel.unique()):
        for gap in sorted(grid.minGap.unique()):
            d=grid[(grid.accel==accel)&(grid.minGap==gap)].sort_values('tau')
            fig.add_trace(go.Scatter(x=d.tau,y=d.score,mode='lines+markers',name=f'가속도 {accel:g} · 간격 {gap:g}m'))
    fig.update_layout(title='보정 자료에서의 후보 오차',xaxis_title='tau (초)')
    st.plotly_chart(finish(fig,'속도 RMSE / 2 + 간격 RMSE / 10',400),width='stretch',key='public_grid')
    st.caption('선택 점수의 정규화 단위는 속도 2m/s·간격 10m로 보정 전에 고정했습니다. 위 그래프에는 검증 자료를 사용하지 않았습니다.')
    per=pd.DataFrame(validation['calibrated']['trajectories'])
    fig=go.Figure(go.Bar(x=per.follower.astype(str),y=per.gap_rmse_m,name='차간격 RMSE',marker_color='#087f79'))
    fig.update_layout(title='검증 차량별 차간격 오차',xaxis_title='공개 자료의 차량 ID',xaxis_type='category')
    st.plotly_chart(finish(fig,'RMSE (m)'),width='stretch',key='public_errors')
    target=st.selectbox('검증 차량 궤적',protocol['validation'],key='public_follower')
    prediction=pd.read_csv(folder/'validation/calibrated/predictions.csv')
    d=prediction[prediction.follower==target]
    for metric,label,unit in [('speed','속도','m/s'),('gap','차간격','m')]:
        suffix='mps' if metric=='speed' else 'm'
        fig=go.Figure()
        for kind,title,color,dash in [('observed','실측','#c57930','solid'),('predicted','SUMO 예측','#087f79','dash')]:
            fig.add_trace(go.Scatter(x=d.time_s,y=d[f'{kind}_{metric}_{suffix}'],name=title,mode='lines',line=dict(color=color,dash=dash)))
        fig.update_layout(title=f'차량 {target} · 실측과 예측 {label}',xaxis_title='추종 구간 시작 후 시간 (초)')
        st.plotly_chart(finish(fig,f'{label} ({unit})'),width='stretch',key='public_'+metric)
    with st.expander('자료 처리와 해석 범위'):
        q=validation['calibrated']['preprocessing']
        st.write('앞차 위치가 측정 흔들림으로 뒤로 움직이는 구간에는 누적 최댓값을 적용했습니다. 뒤차의 실측 속도·간격은 수정하지 않았습니다.')
        st.write(f"이 검증 표본의 최대 앞차 위치 수정량: {max(x['monotonic_adjustment_max_m'] for x in q.values()):.3f}m. 최대 위치 재생 오차: {validation['calibrated']['leader_position_max_error_m']:.2e}m.")
        st.write(f"강제로 관측 궤적을 따라가는 앞차의 급제동 경고 {validation['calibrated']['leader_emergency_warnings']}건, 자율 주행 뒤차 경고 {validation['calibrated']['follower_emergency_warnings']}건. 충돌·순간이동 {validation['calibrated']['collisions']}·{validation['calibrated']['teleports']}건.")
        st.write('원자료의 측정 잡음으로 앞차 가속도가 비현실적으로 커지는 구간이 남습니다. 동일 도로·겹치는 시간대의 작은 표본이며 차량 관계도 일부 연결됩니다. 새로운 현장에 대한 독립 검증이 아닙니다.')
        st.write('교차로 신호·차로 변경·아파트 통행발생량은 이 실험에서 보정하지 않았습니다. 선택값을 가상 교차로의 검증된 현장 매개변수로 자동 적용하지 않습니다.')
        st.dataframe(pd.DataFrame.from_dict(q,orient='index'),width='stretch')
    a,b=st.columns(2)
    a.download_button('보정·검증 결과 JSON',(folder/'summary.json').read_bytes(),file_name='public_calibration_summary.json',mime='application/json')
    b.download_button('검증 궤적 CSV',(folder/'validation/calibrated/predictions.csv').read_bytes(),file_name='ngsim_validation_predictions.csv',mime='text/csv')
    st.markdown('[원자료 · US DOT/FHWA NGSIM](https://data.transportation.gov/d/8ect-6jqj) · [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/)')
    st.caption('CSV는 NGSIM 표본의 SI 단위 변환·구간 추출 자료와 SUMO 예측을 결합한 파생 자료입니다. 공유 시 출처·변경 내용·같은 라이선스를 함께 표시하세요.')

def pedestrian_panel():
    path=ROOT/'experiments/pedestrian_geometry/audit.json'
    if not path.exists():st.info('보행 형상 검증을 실행하고 있습니다.');return
    a=read(path)
    st.subheader('입력 횡단길이와 생성 형상의 관계')
    st.write('입력한 횡단길이는 설계 가정입니다. SUMO 횡단보도는 생성된 차로 폭을 따르며, 시간 검사는 두 길이 중 긴 값을 사용합니다.')
    rows=[]
    for s in a['sweeps']:
        rows.append(dict(방향별차로=s['lanes'],보행속도=s['speed_mps'],입력길이_m=s['assumed_m'],
            생성길이_m=s['generated_m']['ns'],적용길이_m=s['applied_m']['ns'],
            필요시간_초=s['required_seconds']['ns'],배정시간_초=s['budget_seconds']['ns'],
            반초부족시차단=s['half_second_short_rejected']))
    d=pd.DataFrame(rows);st.dataframe(d,hide_index=True,width='stretch')
    fig=go.Figure();base=d[d.보행속도==1]
    for field,label,color in [('입력길이_m','입력 가정','#778b86'),('생성길이_m','SUMO 형상','#c57930'),('적용길이_m','검사에 적용','#087f79')]:
        fig.add_trace(go.Bar(x=base.방향별차로,y=base[field],name=label,marker_color=color))
    fig.update_layout(barmode='group',xaxis_title='방향별 직진 차로 수',title='검사에 적용되는 횡단길이')
    st.plotly_chart(finish(fig,'길이 (m)'),width='stretch',key='geometry_lengths')
    st.write('3개 형상·속도 조건 × 3개 상황, 총 9회 SUMO 실행에서 매회 보행자 12명의 이동 완료와 네 횡단보도 사용을 확인했습니다. 신호 진입·점유 검사 이상은 0건입니다.')
    labels={'assumed_conservative':'입력 가정이 더 긴 경우','geometry_matched':'입력과 형상이 같은 경우','wide_slow':'넓은 횡단·느린 보행'}
    st.dataframe(pd.DataFrame([dict(사례=labels[r['case']],직진차로=r['lanes'],보행속도_mps=r['speed'],
        입력길이_m=r['assumed_m'],생성길이_m=r['geometry_m']['ns'],배정시간_초=r['ns_seconds'],
        실행횟수=r['executed_scenarios'],회당완료보행자=r['pedestrian_completion_per_run'],
        신호검사이상=r['signal_entry_and_occupancy_anomalies']) for r in a['runtime_cases']]),hide_index=True,width='stretch')
    st.caption('고정 보행속도와 합성 형상의 동작 검사입니다. 다양한 보행행태나 현장 안전을 검증한 결과는 아닙니다.')
    st.download_button('보행 형상 검증 JSON',path.read_bytes(),file_name='pedestrian_geometry_audit.json',mime='application/json')

def advanced_panel():
    mode=st.radio('심화 연구 종류',['공개 실측 추종 비교','보행 형상 검증','회전·인접 교차로','대기행렬 검증'],horizontal=True,key='advanced_mode')
    if mode=='공개 실측 추종 비교':public_panel()
    elif mode=='보행 형상 검증':pedestrian_panel()
    else:
        from .ui_networks import network_panel,queue_panel
        if mode=='회전·인접 교차로':network_panel()
        else:queue_panel()
