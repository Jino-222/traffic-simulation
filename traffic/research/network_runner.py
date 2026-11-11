"""Measured-cohort simulation for explicitly defined movement networks."""
from pathlib import Path
import hashlib,json,math,os,random,time,xml.etree.ElementTree as ET
import traci
import traci.constants as tc
from ..io import write_json,sha256
from ..sumo.network import binary,write_xml
from ..results import vehicle_table,write_csv
from ..queue import groups
from .networks import phase_at,validate_plan,write_plan,conflicts

def source_hash():
    here=Path(__file__).parent
    files=[here/'networks.py',Path(__file__),here.parent/'queue.py',here.parent/'results.py']
    return hashlib.sha256(b''.join(p.name.encode()+p.read_bytes() for p in files)).hexdigest()

def allocation(total,weights):
    if total<0 or any(v<0 for v in weights.values()):raise ValueError('Negative demand')
    s=sum(weights.values())
    if not s:return {k:0 for k in weights}
    raw={k:total*v/s for k,v in weights.items()};out={k:math.floor(v) for k,v in raw.items()}
    order=sorted(raw,key=lambda k:(-(raw[k]-out[k]),k))
    for k in order[:total-sum(out.values())]:out[k]+=1
    return out

def create_demand(info,folder,base_rates,extra_rates,seed=17,warmup=300,duration=1800,pedestrian_rate=30,step=.5):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    metadata={};base=[];extra=[];people=[]
    origins=sorted({r['edges'][0] for r in info['flows'].values()})
    for kind,rates,destination in [('base',base_rates,base),('extra',extra_rates,extra)]:
        for period,start,length in [('warmup',0,warmup),('measure',warmup,duration)]:
            for origin in origins:
                weights={f:rates.get(f,0) for f,r in info['flows'].items() if r['edges'][0]==origin}
                counts=allocation(int(math.floor(sum(weights.values())*length/3600+.5)),weights)
                for flow,n in counts.items():
                    entropy=hashlib.sha256(f'{seed}:{flow}:{kind}:{period}'.encode()).digest()
                    rng=random.Random(int.from_bytes(entropy[:8],'big'))
                    times=sorted(math.floor(rng.random()*length/step)*step+start for _ in range(n))
                    for k,t in enumerate(times):
                        vid=f'{flow}_{kind}_{period}_{k}';route=info['flows'][flow]
                        v=ET.Element('vehicle',id=vid,type='car',route=flow,depart=str(t),departLane=str(route['depart_lane']),departSpeed='max')
                        destination.append((t,v))
                        metadata[vid]=dict(direction=route['direction'],movement=flow,source=kind,vehicle_type='car',
                            measured=period=='measure',scheduled=t,edges=route['edges'])
    for route in info['ped_routes']:
        for period,start,length in [('warmup',0,warmup),('measure',warmup,duration)]:
            n=int(math.floor(pedestrian_rate*length/3600+.5))
            for k in range(n):
                t=start+math.floor((k+.5)*length/n/step)*step
                p=ET.Element('person',id=f"p_{route['id']}_{period}_{k}",type='walker',depart=str(t),departPos=str(route['depart_pos']))
                ET.SubElement(p,'walk',edges=route['from']+' '+route['to'],arrivalPos='1',speed='1')
                people.append((t,p))
    for name,vehicles in [('before',base),('after',base+extra)]:
        root=ET.Element('routes')
        ET.SubElement(root,'vType',id='car',vClass='passenger',carFollowModel='Krauss',length='5',minGap='2.5',accel='2.6',decel='4.5',
            tau='1',sigma='0',speedFactor='1',speedDev='0')
        ET.SubElement(root,'vType',id='walker',vClass='pedestrian',maxSpeed='1',speedFactor='1',speedDev='0',impatience='0')
        for flow,r in info['flows'].items():ET.SubElement(root,'route',id=flow,edges=' '.join(r['edges']))
        for _,v in sorted(vehicles+people,key=lambda pair:(pair[0],pair[1].get('id'))):root.append(v)
        write_xml(folder/(name+'.rou.xml'),root)
    write_json(folder/'vehicles.json',metadata)
    # Existing vehicles must be identical in the before/after input, including departure lane/time.
    before={x.get('id'):x.attrib for x in ET.parse(folder/'before.rou.xml').getroot().findall('vehicle')}
    after={x.get('id'):x.attrib for x in ET.parse(folder/'after.rou.xml').getroot().findall('vehicle')}
    if not all(after[k]==v for k,v in before.items()):raise AssertionError('Before vehicles changed in after demand')
    return metadata

