from copy import deepcopy
from dataclasses import replace
import json
import pytest
from traffic.models import Config
from traffic.search import search,aggregate
from traffic.holdout import evaluate
from traffic.sumo.runner import Cancelled

@pytest.fixture(scope="module")
def study(tmp_path_factory):
    root=tmp_path_factory.mktemp("search")
    c=replace(Config(),warmup=0,duration=180,drain=120)
    return root,c,search(c,root,[101,202],[35,45],workers=2)

def test_paired_search_and_reuse(study):
    root,c,r=study
    assert len(r["records"])==6 and not r["failed"]
    assert all(x["eligible"] for x in r["candidates"])
    for seed in [101,202]:
        assert len({x["result"]["demand_hash"] for x in r["records"] if x["seed"]==seed})==1
    rerun=search(c,root,[101,202],[35,45],workers=2,resume=True)
    assert all(x["reused"] for x in rerun["records"])
    assert r["overall_best"]==rerun["overall_best"]
    with pytest.raises(ValueError,match="changed"):
        search(replace(c,duration=181),root,[101,202],[35,45])

def test_missing_or_invalid_reference_cannot_recommend(study):
    records=deepcopy(study[2]["records"])
    for row in records:
        if row["reference"] and row["seed"]==202:row["valid"]=False
    r=aggregate(records,[101,202],[35,45])
    assert r["overall_best"] is None and all(not x["eligible"] for x in r["candidates"])
    assert all("reference" in x["reason"] for x in r["candidates"])

def test_incomplete_cohort_cannot_win_and_directions_match_by_id(study):
    records=deepcopy(study[2]["records"])
    for row in records:
        if row["ns"]==35:
            row["metrics"]["unfinished"]=1
            row["result"]["rows"].reverse()
    result=aggregate(records,[101,202],[35,45])
    assert result["overall_best"]==45
    row=result["candidates"][0]
    assert not row["eligible"] and row["reason"]=="incomplete cohort"

def test_holdout_is_frozen_and_uses_unseen_seeds(study,tmp_path):
    root,_,r=study
    with pytest.raises(ValueError,match="unseen"):
        evaluate(root,tmp_path/"invalid",[101])
    holdout=evaluate(root,tmp_path/"valid",[701],workers=1)
    assert holdout["state"]=="completed"
    assert holdout["frozen"]["selected"]==sorted({r["overall_best"],r["balanced_best"]})
    assert holdout["validation"]["seeds"]==[701]
    assert (tmp_path/"valid"/"frozen_selection.json").exists()

def test_cancel_and_resume(study):
    root,c,_=study
    (root/"CANCEL").touch()
    with pytest.raises(Cancelled):search(c,root,[101,202],[35,45],workers=1)
    assert json.loads((root/"status.json").read_text())["state"]=="cancelled"
    resumed=search(c,root,[101,202],[35,45],workers=1,resume=True)
    assert not (root/"CANCEL").exists() and all(x["reused"] for x in resumed["records"])

def test_failed_candidate_retries_preserving_attempt(study):
    root,c,_=study
    path=root/"seed_101"/"candidate_35"/"search_result.json"
    data=json.loads(path.read_text(encoding="utf-8"));data["valid"]=False
    path.write_text(json.dumps(data),encoding="utf-8")
    result=search(c,root,[101,202],[35,45],workers=1,resume=True)
    retried=[r for r in result["records"] if r["seed"]==101 and r["ns"]==35][0]
    assert not retried["reused"] and retried["valid"]
    assert retried["attempt"].endswith("attempt_002")
    assert (root/"seed_101"/"candidate_35"/"attempt_001"/"tripinfo.xml").exists()

