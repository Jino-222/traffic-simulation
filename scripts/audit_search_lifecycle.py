"""Exercise cancellation during actual SUMO work, resume, and an overloaded no-winner case."""
from pathlib import Path
from dataclasses import replace
import json
from traffic.models import Config,Approach
from traffic.search import search
from traffic.experiment import new_folder
from traffic.io import write_json,sha256
ROOT=Path(__file__).resolve().parents[1]

def main():
    root=new_folder(ROOT/'experiments/search_lifecycle');root.mkdir(parents=True)
    c=replace(Config(),warmup=0,duration=180,drain=120)
    folder=root/'cancel_resume';write_json(folder/'request_config.json',c.to_dict())
    updates=[]
    def stop_after_work(s):
        updates.append(s)
        if s['state']=='running' and s['completed']>=2:(folder/'CANCEL').touch()
    partial=search(c,folder,[515],workers=2,progress=stop_after_work)
    assert partial['cancelled'] and 0<len(partial['records'])<31
    completed={str(r['ns']):sha256(folder/r['attempt']/'tripinfo.xml') for r in partial['records'] if r['valid']}
    write_json(root/'cancelled_snapshot.json',partial)
    resumed=search(c,folder,[515],workers=2,resume=True)
    assert not resumed['cancelled'] and not resumed['failed'] and len(resumed['records'])==31
    for r in resumed['records']:
        if str(r['ns']) in completed:
            assert r['reused'] and sha256(folder/r['attempt']/'tripinfo.xml')==completed[str(r['ns'])]
    overload=replace(c,drain=30,approaches={d:Approach(1,5000,1000) for d in c.approaches})
    nofit=search(overload,root/'no_eligible',[616],[25,55],workers=2)
    assert nofit['overall_best'] is None and nofit['balanced_best'] is None
    assert all(not r['eligible'] and r['pending']+r['unfinished']>0 for r in nofit['candidates'])
    audit=dict(passed=True,path=str(root.relative_to(ROOT)),cancelled_after_valid_runs=len(completed),
        resumed_total=31,preserved_tripinfo_hashes=completed,actual_running_progress=updates,
        no_eligible_case=str((root/'no_eligible').relative_to(ROOT)),
        no_eligible_pending=[r['pending'] for r in nofit['candidates']],no_eligible_unfinished=[r['unfinished'] for r in nofit['candidates']])
    write_json(ROOT/'docs/search_lifecycle_audit.json',audit)
    print(json.dumps({k:v for k,v in audit.items() if k not in ('actual_running_progress','preserved_tripinfo_hashes')},ensure_ascii=False))

if __name__=='__main__':main()
