"""Inspect saved demand XML and measured vehicle records, not regenerated inputs."""
from pathlib import Path
from collections import Counter
import json, math, xml.etree.ElementTree as ET
import pandas as pd
from traffic.io import write_json, sha256
from traffic.results import summary
ROOT=Path(__file__).resolve().parents[1]

def read(p):return json.loads(p.read_text(encoding='utf-8'))

def main():
    rows=[];base=None
    for name in ('baseline','peak_profile','mixed_fleet'):
        folder=ROOT/'experiments/study_v2/scenarios'/name
        result=read(folder/'comparison.json');c=result['config']
        meta=read(folder/'demand/vehicles.json')
        xml=ET.parse(folder/'demand/after.rou.xml').getroot()
        types={t.get('id'):dict(t.attrib) for t in xml.findall('vType') if t.get('id')!='walker'}
        observed={v.get('id'):dict(v.attrib) for v in xml.findall('vehicle')}
        assert set(meta)==set(observed)
        bins=[0,0,0,0];counts=Counter();total=0
        for vid,m in meta.items():
            v=observed[vid]
            assert float(v['depart'])==m['scheduled'] and v['type']==m['vehicle_type']
            if m['measured']:
                part=min(3,int((m['scheduled']-c['warmup'])/c['duration']*4))
                assert 0<=part<=3
                bins[part]+=1;counts[v['type']]+=1;total+=1
        expected=sum(math.floor((c['approaches'][d][kind])*c['duration']/3600+.5)
                     for d in c['approaches'] for kind in ('base','extra'))
        assert total==expected==2600
        assert sum(bins)==total and sum(counts.values())==total
        assert types['car']['length']=='5' and types['car']['accel']=='2.6'
        assert types['bus']['length']=='12' and types['bus']['accel']=='1.2'
        assert types['truck']['length']=='12' and types['truck']['accel']=='1.0'
        if name=='mixed_fleet':
            assert c['vehicle_mix']==dict(car=.85,bus=.05,truck=.10)
            assert set(counts)=={'car','bus','truck'}
            # Type-only experiment: IDs, scheduled departures and measured cohort unchanged.
            assert {k:(v['scheduled'],v['measured'],v['direction']) for k,v in meta.items()}==base
        if name=='baseline':base={k:(v['scheduled'],v['measured'],v['direction']) for k,v in meta.items()}
        metrics={}
        for run in result['sumo']:
            raw=pd.read_csv(folder/run['scenario']/'vehicles.csv')
            measured=raw[raw.measured]
            assert len(measured)==sum(r['requested'] for r in run['rows'])
            completed=measured[measured.status=='completed']
            s=summary(run)
            assert len(completed)==s['completed']
            assert abs(completed.time_loss.mean()-s['time_loss'])<1e-9
            metrics[run['scenario']]=s
        rows.append(dict(scenario=name,config=c,quarter_hour_counts=bins,actual_type_counts=dict(counts),
            type_parameters=types,metrics=metrics,demand_sha256=sha256(folder/'demand/after.rou.xml')))
    audit=dict(passed=True,records=rows,note='Random draws preserve total demand, not exact per-bin or per-type proportions. Single scenario seed 407 is sensitivity evidence, not a general effect estimate.')
    write_json(ROOT/'docs/profile_mix_audit.json',audit)
    lines=['# 시간 수요·차종 민감도 연구','','관측 1시간, 준비 900초, 추가 종료900초, 시드407. 입주 후 총 2,600대는 세 조건에서 같다. 후보는 남북/동서50/30초다. 모든 값은 저장된 XML과 차량별 결과를 대조했다.',
      '', '| 조건 | 15분별 예정 출발 대수 | 실제 승용차/버스/트럭 | 입주 후 시간 손실(초) | 후보 시간 손실(초) |', '|---|---|---|---:|---:|']
    for r in rows:
        count=r['actual_type_counts'];m=r['metrics']
        lines.append(f"| {r['scenario']} | {r['quarter_hour_counts']} | {count.get('car',0)}/{count.get('bus',0)}/{count.get('truck',0)} | {m['after']['time_loss']:.3f} | {m['improved']['time_loss']:.3f} |")
    lines+=['','시간 수요 가중치는 0.8/1.0/1.4/0.8이며 확률적 도착 시각을 변환한다. 총량은 보존하지만 각 15분 구간 대수를 정확한 비율로 강제하지 않는다.',
      '차종은 차량 ID·시드로 결정한 난수를 85/5/10% 확률에 배정한다. 실제 차종 대수는 확률 비율과 약간 다르며, 기본 사례와 예정 출발 시각·방향·ID는 동일하다.',
      '', '| 차종 | 길이(m) | 가속도(m/s²) | 감속도(m/s²) | tau(초) | 최소 간격(m) |','|---|---:|---:|---:|---:|---:|']
    for name,v in rows[-1]['type_parameters'].items():lines.append(f"| {name} | {v['length']} | {v['accel']} | {v['decel']} | {v['tau']} | {v['minGap']} |")
    lines+=['','세 조건의 입주 전·후·후보에서 미진입·미완료를 함께 확인했다. 이 자료는 고정 시드 하나의 민감도 사례이므로 차종 혼합이나 시간대 집중의 보편적 효과 크기로 일반화하지 않는다.',
      '버스 정류장·승하차·별도 화물 경로는 포함하지 않는다. 포화교통류율 공식에 차종 혼합 효과를 자동 반영하지 않으며 SUMO 동작 변화와 구분한다.',
      '', '재현 검사: `python -m scripts.audit_profile_mix` · 근거: `docs/profile_mix_audit.json`']
    (ROOT/'docs/profile_mix_research.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps(dict(passed=True,counts=[dict(scenario=r['scenario'],periods=r['quarter_hour_counts'],types=r['actual_type_counts']) for r in rows]),ensure_ascii=False))

if __name__=='__main__':main()