def run(info,netfile,routefile,metadata,plan,folder,scenario='after',seed=17,warmup=300,duration=1800,drain=600,step=.5,record=False):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    validate_plan(info,plan);write_plan(plan,folder/'signals.xml')
    request=dict(scenario=scenario,seed=seed,warmup=warmup,duration=duration,drain=drain,step=step,record=record,
        plan=plan,net_sha256=sha256(netfile),demand_sha256=sha256(routefile),
        code_sha256=source_hash())
    if (folder/'result.json').exists():
        cached=json.loads((folder/'result.json').read_text(encoding='utf-8'))
        if cached['request']!=request:raise ValueError('Experiment inputs or code changed; use a new output folder')
        return cached
    write_json(folder/'request.json',request)
    active_meta={k:v for k,v in metadata.items() if scenario!='before' or v['source']=='base'}
    edges=sorted({l['edge'] for l in info['lanes'].values() if l['kind']=='road' and not l['pedestrian']})
    lane_meta={k:v for k,v in info['lanes'].items() if v['kind']=='road' and not v['pedestrian']}
    edge_lanes={edge:[k for k,v in lane_meta.items() if v['edge']==edge] for edge in edges}
    link_by_route={(l['from_edge'],l['to_edge']):(tls,i) for tls,t in info['tls'].items() for i,l in t['links'].items() if l['kind']=='vehicle'}
    crossing_links={e:[(tls,i) for tls,t in info['tls'].items() for i,l in t['links'].items() if l['to_edge']==e] for e in info['crossings']}
    phases=[];telemetry=[];anomalies=[];entries={f:0 for f in info['flows']};edge_entries={e:0 for e in edges}
    previous={};last_signal={};ped_previous={};ped_seen=set();ped_done=set();crossings_used=set();stop_age={}
    collision_count=teleports=0;checks=0;start=time.monotonic();conn=None
    label='network_'+str(os.getpid())+'_'+str(time.time_ns())
    cmd=[binary('sumo'),'--net-file',str(netfile),'--route-files',str(routefile),'--additional-files',str(folder/'signals.xml'),
        '--step-length',str(step),'--seed',str(seed),'--time-to-teleport','-1','--max-depart-delay','-1',
        '--collision.action','warn','--collision.check-junctions','true','--pedestrian.striping.dawdling','0',
        '--pedestrian.striping.jamtime','100000','--tripinfo-output',str(folder/'tripinfo.xml'),
        '--tripinfo-output.write-unfinished','true','--tripinfo-output.write-undeparted','true',
        '--error-log',str(folder/'warnings.log'),'--no-step-log','true','--duration-log.disable','true']
    if record:cmd+=['--fcd-output',str(folder/'fcd.xml.gz'),'--device.fcd.period','1','--person-device.fcd.period','1',
                   '--fcd-output.attributes','id,x,y,angle,type,speed,lane,pos']
    write_json(folder/'status.json',dict(state='running',time=0))
    try:
        with (folder/'stdout.log').open('w',encoding='utf-8') as log:
            traci.start(cmd,label=label,stdout=log);conn=traci.getConnection(label)
            for tls,p in plan.items():
                conn.trafficlight.setProgram(tls,'research')
                idx,state,remaining=phase_at(p,0)
                conn.trafficlight.setPhase(tls,idx);conn.trafficlight.setPhaseDuration(tls,remaining)
            while conn.simulation.getTime()<warmup+duration+drain-1e-8:
                if checks%200==0:
                    if (folder.parent/'CANCEL').exists():raise RuntimeError('Network study cancelled')
                    if time.monotonic()-start>300:raise TimeoutError('Network experiment exceeded 300 seconds')
                    write_json(folder/'status.json',dict(state='running',time=conn.simulation.getTime(),end=warmup+duration+drain))
                conn.simulationStep();now=conn.simulation.getTime();t=round(now-step,6)
                states={tls:conn.trafficlight.getRedYellowGreenState(tls) for tls in plan}
                for tls,state in states.items():
                    expected=phase_at(plan[tls],t)[1]
                    if state!=expected:anomalies.append(dict(type='phase_mismatch',tls=tls,time=t,expected=expected,actual=state))
                    if conflicts(info,tls,state):anomalies.append(dict(type='conflicting_greens',tls=tls,time=t))
                    if state!=last_signal.get(tls):phases.append(dict(time=t,tls=tls,state=state));last_signal[tls]=state
                for vid in conn.simulation.getDepartedIDList():
                    conn.vehicle.subscribe(vid,[tc.VAR_ROAD_ID,tc.VAR_LANE_ID,tc.VAR_LANEPOSITION,tc.VAR_SPEED,tc.VAR_LENGTH])
                collision_count+=conn.simulation.getCollidingVehiclesNumber();teleports+=conn.simulation.getStartingTeleportNumber()
                values=conn.vehicle.getAllSubscriptionResults();lane_points={lane:[] for lane in lane_meta};halting={e:0 for e in edges};vehicles={e:0 for e in edges}
                for vid,v in values.items():
                    edge=v[tc.VAR_ROAD_ID];lane=v[tc.VAR_LANE_ID];m=active_meta[vid];prior=previous.get(vid)
                    if prior!=edge:
                        if edge in edge_entries:edge_entries[edge]+=1
                        if edge.startswith(':') and prior in m['edges']:
                            at=m['edges'].index(prior)
                            if at+1<len(m['edges']):
                                tls,i=link_by_route[(prior,m['edges'][at+1])]
                                if states[tls][int(i)] not in 'GgyY':anomalies.append(dict(type='red_vehicle_entry',vehicle=vid,tls=tls,time=t))
                                entries[m['movement']]+=1
                        if not edge.startswith(':') and edge not in m['edges']:anomalies.append(dict(type='wrong_route',vehicle=vid,time=t,edge=edge))
                    previous[vid]=edge
                    speed=v[tc.VAR_SPEED];stop_age[vid]=stop_age.get(vid,0)+step if speed<.1 else 0
                    if edge in vehicles:vehicles[edge]+=1;halting[edge]+=int(speed<.1)
                    if lane in lane_points and stop_age[vid]>1:
                        lane_points[lane].append(dict(front=v[tc.VAR_LANEPOSITION],length=v[tc.VAR_LENGTH]))
                stop_age={k:v for k,v in stop_age.items() if k in values}
                pids=set(conn.person.getIDList());ped_seen.update(pids)
                for pid in pids:
                    edge=conn.person.getRoadID(pid)
                    if edge in info['crossings']:
                        crossings_used.add(edge)
                        for tls,i in crossing_links[edge]:
                            if edge!=ped_previous.get(pid) and states[tls][int(i)] not in 'Gg':
                                anomalies.append(dict(type='red_pedestrian_entry',person=pid,tls=tls,time=t))
                            active=[j for j in info['tls'][tls]['links'] if states[tls][int(j)] in 'Gg']
                            if any(j in info['tls'][tls]['foes'][i] for j in active):
                                anomalies.append(dict(type='pedestrian_occupancy_conflict',person=pid,tls=tls,time=t))
                    ped_previous[pid]=edge
                ped_done.update(set(ped_previous)-pids)
                if checks%round(5/step)==0:
                    for edge in edges:
                        lengths=[];boundary=False
                        for lane in edge_lanes[edge]:
                            points=lane_points[lane];lengths.extend(groups(points,10,end=lane_meta[lane]['length']))
                            boundary|=any(p['front']-p['length']<=10 for p in points)
                        telemetry.append(dict(time=t,interval_end=now,observation=warmup<=t<warmup+duration,edge=edge,
                            vehicles=vehicles[edge],halting=halting[edge],entries=edge_entries[edge],
                            geometric_queue_m=max(lengths,default=0),upstream_boundary_occupied=boundary))
                checks+=1
            conn.close();conn=None
    except Exception as exc:
        write_json(folder/'status.json',dict(state='failed',error=str(exc)))
        raise
    finally:
        if conn:conn.close()
    rows=vehicle_table(folder/'tripinfo.xml',metadata,scenario)
    for r in rows:r['movement']=metadata[r['id']]['movement']
    write_csv(folder/'vehicles.csv',rows);write_csv(folder/'telemetry.csv',telemetry);write_csv(folder/'phases.csv',phases)
    grouped=[]
    for flow in info['flows']:
        chosen=[r for r in rows if r['measured'] and r['movement']==flow];done=[r for r in chosen if r['status']=='completed']
        grouped.append(dict(movement=flow,direction=info['flows'][flow]['direction'],requested=len(chosen),completed=len(done),
            pending=sum(r['status']=='pending' for r in chosen),unfinished=sum(r['status']=='unfinished' for r in chosen),
            time_loss=sum(r['time_loss'] for r in done)/len(done) if done else None,
            depart_delay=sum(r['depart_delay'] for r in done)/len(done) if done else None))
    completed=sum(r['completed'] for r in grouped);count=sum(r['requested'] for r in grouped)
    measured=[r for r in telemetry if r['observation']]
    edge_stats={edge:dict(mean_halting=sum(r['halting'] for r in measured if r['edge']==edge)/max(1,sum(r['edge']==edge for r in measured)),
        max_geometric_queue_m=max((r['geometric_queue_m'] for r in measured if r['edge']==edge),default=0),
        boundary_occupied_samples=sum(r['upstream_boundary_occupied'] for r in measured if r['edge']==edge)) for edge in edges}
    result=dict(request=request,rows=grouped,requested=count,completed=completed,pending=sum(r['pending'] for r in grouped),
        unfinished=sum(r['unfinished'] for r in grouped),mean_time_loss=sum((r['time_loss'] or 0)*r['completed'] for r in grouped)/completed if completed else None,
        mean_depart_delay=sum((r['depart_delay'] or 0)*r['completed'] for r in grouped)/completed if completed else None,
        collisions=collision_count,teleports=teleports,anomaly_count=len(anomalies),anomalies=anomalies,
        movement_entries=entries,edge_stats=edge_stats,pedestrian_seen=len(ped_seen),pedestrian_completed=len(ped_done),
        crossings_used=sorted(crossings_used),steps=checks,elapsed_seconds=time.monotonic()-start,
        integrity_passed=not(anomalies or collision_count or teleports),
        scope='Scheduled-departure observation cohort; time means only completed vehicles. Edge series sampled every 5 s; includes warmup/drain with observation flag.',
        queue_definition='Longest contiguous group with speed<0.1m/s for >1s and bumper gap<=10m, maximum across lanes. Boundary flag is observed truncation risk, not proof of spillback.')
    if count!=completed+result['pending']+result['unfinished']:raise AssertionError('Cohort accounting mismatch')
    write_json(folder/'result.json',result);write_json(folder/'status.json',dict(state='completed' if result['integrity_passed'] else 'needs_review'))
    return result
