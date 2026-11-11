"""Resumable paired-demand signal search. No learned AI scores."""
from pathlib import Path
from dataclasses import replace
from concurrent.futures import ProcessPoolExecutor,as_completed
from datetime import datetime,timezone
import json,hashlib,traceback,statistics,os
from .models import Config,MODEL_VERSION
from .validation import validate
from .analytic import candidates
from .io import write_json,sha256
from .results import summary,write_csv
from .sumo.network import build
from .sumo.demand import create as create_demand
from .sumo.signals import create as create_signals
from .sumo.runner import run,Cancelled

PROTOCOL_VERSION=2

def core_hash():
    root=Path(__file__).parent
    files=[root/n for n in ["models.py","validation.py","analytic.py","results.py","io.py","search.py"]]
    files+=sorted((root/"sumo").glob("*.py"))
    return hashlib.sha256(b"".join(p.name.encode()+p.read_bytes() for p in files)).hexdigest()

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,allow_nan=False).encode()).hexdigest()

def load_info(path):
    info=json.loads(Path(path).read_text(encoding="utf-8"))
    for k in ("vehicle_links","ped_links"):info[k]={int(i):v for i,v in info[k].items()}
    return info

def prepare_seed(c,folder,signature):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    key=digest(dict(config=c.fingerprint(),source=signature))
    manifest=folder/"prepared.json"
    if manifest.exists():
        saved=json.loads(manifest.read_text(encoding="utf-8"))
        if saved["key"]!=key:raise ValueError("Prepared experiment differs; choose a new output directory.")
        for rel,hashvalue in saved["files"].items():
            if not (folder/rel).exists() or sha256(folder/rel)!=hashvalue:raise ValueError("Prepared input integrity check failed: "+rel)
        return saved
    errors=validate(c)
    if any(errors.values()):raise ValueError(str(errors))
    info=build(c,folder/"network")
    if any(validate(c,info["crossing_lengths"]).values()):raise ValueError("Generated crossing constraints fail")
    create_demand(c,folder/"demand",folder/"network"/"network.net.xml")
    write_json(folder/"inputs.json",c.to_dict())
    fixed=["inputs.json","network/network.net.xml","network/network_info.json","demand/after.rou.xml","demand/vehicles.json"]
    saved=dict(key=key,source_hash=signature,files={rel:sha256(folder/rel) for rel in fixed})
    write_json(manifest,saved)
    return saved

def _run_job(job):
    seedfolder=Path(job["seedfolder"]);folder=Path(job["folder"]);folder.mkdir(parents=True,exist_ok=True)
    statusfile=folder/"status.json";resultfile=folder/"search_result.json"
    if resultfile.exists():
        saved=json.loads(resultfile.read_text(encoding="utf-8"))
        if saved["job_key"]==job["key"] and saved["valid"]:
            return dict(saved,reused=True)
    if Path(job["cancel"]).exists():raise Cancelled("Search cancellation requested")
    write_json(statusfile,dict(state="running",seed=job["seed"],ns=job["ns"],ew=job["ew"]))
    try:
        c=Config.from_dict(json.loads((seedfolder/"inputs.json").read_text(encoding="utf-8")))
        c=replace(c,improved_ns=job["ns"],improved_ew=job["ew"])
        errors=validate(c)
        if any(errors.values()):raise ValueError(str(errors))
        info=load_info(seedfolder/"network"/"network_info.json")
        if any(validate(c,info["crossing_lengths"]).values()):raise ValueError("Generated crossing constraints fail")
        attempts=[p for p in folder.glob("attempt_*") if p.is_dir()]
        attempt=folder/f"attempt_{len(attempts)+1:03d}";attempt.mkdir()
        phases=create_signals(c,job["ns"],job["ew"],info,attempt/"signals.add.xml")
        write_json(attempt/"expected_phases.json",phases)
        demand=seedfolder/"demand"/"after.rou.xml"
        metadata=json.loads((seedfolder/"demand"/"vehicles.json").read_text(encoding="utf-8"))
        result=run(c,"improved",attempt,seedfolder/"network"/"network.net.xml",demand,attempt/"signals.add.xml",info,phases,metadata,job["cancel"])
        result["demand_hash"]=sha256(demand)
        valid=not (result["anomaly_count"] or result["collisions"] or result["teleports"])
        value=dict(job_key=job["key"],source_hash=job["signature"],seed=job["seed"],ns=job["ns"],ew=job["ew"],
            candidate_id=f"NS{job['ns']:g}_EW{job['ew']:g}",reference=job["reference"],result=result,metrics=summary(result),
            valid=valid,reused=False,attempt=str(attempt.relative_to(Path(job["root"]))))
        write_json(resultfile,value)
        write_json(statusfile,dict(state="completed" if valid else "needs_review",attempt=attempt.name))
        return value
    except Cancelled:
        write_json(statusfile,dict(state="cancelled"));raise
    except Exception:
        (folder/"error.log").write_text(traceback.format_exc(),encoding="utf-8")
        write_json(statusfile,dict(state="failed"));raise

