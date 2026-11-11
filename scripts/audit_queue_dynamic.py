"""Known moving/stopped layouts test FCD queue reconstruction and truncation flags."""
from pathlib import Path
from dataclasses import replace
import json,time,gzip,xml.etree.ElementTree as ET
import pandas as pd
import traci
from traffic.models import Config,Approach
from traffic.sumo.network import build,binary,write_xml
from traffic.sumo.detectors import create as detectors
from traffic.queue import audit
from traffic.io import write_json

ROOT=Path(__file__).resolve().parents[1]

def main():
    folder=ROOT/'experiments/queue_dynamic_audit';sub=folder/'after';sub.mkdir(parents=True,exist_ok=True)
    c=replace(Config(),record_trajectories=True,pedestrian_rate=0,warmup=0,duration=60,drain=0)
    c.approaches['N']=Approach(2,0,0)
    build(c,folder/'network');write_json(folder/'inputs.json',c.to_dict())
    sensorfile,sensors=detectors(c,folder/'network/network.net.xml',sub)
    route=ET.Element('routes');ET.SubElement(route,'vType',id='test',length='5',minGap='2.5',sigma='0')
    ET.SubElement(route,'route',id='north',edges='N_in S_out')
    positions={1:[250,240,230,100,90],2:[270,258,246]}
    for lane,values in positions.items():
        for i,x in enumerate(values):ET.SubElement(route,'vehicle',id=f'v{lane}_{i}',type='test',route='north',depart='0',
            departPos=str(x),departLane=str(lane),departSpeed='0')
    (folder/'demand').mkdir(exist_ok=True);write_xml(folder/'demand/after.rou.xml',route)
    label='queue_dynamic_'+str(time.time_ns());conn=None;points=[];e2=[]
    with (sub/'stdout.log').open('w',encoding='utf-8') as log:
        try:
            traci.start([binary('sumo'),'--net-file',str(folder/'network/network.net.xml'),
                '--route-files',str(folder/'demand/after.rou.xml'),'--additional-files',str(sensorfile),'--step-length','.5',
                '--fcd-output',str(sub/'fcd.xml.gz'),'--fcd-output.attributes','id,x,y,angle,type,speed,lane,pos',
                '--no-step-log','true','--duration-log.disable','true','--error-log',str(sub/'warnings.log')],label=label,stdout=log)
            conn=traci.getConnection(label);conn.simulationStep()
            for lane,values in positions.items():
                for i,x in enumerate(values):
                    vid=f'v{lane}_{i}';conn.vehicle.moveTo(vid,f'N_in_{lane}',x)
                    conn.vehicle.setLaneChangeMode(vid,0);conn.vehicle.setSpeedMode(vid,0);conn.vehicle.setSpeed(vid,0)
            for k in range(32):
                if k in (8,16):
                    layout=[250,240,230,220,210] if k==8 else [42,32,22,12,2]
                    for i,x in enumerate(layout):conn.vehicle.moveTo(f'v1_{i}','N_in_1',x)
                if k==24:
                    for vid in conn.vehicle.getIDList():conn.vehicle.setSpeed(vid,1)
                conn.simulationStep();t=conn.simulation.getTime()-.5
                for vid in conn.vehicle.getIDList():points.append(dict(time=t,id=vid,front=conn.vehicle.getLanePosition(vid),speed=conn.vehicle.getSpeed(vid)))
                if t in (2,6,10,14):
                    e2.append(dict(time=t,lanes={s['lane']:conn.lanearea.getJamLengthMeters(s['id']) for s in sensors if s['direction']=='N'}))
        finally:
            if conn:conn.close()
    definition=audit(sub);d=pd.read_csv(sub/'geometric_queue.csv');n=d[d.direction=='N']
    expected=[dict(time=2,queue_m=29,boundary=False,case='Separated groups: max(25,15,29), not their sum'),
        dict(time=6,queue_m=45,boundary=False,case='Five joined vehicles in lane 1'),
        dict(time=10,queue_m=42,boundary=True,case='Rear extends upstream; length clipped at observation boundary'),
        dict(time=14,queue_m=0,boundary=False,case='All cars resume at 1 m/s; stop qualification resets')]
    checks=[]
    for e in expected:
        r=n[n.time==e['time']].iloc[0]
        ok=abs(r.queue_m-e['queue_m'])<.02 and bool(r.upstream_limit)==e['boundary']
        checks.append(dict(**e,actual_queue_m=float(r.queue_m),actual_boundary=bool(r.upstream_limit),passed=ok))
        assert ok,checks[-1]
    original={(p['time'],p['id']):p for p in points};compared=0;max_position_error=0;max_speed_error=0
    with gzip.open(sub/'fcd.xml.gz','rb') as stream:
        for _,el in ET.iterparse(stream,events=('end',)):
            if el.tag!='timestep':continue
            t=float(el.get('time'))
            for v in el.findall('vehicle'):
                p=original.get((t,v.get('id')))
                if p:
                    max_position_error=max(max_position_error,abs(float(v.get('pos'))-p['front']))
                    max_speed_error=max(max_speed_error,abs(float(v.get('speed'))-p['speed']));compared+=1
            el.clear()
    assert compared==len(points) and max_position_error<.011 and max_speed_error<.011
    result=dict(passed=True,cases=checks,raw_e2=e2,fcd_point_checks=compared,
        fcd_max_position_error_m=max_position_error,fcd_max_speed_error_mps=max_speed_error,
        reconstruction=definition,
        interpretation='Known controlled layouts validate the geometric definition. Raw E2 separated-group values differ and remain separate.',
        limitations='Sampled and rounded FCD, strict speed/duration threshold, front-on-lane membership. Boundary flag is possible truncation, not proven network spillback.')
    write_json(folder/'audit.json',result);print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
