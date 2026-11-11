"""Shared application shell and chart tokens. Reference: CARTO Builder workspace."""
from pathlib import Path
import html
import streamlit as st
import plotly.graph_objects as go
import plotly.io as pio

ROOT=Path(__file__).resolve().parents[1]
FONT='Pretendard Variable, Pretendard, Malgun Gothic, sans-serif'
COLORS={'before':'#8190a5','after':'#c58a3b','improved':'#3267c8','adjusted':'#3267c8'}
VIEWS=['전후 비교','SUMO 실험','상세 그래프','후보 탐색','궤적 재생','대구 범어네거리','심화 연구','계산 공식·가정','연구 기록']
DESCRIPTIONS={
 '전후 비교':'방향별 교통 수요와 신호 배분에 따른 가정상 처리능력을 비교합니다.',
 'SUMO 실험':'동일한 입주 후 수요를 사용해 기준 신호와 조정 후보를 실행합니다.',
 '상세 그래프':'저장된 실행의 완료 상태, 방향별 영향과 시간 변화를 분석합니다.',
 '후보 탐색':'제약을 만족하는 후보를 비교하고 별도 시드 검증 결과를 확인합니다.',
 '궤적 재생':'실행 당시 저장한 차량·보행자 위치와 신호 상태를 재생합니다.',
 '대구 범어네거리':'실제 도로 형상과 합성 수요를 결합한 도시 확장 사례입니다.',
 '심화 연구':'공개 자료 비교와 별도로 구성한 도로·보행·대기행렬 연구를 검토합니다.',
 '계산 공식·가정':'계산식, 신호·보행 제약과 지표의 적용 범위를 확인합니다.',
 '연구 기록':'실험 근거와 검증 기록을 열람하고 내려받습니다.'}

def install():
    st.html('<style>'+ (ROOT/'frontend/workspace.css').read_text(encoding='utf-8')+'</style>')
    pio.templates['traffic_workspace']=go.layout.Template(layout=dict(
        font=dict(family=FONT,size=13,color='#23334c'),paper_bgcolor='#ffffff',plot_bgcolor='#ffffff',
        colorway=list(COLORS.values())[:3],xaxis=dict(gridcolor='#eef1f5',linecolor='#d8e0e8',zerolinecolor='#d8e0e8'),
        yaxis=dict(gridcolor='#eef1f5',linecolor='#d8e0e8',zerolinecolor='#d8e0e8'),
        hoverlabel=dict(bgcolor='#172b4d',font_color='white',font_family=FONT),
        margin=dict(l=20,r=20,t=50,b=60)))
    pio.templates.default='plotly_white+traffic_workspace'

def navigation():
    with st.sidebar:
        st.html('<div class="workspace-brand"><span class="brand-glyph">T</span><div><strong>교통영향 분석</strong><small>ANALYSIS WORKSPACE</small></div></div><div class="nav-caption">분석 작업</div>')
        view=st.radio('연구 화면',VIEWS,key='research_view',label_visibility='collapsed',width='stretch')
        st.divider()
    return view

def heading(view):
    city=view=='대구 범어네거리'
    family='도시 확장 사례 / OSM 도로망' if city else ('연구 자료 / 별도 실험' if view in ['심화 연구','연구 기록'] else '기본 모델 / 합성 교차로')
    st.html(f'<div class="workspace-topline"><span>교통영향 분석<span class="crumb-separator">/</span>{family}</span><span class="mode-badge">저장된 도시 실험</span></div>' if city else f'<div class="workspace-topline"><span>교통영향 분석<span class="crumb-separator">/</span>{family}</span><span class="mode-badge">연구용 모델</span></div>')
    st.title(view)
    st.markdown(f'<p class="page-description">{html.escape(DESCRIPTIONS[view])}</p>',unsafe_allow_html=True)
    if not city:st.html('<div class="scope-strip"><strong>적용 범위</strong><span>기본 모델은 합성 단일 직진 교차로입니다. 실제 도로 적용·안전 판단·공식 LOS 판정용으로 검증되지 않았습니다.</span></div>')
