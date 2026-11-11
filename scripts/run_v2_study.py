"""Run discovery, frozen holdout and a full-duration scenario library."""
from pathlib import Path
from dataclasses import replace
import json
from traffic.models import Config
from traffic.scenarios import library,metadata
from traffic.search import search,core_hash
from traffic.holdout import evaluate
from traffic.experiment import execute
from traffic.io import write_json
ROOT=Path(__file__).resolve().parents[1]
def main(output=None):
    root=Path(output) if output else ROOT/"experiments"/"study_v2"
    root.mkdir(parents=True,exist_ok=True)
    def progress(value):
        write_json(root/"status.json",value)
        print(json.dumps(value,ensure_ascii=False),flush=True)
    c=Config()
    progress(dict(stage="discovery",state="running"))
    saved=root/'discovery/search_summary.json'
    if saved.exists() and json.loads((root/'discovery/status.json').read_text(encoding='utf-8'))['state']=='completed':
        previous=json.loads(saved.read_text(encoding='utf-8'))
        if previous['source_hash']!=core_hash():raise ValueError('Simulation core changed; use --output with a new folder')
        # Preserve the exact discovery report whose hash was frozen before validation.
        progress(dict(stage='discovery',state='completed',reused=True))
    else:
        search(c,root/"discovery",[101,202,303],workers=2,resume=True,
               progress=lambda s:progress(dict(stage="discovery",**s)))
    progress(dict(stage="holdout",state="running"))
    evaluate(root/"discovery",root/"holdout",[701,809,911],workers=2)
    scenarios=library()
    for i,(sid,sc) in enumerate(scenarios.items()):
        folder=root/"scenarios"/sid
        config=replace(sc.config,stochastic=True,seed=407,record_trajectories=False)
        existing=folder/"comparison.json"
        if existing.exists() and (folder/"status.json").exists():
            data=json.loads(existing.read_text(encoding="utf-8"))
            state=json.loads((folder/"status.json").read_text(encoding="utf-8"))
            if Config.from_dict(data["config"]).fingerprint()!=config.fingerprint():
                raise ValueError('Scenario input changed; use --output with a new folder')
            if state["state"]=="completed":
                progress(dict(stage="scenarios",scenario=sid,completed=i+1,total=len(scenarios),reused=True));continue
        progress(dict(stage="scenarios",state="running",scenario=sid,completed=i,total=len(scenarios)))
        execute(config,folder)
        write_json(folder/"scenario.json",metadata(sc))
    progress(dict(stage="finished",state="completed",scenarios=len(scenarios),source_hash=core_hash()))
if __name__=="__main__":
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path)
    args=parser.parse_args();main(args.output)

