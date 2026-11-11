"""Summarize measured experiment artifacts; never infer missing runs."""
from pathlib import Path
import json, statistics
from traffic.io import write_json

ROOT=Path(__file__).resolve().parents[1]
NAMES=["baseline","candidate_49_31","seed_11","seed_22","seed_33","seed_44","seed_55",
       "high_demand","zero_demand","asymmetric_lanes","slow_pedestrian"]

def average(rows,key):
    n=sum(r["completed"] for r in rows)
    return sum((r[key] or 0)*r["completed"] for r in rows)/n if n else None

def load():
    studies={}
    for name in NAMES:
        folder=ROOT/"experiments"/name
        status=json.loads((folder/"status.json").read_text(encoding="utf-8"))
        if status["state"]!="completed": raise RuntimeError(f"{name}: {status['state']}")
        data=json.loads((folder/"comparison.json").read_text(encoding="utf-8"))
        runs={}
        for run in data["sumo"]:
            rows=run["rows"]
            assert all(r["requested"]==r["completed"]+r["pending"]+r["unfinished"] for r in rows)
            runs[run["scenario"]]=dict(
                requested=sum(r["requested"] for r in rows),completed=sum(r["completed"] for r in rows),
                pending=sum(r["pending"] for r in rows),unfinished=sum(r["unfinished"] for r in rows),
                time_loss=average(rows,"time_loss"),waiting_time=average(rows,"waiting_time"),
                depart_delay=average(rows,"depart_delay"),directional_time_loss={r["direction"]:r["time_loss"] for r in rows},
                anomalies=run["anomaly_count"],collisions=run["collisions"],teleports=run["teleports"],
                checked_steps=run["checked_steps"],pedestrians=run["pedestrian_completed"],
                elapsed_seconds=run["elapsed_seconds"],demand_hash=run["demand_hash"])
        assert runs["after"]["demand_hash"]==runs["improved"]["demand_hash"]
        studies[name]=dict(config=data["config"],runs=runs,source_hash=data["manifest"]["source_hash"])
    return studies

def main():
    studies=load()
    reps=[]
    for seed in [11,22,33,44,55]:
        runs=studies[f"seed_{seed}"]["runs"]
        a,b=runs["after"]["time_loss"],runs["improved"]["time_loss"]
        reps.append(dict(seed=seed,before=runs["before"]["time_loss"],after=a,improved=b,reduction_pct=100*(a-b)/a,
                         delta=b-a))
    stats=dict(mean_reduction_pct=statistics.mean(x["reduction_pct"] for x in reps),
               min_reduction_pct=min(x["reduction_pct"] for x in reps),
               max_reduction_pct=max(x["reduction_pct"] for x in reps),
               mean_delta_seconds=statistics.mean(x["delta"] for x in reps),
               sd_delta_seconds=statistics.stdev(x["delta"] for x in reps))
    write_json(ROOT/"docs"/"study_summary.json",dict(studies=studies,replicates=reps,statistics=stats))
    table=["| 실험 | 관측 초 | 입주 후 시간 손실 | 후보 시간 손실 | 입주 후 미진입+미완료 | 후보 미진입+미완료 |",
           "|---|---:|---:|---:|---:|---:|"]
    def fmt(x):return "해당 없음" if x is None else f"{x:.3f}"
    for name,s in studies.items():
        a,b=s["runs"]["after"],s["runs"]["improved"]
        table.append(f"| {name} | {s['config']['duration']} | {fmt(a['time_loss'])} | {fmt(b['time_loss'])} | {a['pending']+a['unfinished']} | {b['pending']+b['unfinished']} |")
    tables="\n".join(table)
    table=["| 시드 | 입주 전 | 입주 후 | 후보 50/30 | 감소율 |","|---|---:|---:|---:|---:|"]
    for r in reps:
        table.append(f"| {r['seed']} | {r['before']:.3f} | {r['after']:.3f} | {r['improved']:.3f} | {r['reduction_pct']:.2f}% |")
    tables+="\n\n"+"\n".join(table)
    tables+=f"\n\n5회 감소율의 평균은 {stats['mean_reduction_pct']:.2f}%, 범위는 {stats['min_reduction_pct']:.2f}~{stats['max_reduction_pct']:.2f}%입니다. 쌍별 시간 손실 차이(후보−입주 후)의 평균은 {stats['mean_delta_seconds']:.3f}초, 표본 표준편차는 {stats['sd_delta_seconds']:.3f}초입니다. 이 5개 합성 실험으로 현장 효과나 통계적 일반화를 주장하지 않습니다."
    base=studies["baseline"]["runs"]
    table=["| 방향 | 입주 전 | 입주 후 | 후보 50/30 | 후보−입주 후 |","|---|---:|---:|---:|---:|"]
    for d,label in zip(["N","S","E","W"],["북측","남측","동측","서측"]):
        b,a,i=[base[k]["directional_time_loss"][d] for k in ["before","after","improved"]]
        table.append(f"| {label} | {b:.3f} | {a:.3f} | {i:.3f} | {i-a:+.3f} |")
    tables+="\n\n**기본 실험의 방향별 시간 손실(초/완료 차량)**\n\n"+"\n".join(table)
    total=sum(r["checked_steps"] for s in studies.values() for r in s["runs"].values())
    anomaly=sum(r["anomalies"]+r["collisions"]+r["teleports"] for s in studies.values() for r in s["runs"].values())
    tables+=f"\n\n정식 연구 묶음 {len(studies)}개 × 3상황 = {len(studies)*3}회에서 {total:,}개 시뮬레이션 스텝을 검사했습니다. 동작 이상·충돌 관측·차량 텔레포트 합계는 {anomaly}입니다. 이 수치는 소프트웨어 동작 확인이며 안전 인증이 아닙니다."
    text=(ROOT/"docs"/"research_notes.md").read_text(encoding="utf-8")
    (ROOT/"docs"/"research_report.md").write_text(text.replace("{{MEASURED_RESULTS}}",tables),encoding="utf-8")
    print(json.dumps(dict(replicates=reps,statistics=stats,studies=len(studies),scenarios=len(studies)*3,steps=total,anomalies=anomaly),ensure_ascii=False,indent=2))

if __name__=="__main__":main()

