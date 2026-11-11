from dataclasses import replace
import math
import pytest
from traffic.models import Config, Approach, DIRECTIONS
from traffic.analytic import calculate, candidates
from traffic.validation import validate

def test_reference_values():
    results=calculate(Config())
    assert results[0]["rows"][0]["capacity"]==760
    assert results[1]["rows"][0]["vc"]==pytest.approx(900/760)
    assert [r["capacity"] for r in results[2]["rows"]]==[960,960,560,560]
    assert results[2]["rows"][2]["vc"]==pytest.approx(550/560)

def test_zero_extra_preserves_before():
    c=Config()
    c.approaches={d:replace(a,extra=0) for d,a in c.approaches.items()}
    a,b,_=calculate(c)
    assert a["rows"]==b["rows"]

def test_same_signal_preserves_after():
    c=replace(Config(),improved_ns=40,improved_ew=40)
    assert calculate(c)[1]["rows"]==calculate(c)[2]["rows"]

def test_double_lanes_double_capacity():
    c=Config();c.approaches["N"].lanes=2
    assert calculate(c)[0]["rows"][0]["capacity"]==1520

def test_demand_changes_only_ratio():
    c=Config();c.approaches["N"].extra=1000
    before,after,_=calculate(c)
    assert before["rows"][0]["capacity"]==after["rows"][0]["capacity"]
    assert before["rows"][0]["vc"]<after["rows"][0]["vc"]

def test_transfer_has_opposite_effects():
    base=calculate(Config())
    assert base[2]["rows"][0]["capacity"]>base[1]["rows"][0]["capacity"]
    assert base[2]["rows"][2]["capacity"]<base[1]["rows"][2]["capacity"]

@pytest.mark.parametrize("key,value",[
    ("cycle",0),("cycle",91),("pedestrian_speed",0),("pedestrian_speed",float("nan")),
    ("start_loss",-1),("saturation",float("inf")),("before_ns",2),
    ("pedestrian_budget_ns",22),("improved_ew",20),("step_length",0)
])
def test_bad_inputs_block_calculation(key,value):
    c=replace(Config(),**{key:value})
    result=calculate(c)
    assert any(s["errors"] for s in result)
    assert all(not s["rows"] for s in result if s["errors"])

def test_generated_geometry_is_checked():
    assert validate(Config(),{"ns":30,"ew":6})["before"]

def test_zero_volume():
    c=Config();c.approaches={d:Approach(1,0,0) for d in DIRECTIONS}
    assert all(r["vc"]==0 for s in calculate(c) for r in s["rows"])

def test_candidates_obey_constraints():
    choices=candidates(Config())
    assert choices[0]["ns"]==49
    assert choices[0]["ew"]==31
    assert choices[0]["max_vc"]==pytest.approx(900/940)
    assert all(not validate(replace(Config(),improved_ns=x["ns"],improved_ew=x["ew"]))["improved"] for x in choices)

def test_roundtrip_and_hash():
    c=Config()
    assert Config.from_dict(c.to_dict())==c
    assert replace(c,seed=43).fingerprint()!=c.fingerprint()
    assert replace(c,cycle=90.0).fingerprint()==c.fingerprint()

