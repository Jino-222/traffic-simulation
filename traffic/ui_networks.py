"""Visual inspection of saved turning, corridor, and queue verification cases."""
from pathlib import Path
import json
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from .dashboard import finish
from .research.networks import load_info

ROOT=Path(__file__).resolve().parents[1]
NAMES={'before':'입주 전','after':'입주 후','adjusted':'녹색 배분 조정',
       'downstream_bottleneck_150':'하류 녹색 축소 · 150m','downstream_bottleneck_75':'하류 녹색 축소 · 75m'}
def label(case):return NAMES.get(case,'시차 '+str(int(case.split('_')[1]))+'초' if case.startswith('offset_') else case)
def read(path):return json.loads(path.read_text(encoding='utf-8'))

def map_figure(info,flow):
    fig=go.Figure();selected=info['flows'][flow];highlight={e+'_'+str(selected['depart_lane']) for e in selected['edges']}
    for frm,to in zip(selected['edges'],selected['edges'][1:]):
        for t in info['tls'].values():
            for l in t['links'].values():
                if l['from_edge']==frm and l['to_edge']==to:highlight.update(l['internal_chain'])
    for lane in info['geometry']['lanes']:
        selected_lane=lane['id'] in highlight
        fig.add_trace(go.Scatter(x=[p[0] for p in lane['shape']],y=[p[1] for p in lane['shape']],mode='lines',
            line=dict(color='#087f79' if selected_lane else '#d0d9d5',width=5 if selected_lane else (2 if not lane['pedestrian'] else 1)),
            name=lane['id'],showlegend=False,hovertemplate=lane['id']+'<extra></extra>'))
    for j in info['geometry']['junctions']:
        if j['id'] in info['tls']:fig.add_annotation(x=j['x'],y=j['y'],text=j['id'],showarrow=False,bgcolor='white')
    fig.update_layout(title='생성 도로망과 선택 이동류: '+flow,xaxis_title='모델 좌표 x (m)',showlegend=False)
    fig.update_yaxes(scaleanchor='x',scaleratio=1)
    return finish(fig,'모델 좌표 y (m)',430)

