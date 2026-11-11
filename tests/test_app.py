from pathlib import Path
import sys
import pytest
from streamlit.testing.v1 import AppTest
ROOT=Path(__file__).resolve().parents[1]

@pytest.fixture(autouse=True)
def restore_main_module_after_streamlit_test():
    # AppTest temporarily installs app.py as __main__; Windows spawn must not inherit it.
    original=sys.modules.get('__main__')
    yield
    if original is not None:sys.modules['__main__']=original

def app():
    return AppTest.from_file(str(ROOT/"app.py"),default_timeout=30).run()

def test_app_default_load():
    at=app()
    assert not at.exception
    assert [m.value for m in at.metric][:3]==["0.855","1.184","0.982"]
    assert not at.error

def test_signal_warning_and_recovery():
    at=app()
    at.number_input(key="w_improved_ns").set_value(60.0).run()
    assert not at.exception
    assert any("신호 합계" in e.value for e in at.error)
    at.number_input(key="w_improved_ew").set_value(20.0).run()
    assert any("보행 배정" in e.value for e in at.error)
    at.number_input(key="w_improved_ns").set_value(50.0)
    at.number_input(key="w_improved_ew").set_value(30.0).run()
    assert not at.error
    assert not at.exception

def test_pedestrian_error():
    at=app()
    at.number_input(key="w_pedestrian_speed").set_value(.5).run()
    assert any("보행 배정" in e.value for e in at.error)
    assert not at.exception

def test_one_click_launches_only_once(tmp_path,monkeypatch):
    from unittest.mock import Mock
    import subprocess
    import traffic.experiment
    proc=Mock();proc.poll.return_value=0
    launch=Mock(return_value=proc)
    monkeypatch.setattr(subprocess,"Popen",launch)
    monkeypatch.setattr(traffic.experiment,"new_folder",lambda root:tmp_path/"ui_run")
    at=app()
    at.radio(key='research_view').set_value('SUMO 실험').run()
    next(b for b in at.button if b.label=="세 시나리오 SUMO 실행").click().run()
    assert not at.exception
    at.run()
    assert not at.exception
    assert launch.call_count==1

def test_reset_updates_visible_and_computed_values():
    at=app()
    at.number_input(key="w_improved_ns").set_value(60.0).run()
    next(b for b in at.button if b.label=="↺ 기본값 복원").click().run()
    assert at.number_input(key="w_improved_ns").value==50.0
    at.number_input(key="w_seed").set_value(43).run()
    assert at.number_input(key="w_improved_ns").value==50.0
    assert not at.error and not at.exception

def test_profile_and_mixed_fleet_presets_apply_to_widgets():
    at=app()
    at.selectbox(key='preset').set_value('peak_profile').run()
    next(b for b in at.button if b.label=='시나리오 적용').click().run()
    assert at.text_input(key='profile_text').value=='0.8, 1.0, 1.4, 0.8'
    at.selectbox(key='preset').set_value('mixed_fleet').run()
    next(b for b in at.button if b.label=='시나리오 적용').click().run()
    assert at.number_input(key='w_mix_bus').value==.05
    assert at.number_input(key='w_mix_truck').value==.10
    assert at.text_input(key='profile_text').value=='1.0'
    assert not at.exception and not at.error

def test_detail_and_search_pages_render_saved_results():
    at=app()
    at.radio(key='research_view').set_value('상세 그래프').run()
    assert not at.exception
    assert any('20.41' in e.value for e in at.metric)
    at.radio(key='graph_group').set_value('시간·분포 분석').run()
    assert not at.exception
    at.radio(key='research_view').set_value('후보 탐색').run()
    assert not at.exception
    assert all('holdout' not in str(p) for p in at.selectbox(key='search_history').options)
    assert any('별도 시드 재검증' in msg.value for msg in at.subheader)

def test_advanced_research_separates_real_sample_and_geometry_audit():
    at=app()
    at.radio(key='research_view').set_value('심화 연구').run()
    assert not at.exception
    assert any('1.253' in m.value for m in at.metric)
    at.selectbox(key='public_follower').set_value(142).run()
    assert not at.exception
    at.radio(key='advanced_mode').set_value('보행 형상 검증').run()
    assert not at.exception and len(at.dataframe)==2

def test_network_and_dynamic_queue_research_pages_render():
    at=app()
    at.radio(key='research_view').set_value('심화 연구').run()
    at.radio(key='advanced_mode').set_value('회전·인접 교차로').run()
    assert not at.exception
    assert any('추천하지 않습니다' in msg.value for msg in at.info)
    at.radio(key='network_family').set_value('인접 교차로와 하류 막힘').run()
    at.selectbox(key='network_case_corridor').set_value('downstream_bottleneck_75').run()
    assert not at.exception and len(at.dataframe)>=2
    at.radio(key='advanced_mode').set_value('대기행렬 검증').run()
    assert not at.exception and len(at.dataframe)==1

