"""Record a selected candidate, then check it against the frozen holdout run."""
from pathlib import Path
from dataclasses import replace
import json
from traffic.models import Config
from traffic.experiment import execute
from traffic.io import write_json
def main():
    root=Path(__file__).resolve().parents[1]
    training=json.loads((root/"experiments/study_v2/discovery/search_summary.json").read_text(encoding="utf-8"))
    chosen=training["overall_best"]
    if chosen is None:raise ValueError("No eligible candidate")
    c=replace(Config(),seed=701,stochastic=True,record_trajectories=True,improved_ns=chosen,improved_ew=80-chosen)
    out=root/"experiments/selected_replay_701"
    if (out/"comparison.json").exists():raise ValueError("Already recorded; inspect saved result instead of overwriting")
    data=execute(c,out,lambda s:print(json.dumps(s,ensure_ascii=False),flush=True))
    write_json(out/"selection.json",dict(discovery_seeds=training["seeds"],candidate=chosen,validation_seed=701,
        selected_before_validation=True,purpose="Actual-trajectory demonstration of frozen overall-mean candidate"))
    print("Selected replay recorded",flush=True)
if __name__=="__main__":main()

