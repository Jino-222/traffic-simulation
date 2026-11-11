from dataclasses import replace
import csv,json,random,xml.etree.ElementTree as ET
from pathlib import Path
import pytest
import pandas as pd
from traffic.models import Config,DIRECTIONS
from traffic.scenarios import library
from traffic.sumo.demand import departures,create
from traffic.sumo.network import build
from traffic.experiment import execute
from traffic.validation import validate

@pytest.mark.parametrize("scenario",list(library()))
def test_named_scenarios_are_valid_and_independent(scenario):
    cases=library()
    assert not any(validate(cases[scenario].config).values())
    cases[scenario].config.approaches["N"].base=999
    assert library()["baseline"].config.approaches["N"].base==650

@pytest.mark.parametrize("randomized",[False,True])
def test_profile_preserves_total_and_time_bounds(randomized):
    uniform=departures(650,900,3600,random.Random(42),randomized,.5)
    peak=departures(650,900,3600,random.Random(42),randomized,.5,[.8,1,1.4,.8])
    assert len(uniform)==len(peak)==650
    assert min(peak)>=900 and max(peak)<4500
    if not randomized:
        buckets=[sum(900+i*900<=t<900+(i+1)*900 for t in peak) for i in range(4)]
        assert buckets[2]>buckets[1]>buckets[0]
        assert sum(buckets)==650

@pytest.mark.parametrize("changes",[
    {"demand_profile":[0,0]},{"demand_profile":[.5,1]},{"demand_profile":[float("nan")]},
    {"vehicle_mix":{"car":1,"bus":.1,"truck":0}},{"trajectory_period":.75},{"car_tau":.1}
])
def test_invalid_new_assumptions_are_rejected(changes):
    assert all(validate(replace(Config(),**changes)).values())

@pytest.fixture(scope="module")
def enhanced_run(tmp_path_factory):
    folder=tmp_path_factory.mktemp("enhanced")
    c=replace(Config(),warmup=90,duration=180,drain=120,record_trajectories=True,
              demand_profile=[.8,1,1.4,.8],vehicle_mix={"car":.85,"bus":.05,"truck":.1})
    return folder,execute(c,folder)

def test_recorded_positions_match_independent_live_probes(enhanced_run):
    folder,result=enhanced_run
    for run in result["sumo"]:
        audit=run["replay_audit"]
        assert audit["checks"]>0 and audit["matched"]==audit["checks"] and not audit["errors"]
        index=json.loads((folder/run["scenario"]/"replay"/"index.json").read_text(encoding="utf-8"))
        assert any(a["kind"]=="person" for a in index["agents"])
        assert any(a["type"] in ("bus","truck") for a in index["agents"])
        assert index["frames"]==780

def test_recorded_experiment_automatically_exports_geometric_queue(enhanced_run):
    folder,result=enhanced_run
    for run in result['sumo']:
        assert run['geometric_queue']['samples']==4*390
        queues=pd.read_csv(folder/run['scenario']/'geometric_queue.csv')
        sensors=json.loads((folder/run['scenario']/'detectors.json').read_text())['detectors']
        for d in DIRECTIONS:
            limit=max(s['length'] for s in sensors if s['direction']==d)
            assert queues.loc[queues.direction==d,'queue_m'].between(0,limit+.01).all()

def test_raw_tripinfo_and_exported_statistics_agree(enhanced_run):
    folder,data=enhanced_run
    metadata=json.loads((folder/"demand"/"vehicles.json").read_text(encoding="utf-8"))
    for run in data["sumo"]:
        tripinfo={t.get("id"):t.attrib for t in ET.parse(folder/run["scenario"]/"tripinfo.xml").getroot().findall("tripinfo")}
        for row in run["rows"]:
            ids=[v for v,m in metadata.items() if m["measured"] and m["direction"]==row["direction"]
                 and (run["scenario"]!="before" or m["source"]=="base")]
            completed=[tripinfo[v] for v in ids if v in tripinfo and float(tripinfo[v]["arrival"])>=0]
            assert len(ids)==row["requested"]
            assert len(completed)==row["completed"]
            losses=[float(v["timeLoss"]) for v in completed]
            assert row["time_loss"]==pytest.approx(pd.Series(losses).mean())
            assert row["time_loss_p90"]==pytest.approx(pd.Series(losses).quantile(.9))

def test_telemetry_conserves_vehicles_and_separates_queue_units(enhanced_run):
    folder,data=enhanced_run
    for run in data["sumo"]:
        values=pd.read_csv(folder/run["scenario"]/"telemetry.csv")
        assert (values["scheduled"]==values["pending"]+values["active"]+values["completed"]).all()
        assert (values[["pending","active","halting","queue_m"]]>=0).all().all()
        assert values["observation"].any() and (~values["observation"]).any()
        sensors=json.loads((folder/run["scenario"]/"detectors.json").read_text())
        for direction in DIRECTIONS:
            maximum=max(d["length"] for d in sensors["detectors"] if d["direction"]==direction)
            assert values.loc[values.direction==direction,"queue_m"].max()<=maximum+1
    before=ET.parse(folder/"demand"/"before.rou.xml").getroot()
    after=ET.parse(folder/"demand"/"after.rou.xml").getroot()
    b={e.get("id"):e.attrib for e in before.findall("vehicle")}
    a={e.get("id"):e.attrib for e in after.findall("vehicle")}
    assert all(a[k]==v for k,v in b.items())