def aggregate(records,seeds,ns_values):
    references={r["seed"]:r for r in records if r["reference"]}
    rows=[]
    for ns in ns_values:
        samples=[r for r in records if r["ns"]==ns and r["valid"]]
        byseed={r["seed"]:r for r in samples}
        samples=[byseed[s] for s in seeds if s in byseed]
        full=len(samples)==len(seeds)
        pending=sum(r["metrics"]["pending"] for r in samples)
        unfinished=sum(r["metrics"]["unfinished"] for r in samples)
        requested=sum(r["metrics"]["requested"] for r in samples)
        completed=sum(r["metrics"]["completed"] for r in samples)
        reference_complete=all(s in references and references[s]["valid"] and
            not references[s]["metrics"]["pending"] and not references[s]["metrics"]["unfinished"]
            for s in seeds)
        eligible=full and reference_complete and bool(requested) and not pending and not unfinished
        losses=[r["metrics"]["time_loss"] for r in samples if r["metrics"]["time_loss"] is not None]
        worst=[r["metrics"]["worst_direction_time_loss"] for r in samples if r["metrics"]["worst_direction_time_loss"] is not None]
        paired=[];direction_deltas=[]
        for r in samples:
            ref=references.get(r["seed"])
            if not ref or not ref["valid"]:continue
            if r["result"]["demand_hash"]!=ref["result"]["demand_hash"]:raise ValueError("Unpaired demand")
            if r["metrics"]["time_loss"] is not None and ref["metrics"]["time_loss"] is not None:
                paired.append(r["metrics"]["time_loss"]-ref["metrics"]["time_loss"])
            reference_rows={v["direction"]:v for v in ref["result"]["rows"]}
            for b in r["result"]["rows"]:
                a=reference_rows[b["direction"]]
                if a["time_loss"] is not None and b["time_loss"] is not None:
                    direction_deltas.append(dict(seed=r["seed"],direction=a["direction"],delta=b["time_loss"]-a["time_loss"]))
        rows.append(dict(ns=ns,ew=samples[0]["ew"] if samples else None,seed_count=len(samples),expected_seeds=len(seeds),
            eligible=eligible,reference_complete=reference_complete,requested=requested,completed=completed,pending=pending,unfinished=unfinished,
            mean_time_loss=statistics.mean(losses) if losses else None,
            worst_direction_time_loss=statistics.mean(worst) if worst else None,
            paired_delta_mean=statistics.mean(paired) if paired else None,
            paired_delta_sd=statistics.stdev(paired) if len(paired)>1 else None,
            worst_paired_direction_delta=max((x["delta"] for x in direction_deltas),default=None),
            direction_deltas=direction_deltas,
            reason="eligible" if eligible else ("missing or invalid runs" if not full else
                ("reference missing, invalid or incomplete" if not reference_complete else
                 ("no demand" if not requested else "incomplete cohort")))))
    eligible=[r for r in rows if r["eligible"]]
    for row in rows:
        row["pareto"]=row["eligible"] and not any(
            other["mean_time_loss"]<=row["mean_time_loss"] and other["worst_direction_time_loss"]<=row["worst_direction_time_loss"] and
            (other["mean_time_loss"]<row["mean_time_loss"] or other["worst_direction_time_loss"]<row["worst_direction_time_loss"])
            for other in eligible)
    best=min(eligible,key=lambda r:(r["mean_time_loss"],r["worst_direction_time_loss"])) if eligible else None
    balanced=min(eligible,key=lambda r:(r["worst_direction_time_loss"],r["mean_time_loss"])) if eligible else None
    return dict(candidates=rows,overall_best=best["ns"] if best else None,balanced_best=balanced["ns"] if balanced else None,
        selection_rule="All candidate and paired reference seeds valid with complete scheduled observation cohorts; then compare mean time loss or worst-direction mean.",
        note="No eligible candidate is a valid result. Completed-only averages for incomplete cohorts are descriptive, not ranked as improvements.")

