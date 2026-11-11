from dataclasses import replace
import json, xml.etree.ElementTree as ET
from pathlib import Path
import pytest
from traffic.models import Config, DIRECTIONS, OPPOSITE
from traffic.experiment import execute
from traffic.sumo.network import build
from traffic.sumo.demand import create
from traffic.sumo.signals import create as signals

def test_vehicle_connections_and_sidewalks(tmp_path):
    c=Config();c.approaches["N"].lanes=2;c.approaches["E"].lanes=3
    info=build(c,tmp_path)
    net=ET.parse(tmp_path/"network.net.xml").getroot()
    for d in DIRECTIONS:
        assert len(info["lane_ids"][d])==c.approaches[d].lanes
        cons=[x for x in net.findall("connection") if x.get("from")==f"{d}_in" and x.get("tl")=="C"]
        assert len(cons)==c.approaches[d].lanes
        assert all(x.get("to")==f"{OPPOSITE[d]}_out" and int(x.get("fromLane"))>=1 for x in cons)
    assert len(info["crossing_sides"])==4

def test_same_base_vehicles_and_exact_counts(tmp_path):
    c=replace(Config(),warmup=0,duration=3600,stochastic=True)
    info=build(c,tmp_path/"net")
    meta,hashes=create(c,tmp_path/"demand",tmp_path/"net"/"network.net.xml")
    before=ET.parse(tmp_path/"demand"/"before.rou.xml").getroot()
    after=ET.parse(tmp_path/"demand"/"after.rou.xml").getroot()
    b={e.get("id"):e.attrib for e in before.findall("vehicle")}
    a={e.get("id"):e.attrib for e in after.findall("vehicle")}
    assert len(b)==2000 and len(a)==2600
    assert all(a[k]==v for k,v in b.items())
    assert len(before.findall("person"))==240
    for d in DIRECTIONS:
        assert sum(m["direction"]==d and m["measured"] for m in meta.values())==c.approaches[d].base+c.approaches[d].extra

def test_signals_no_conflicting_greens(tmp_path):
    c=Config();info=build(c,tmp_path/"net")
    plan=signals(c,50,30,info,tmp_path/"signals.xml")
    assert sum(p["duration"] for p in plan)==90
    for p in plan:
        vg={d for i,d in info["vehicle_links"].items() if p["state"][i]=="G"}
        pg={d for i,d in info["ped_links"].items() if p["state"][i]=="G"}
        assert not (vg & {"N","S"} and vg & {"E","W"})
        assert not vg.intersection(pg)

@pytest.fixture(scope="module")
def smoke(tmp_path_factory):
    folder=tmp_path_factory.mktemp("smoke")
    # Streamlit number inputs serialize signal values as floats.
    c=replace(Config(),warmup=0,duration=180,drain=120,all_red=2.0,yellow=3.0,cycle=90.0)
    return execute(c,folder)

def test_actual_signal_and_pedestrian_behavior(smoke):
    for r in smoke["sumo"]:
        assert r["anomaly_count"]==r["collisions"]==r["teleports"]==0
        assert r["checked_steps"]==600
        assert len(r["crossings_used"])==4
        assert r["pedestrian_completed"]==r["pedestrian_departed"]==12

def test_cohort_accounting(smoke):
    for result in smoke["sumo"]:
        for row in result["rows"]:
            assert row["requested"]==row["completed"]+row["unfinished"]+row["pending"]
            assert row["crossed_cohort"]<=row["inserted"]
            assert row["time_loss"]>=0 and row["waiting_time"]>=0
    assert smoke["sumo"][1]["demand_hash"]==smoke["sumo"][2]["demand_hash"]

def test_same_signal_reproducible(tmp_path):
    c=replace(Config(),warmup=0,duration=90,drain=120,improved_ns=40,improved_ew=40)
    data=execute(c,tmp_path)
    assert data["sumo"][1]["rows"]==data["sumo"][2]["rows"]

def test_fractional_clearance_runs(tmp_path):
    c=replace(Config(),all_red=2.5,cycle=91.0,warmup=0,duration=91,drain=120)
    data=execute(c,tmp_path)
    for result in data["sumo"]:
        assert result["anomaly_count"]==0
    phases=json.loads((tmp_path/"improved"/"expected_phases.json").read_text())
    assert [p["duration"] for p in phases if p["name"].endswith("all_red")]==[2.5,2.5]

def test_cancel_status(tmp_path):
    (tmp_path/"CANCEL").touch()
    from traffic.sumo.runner import Cancelled
    with pytest.raises(Cancelled):
        execute(replace(Config(),warmup=0,duration=60,drain=60),tmp_path)
    assert json.loads((tmp_path/"status.json").read_text(encoding="utf-8"))["state"]=="cancelled"

