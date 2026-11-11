"""Audit paired demand, movement paths, frozen offset selection and actual outcomes."""
from pathlib import Path
import json,gzip,xml.etree.ElementTree as ET
import pandas as pd
from traffic.io import sha256,write_json
from traffic.research.networks import load_info,validate_plan
from traffic.research.network_runner import source_hash

ROOT=Path(__file__).resolve().parents[1]
def read(p):return json.loads(p.read_text(encoding='utf-8'))

def main():
    folder=ROOT/'experiments/network_study_v1';s=read(folder/'summary.json');discovery=read(folder/'discovery.json')
    assert read(folder/'status.json')['state']=='completed'
    assert s['protocol']['engine_sha256']==source_hash()
    assert s['frozen']['discovery_sha256']==sha256(folder/'discovery.json')
    assert s['frozen']['selected_before_validation'] and not s['validation_used_for_selection']
    assert set(s['protocol']['discovery_seeds']).isdisjoint(s['protocol']['validation_seeds'])
    records=discovery['records']+s['validation_records'];assert len(records)==39
    paired=0;path_checks=0;recorded_cases=[]
    for r in records:
        sub=folder/r['path'];assert read(sub/'status.json')['state']=='completed'
        assert r['integrity_passed'] and r['collisions']==r['teleports']==r['anomaly_count']==0
        assert r['requested']==r['completed']+r['pending']+r['unfinished']
        assert all(v>0 for v in r['movement_entries'].values())
        assert r['pedestrian_seen']==r['pedestrian_completed']>0
        expected_crossings=4 if r['family']=='turning' else 8
        assert len(r['crossings_used'])==expected_crossings
        length=75 if r['case'].endswith('_75') else 150
        netfolder=folder/'networks'/f"{r['family']}_{length}";info=load_info(netfolder)
        assert r['request']['net_sha256']==sha256(netfolder/'net.xml')
        validate_plan(info,r['request']['plan'])
        demand=folder/'demand'/f"{r['family']}_{length}"/f"seed_{r['seed']}"
        name='before' if r['case']=='before' else 'after'
        assert r['request']['demand_sha256']==sha256(demand/(name+'.rou.xml'))
        b={v.get('id'):v.attrib for v in ET.parse(demand/'before.rou.xml').getroot().findall('vehicle')}
        a={v.get('id'):v.attrib for v in ET.parse(demand/'after.rou.xml').getroot().findall('vehicle')}
        assert all(a[k]==v for k,v in b.items());paired+=1
        if r['request']['record']:
            meta=read(demand/'vehicles.json');csv=pd.read_csv(sub/'vehicles.csv')
            complete=set(csv.loc[csv.status=='completed','id']);observed={v:[] for v in complete}
            with gzip.open(sub/'fcd.xml.gz','rb') as stream:
                for _,el in ET.iterparse(stream,events=('end',)):
                    if el.tag!='timestep':continue
                    for v in el.findall('vehicle'):
                        vid=v.get('id');lane=info['lanes'].get(v.get('lane'))
                        if vid in observed and lane and lane['kind']=='road':
                            route=observed[vid]
                            if not route or route[-1]!=lane['edge']:route.append(lane['edge'])
                    el.clear()
            for vid,route in observed.items():assert route==meta[vid]['edges'],(vid,route,meta[vid]['edges'])
            path_checks+=len(observed);recorded_cases.append(dict(path=r['path'],completed_paths=len(observed),matched=True))
    pairs=[]
    offset=s['frozen']['selected_case']
    for seed in s['protocol']['validation_seeds']:
        a=next(r for r in s['validation_records'] if r['seed']==seed and r['case']=='offset_00')
        b=next(r for r in s['validation_records'] if r['seed']==seed and r['case']==offset)
        assert a['request']['demand_sha256']==b['request']['demand_sha256']
        assert a['pending']==a['unfinished']==b['pending']==b['unfinished']==0
        pairs.append(dict(seed=seed,reference_loss=a['mean_time_loss'],selected_loss=b['mean_time_loss'],delta=b['mean_time_loss']-a['mean_time_loss']))
    result=dict(passed=True,runs=len(records),input_hash_checks=paired,complete_path_checks=path_checks,recorded_cases=recorded_cases,
        crossings_per_family=dict(turning=4,corridor=8),all_phase_route_pedestrian_checks_passed=True,
        frozen_offset=s['frozen']['offset_seconds'],validation_pairs=pairs,
        paired_delta_mean=sum(p['delta'] for p in pairs)/len(pairs),
        note='Integrity passing includes overloaded runs; it does not make incomplete-vehicle mean travel statistics representative of all demand.')
    write_json(ROOT/'docs/network_study_audit.json',result);print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
