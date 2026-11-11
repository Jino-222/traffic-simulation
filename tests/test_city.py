import hashlib,json,sys
from pathlib import Path
import pytest
from traffic.city import CASE,ROOT,derive,load_case,summarize_cohort,read
from traffic.ui_city import result_charts,table_for
from streamlit.testing.v1 import AppTest

@pytest.fixture(autouse=True)
def restore_main():
    old=sys.modules.get('__main__');yield
    if old is not None:sys.modules['__main__']=old

def test_cohort_uses_scheduled_time_and_excludes_censored_means():
    vehicles=[{'id':str(i),'depart':t,'route':'NS'} for i,t in enumerate([299,300,301,302,1499,1500])]
    trips={'0':{'depart':310,'arrival':400,'timeLoss':999,'waitingTime':999},
           '1':{'depart':320,'arrival':500,'timeLoss':10,'waitingTime':3},
           '2':{'depart':400,'arrival':-1,'timeLoss':800,'waitingTime':500},
           '3':{'depart':-1,'arrival':-1},
           '5':{'depart':1500,'arrival':1800,'timeLoss':999,'waitingTime':999}}
    d=summarize_cohort(vehicles,trips,300,1500)
    assert d['counts']==dict(requested=4,completed=1,running=1,waiting=2)
    assert d['mean_time_loss_s']==10 and d['mean_waiting_time_s']==3
    assert d['completion_rate']==.25 and not d['ranking_eligible']

def test_empty_cohort_has_no_invented_average():
    d=summarize_cohort([],{},300,1500)
    assert d['mean_time_loss_s'] is None and d['completion_rate'] is None

def test_frozen_source_hashes_and_same_origin_replay():
    manifest=read(CASE/'import_manifest.json')
    assert len(manifest['files'])==92
    for name,digest in manifest['files'].items():
        assert hashlib.sha256((CASE/name).read_bytes()).hexdigest()==digest,name
    for name in ['geometry','results','before','after','adjusted']:
        assert (ROOT/f'static/daegu/{name}.json').read_bytes()==(CASE/f'web/{name}.json').read_bytes()

def test_new_metrics_recompute_from_tripinfo_and_match_original_all_requests():
    d=load_case();assert derive()==d['metrics']
    for sid,r in d['metrics']['scopes']['all'].items():
        original=d['original']['results'][sid]
        assert all(value==original['counts'][key] for key,value in r['counts'].items())
        assert round(r['mean_time_loss_s'],2)==original['completed_time_loss_mean_s']
        assert not r['ranking_eligible']
    assert [r['counts']['requested'] for r in d['metrics']['scopes']['observation'].values()]==[884,1084,1084]

@pytest.mark.parametrize('scope',['all','observation'])
def test_charts_table_and_csv_use_selected_population(scope):
    d=load_case();r=d['metrics']['scopes'][scope];figs=result_charts(d,scope)
    assert list(figs['종료 시 차량 상태'].data[0].y)==[v['counts']['completed'] for v in r.values()]
    for trace,sid in zip(figs['완료 차량 시간 손실 분포'].data,r):
        assert len(trace.x)==r[sid]['counts']['completed']
        assert trace.y[-1]==100
    table=table_for(d,scope)
    assert table['출발 요청 (대)'].tolist()==[v['counts']['requested'] for v in r.values()]
    for f in figs.values():json.loads(f.to_json())

def test_city_pages_and_navigation_preserve_basic_inputs(monkeypatch):
    from unittest.mock import Mock
    launch=Mock();monkeypatch.setattr('subprocess.Popen',launch)
    at=AppTest.from_file(str(ROOT/'app.py'),default_timeout=30).run()
    at.number_input(key='w_base_N').set_value(777.0)
    at.number_input(key='w_lanes_N').set_value(2)
    at.checkbox(key='w_record_trajectories').check()
    at.number_input(key='w_improved_ns').set_value(60.0).run()
    assert at.error
    at.radio(key='research_view').set_value('대구 범어네거리').run()
    assert not at.exception and not at.error and not at.number_input
    for page in ['실험 결과','계산 기준·검증','시각화 자료','지도·궤적']:
        at.radio(key='city_page').set_value(page).run();assert not at.exception
        if page=='실험 결과':
            assert at.metric[0].value=='1,173대'
            at.selectbox(key='city_cohort').set_value('observation').run()
            assert at.metric[0].value=='902대'
    assert launch.call_count==0
    at.radio(key='research_view').set_value('전후 비교').run()
    assert not at.exception
    assert at.number_input(key='w_base_N').value==777
    assert at.number_input(key='w_lanes_N').value==2
    assert at.checkbox(key='w_record_trajectories').value
    assert at.number_input(key='w_improved_ns').value==60
    assert at.error