def network_panel():
    folder=ROOT/'experiments/network_study_v1'
    path=folder/'summary.json'
    if not path.exists():
        st.info('회전·인접 교차로 반복 실험을 진행하고 있습니다.')
        if (folder/'status.json').exists():st.write(read(folder/'status.json'))
        return
    s=read(path);discovery=read(folder/'discovery.json')
    choice=st.radio('도로망 연구',['좌·우회전 교차로','인접 교차로와 하류 막힘'],horizontal=True,key='network_family')
    family='turning' if choice=='좌·우회전 교차로' else 'corridor'
    rows=[r for r in discovery['records'] if r['family']==family]
    table=[r for r in s['discovery'] if r['family']==family]
    if family=='turning':
        st.subheader('12개 이동류와 보행 전용 현시')
        st.write('각 방향에 우회전·직진·좌회전 전용 차로를 두었습니다. 한 진입 방향씩 차량을 보내고, 모든 차량 신호가 적색인 보행 전용 구간을 따로 배정했습니다.')
        st.caption('기존 차량 250대/시간씩 · 추가 북 150·남 100·동 50·서 50대/시간 · 우/직/좌 20/60/20% · 동일 주기 128.5초')
        st.write('기준 녹색은 북·동·남·서 18/18/18/18초, 비교안은 24/14/20/14초입니다. 비교안은 사전 지정한 가설이며 최적 신호를 뜻하지 않습니다.')
        order=['before','after','adjusted'];by={r['case']:r for r in table}
        change=by['adjusted']['mean_time_loss']-by['after']['mean_time_loss']
        st.info(f'이 사전 지정 조정안의 평균 시간 손실 변화: {change:+.2f}초. '+('평균이 증가해 개선안으로 추천하지 않습니다.' if change>0 else '평균은 감소했으며 이동류별 불이익도 함께 확인해야 합니다.'))
        fig=go.Figure(go.Bar(x=[label(k) for k in order],y=[by[k]['mean_time_loss'] for k in order],marker_color=['#778b86','#c57930','#087f79']))
        fig.update_layout(title='3개 시드 평균 · 입주와 신호 배분 영향')
        st.plotly_chart(finish(fig,'완료 차량 평균 시간 손실 (초)'),width='stretch',key='turning_overview')
    else:
        st.subheader('교차로 시차와 하류 처리능력')
        st.write('150m 간격의 두 직진 교차로에서 J1의 신호 시작 시각을 바꿨습니다. 같은 차량 수요로 0·11·22·45·67초를 비교하고, 선택을 고정한 뒤 다른 시드에서 재검증했습니다.')
        st.caption('주기 90초 · 정상 남북/동서 40/40초 · 하류 제한 사례 J1은 65/15초 · 보행 신호 포함 · 관측 30분, 준비 5분, 추가 종료 10분')
        offset=int(s['frozen']['offset_seconds'])
        st.info(f'탐색 범위에서 선택한 J1 시차: {offset}초. 검증 시드는 {s["protocol"]["validation_seeds"]}이며 선택에 사용하지 않았습니다.')
        fig=go.Figure()
        for seed in s['protocol']['discovery_seeds']:
            cases=sorted([r for r in rows if r['seed']==seed and r['case'].startswith('offset_')],key=lambda r:int(r['case'].split('_')[1]))
            fig.add_trace(go.Scatter(x=[int(r['case'].split('_')[1]) for r in cases],y=[r['mean_time_loss'] for r in cases],mode='lines+markers',name=f'시드 {seed}'))
        fig.update_layout(title='신호 시차별 실제 실행 결과',xaxis_title='J1 주기 시작 지연 (초)')
        st.plotly_chart(finish(fig,'완료 차량 평균 시간 손실 (초)'),width='stretch',key='corridor_offsets')
        st.dataframe(pd.DataFrame([dict(검증후보=label(r['case']),평균시간손실_초=r['mean_time_loss'],미진입합계=r['pending'],미완료합계=r['unfinished']) for r in s['validation']]),hide_index=True,width='stretch')
    st.dataframe(pd.DataFrame([dict(조건=label(r['case']),평균시간손실_초=r['mean_time_loss'],미진입합계=r['pending'],미완료합계=r['unfinished'],완료차량평균비교가능=r['eligible']) for r in table]),hide_index=True,width='stretch')
    st.caption('평균은 각 시드의 완료 차량 평균을 다시 평균한 값입니다. 미진입·미완료는 3개 시드 합계입니다. 미처리가 남는 조건은 완료 차량 평균만으로 순위를 매기지 않습니다.')
    col1,col2=st.columns(2)
    seed=col1.selectbox('상세 실험 시드',s['protocol']['discovery_seeds'],key='network_seed')
    cases=sorted({r['case'] for r in rows},key=lambda k:(k not in ('after','offset_11'),k))
    case=col2.selectbox('상세 실험 조건',cases,format_func=label,key='network_case_'+family)
    r=next(r for r in rows if r['seed']==seed and r['case']==case);sub=folder/r['path']
    net=folder/'networks'/(f'corridor_{75 if case.endswith("_75") else 150}' if family=='corridor' else 'turning_150')
    info=load_info(net)
    flow=st.selectbox('강조할 이동류',list(info['flows']),key='network_flow_'+family)
    st.plotly_chart(map_figure(info,flow),width='stretch',key='network_geometry')
    st.caption(f"이 기록의 신호·보행·경로 검사 이상 {r['anomaly_count']}건, 충돌 {r['collisions']}건, 순간이동 {r['teleports']}건. 보행자 완료 {r['pedestrian_completed']}/{r['pedestrian_seen']}명.")
    movement=pd.DataFrame(r['rows'])
    fig=go.Figure(go.Bar(x=movement.movement,y=movement.time_loss,marker_color='#087f79'))
    fig.update_layout(title='이동류별 시간 손실',xaxis_type='category')
    st.plotly_chart(finish(fig,'완료 차량 평균 시간 손실 (초)'),width='stretch',key='network_movements')
    if family=='corridor':
        raw=pd.read_csv(sub/'telemetry.csv');raw=raw[raw.observation]
        fig=go.Figure()
        for edge,title in [('W_in','상류 진입 도로'),('link_E','두 교차로 사이 도로')]:
            d=raw[raw.edge==edge]
            fig.add_trace(go.Scatter(x=(d.time-r['request']['warmup'])/60,y=d.halting,mode='lines',name=title))
        fig.update_layout(title='하류 제한과 상류 정지 차량',xaxis_title='관측 시작 후 시간 (분)')
        st.plotly_chart(finish(fig,'정지 차량 수 (대)'),width='stretch',key='corridor_propagation')
        e=r['edge_stats']['link_E']
        st.write(f"연결도로 최장 연속 정지 차량군 {e['max_geometric_queue_m']:.1f}m · 상류 경계 가까이에 정지 차량이 관측된 5초 표본 {e['boundary_occupied_samples']}개")
        st.caption('경계 표지만으로 상류 정체 전파를 확정하지 않습니다. 하류 녹색 축소 전후의 상류 정지 차량·미진입·미완료를 함께 비교합니다. 도로를 75m로 줄이면 저장공간과 통행시간·신호 도착 시각이 함께 달라집니다.')
    st.caption('합성 도로·고정 보행속도·고정 차종의 연구 사례입니다. 현장 신호·안전·공식 교통영향평가를 검증한 결과가 아닙니다.')
    st.download_button('도로망 연구 요약 JSON',path.read_bytes(),file_name='network_study_summary.json',mime='application/json')

