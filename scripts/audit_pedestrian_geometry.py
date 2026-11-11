"""Verify assumed versus generated crossing lengths, boundary checks and occupancy."""
from pathlib import Path
from dataclasses import replace
import math,json
from traffic.models import Config,Approach
from traffic.validation import validate
from traffic.sumo.network import build
from traffic.experiment import execute
from traffic.io import write_json

ROOT=Path(__file__).resolve().parents[1]

def main():
    folder=ROOT/'experiments/pedestrian_geometry';folder.mkdir(parents=True,exist_ok=True)
    sweeps=[]
    for lanes in (1,2,3,4):
        c=Config();c.approaches={d:Approach(lanes,40,0) for d in c.approaches}
        info=build(c,folder/f'network_{lanes}_lanes')
        for speed in (.7,1.0):
            lengths={axis:max(20,actual) for axis,actual in info['crossing_lengths'].items()}
            need={axis:3+length/speed+2 for axis,length in lengths.items()}
            budget={axis:math.ceil(value*2)/2 for axis,value in need.items()}
            cfg=replace(c,pedestrian_speed=speed,pedestrian_budget_ns=budget['ns'],pedestrian_budget_ew=budget['ew'],
                before_ns=budget['ns'],before_ew=budget['ew'],improved_ns=budget['ns'],improved_ew=budget['ew'],
                cycle=budget['ns']+budget['ew']+10)
            valid=not any(validate(cfg,info['crossing_lengths']).values())
            invalid=replace(cfg,pedestrian_budget_ns=budget['ns']-.5)
            rejected=any('보행 배정' in msg for msgs in validate(invalid,info['crossing_lengths']).values() for msg in msgs)
            assert valid and rejected
            sweeps.append(dict(lanes=lanes,speed_mps=speed,assumed_m=20,generated_m=info['crossing_lengths'],
                applied_m=lengths,required_seconds=need,budget_seconds=budget,valid=valid,half_second_short_rejected=rejected))
    cases=[]
    for name,lanes,assumed,speed in [('assumed_conservative',1,20,1),('geometry_matched',1,6.4,1),('wide_slow',4,20,.7)]:
        cfg=Config();cfg.approaches={d:Approach(lanes,40,0) for d in cfg.approaches}
        geometry=build(cfg,folder/name/'geometry_probe')
        ns=math.ceil((3+max(assumed,geometry['crossing_lengths']['ns'])/speed+2)*2)/2
        ew=math.ceil((3+max(assumed,geometry['crossing_lengths']['ew'])/speed+2)*2)/2
        cfg=replace(cfg,road_length=100,warmup=0,duration=180,drain=180,pedestrian_speed=speed,
            crossing_length_ns=assumed,crossing_length_ew=assumed,pedestrian_budget_ns=ns,pedestrian_budget_ew=ew,
            before_ns=ns,before_ew=ew,improved_ns=ns,improved_ew=ew,cycle=ns+ew+10)
        resultfile=folder/name/'comparison.json'
        result=json.loads(resultfile.read_text(encoding='utf-8')) if resultfile.exists() else execute(cfg,folder/name)
        assert result['config']==cfg.to_dict()
        for r in result['sumo']:
            assert r['anomaly_count']==r['collisions']==r['teleports']==0
            assert r['pedestrian_completed']==r['pedestrian_departed']==12
            assert len(r['crossings_used'])==4
        cases.append(dict(case=name,lanes=lanes,speed=speed,assumed_m=assumed,geometry_m=result['manifest']['geometry_crossing_lengths'],
            ns_seconds=ns,ew_seconds=ew,executed_scenarios=3,all_four_crossings_used=True,
            pedestrian_completion_per_run=12,signal_entry_and_occupancy_anomalies=0))
    audit=dict(sweeps=sweeps,runtime_cases=cases,passed=True,
        interpretation='Input is an assumed design crossing length. Generated SUMO crossing geometry follows lane widths. Validation uses the larger length; an assumed 20 m is not silently presented as a 20 m generated crossing.',
        limitations='Deterministic fixed-speed walkers and synthetic geometry; no heterogeneous walking response or field safety certification.')
    write_json(folder/'audit.json',audit);print(json.dumps(audit,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
