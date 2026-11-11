"""Compare every detailed plot family with saved observation rows."""
from pathlib import Path
from collections import defaultdict
import json, statistics
from traffic.dashboard import load,detail,search_figures
from traffic.io import write_json,sha256
ROOT=Path(__file__).resolve().parents[1]

def close(a,b):
    assert len(a)==len(b),(len(a),len(b))
    for x,y in zip(a,b):assert abs(float(x)-float(y))<1e-8,(x,y)

def main():
    folder=ROOT/'experiments/baseline_v2';data,tables=load(folder);checks=0;heat_scales=[]
    for direction in ('N','S','E','W'):
        for sid in ('before','after','improved'):
            plots=detail(data,tables,direction,sid)
            for i,scenario in enumerate(('before','after','improved')):
                records=tables[scenario]['telemetry'].to_dict('records');bins=defaultdict(list)
                for r in records:
                    if r['direction']==direction and r['observation']:
                        bins[int((r['time']-data['config']['warmup'])//30)*.5].append(r['halting'])
                tr=plots['정지 차량의 시간 변화'].data[i]
                close(tr.x,sorted(bins));close(tr.y,[statistics.mean(bins[k]) for k in sorted(bins)]);checks+=1
            records=tables[sid]['telemetry'].to_dict('records')
            selected=[r for r in records if r['direction']==direction][::10]
            for trace,key in zip(plots['누적 차량 흐름'].data,('scheduled','inserted','crossed','completed')):
                close(trace.y,[r[key] for r in selected]);checks+=1
            heat=plots['방향별 혼잡 집중 시간'].data[0];heat_scales.append(heat.zmax)
            bins=defaultdict(list)
            for r in records:
                if r['observation']:bins[r['direction'],int((r['time']-data['config']['warmup'])//60)].append(r['halting'])
            for j,d in enumerate(('N','S','E','W')):
                close(heat.z[j],[statistics.mean(bins[d,int(m)]) for m in heat.x]);checks+=1
            phase=plots['실제 신호 타임라인'].data[0];by_time={r['time']:r['signal'] for r in records}
            links={d:int(k) for k,d in data['vehicle_links'].items()}
            for j,d in enumerate(('N','S','E','W')):
                expected=[by_time[t+data['config']['warmup']][links[d]] for t in phase.x]
                assert list(phase.text[j])==expected;checks+=1
            queue=plots['위치로 재구성한 최장 정지 차량군']
            for i,scenario in enumerate(('before','after','improved')):
                bins=defaultdict(list)
                for r in tables[scenario]['geometric_queue'].to_dict('records'):
                    if r['direction']==direction and data['config']['warmup']<=r['time']<data['config']['warmup']+data['config']['duration']:
                        bins[int((r['time']-data['config']['warmup'])//30)*.5].append(r['queue_m'])
                close(queue.data[i].y,[max(bins[k]) for k in sorted(bins)]);checks+=1
    assert len(set(heat_scales))==1
    report=json.loads((ROOT/'experiments/study_v2/discovery/search_summary.json').read_text(encoding='utf-8'))
    figs=search_figures(report);candidates=sorted(report['candidates'],key=lambda r:r['ns'])
    for tr,key in zip(figs['후보 배분과 성능'].data[:2],('mean_time_loss','worst_direction_time_loss')):
        close(tr.y,[r[key] for r in candidates]);checks+=1
    refs={r['seed']:r for r in report['records'] if r['reference']}
    for tr in figs['시드별 기준 대비 차이'].data:
        ns=int(tr.name.split()[1][:-1]);raw=[r for r in report['records'] if r['ns']==ns]
        close(tr.y,[r['metrics']['time_loss']-refs[r['seed']]['metrics']['time_loss'] for r in raw]);checks+=1
    write_json(ROOT/'docs/chart_values_audit.json',dict(passed=True,trace_checks=checks,shared_heatmap_max=heat_scales[0],
        directions=4,situations=3,candidates=len(candidates),baseline_hash=sha256(folder/'comparison.json'),
        plotted_source_hash=sha256(ROOT/'traffic/dashboard.py')))
    print(f'Passed: {checks} trace comparisons; shared heatmap scale; all 31 candidate values')

if __name__=='__main__':main()