def queue_panel():
    path=ROOT/'experiments/queue_dynamic_audit/audit.json'
    if not path.exists():st.info('동적 대기행렬 검증을 진행하고 있습니다.');return
    a=read(path)
    st.subheader('알려진 차량 배치로 길이와 경계를 검증')
    st.write('차량의 앞범퍼 위치와 길이로 연속 정지 차량군을 구성합니다. 평행 차로의 길이를 합산하지 않고 가장 긴 차량군을 사용합니다.')
    labels=['떨어진 차량군·두 차로','한 차로의 차량군 연결','상류 관측 경계 초과','차량 재출발']
    table=[dict(검증사례=title,기대길이_m=c['queue_m'],계산길이_m=c['actual_queue_m'],경계표시=c['actual_boundary'],일치=c['passed']) for title,c in zip(labels,a['cases'])]
    st.dataframe(pd.DataFrame(table),hide_index=True,width='stretch')
    raw=pd.read_csv(ROOT/'experiments/queue_dynamic_audit/after/geometric_queue.csv');raw=raw[raw.direction=='N']
    fig=go.Figure(go.Scatter(x=raw.time,y=raw.queue_m,mode='lines+markers',name='위치 기반 최장 차량군'))
    for time_,text in [(4.5,'차량군 연결'),(8.5,'상류 경계 이동'),(12.5,'재출발')]:fig.add_vline(x=time_,line_dash='dot',annotation_text=text)
    fig.update_layout(title='배치 변경과 재출발에 따른 계산값',xaxis_title='시뮬레이션 시각 (초)')
    st.plotly_chart(finish(fig,'관측 구간 안의 길이 (m)'),width='stretch',key='queue_dynamic')
    st.write(f"원시 궤적과 실행 중 직접 관측값 {a['fcd_point_checks']}건을 대조했습니다. 최대 위치 차이는 {a['fcd_max_position_error_m']:.3f}m, 속도 차이는 {a['fcd_max_speed_error_mps']:.3f}m/s입니다.")
    st.info('떨어진 차량군 사례에서 E2 원시 길이는 한 차로 165m였지만, 정의한 최장 연속 차량군은 두 차로 전체에서 29m였습니다. 두 값을 구분하고 위치 기반 정의의 검증 결과를 사용합니다.')
    st.caption('기본 판정: 속도 0.1m/s 미만, 정지 1초 초과, 차량 사이 간격 10m 이하. 궤적의 기록 주기·반올림과 앞범퍼 기준 포함 범위에 따른 한계가 있습니다.')
    st.download_button('동적 대기행렬 검증 JSON',path.read_bytes(),file_name='queue_dynamic_audit.json',mime='application/json')
