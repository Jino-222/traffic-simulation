from pathlib import Path
from datetime import datetime, timezone
import csv, json, platform, subprocess, traceback, uuid, hashlib
from importlib.metadata import version
from .models import Config, MODEL_VERSION, scenario_specs
from .validation import validate
from .analytic import calculate, candidates
from .io import write_json, sha256
from .sumo.network import build, binary
from .sumo.demand import create as create_demand
from .sumo.signals import create as create_signals
from .sumo.runner import run, Cancelled
from .sumo.replay import export as export_replay
from .queue import audit as reconstruct_queue

def execute(c, folder, progress=None):
    folder=Path(folder).resolve()
    folder.mkdir(parents=True,exist_ok=True)
    def status(state, message, **extra):
        data=dict(state=state,message=message,**extra)
        write_json(folder/"status.json",data)
        if progress: progress(data)
    status("running","입력 조건 검사")
    write_json(folder/"inputs.json",c.to_dict())
    try:
        errors=validate(c)
        if any(errors.values()): raise ValueError(json.dumps(errors,ensure_ascii=False))
        info=build(c,folder/"network")
        errors=validate(c,info["crossing_lengths"])
        if any(errors.values()): raise ValueError("생성 횡단길이 검사: "+json.dumps(errors,ensure_ascii=False))
        metadata,hashes=create_demand(c,folder/"demand",folder/"network"/"network.net.xml")
        code_files=sorted(Path(__file__).parent.rglob("*.py"))
        code_hash=hashlib.sha256(b"".join(p.relative_to(Path(__file__).parent).as_posix().encode()+p.read_bytes() for p in code_files)).hexdigest()
        manifest=dict(schema_version=2,model_version=MODEL_VERSION,synthetic=True,source_hash=code_hash,
                      experiment_id=folder.name,
                      created_utc=datetime.now(timezone.utc).isoformat(),input_hash=c.fingerprint(),
                      python=platform.python_version(),packages={p:version(p) for p in ["eclipse-sumo","traci","sumolib","streamlit","plotly"]},
                      network_hash=sha256(folder/"network"/"network.net.xml"),demand_hashes=hashes,
                      vehicle_parameters=dict(length=5,minGap=2.5,accel=2.6,decel=4.5,tau=c.car_tau,sigma=c.car_sigma,speedFactor=1),
                      vehicle_mix=c.vehicle_mix,demand_profile=c.demand_profile,
                      telemetry_period=c.telemetry_period,trajectory_period=c.trajectory_period if c.record_trajectories else None,
                      e2=dict(enabled=c.e2_enabled,speed=c.e2_speed_threshold,time=c.e2_time_threshold,gap=c.e2_jam_gap),
                      demand_method="fixed rounded count; seeded uniform arrival times" if c.stochastic else "fixed rounded count; equally spaced arrival times",
                      measured_cohort=f"scheduled departures in [{c.warmup}, {c.warmup+c.duration}) seconds",
                      observation_window=f"[{c.warmup}, {c.warmup+c.duration}) seconds",
                      end_time=c.warmup+c.duration+c.drain,
                      geometry_crossing_lengths=info["crossing_lengths"],
                      warnings=["합성 데이터 결과이며 현장 교통영향평가·안전 판단용이 아님",
                                "공식 기반 포화교통류율·손실시간과 SUMO 차량 동작은 별개 가정",
                                "시간 지표는 완료 차량에 한정; 미완료·미진입 차량과 함께 해석",
                                "정지 차량 대수는 대기행렬 길이(m)가 아님"])
        write_json(folder/"manifest.json",manifest)
        analytic=calculate(c)
        write_json(folder/"analytic.json",analytic)
        results=[]
        for i,(sid,title,ns,ew,added) in enumerate(scenario_specs(c)):
            if (folder/"CANCEL").exists(): raise Cancelled("사용자가 실험을 중단했습니다.")
            status("running",f"{title} SUMO 실행",scenario=sid,completed=i,total=3)
            sub=folder/sid;sub.mkdir(exist_ok=True)
            phases=create_signals(c,ns,ew,info,sub/"signals.add.xml")
            write_json(sub/"expected_phases.json",phases)
            demand=folder/"demand"/("after.rou.xml" if added else "before.rou.xml")
            result=run(c,sid,sub,folder/"network"/"network.net.xml",demand,sub/"signals.add.xml",info,phases,metadata,folder/"CANCEL")
            result["demand_hash"]=sha256(demand)
            result["experiment_id"]=folder.name
            result["candidate_id"]=f"NS{ns:g}_EW{ew:g}"
            result["replay_audit"]=export_replay(sub,folder/"network",metadata)
            result["geometric_queue"]=reconstruct_queue(sub) if c.record_trajectories else None
            write_json(sub/"result.json",result)
            results.append(result)
        combined=dict(config=c.to_dict(),manifest=manifest,analytic=analytic,sumo=results,
                      candidate_suggestions=candidates(c))
        write_json(folder/"comparison.json",combined)
        flat=[dict(scenario=r["scenario"],**row) for r in results for row in r["rows"]]
        with (folder/"comparison.csv").open("w",newline="",encoding="utf-8-sig") as f:
            w=csv.DictWriter(f,fieldnames=list(flat[0]));w.writeheader();w.writerows(flat)
        bad=sum(r["anomaly_count"]+r["collisions"]+r["teleports"]+len((r.get("replay_audit") or {}).get("errors",[])) for r in results)
        status("needs_review" if bad else "completed","동작 이상 검토 필요" if bad else "세 시나리오 실행 완료",completed=3,total=3)
        return combined
    except Cancelled:
        status("cancelled","사용자 중단")
        raise
    except Exception as e:
        (folder/"error.log").write_text(traceback.format_exc(),encoding="utf-8")
        status("failed",str(e))
        raise

def new_folder(root):
    return Path(root)/(datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")+"_"+uuid.uuid4().hex[:6])

def main():
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--config",required=True);p.add_argument("--output",required=True)
    args=p.parse_args()
    c=Config.from_dict(json.loads(Path(args.config).read_text(encoding="utf-8")))
    execute(c,args.output,lambda x:print(json.dumps(x,ensure_ascii=False),flush=True))

if __name__=="__main__": main()
