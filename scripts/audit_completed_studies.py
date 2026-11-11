"""Audit completed scenario and public-data studies against their declared scope."""
from pathlib import Path
import json,math
from traffic.results import summary
from traffic.io import write_json,sha256
ROOT=Path(__file__).resolve().parents[1]

def read(p):return json.loads(p.read_text(encoding='utf-8'))

def check_experiment(path):
    d=read(path/'comparison.json');status=read(path/'status.json')
    assert status['state']=='completed',(path,status)
    assert len(d['sumo'])==3
    for run in d['sumo']:
        assert run['anomaly_count']==run['collisions']==run['teleports']==0
        for r in run['rows']:
            assert r['requested']==r['pending']+r['unfinished']+r['completed']
    assert d['sumo'][1]['demand_hash']==d['sumo'][2]['demand_hash']
    for sid in ('before','after'):
        assert sha256(path/'demand'/f'{sid}.rou.xml')==d['manifest']['demand_hashes'][sid]
    metrics={r['scenario']:summary(r) for r in d['sumo']}
    return d,dict(experiment=path.name,metrics=metrics,all_integrity_checks_passed=True,
        comparison_sha256=sha256(path/'comparison.json'))

def main():
    study=ROOT/'experiments/study_v2';assert read(study/'status.json')['state']=='completed'
    paths=sorted((study/'scenarios').glob('*/comparison.json'));assert len(paths)==16
    records=[];configs={};data={}
    for p in paths:
        d,r=check_experiment(p.parent);records.append(r);configs[p.parent.name]=d['config'];data[p.parent.name]=d
    zero=records[next(i for i,r in enumerate(records) if r['experiment']=='zero_demand')]
    assert all(r['requested']==0 and r['time_loss'] is None for r in zero['metrics'].values())
    baseline=configs['baseline']
    assert configs['irregular']==baseline,'The existing batch intentionally used random arrivals for all presets'
    regular,regular_record=check_experiment(ROOT/'experiments/arrival_control_regular')
    different=[k for k in baseline if baseline[k]!=regular['config'][k]]
    assert different==['stochastic'],different
    base_totals={sid:{r['direction']:r['requested'] for r in run['rows']} for sid,run in zip(('before','after','improved'),data['baseline']['sumo'])}
    regular_totals={sid:{r['direction']:r['requested'] for r in run['rows']} for sid,run in zip(('before','after','improved'),regular['sumo'])}
    assert base_totals==regular_totals
    for name in ('ns_focus','ew_focus','peak_profile','mixed_fleet'):
        assert sum(r['requested'] for r in data[name]['sumo'][1]['rows'])==sum(base_totals['after'].values())
    public=read(ROOT/'experiments/public_calibration_v2/summary.json')
    protocol=public['protocol'];frozen=public['frozen'];val=public['validation']
    assert set(protocol['train']).isdisjoint(protocol['validation'])
    assert public['validation_used_for_selection'] is False and frozen['selected_before_validation']
    assert public['calibration_candidates']==24 and all(v['valid'] for v in val.values())
    assert frozen['protocol_sha256']==sha256(ROOT/'experiments/public_calibration_v2/protocol.json')
    peds=read(ROOT/'experiments/pedestrian_geometry/audit.json')
    assert peds['passed'] and len(peds['sweeps'])==8 and sum(c['executed_scenarios'] for c in peds['runtime_cases'])==9
    audit=dict(passed=True,scenario_presets=16,scenario_sumo_runs=48,records=records,
        batch_note='All 16 presets ran with stochastic=True and seed=407. baseline and irregular are duplicate configs in this batch, not independent evidence.',
        regular_arrival_control=regular_record,arrival_control_changed_fields=different,
        distinct_configs_including_control=16,
        public=dict(candidates=24,train_trajectories=len(protocol['train']),validation_trajectories=len(protocol['validation']),
            selected_parameters=frozen['parameters'],selected_baseline=frozen['parameters']==protocol['baseline'],
            validation_speed_rmse_mps=val['calibrated']['mean_speed_rmse_mps'],validation_gap_rmse_m=val['calibrated']['mean_gap_rmse_m'],
            leader_position_max_error_m=val['calibrated']['leader_position_max_error_m']),
        pedestrian=dict(geometry_boundary_cases=8,sumo_runs=9,passed=True))
    write_json(ROOT/'docs/completed_studies_audit.json',audit)
    print(json.dumps({k:v for k,v in audit.items() if k not in ('records','regular_arrival_control')},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
