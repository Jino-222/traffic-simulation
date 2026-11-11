"""Read-only city case adapter. Keep cohorts and validation scope explicit."""
from pathlib import Path
import json, statistics, xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
CASE=ROOT/'case_studies/daegu_beomeo/v1'
NAMES={'before':'입주 전','after':'입주 후','adjusted':'신호 조정안'}
SCOPES={'all':'전체 출발 요청 · 0–1,500초','observation':'관측기간 출발 예정 · 300–1,500초'}

def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))

def summarize_cohort(vehicles,trips,start,end):
    rows=[v for v in vehicles if start<=float(v['depart'])<end]
    counts={'requested':len(rows),'completed':0,'running':0,'waiting':0}
    losses=[];waits=[];directions={}
    for v in rows:
        trip=trips.get(v['id'])
        state='waiting' if trip is None or float(trip.get('depart',-1))<0 else ('completed' if float(trip.get('arrival',-1))>=0 else 'running')
        counts[state]+=1
        d=v['route'][0];x=directions.setdefault(d,{'requested':0,'completed':0,'running':0,'waiting':0,'losses':[]})
        x['requested']+=1;x[state]+=1
        if state=='completed':
            loss=float(trip['timeLoss']);losses.append(loss);waits.append(float(trip['waitingTime']));x['losses'].append(loss)
    for x in directions.values():
        x['mean_time_loss_s']=statistics.mean(x.pop('losses')) if x['completed'] else None
    return {'counts':counts,'completion_rate':counts['completed']/counts['requested'] if counts['requested'] else None,
        'mean_time_loss_s':statistics.mean(losses) if losses else None,
        'mean_waiting_time_s':statistics.mean(waits) if waits else None,'completed_time_loss_s':losses,
        'directions':directions,'scheduled_start_s':start,'scheduled_end_exclusive_s':end,
        'end_status_time_s':2100,'ranking_eligible':counts['waiting']+counts['running']==0}

def derive(case=CASE):
    case=Path(case);meta=read(case/'data/experiment.json');demand=read(case/'data/vehicles.json')
    output={'schema_version':1,'case_id':'daegu_beomeo_v1','scopes':{},'method':{
        'membership':'scheduled departure time, not actual insertion time',
        'completed_means':'only arrived vehicles by simulation end; not a censoring-corrected overall mean',
        'mean_stopped':'all vehicles currently in the network, sampled every 2 s in [300,1500), speed <0.1 m/s',
        'edge_speed':'SUMO edgeData speed weighted by sampledSeconds in [300,1500)',
        'validation':'synthetic demand, one seed, one candidate, no pedestrian clearance or field validation'}}
    for scope,start in [('all',0),('observation',meta['warmup_s'])]:
        output['scopes'][scope]={}
        for name in NAMES:
            vehicles=[v for v in demand if name!='before' or v['group']=='base']
            trips={t.get('id'):dict(t.attrib) for t in ET.parse(case/f'runs/{name}/tripinfo.xml').getroot().findall('tripinfo')}
            output['scopes'][scope][name]=summarize_cohort(vehicles,trips,start,meta['observation_end_s'])
    return output

def load_case(case=CASE):
    case=Path(case)
    return {'metrics':read(case/'derived_metrics.json'),'original':read(case/'web/results.json'),
        'audit':read(case/'output/audit.json'),'network':read(case/'network/network_summary.json'),
        'source':read(case/'data/source.json'),'experiment':read(case/'data/experiment.json')}