def search(config,root,seeds=(101,202,303),ns_values=None,workers=2,resume=False,progress=None):
    root=Path(root).resolve();root.mkdir(parents=True,exist_ok=True)
    seeds=list(seeds)
    if not seeds or len(set(seeds))!=len(seeds):raise ValueError("Unique nonempty seeds required")
    c=replace(config,record_trajectories=False,stochastic=True)
    choices=candidates(c,limit=1000)
    allowed={x["ns"]:x["ew"] for x in choices}
    ns_values=sorted(allowed if ns_values is None else ns_values)
    if any(ns not in allowed for ns in ns_values):raise ValueError("Candidate violates signal/pedestrian constraints")
    if not ns_values:raise ValueError("No signal candidate satisfies the input constraints")
    signature=core_hash()
    descriptor=dict(protocol_version=PROTOCOL_VERSION,model_version=MODEL_VERSION,source_hash=signature,
        config=c.to_dict(),seeds=seeds,ns_values=ns_values,
        candidate_scope="fixed cycle/yellow/all-red; integer NS green, remaining EW green")
    manifest=root/"search_manifest.json"
    if manifest.exists():
        old=json.loads(manifest.read_text(encoding="utf-8"))
        if digest(old)!=digest(descriptor):raise ValueError("Search inputs/source changed; use a new directory.")
    else:write_json(manifest,descriptor)
    cancel=root/"CANCEL"
    if resume and cancel.exists():cancel.unlink()
    def status(state,**extra):
        value=dict(state=state,**extra)
        write_json(root/"status.json",value)
        if progress:progress(value)
    if cancel.exists():
        status("cancelled",completed=0,total=0)
        raise Cancelled("Use resume to continue cancelled search")
    jobs=[];refs=[]
    for seed in seeds:
        sc=replace(c,seed=seed)
        seedfolder=root/f"seed_{seed}"
        prepare_seed(sc,seedfolder,signature)
        values=sorted(set(ns_values)|{c.before_ns})
        for ns in values:
            ew=c.cycle-2*(c.yellow+c.all_red)-ns
            reference=ns==c.before_ns
            params=dict(seed=seed,ns=ns,ew=ew,prepared=json.loads((seedfolder/"prepared.json").read_text())["key"])
            jobs.append(dict(**params,key=digest(params),seedfolder=str(seedfolder),
                folder=str(seedfolder/f"candidate_{ns:g}"),cancel=str(cancel),root=str(root),signature=signature,reference=reference))
    status("running",completed=0,total=len(jobs),message="paired SUMO candidate evaluation")
    records=[];failed=[]
    with ProcessPoolExecutor(max_workers=max(1,min(workers,4))) as pool:
        futures={pool.submit(_run_job,j):j for j in jobs}
        for future in as_completed(futures):
            j=futures[future]
            try:records.append(future.result())
            except Cancelled:pass
            except Exception as e:failed.append(dict(seed=j["seed"],ns=j["ns"],error=str(e)))
            done=sum(f.done() for f in futures)
            status("cancelling" if cancel.exists() else "running",completed=done,total=len(jobs),failed=len(failed))
    report=aggregate(records,seeds,ns_values)
    report.update(failed=failed,records=records,seeds=seeds,source_hash=signature,
                  ns_values=ns_values,cancelled=cancel.exists(),model_version=MODEL_VERSION)
    write_json(root/"search_summary.json",report)
    flat=[{k:v for k,v in r.items() if k!="direction_deltas"} for r in report["candidates"]]
    write_csv(root/"candidate_comparison.csv",flat)
    final="cancelled" if cancel.exists() else ("needs_review" if failed or len(records)!=len(jobs) or any(not r["valid"] for r in records) else "completed")
    status(final,completed=len(records)+len(failed),total=len(jobs),failed=len(failed),eligible=sum(r["eligible"] for r in report["candidates"]))
    return report

def main():
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--config",required=True);p.add_argument("--output",required=True)
    p.add_argument("--seeds",default="101,202,303");p.add_argument("--ns",default="")
    p.add_argument("--workers",type=int,default=2);p.add_argument("--resume",action="store_true")
    args=p.parse_args()
    c=Config.from_dict(json.loads(Path(args.config).read_text(encoding="utf-8")))
    report=search(c,args.output,[int(s) for s in args.seeds.split(",")],
        [int(v) for v in args.ns.split(",")] if args.ns else None,args.workers,args.resume,
        lambda s:print(json.dumps(s,ensure_ascii=False),flush=True))
    print(json.dumps({k:report[k] for k in ["overall_best","balanced_best","cancelled","failed"]},ensure_ascii=False),flush=True)

if __name__=="__main__":main()

