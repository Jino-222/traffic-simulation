"""Open-loop SUMO follower calibration against a bounded public NGSIM sample.

Only the leader is prescribed after initialization. Target followers evolve freely.
This is a pair-following experiment, not a reproduction of the source intersection.
"""
from pathlib import Path
import hashlib, itertools, json, os, subprocess, time
import xml.etree.ElementTree as ET
import numpy as np
import pandas as pd
import traci
import traci.constants as tc
from ..io import write_json, sha256
from ..sumo.network import binary, write_xml

ROOT=Path(__file__).resolve().parents[2]
DATA=ROOT/'data/public/ngsim'
DEFAULT_OUTPUT=ROOT/'experiments/public_calibration_v1'
BASELINE=dict(tau=1.0,minGap=2.5,accel=2.6)
GRID=[dict(tau=t,minGap=g,accel=a) for t,g,a in itertools.product([.6,1.0,1.4,1.8],[.5,1.5,2.5],[1.0,2.6])]
DT=.1

def prepare_trace(frame):
    """Freeze preprocessing: monotone leader position, unmodified measured targets."""
    d=frame.copy()
    if len(d)<2 or not np.allclose(np.diff(d.global_time),100):
        raise ValueError('Expected uninterrupted 100 ms observations')
    values=d[['local_y_m_lead','local_y_m','speed_mps','speed_mps_lead','space_headway_m','v_length_m_lead','v_length_m']].to_numpy()
    if not np.isfinite(values).all():raise ValueError('Non-finite observed values')
    sign=1 if d.local_y_m_lead.iloc[-1]>d.local_y_m_lead.iloc[0] else -1
    raw=sign*(d.local_y_m_lead.to_numpy()-d.local_y_m_lead.iloc[0])
    leader=np.maximum.accumulate(raw)
    correction=leader-raw
    lengths=d.v_length_m_lead.to_numpy()
    if np.ptp(lengths)>1e-6 or np.ptp(d.v_length_m)>1e-6:raise ValueError('Vehicle length changes inside a segment')
    target_gap=d.space_headway_m.to_numpy()-lengths
    if np.min(target_gap)<=0:raise ValueError('Observed overlapping vehicles require review')
    coordinate_headway=sign*(d.local_y_m_lead-d.local_y_m).to_numpy()
    error=float(np.max(np.abs(coordinate_headway-d.space_headway_m.to_numpy())))
    if error>.1:raise ValueError('Headway does not agree with longitudinal coordinates')
    speed=np.diff(leader)/DT
    return dict(time=np.arange(len(d))*DT,leader=leader,leader_interval_speed=speed,
        observed_speed=d.speed_mps.to_numpy(),observed_gap=target_gap,
        initial_headway=float(d.space_headway_m.iloc[0]),follower_length=float(d.v_length_m.iloc[0]),
        leader_length=float(lengths[0]),global_time=d.global_time.to_numpy(),
        quality=dict(backward_intervals=int((np.diff(raw)<-1e-9).sum()),
          monotonic_adjustment_max_m=float(correction.max()),monotonic_adjustment_rmse_m=float(np.sqrt(np.mean(correction**2))),
          headway_coordinate_max_error_m=error,leader_interval_speed_max_mps=float(speed.max()),
          leader_interval_accel_max_abs_mps2=float(np.max(np.abs(np.diff(speed)/DT))),
          leader_reported_vs_interval_speed_rmse_mps=float(np.sqrt(np.mean((speed-d.speed_mps_lead.to_numpy()[1:])**2)))))

def metrics(observed_speed,predicted_speed,observed_gap,predicted_gap):
    vs=np.asarray(predicted_speed)-np.asarray(observed_speed)
    gs=np.asarray(predicted_gap)-np.asarray(observed_gap)
    if not len(vs) or len(vs)!=len(gs):raise ValueError('Empty or mismatched comparison')
    vr=float(np.sqrt(np.mean(vs**2)));gr=float(np.sqrt(np.mean(gs**2)))
    return dict(speed_rmse_mps=vr,gap_rmse_m=gr,speed_bias_mps=float(vs.mean()),gap_bias_m=float(gs.mean()),
                score=vr/2.0+gr/10.0,frames=len(vs))

