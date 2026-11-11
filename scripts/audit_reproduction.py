"""Audit final GUI replay against the original baseline."""
from pathlib import Path
import json
from traffic.models import Config
from traffic.io import write_json
ROOT=Path(__file__).resolve().parents[1]
base=json.loads((ROOT/"experiments"/"baseline"/"comparison.json").read_text(encoding="utf-8"))
replays=[]
for file in sorted((ROOT/"experiments").glob("20*/comparison.json")):
    value=json.loads(file.read_text(encoding="utf-8"))
    if Config.from_dict(value["config"])==Config.from_dict(base["config"]):
        equal=[old["rows"]==new["rows"] for old,new in zip(base["sumo"],value["sumo"])]
        assert all(equal),file
        assert all(r["anomaly_count"]==r["collisions"]==r["teleports"]==0 for r in value["sumo"])
        replays.append(dict(folder=file.parent.name,all_directional_metrics_identical=True,
                            source_hash=value["manifest"]["source_hash"],
                            after_improved_same_demand=value["sumo"][1]["demand_hash"]==value["sumo"][2]["demand_hash"]))
assert replays,"No completed full-duration GUI reproduction found"
write_json(ROOT/"docs"/"reproduction_audit.json",dict(baseline="baseline",replays=replays,
    note="Final network-generation float-input fix does not change observed baseline metrics. GUI and CLI agree."))
print(json.dumps(replays,indent=2))

