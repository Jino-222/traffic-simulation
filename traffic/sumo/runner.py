from pathlib import Path
import csv, math, os, subprocess, time, xml.etree.ElementTree as ET
import traci
import traci.constants as tc
from ..models import DIRECTIONS, OPPOSITE
from ..io import write_json
from .network import binary
from .detectors import create as create_detectors
from ..results import vehicle_table,write_csv,quantile

class Cancelled(Exception): pass

def run(c, scenario_id, folder, netfile, routefile, signalfile, info, phases, metadata, cancel_file=None):
    folder=Path(folder); folder.mkdir(parents=True,exist_ok=True)
    stop=c.warmup+c.duration+c.drain
    detectorfile,detectors=create_detectors(c,netfile,folder)
    cmd=[binary("sumo"),"--net-file",str(netfile),"--route-files",str(routefile),
         "--additional-files",str(signalfile)+","+str(detectorfile),"--step-length",str(c.step_length),
         "--seed",str(c.seed),"--time-to-teleport","-1","--max-depart-delay","-1",
         "--pedestrian.striping.dawdling","0","--pedestrian.striping.jamtime","100000",
         "--collision.action","warn","--collision.check-junctions","true",
         "--tripinfo-output",str(folder/"tripinfo.xml"),"--tripinfo-output.write-unfinished","true",
         "--tripinfo-output.write-undeparted","true","--summary-output",str(folder/"summary.xml"),
         "--error-log",str(folder/"warnings.log"),"--no-step-log","true","--duration-log.disable","true",
         "--xml-validation","never"]
    if c.record_trajectories:
        cmd.extend(["--fcd-output",str(folder/"fcd.xml.gz"),"--device.fcd.probability","1",
                    "--device.fcd.period",str(c.trajectory_period),"--person-device.fcd.probability","1",
                    "--person-device.fcd.period",str(c.trajectory_period),
                    "--fcd-output.attributes","id,x,y,angle,type,speed,lane,pos"])
    label=f"{scenario_id}_{os.getpid()}_{time.time_ns()}"
    vehicle_departs={}; crossed={}; arrivals={}; last_edges={}
    ped_crossings=set(); ped_crossed_ids=set(); ped_departed=set(); ped_arrived=set()
    phase_log=[]; series=[]; anomalies=[]; checked_steps=0; collisions=0; teleports=0
    telemetry=[];probes=[]
    active_meta={v:m for v,m in metadata.items() if scenario_id!="before" or m["source"]=="base"}
    schedules={d:sorted(m["scheduled"] for m in active_meta.values() if m["direction"]==d) for d in DIRECTIONS}
    scheduled_count={d:0 for d in DIRECTIONS}
    departed_count={d:0 for d in DIRECTIONS};arrived_count={d:0 for d in DIRECTIONS};crossed_count={d:0 for d in DIRECTIONS}
    conn=None; last_state=None; prev_ped_edges={}; measured_stops={d:[] for d in DIRECTIONS}
    stdout_file=(folder/"sumo_stdout.log").open("w",encoding="utf-8")
    started=time.monotonic()
    last_progress=started
    try:
        traci.start(cmd,label=label,stdout=stdout_file,verbose=False)
        conn=traci.getConnection(label)
        # Both expected and active program are captured before the first step.
        active=conn.trafficlight.getAllProgramLogics("C")
        selected=[p for p in active if p.programID=="study"]
        if not selected: raise RuntimeError("연구 신호 프로그램이 로드되지 않았습니다.")
        conn.trafficlight.setProgram("C","study")
        conn.trafficlight.setPhase("C",0)
        observed=[dict(duration=p.duration,state=p.state) for p in selected[0].phases]
        if observed != [dict(duration=p["duration"],state=p["state"]) for p in phases]:
            raise RuntimeError("설정 신호와 SUMO 신호 프로그램이 다릅니다.")
        while conn.simulation.getTime()<stop-1e-6:
            if checked_steps%100==0:
                if cancel_file and Path(cancel_file).exists(): raise Cancelled("사용자가 실험을 중단했습니다.")
                if time.monotonic()-started>300: raise TimeoutError("시나리오 실행 제한시간 300초 초과")
            conn.simulationStep()
            now=conn.simulation.getTime()
            # SUMO updates signals inside simulationStep; use the returned state for this interval.
            t=round(now-c.step_length,6)
            state=conn.trafficlight.getRedYellowGreenState("C")
            position=t % c.cycle
            expected=None
            for phase in phases:
                if position < phase["duration"]-1e-6:
                    expected=phase["state"];break
                position-=phase["duration"]
            if expected is not None and state!=expected:
                anomalies.append(dict(type="phase_timing_mismatch",time=t,expected=expected,actual=state))
            if state!=last_state:
                phase_log.append(dict(time=t,phase=conn.trafficlight.getPhase("C"),state=state))
                last_state=state
            # Validate actual states against requested movement groups.
            greens={d for i,d in info["vehicle_links"].items() if state[int(i)] in "Gg"}
            if greens.intersection(("N","S")) and greens.intersection(("E","W")):
                anomalies.append(dict(type="vehicle_conflict",time=t))
            for idx,side in info["ped_links"].items():
                if state[int(idx)] in "Gg" and side in greens:
                    anomalies.append(dict(type="ped_signal_conflict",time=t,side=side))
            for vid in conn.simulation.getDepartedIDList():
                vehicle_departs[vid]=now
                departed_count[metadata[vid]["direction"]]+=1
                conn.vehicle.subscribe(vid,[tc.VAR_ROAD_ID])
            for vid in conn.simulation.getArrivedIDList():
                arrivals[vid]=now
                arrived_count[metadata[vid]["direction"]]+=1
            collisions+=conn.simulation.getCollidingVehiclesNumber()
            teleports+=conn.simulation.getStartingTeleportNumber()
            for vid,values in conn.vehicle.getAllSubscriptionResults().items():
                edge=values[tc.VAR_ROAD_ID]
                d=metadata[vid]["direction"]
                if last_edges.get(vid)==f"{d}_in" and edge.startswith(":C_"):
                    indices=[int(i) for i,side in info["vehicle_links"].items() if side==d]
                    if not any(state[i] in "GgyY" for i in indices):
                        anomalies.append(dict(type="vehicle_red_entry",time=t,vehicle=vid))
                if edge==f"{OPPOSITE[d]}_out" and vid not in crossed:
                    crossed[vid]=now
                    crossed_count[d]+=1
                last_edges[vid]=edge
            pids=conn.person.getIDList()
            ped_departed.update(pids)
            for pid in pids:
                edge=conn.person.getRoadID(pid)
                if edge in info["crossing_sides"]:
                    side=info["crossing_sides"][edge]
                    ped_crossings.add(edge); ped_crossed_ids.add(pid)
                    if prev_ped_edges.get(pid)!=edge:
                        sig=[int(i) for i,s in info["ped_links"].items() if s==side]
                        if not any(state[i] in "Gg" for i in sig):
                            anomalies.append(dict(type="ped_red_entry",time=t,person=pid))
                    if side in greens:
                        anomalies.append(dict(type="ped_occupancy_conflict",time=t,person=pid))
                prev_ped_edges[pid]=edge
            for pid in set(prev_ped_edges)-set(pids): ped_arrived.add(pid)
            for d in DIRECTIONS:
                while scheduled_count[d]<len(schedules[d]) and schedules[d][scheduled_count[d]]<=t+1e-6:
                    scheduled_count[d]+=1
            if checked_steps%max(1,round(c.telemetry_period/c.step_length))==0:
                for d in DIRECTIONS:
                    edge=f"{d}_in"
                    lane_jams=[(conn.lanearea.getJamLengthMeters(det["id"]),det["length"]) for det in detectors if det["direction"]==d]
                    speed=conn.edge.getLastStepMeanSpeed(edge)
                    telemetry.append(dict(time=t,interval_end=now,direction=d,
                        phase=conn.trafficlight.getPhase("C"),signal=state,
                        observation=c.warmup<=t<c.warmup+c.duration,
                        scheduled=scheduled_count[d],inserted=departed_count[d],crossed=crossed_count[d],completed=arrived_count[d],
                        pending=scheduled_count[d]-departed_count[d],active=departed_count[d]-arrived_count[d],
                        halting=conn.edge.getLastStepHaltingNumber(edge),vehicles=conn.edge.getLastStepVehicleNumber(edge),
                        mean_speed=speed if speed>=0 else None,
                        queue_m=max((x[0] for x in lane_jams),default=None),
                        queue_sensor_limit=any(jam>=length-c.e2_jam_gap for jam,length in lane_jams)))
            if c.record_trajectories and checked_steps%max(1,round(30/c.step_length))==0:
                points=[]
                for vid in list(conn.vehicle.getAllSubscriptionResults())[:3]:
                    points.append(dict(id=vid,kind="vehicle",xy=list(conn.vehicle.getPosition(vid)),
                        speed=conn.vehicle.getSpeed(vid),angle=conn.vehicle.getAngle(vid)))
                for pid in list(pids)[:2]:
                    points.append(dict(id=pid,kind="person",xy=list(conn.person.getPosition(pid)),
                        speed=conn.person.getSpeed(pid),angle=conn.person.getAngle(pid)))
                probes.append(dict(time=t,interval_end=now,signal=state,points=points))
            # Counts are defined as halting vehicles on each entire inbound edge, NOT queue length in metres.
            if c.warmup<=t<c.warmup+c.duration:
                counts={d:conn.edge.getLastStepHaltingNumber(f"{d}_in") for d in DIRECTIONS}
                for d in DIRECTIONS: measured_stops[d].append(counts[d])
                if int(round(t/c.step_length))%max(1,int(10/c.step_length))==0:
                    series.append(dict(time=t,**counts))
            checked_steps+=1
            if time.monotonic()-last_progress>=1:
                try:
                    write_json(folder/"progress.json",dict(time=now,end=stop,scenario=scenario_id))
                except PermissionError:
                    # A temporary OneDrive lock on progress must not alter simulation results.
                    pass
                last_progress=time.monotonic()
        conn.close();conn=None
    finally:
        if conn is not None:
            try: conn.close()
            except Exception: pass
        stdout_file.close()
    triproot=ET.parse(folder/"tripinfo.xml").getroot()
    trips={v.get("id"):v.attrib for v in triproot.findall("tripinfo")}
    vehicle_rows=vehicle_table(folder/"tripinfo.xml",metadata,scenario_id)
    write_csv(folder/"vehicles.csv",vehicle_rows,fields=["id","direction","source","vehicle_type","measured","scheduled","status","depart","arrival","time_loss","waiting_time","depart_delay","travel_time"])
    all_meta={vid:m for vid,m in metadata.items() if scenario_id!="before" or m["source"]=="base"}
    rows=[]
    for d in DIRECTIONS:
        ids=[vid for vid,m in all_meta.items() if m["direction"]==d and m["measured"]]
        inserted=[v for v in ids if v in vehicle_departs]
        complete=[v for v in ids if v in arrivals]
        crossed_cohort=[v for v in ids if v in crossed]
        def mean_attr(key):
            return sum(float(trips[v][key]) for v in complete)/len(complete) if complete else None
        rows.append(dict(direction=d,requested=len(ids),inserted=len(inserted),completed=len(complete),
                         crossed_cohort=len(crossed_cohort),pending=len(ids)-len(inserted),
                         unfinished=len(inserted)-len(complete),completion_rate=len(complete)/len(ids) if ids else None,
                         crossed_in_window=sum(1 for v,t in crossed.items() if all_meta[v]["direction"]==d and c.warmup<=t<c.warmup+c.duration),
                         waiting_time=mean_attr("waitingTime"),time_loss=mean_attr("timeLoss"),
                         depart_delay=mean_attr("departDelay"),travel_time=mean_attr("duration"),
                         mean_halting=sum(measured_stops[d])/len(measured_stops[d]) if measured_stops[d] else 0,
                         max_halting=max(measured_stops[d],default=0),
                         time_loss_p90=quantile([float(trips[v]["timeLoss"]) for v in complete],.9),
                         time_loss_median=quantile([float(trips[v]["timeLoss"]) for v in complete],.5),
                         max_queue_m=max((r["queue_m"] for r in telemetry if r["direction"]==d and r["observation"] and r["queue_m"] is not None),default=None)))
    write_json(folder/"phase_log.json",phase_log)
    write_json(folder/"observations.json",dict(departed=vehicle_departs,crossed=crossed,arrived=arrivals))
    write_json(folder/"anomalies.json",anomalies[:1000])
    write_csv(folder/"telemetry.csv",telemetry)
    write_json(folder/"trajectory_probes.json",probes)
    write_json(folder/"data_dictionary.json",dict(
        metric_cohort="scheduled departures in observation window; time averages only completed vehicles",
        telemetry_scope="all demand including warmup; cumulative event counts sampled at end of interval",
        telemetry_time="SUMO interval start; interval_end is returned TraCI time",
        observations_time="returned TraCI step-end times; used by v1 throughput accounting",
        trajectory_time="FCD simulation timestamp; independent probes record interval start and end",
        queue_metres="maximum lane E2 jam length in an approach; parallel lane lengths never added",
        queue_limit="potential detector-boundary truncation; does not measure vehicles outside the network"))
    if series:
        with (folder/"halting_series.csv").open("w",newline="",encoding="utf-8-sig") as f:
            w=csv.DictWriter(f,fieldnames=list(series[0]));w.writeheader();w.writerows(series)
    result=dict(scenario=scenario_id,rows=rows,phase_count=len(phase_log),checked_steps=checked_steps,
                collisions=collisions,teleports=teleports,anomaly_count=len(anomalies),
                pedestrian_departed=len(ped_departed),pedestrian_completed=len(ped_arrived),
                pedestrian_crossed=len(ped_crossed_ids),crossings_used=sorted(ped_crossings),
                elapsed_seconds=time.monotonic()-started,
                trajectories_recorded=c.record_trajectories,telemetry_rows=len(telemetry),
                metric_scope="completed scheduled-departure cohort; incomplete/pending separately counted; halting measured on inbound edges")
    write_json(folder/"result.json",result)
    return result

