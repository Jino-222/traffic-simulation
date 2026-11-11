"""Geometry-defined stopped groups, kept separate from unverified E2 readings."""
from pathlib import Path
import gzip,json,xml.etree.ElementTree as ET
from .io import write_json,sha256
from .results import write_csv

def groups(points,gap_limit,start=0,end=float("inf")):
    ordered=sorted(points,key=lambda p:p["front"],reverse=True)
    answer=[];current=[]
    for point in ordered:
        if current and current[-1]["front"]-current[-1]["length"]-point["front"]>gap_limit:
            answer.append(max(0,min(current[0]["front"],end)-max(start,current[-1]["front"]-current[-1]["length"])))
            current=[]
        current.append(point)
    if current:answer.append(max(0,min(current[0]["front"],end)-max(start,current[-1]["front"]-current[-1]["length"])))
    return answer

def audit(folder):
    folder=Path(folder)
    source=folder/"fcd.xml.gz"
    if not source.exists():return None
    c=json.loads((folder.parent/"inputs.json").read_text(encoding="utf-8"))
    detectors=json.loads((folder/"detectors.json").read_text(encoding="utf-8"))["detectors"]
    lane_meta={s["lane"]:s for s in detectors}
    types={v.get("id"):float(v.get("length","5")) for v in ET.parse(folder.parent/"demand/after.rou.xml").getroot().findall("vType")}
    stop={};rows=[];previous_t=None;step=c["trajectory_period"]
    with gzip.open(source,"rb") as stream:
        for _,element in ET.iterparse(stream,events=("end",)):
            if element.tag!="timestep":continue
            t=float(element.get("time"))
            dt=step if previous_t is None else t-previous_t;previous_t=t
            present=set();lanes={k:[] for k in lane_meta}
            for v in element:
                if v.tag!="vehicle":continue
                vid=v.get("id");present.add(vid);lane=v.get("lane");speed=float(v.get("speed"))
                stop[vid]=stop.get(vid,0)+dt if speed<c["e2_speed_threshold"] else 0
                if lane in lanes and stop[vid]>c["e2_time_threshold"]:
                    lanes[lane].append(dict(front=float(v.get("pos")),length=types[v.get("type")]))
            stop={k:v for k,v in stop.items() if k in present}
            if abs(t/c["telemetry_period"]-round(t/c["telemetry_period"]))<1e-6:
                directional={d:dict(queue_m=0,upstream_limit=False,stopped_qualified=0) for d in ("N","S","E","W")}
                for lane,points in lanes.items():
                    meta=lane_meta[lane];values=groups(points,c["e2_jam_gap"],end=meta["length"])
                    value=directional[meta["direction"]]
                    value["queue_m"]=max(value["queue_m"],max(values,default=0))
                    value["stopped_qualified"]+=len(points)
                    value["upstream_limit"]|=any(p["front"]-p["length"]<=c["e2_jam_gap"] for p in points)
                for d,value in directional.items():rows.append(dict(time=t,direction=d,**value))
            element.clear()
    write_csv(folder/"geometric_queue.csv",rows)
    metadata=dict(source_hash=sha256(source),samples=len(rows),
        definition="Longest contiguous stopped group per lane, then maximum across parallel lanes; front-to-tail length, clipped to detector bounds.",
        stopped_speed_lt_mps=c["e2_speed_threshold"],stopped_duration_gt_s=c["e2_time_threshold"],
        maximum_bumper_gap_m=c["e2_jam_gap"],recording_step=step,
        inclusion="Vehicle front is on an incoming motor lane in FCD. This differs from E2 partial-body membership.",
        precision="FCD positions/speeds are rounded; sample-period stop duration, not sub-sample inference.",
        e2_status="Raw E2 values preserved. Controlled separated-group audit did not agree; do not label E2 queue as validated.",
        upstream_limit="A qualified stopped vehicle rear is within the gap threshold of the upstream observation boundary; potential truncation, not proof of spillback.")
    write_json(folder/"geometric_queue_definition.json",metadata)
    return metadata

