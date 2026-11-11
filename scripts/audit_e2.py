"""Controlled E2 test: reconstruct jam lengths from independently sampled positions."""
from pathlib import Path
from dataclasses import replace
import json,xml.etree.ElementTree as ET,time
import traci
from traffic.models import Config,Approach
from traffic.sumo.network import build,binary,write_xml
from traffic.sumo.detectors import create
from traffic.io import write_json

def expected_jams(points,gap_limit):
    points=sorted(points,key=lambda p:p["front"],reverse=True)
    jams=[];group=[]
    for p in points:
        if group and group[-1]["front"]-group[-1]["length"]-p["front"]>gap_limit:
            jams.append(group[0]["front"]-(group[-1]["front"]-group[-1]["length"]));group=[]
        group.append(p)
    if group:jams.append(group[0]["front"]-(group[-1]["front"]-group[-1]["length"]))
    return jams

def main():
    folder=Path(__file__).resolve().parents[1]/"experiments/e2_audit"
    folder.mkdir(parents=True,exist_ok=True)
    c=Config();c.approaches["N"]=Approach(2,0,0)
    c=replace(c,pedestrian_rate=0)
    build(c,folder/"network")
    detectorfile,detectors=create(c,folder/"network/network.net.xml",folder)
    routes=ET.Element("routes")
    ET.SubElement(routes,"vType",id="test",length="5",minGap="2.5",sigma="0")
    ET.SubElement(routes,"route",id="north",edges="N_in S_out")
    positions={1:[250,240,230,100,90],2:[270,258,246]}
    for lane,values in positions.items():
        for i,pos in enumerate(values):
            ET.SubElement(routes,"vehicle",id=f"v_{lane}_{i}",type="test",route="north",depart="0",
                          departLane=str(lane),departPos=str(pos),departSpeed="0")
    write_xml(folder/"routes.xml",routes)
    label="e2_audit_"+str(time.time_ns());conn=None;samples=[]
    with (folder/"sumo.log").open("w",encoding="utf-8") as log:
        try:
            traci.start([binary("sumo"),"--net-file",str(folder/"network/network.net.xml"),"--route-files",str(folder/"routes.xml"),
                         "--additional-files",str(detectorfile),"--step-length",".5","--no-step-log","true",
                         "--time-to-teleport","-1"],label=label,stdout=log)
            conn=traci.getConnection(label);conn.simulationStep()
            for lane,values in positions.items():
                for i,pos in enumerate(values):
                    vid=f"v_{lane}_{i}"
                    conn.vehicle.moveTo(vid,f"N_in_{lane}",pos)
                    conn.vehicle.setSpeedMode(vid,0);conn.vehicle.setLaneChangeMode(vid,0);conn.vehicle.setSpeed(vid,0)
            for _ in range(8):conn.simulationStep()
            for sensor in [d for d in detectors if d["direction"]=="N"]:
                points=[dict(id=v,front=conn.vehicle.getLanePosition(v),length=conn.vehicle.getLength(v),speed=conn.vehicle.getSpeed(v))
                        for v in conn.lane.getLastStepVehicleIDs(sensor["lane"])]
                jams=expected_jams(points,c.e2_jam_gap)
                samples.append(dict(detector=sensor["id"],points=points,independent_clusters_m=jams,
                    independent_max_m=max(jams,default=0),independent_sum_m=sum(jams),
                    actual_m=conn.lanearea.getJamLengthMeters(sensor["id"]),
                    actual_vehicles=conn.lanearea.getJamLengthVehicle(sensor["id"])))
        finally:
            if conn:conn.close()
    audit=dict(thresholds=dict(speed=c.e2_speed_threshold,time=c.e2_time_threshold,gap=c.e2_jam_gap),
               samples=samples,directional_max_m=max(x["actual_m"] for x in samples),
               sum_parallel_lanes_m=sum(x["actual_m"] for x in samples),
               purpose="Known stopped vehicle groups; compare SUMO E2 retrieval to front/rear geometry, and distinguish max from sum.")
    write_json(folder/"audit.json",audit);print(json.dumps(audit,indent=2))
if __name__=="__main__":main()

