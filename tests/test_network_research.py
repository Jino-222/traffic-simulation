from copy import deepcopy
from pathlib import Path
import pytest
from traffic.research.networks import turning_network,corridor_network,turning_plan,corridor_plan,validate_plan,phase_at,load_info
from traffic.research.network_runner import allocation,create_demand,run

def test_turn_routes_and_generated_conflict_matrix(tmp_path):
    info=turning_network(tmp_path)
    assert len(info['flows'])==12 and len(info['crossings'])==4
    links=info['tls']['C']['links']
    assert sum(len(l['internal_chain'])>1 for l in links.values())==8
    plan=turning_plan(info);validate_plan(info,plan)
    broken=deepcopy(plan);state=list(broken['C']['phases'][0]['state'])
    # Add a pedestrian green that conflicts with a served vehicle movement.
    vehicle=next(i for i,l in links.items() if l['kind']=='vehicle' and state[i]=='G')
    foe=next(i for i in info['tls']['C']['foes'][vehicle] if links[i]['kind']=='pedestrian')
    state[foe]='G';broken['C']['phases'][0]['state']=''.join(state)
    with pytest.raises(ValueError,match='Conflicting green'):validate_plan(info,broken)
    assert load_info(tmp_path)['tls']['C']['foes']==info['tls']['C']['foes']

def test_offset_phase_boundaries_and_demand_rounding(tmp_path):
    info=corridor_network(tmp_path);p=corridor_plan(info,11)
    assert phase_at(p['J1'],11)[1]==phase_at(p['J0'],0)[1]
    assert phase_at(p['J1'],51)[1]==phase_at(p['J0'],40)[1]
    assert sum(allocation(7,{'a':.2,'b':.6,'c':.2}).values())==7
    assert allocation(0,{'a':0})=={'a':0}
    with pytest.raises(ValueError,match='pedestrian'):corridor_plan(info,11,10)

@pytest.mark.parametrize('kind',['turning','corridor'])
def test_runtime_movements_pedestrians_and_offsets(tmp_path,kind):
    info=turning_network(tmp_path/'net') if kind=='turning' else corridor_network(tmp_path/'net')
    rates={f:120 for f in info['flows']}
    meta=create_demand(info,tmp_path/'demand',rates,{},warmup=0,duration=180,pedestrian_rate=40)
    plan=turning_plan(info) if kind=='turning' else corridor_plan(info,11)
    r=run(info,tmp_path/'net/net.xml',tmp_path/'demand/after.rou.xml',meta,plan,tmp_path/'run',warmup=0,duration=180,drain=300)
    assert r['integrity_passed'] and r['requested']==r['completed']
    assert all(n>0 for n in r['movement_entries'].values())
    assert r['pedestrian_seen']==r['pedestrian_completed'] and r['pedestrian_seen']>0
    assert len(r['crossings_used'])==len(info['crossings'])
    assert sum(row['requested'] for row in r['rows'])==r['requested']
