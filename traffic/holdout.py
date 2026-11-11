"""Freeze discovery choices before evaluating unseen demand seeds."""
import json
from pathlib import Path
from .models import Config
from .search import search,core_hash
from .io import write_json,sha256

def evaluate(training,output,seeds=(701,809,911),workers=2):
    training=Path(training);output=Path(output)
    report=json.loads((training/"search_summary.json").read_text(encoding="utf-8"))
    manifest=json.loads((training/"search_manifest.json").read_text(encoding="utf-8"))
    state=json.loads((training/"status.json").read_text(encoding="utf-8"))
    if state["state"]!="completed" or report["failed"] or report["cancelled"]:
        raise ValueError("Training search is not complete")
    if set(seeds)&set(report["seeds"]):
        raise ValueError("Validation seeds must be unseen")
    if report["source_hash"]!=core_hash():
        raise ValueError("Core source changed after selection; rerun discovery in a new folder")
    selected=sorted({report[k] for k in ("overall_best","balanced_best") if report[k] is not None})
    frozen=dict(training=str(training.resolve()),training_summary_hash=sha256(training/"search_summary.json"),
                discovery_seeds=report["seeds"],validation_seeds=list(seeds),
                overall_best=report["overall_best"],balanced_best=report["balanced_best"],selected=selected)
    output.mkdir(parents=True,exist_ok=True)
    frozenfile=output/"frozen_selection.json"
    if frozenfile.exists():
        if json.loads(frozenfile.read_text(encoding="utf-8"))!=frozen:
            raise ValueError("Frozen selection changed; choose a new validation folder")
    else:write_json(frozenfile,frozen)
    if not selected:
        result=dict(state="no_eligible_candidate",frozen=frozen,conclusion="Discovery produced no eligible candidate.")
    else:
        validation=search(Config.from_dict(manifest["config"]),output/"runs",seeds,selected,workers,resume=True)
        result=dict(state="completed" if not validation["failed"] and not validation["cancelled"] else "needs_review",
                    frozen=frozen,validation=validation,
                    interpretation="Choices are frozen from discovery. Validation results do not reselect a winner; report each chosen candidate and its paired changes.")
    write_json(output/"holdout_summary.json",result)
    return result

def main():
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--training",required=True);p.add_argument("--output",required=True)
    p.add_argument("--seeds",default="701,809,911");p.add_argument("--workers",type=int,default=2)
    a=p.parse_args()
    r=evaluate(a.training,a.output,[int(x) for x in a.seeds.split(",")],a.workers)
    print(json.dumps(dict(state=r["state"],selection=r["frozen"]["selected"]),ensure_ascii=False),flush=True)

if __name__=="__main__":main()

