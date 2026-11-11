from dataclasses import replace
from pathlib import Path
import argparse, json
from traffic.models import Config, Approach, DIRECTIONS
from traffic.experiment import execute
from traffic.io import write_json

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--suite",choices=["baseline","replicates","stress","candidate","pedestrian"],default="baseline")
    args=parser.parse_args()
    base=Config()
    studies={
        "baseline":[("baseline",base)],
        "replicates":[(f"seed_{s}",replace(base,stochastic=True,seed=s)) for s in [11,22,33,44,55]],
        "stress":[
            ("high_demand",replace(base,approaches={d:Approach(1,1200,400) for d in DIRECTIONS},warmup=300,duration=900,drain=300)),
            ("zero_demand",replace(base,approaches={d:Approach(1,0,0) for d in DIRECTIONS},warmup=0,duration=180,drain=120)),
            ("asymmetric_lanes",replace(base,approaches={d:Approach(n,base.approaches[d].base,base.approaches[d].extra) for d,n in zip(DIRECTIONS,[2,1,3,1])},warmup=0,duration=180,drain=120))
        ],
        "candidate":[("candidate_49_31",replace(base,improved_ns=49,improved_ew=31))],
        "pedestrian":[("slow_pedestrian",replace(base,pedestrian_speed=.7,
            pedestrian_budget_ns=34,pedestrian_budget_ew=34,improved_ns=46,improved_ew=34,
            warmup=0,duration=180,drain=120))]
    }
    for name,c in studies[args.suite]:
        saved=Path("experiments")/name/"comparison.json"
        status=saved.parent/"status.json"
        if saved.exists() and status.exists():
            prior=json.loads(saved.read_text(encoding="utf-8"))
            if json.loads(status.read_text(encoding="utf-8"))["state"]=="completed" and Config.from_dict(prior["config"])==c:
                print(f"REUSE completed {name}",flush=True)
                continue
        print(f"START {name}",flush=True)
        result=execute(c,Path("experiments")/name,lambda x:print(json.dumps(x,ensure_ascii=False),flush=True))
        print(json.dumps({"name":name,"runs":[{"scenario":s["scenario"],"anomalies":s["anomaly_count"],"elapsed":s["elapsed_seconds"],
            "pending":sum(r["pending"]+r["unfinished"] for r in s["rows"])} for s in result["sumo"]]},ensure_ascii=False),flush=True)

if __name__=="__main__":main()
