"""One-time migration of existing UI shell; numeric model remains unchanged."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
app=ROOT/'app.py'
s=app.read_text(encoding='utf-8')
if 'from traffic import theme' in s:raise SystemExit('Workspace migration already applied.')
s=s.replace('from traffic.ui_advanced import advanced_panel','from traffic.ui_advanced import advanced_panel\nfrom traffic import theme\nfrom traffic.ui_city import city_panel')
start=s.index('st.set_page_config(');end=s.index('\ndef apply_config',start)
s=s[:start]+'st.set_page_config(page_title="교통영향 분석 | Traffic Workspace",layout="wide")\ntheme.install()\nview=theme.navigation()\n'+s[end:]
s=s.replace('defaults=Config()\ndef number','defaults=Config.from_dict(st.session_state.get("scenario_config",Config().to_dict()))\ndef number')
s=s.replace('    value=int(value) if integer else float(value)','    value=getattr(defaults,key,value)\n    value=int(value) if integer else float(value)')
s=s.replace('f"lanes_{d}",1,integer=True','f"lanes_{d}",defaults.approaches[d].lanes,integer=True')
s=s.replace('value=False,key="w_stochastic"','value=defaults.stochastic,key="w_stochastic"').replace("value=False,key='w_record_trajectories'","value=defaults.record_trajectories,key='w_record_trajectories'")
s=s.replace('with st.expander("교통량과 직진 차로",expanded=True):','with st.expander("교통량과 직진 차로"):').replace('with st.expander("차량 신호시간",expanded=True):','with st.expander("차량 신호시간"):')
start=s.index('with st.sidebar:\n    st.markdown("### 실험 조건")');end=s.index('\nanalysis=calculate(c)',start)
block=s[start:end]
s=s[:start]+'if view!="대구 범어네거리":\n'+''.join('    '+line+'\n' for line in block.splitlines())+'    st.session_state["scenario_config"]=c.to_dict()\nelse:\n    c=defaults\n    with st.sidebar:\n        st.caption("도시 사례 · 고정 실행 기록")\n        st.markdown("**대구 범어네거리**")\n        st.caption("SUMO 1.28 · seed 2026\\n\\n실제 도로 형상 / 합성 수요\\n\\n기본 모델의 입력값과 독립된 사례입니다.")\n'+s[end:]
start=s.index("st.html('<div class=\"eyebrow\"");end=s.index("if view=='전후 비교':",start)
s=s[:start]+"theme.heading(view)\nif view=='대구 범어네거리':city_panel()\n"+s[end:]
app.write_text(s,encoding='utf-8')
for name in ['charts.py','dashboard.py']:
 p=ROOT/'traffic'/name;s=p.read_text(encoding='utf-8')
 s=s.replace('import plotly.graph_objects as go','import plotly.graph_objects as go\nfrom .theme import FONT')
 for a,b in {'#84968d':'#8190a5','#778b86':'#8190a5','#d58a40':'#c58a3b','#c57930':'#c58a3b','#14786e':'#3267c8','#087f79':'#3267c8','#19312d':'#23334c','#edf2ea':'#f1f4f8','#bac5bf':'#a9b5c4','#d7e1d7':'#dce3ec','#63786f':'#5c6b80','#cad6c3':'#c6d3e5','#d5decf':'#dce5ef','#6b7d64':'#687991','rx="18"':'rx="4"','rx="11"':'rx="4"'}.items():s=s.replace(a,b)
 s=s.replace('family="Malgun Gothic, sans-serif"','family=FONT')
 p.write_text(s,encoding='utf-8')
p=ROOT/'frontend/replay.css';s=p.read_text(encoding='utf-8')
s=s.replace('system-ui,"Malgun Gothic",sans-serif','"Pretendard Variable", "Malgun Gothic",sans-serif')
for a,b in {'#193b33':'#23334c','#a9c3b7':'#d3dce8','#087f79':'#3267c8','#d4e1d8':'#dce3ec','#516d62':'#66768c','border-radius:14px':'border-radius:4px','border-radius:7px':'border-radius:4px'}.items():s=s.replace(a,b)
p.write_text('@font-face{font-family:"Pretendard Variable";src:url("/app/static/fonts/PretendardVariable.woff2") format("woff2");font-weight:100 900;font-display:swap}\n'+s,encoding='utf-8')
