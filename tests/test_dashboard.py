from pathlib import Path
import json
import pytest
from traffic.dashboard import load,overview,detail,insight,search_figures
ROOT=Path(__file__).resolve().parents[1]

def test_overview_plots_match_saved_full_baseline():
    data,tables=load(ROOT/'experiments/baseline_v2')
    figures=overview(data)
    state=figures['출발 예정 차량의 최종 상태']
    for i,run in enumerate(data['sumo']):
        assert sum(trace.y[i] for trace in state.data)==sum(r['requested'] for r in run['rows'])
    dumbbell=figures['방향별 이익과 불이익']
    actual=dumbbell.data[-1].x
    assert list(actual)==[r['time_loss'] for r in data['sumo'][2]['rows']]
    assert '동측, 서측' in insight(data)
    detailed=detail(data,tables,'N','after')
    distribution=detailed['완료 차량 시간 손실 분포']
    for trace,run in zip(distribution.data,data['sumo']):
        row=next(r for r in run['rows'] if r['direction']=='N')
        assert len(trace.y)==row['completed']
        assert sum(trace.y)/len(trace.y)==pytest.approx(row['time_loss'])
    # All plotted figures can be serialized without invalid values.
    for fig in list(figures.values())+list(detailed.values()):
        assert 'data' in json.loads(fig.to_json())

def test_search_plot_preserves_candidate_values():
    report=json.loads((ROOT/'experiments/search_smoke/search_summary.json').read_text(encoding='utf-8'))
    figs=search_figures(report)
    curve=figs['후보 배분과 성능'].data[0]
    expected=sorted(report['candidates'],key=lambda r:r['ns'])
    assert list(curve.x)==[r['ns'] for r in expected]
    assert list(curve.y)==[r['mean_time_loss'] for r in expected]