def make_network(folder,segments):
    folder.mkdir(parents=True,exist_ok=True)
    nodes=ET.Element('nodes');edges=ET.Element('edges')
    for i,s in enumerate(segments):
        fid=int(s['follower']);start='a'+str(fid);end='b'+str(fid)
        ET.SubElement(nodes,'node',id=start,x='0',y=str(i*20),type='dead_end')
        ET.SubElement(nodes,'node',id=end,x='5000',y=str(i*20),type='dead_end')
        ET.SubElement(edges,'edge',{'id':'e'+str(fid),'from':start,'to':end,'numLanes':'1','speed':'22.222222'})
    write_xml(folder/'nodes.xml',nodes);write_xml(folder/'edges.xml',edges)
    p=subprocess.run([binary('netconvert'),'--node-files',str(folder/'nodes.xml'),'--edge-files',str(folder/'edges.xml'),
        '--output-file',str(folder/'net.xml')],capture_output=True,text=True,timeout=60,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    (folder/'netconvert.log').write_text(p.stdout+p.stderr,encoding='utf-8')
    if p.returncode:raise RuntimeError(p.stderr)
    return folder/'net.xml'

def simulate(parameters,segments,data_folder,netfile,output,save_predictions=False):
    """Run independent observed pairs on separate straight lanes in one SUMO process."""
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    traces={int(s['follower']):prepare_trace(pd.read_csv(Path(data_folder)/s['file'])) for s in segments}
    routes=ET.Element('routes')
    for fid,tr in traces.items():
        for role,length in [('L',tr['leader_length']),('F',tr['follower_length'])]:
            opts={k:str(v) for k,v in parameters.items()}
            ET.SubElement(routes,'vType',dict(id=role+str(fid),carFollowModel='Krauss',length=str(length),
                sigma='0',decel='4.5',emergencyDecel='9',maxSpeed='22.222222',speedFactor='1',speedDev='0',**opts))
        ET.SubElement(routes,'route',id='r'+str(fid),edges='e'+str(fid))
        for role,pos in [('L',200+tr['initial_headway']),('F',200)]:
            ET.SubElement(routes,'vehicle',id=role+str(fid),type=role+str(fid),route='r'+str(fid),
                depart='0',departPos=str(pos),departSpeed='0')
    write_xml(output/'routes.xml',routes)
    label='public_'+str(os.getpid())+'_'+str(time.time_ns());conn=None
    rows=[];collisions=teleports=0;leader_error=0.0;started=time.monotonic()
    with (output/'stdout.log').open('w',encoding='utf-8') as log:
        try:
            traci.start([binary('sumo'),'--net-file',str(netfile),'--route-files',str(output/'routes.xml'),
                '--step-length',str(DT),'--step-method.ballistic','false','--seed','1729',
                '--time-to-teleport','-1','--collision.action','warn','--collision.mingap-factor','0',
                '--error-log',str(output/'warnings.log'),'--no-step-log','true','--duration-log.disable','true'],
                label=label,stdout=log)
            conn=traci.getConnection(label);conn.simulationStep()
            if len(conn.vehicle.getIDList())!=2*len(traces):raise RuntimeError('Pair insertion was not complete')
            for fid,tr in traces.items():
                lane='e'+str(fid)+'_0';lead='L'+str(fid);follow='F'+str(fid)
                conn.vehicle.moveTo(lead,lane,200+tr['initial_headway'])
                conn.vehicle.moveTo(follow,lane,200)
                conn.vehicle.setLaneChangeMode(lead,0);conn.vehicle.setLaneChangeMode(follow,0)
                conn.vehicle.setSpeedMode(lead,0)
                conn.vehicle.setPreviousSpeed(lead,float(tr['leader_interval_speed'][0]))
                conn.vehicle.setPreviousSpeed(follow,float(tr['observed_speed'][0]))
                conn.vehicle.subscribe(lead,[tc.VAR_LANEPOSITION,tc.VAR_SPEED])
                conn.vehicle.subscribe(follow,[tc.VAR_LANEPOSITION,tc.VAR_SPEED])
            active=set(traces)
            for k in range(1,max(len(t['time']) for t in traces.values())):
                if time.monotonic()-started>300:raise TimeoutError('Calibration candidate exceeded 300 seconds')
                for fid in list(active):
                    tr=traces[fid]
                    if k>=len(tr['time']):
                        conn.vehicle.remove('F'+str(fid));conn.vehicle.remove('L'+str(fid));active.remove(fid)
                    else:conn.vehicle.setSpeed('L'+str(fid),float(tr['leader_interval_speed'][k-1]))
                conn.simulationStep()
                collisions+=conn.simulation.getCollidingVehiclesNumber();teleports+=conn.simulation.getStartingTeleportNumber()
                values=conn.vehicle.getAllSubscriptionResults()
                for fid in active:
                    tr=traces[fid];lead=values['L'+str(fid)];follow=values['F'+str(fid)]
                    observed_leader=200+tr['initial_headway']+tr['leader'][k]
                    leader_error=max(leader_error,abs(lead[tc.VAR_LANEPOSITION]-observed_leader))
                    rows.append(dict(follower=fid,time_s=round(k*DT,6),global_time_ms=int(tr['global_time'][k]),
                        observed_speed_mps=float(tr['observed_speed'][k]),predicted_speed_mps=follow[tc.VAR_SPEED],
                        observed_gap_m=float(tr['observed_gap'][k]),
                        predicted_gap_m=lead[tc.VAR_LANEPOSITION]-follow[tc.VAR_LANEPOSITION]-tr['leader_length'],
                        leader_position_m=lead[tc.VAR_LANEPOSITION],prescribed_leader_position_m=float(observed_leader)))
        finally:
            if conn:conn.close()
    d=pd.DataFrame(rows);per=[]
    for fid,g in d.groupby('follower'):
        per.append(dict(follower=int(fid),**metrics(g.observed_speed_mps,g.predicted_speed_mps,g.observed_gap_m,g.predicted_gap_m)))
    valid=collisions==0 and teleports==0 and leader_error<1e-6 and bool((d.predicted_gap_m>=0).all())
    warning_text=(output/'warnings.log').read_text(encoding='utf-8') if (output/'warnings.log').exists() else ''
    warnings=warning_text.splitlines()
    result=dict(parameters=parameters,valid=valid,collisions=collisions,teleports=teleports,
        leader_emergency_warnings=sum("Vehicle 'L" in s and 'emergency braking' in s for s in warnings),
        follower_emergency_warnings=sum("Vehicle 'F" in s and 'emergency braking' in s for s in warnings),
        integrity_definition='No physical overlap/teleport and prescribed leader positions reproduced; does not establish realistic accelerations or field validity',
        leader_position_max_error_m=leader_error,minimum_predicted_gap_m=float(d.predicted_gap_m.min()),
        mean_score=float(np.mean([x['score'] for x in per])),
        mean_speed_rmse_mps=float(np.mean([x['speed_rmse_mps'] for x in per])),
        mean_gap_rmse_m=float(np.mean([x['gap_rmse_m'] for x in per])),
        trajectories=per,elapsed_seconds=time.monotonic()-started,
        preprocessing={str(fid):tr['quality'] for fid,tr in traces.items()})
    if save_predictions:d.to_csv(output/'predictions.csv',index=False,encoding='utf-8-sig')
    write_json(output/'result.json',result)
    return result

def run(output=DEFAULT_OUTPUT):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    audit=json.loads((DATA/'audit.json').read_text(encoding='utf-8'))
    for s in audit['segments']:
        if sha256(DATA/s['file'])!=s['sha256']:raise ValueError('Public segment changed since import audit')
    train=[s for s in audit['segments'] if s['split']=='calibration']
    holdout=[s for s in audit['segments'] if s['split']=='validation']
    if set(s['follower'] for s in train)&set(s['follower'] for s in holdout):raise ValueError('Overlapping target followers')
    import sumo
    protocol=dict(version=1,source_sha256=audit['raw_sha256'],code_sha256=sha256(__file__),sumo_version=sumo.__version__,
        train=[s['follower'] for s in train],validation=[s['follower'] for s in holdout],grid=GRID,baseline=BASELINE,
        dt=DT,model='Krauss',fixed=dict(sigma=0,decel=4.5,emergencyDecel=9,maxSpeed=22.222222,seed=1729),
        objective='Equal trajectory mean of speed RMSE / 2 m/s + bumper-gap RMSE / 10 m; exclude t=0 initialization',
        preprocessing='Longitudinal leader position oriented along motion, cumulative maximum removes backward tracking noise; target speeds and headways unchanged',
        control='Leader interval speed reproduces monotone positions; follower initialized once then evolves freely; no signals or other traffic',
        collision_definition='Physical overlap: collision.mingap-factor=0; model minGap remains in car following',
        split='Frozen follower-ID split; overlapping times and some related leaders, not independent site validation',
        source_url=audit['source_url'],license=audit['license'],license_url=audit['license_url'])
    p=output/'protocol.json'
    if p.exists() and json.loads(p.read_text(encoding='utf-8'))!=protocol:raise ValueError('Protocol/code changed: choose a new output folder')
    write_json(p,protocol)
    train_net=make_network(output/'calibration_network',train)
    results=[]
    for i,params in enumerate(GRID):
        folder=output/'calibration'/f'candidate_{i:02d}'
        write_json(output/'status.json',dict(stage='calibration',state='running',completed=i,total=len(GRID)))
        r=json.loads((folder/'result.json').read_text(encoding='utf-8')) if (folder/'result.json').exists() else simulate(params,train,DATA,train_net,folder)
        if r['parameters']!=params:raise ValueError('Cached candidate parameters differ')
        results.append(dict(candidate=i,**r));print(f'candidate {i+1}/{len(GRID)} score={r["mean_score"]:.4f} valid={r["valid"]}',flush=True)
    pd.DataFrame([dict(candidate=r['candidate'],**r['parameters'],valid=r['valid'],score=r['mean_score'],
        speed_rmse_mps=r['mean_speed_rmse_mps'],gap_rmse_m=r['mean_gap_rmse_m']) for r in results]).to_csv(output/'calibration.csv',index=False)
    eligible=[r for r in results if r['valid']]
    if not eligible:raise RuntimeError('No valid candidate; preserve failed results for review')
    selected=min(eligible,key=lambda r:(r['mean_score'],r['candidate']))
    frozen=dict(parameters=selected['parameters'],candidate=selected['candidate'],calibration_score=selected['mean_score'],
        protocol_sha256=sha256(p),calibration_csv_sha256=sha256(output/'calibration.csv'),selected_before_validation=True)
    chosen_file=output/'frozen_selection.json'
    if chosen_file.exists() and json.loads(chosen_file.read_text(encoding='utf-8'))!=frozen:raise ValueError('Frozen selection differs')
    write_json(chosen_file,frozen)
    validation_net=make_network(output/'validation_network',holdout)
    comparisons={}
    for name,params in [('baseline',BASELINE),('calibrated',frozen['parameters'])]:
        folder=output/'validation'/name
        write_json(output/'status.json',dict(stage='validation',state='running',candidate=name))
        comparisons[name]=json.loads((folder/'result.json').read_text(encoding='utf-8')) if (folder/'result.json').exists() else simulate(params,holdout,DATA,validation_net,folder,True)
    summary=dict(protocol=protocol,frozen=frozen,calibration_candidates=len(results),eligible_candidates=len(eligible),
        calibration_best=selected,validation=comparisons,validation_used_for_selection=False,
        valid=all(r['valid'] for r in comparisons.values()),
        limitations=['Small convenience sample from one road and overlapping times; target IDs separated but observations not fully independent.',
          'One-dimensional pair following with measured leader trajectory; ignores source signals, lane changing, and other vehicles.',
          'Video-derived target speeds and close gaps contain measurement noise; monotone leader correction and emergency-braking warnings are disclosed. Forced leaders can have unrealistic acceleration; this is a limitation of this replay calibration.',
          'Finite parameter grid and explicit normalized loss; no global optimum or field safety claim.',
          'Results do not calibrate synthetic apartment trip generation or validate intersection signal benefits.'])
    write_json(output/'summary.json',summary)
    write_json(output/'status.json',dict(stage='complete',state='completed' if summary['valid'] else 'needs_review'))
    print(json.dumps({k:dict(score=v['mean_score'],speed_rmse=v['mean_speed_rmse_mps'],gap_rmse=v['mean_gap_rmse_m'],valid=v['valid']) for k,v in comparisons.items()}))
    return summary

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=DEFAULT_OUTPUT)
    run(parser.parse_args().output)
