"""Stream SUMO FCD into small browser-readable chunks and verify TraCI probes."""
from pathlib import Path
import gzip,json,math,xml.etree.ElementTree as ET
from ..io import write_json,sha256

def export(folder,network_folder,metadata,chunk_seconds=120):
    folder=Path(folder);network_folder=Path(network_folder)
    source=folder/"fcd.xml.gz"
    if not source.exists():return None
    dest=folder/"replay";dest.mkdir(exist_ok=True)
    phases=json.loads((folder/"phase_log.json").read_text(encoding="utf-8"))
    probes=json.loads((folder/"trajectory_probes.json").read_text(encoding="utf-8"))
    probe_map={round(p["time"],6):p for p in probes}
    ids={};agents=[];lane_ids={};lanes=[];chunks=[];frames=[];bucket=None
    checks=[];errors=[];total_frames=0;total_positions=0
    def flush():
        if not frames:return
        name=f"chunk_{len(chunks):04d}.json"
        write_json(dest/name,frames)
        chunks.append(dict(file=name,start=frames[0][0],end=frames[-1][0],frames=len(frames),sha256=sha256(dest/name)))
        frames.clear()
    with gzip.open(source,"rb") as stream:
        for event,element in ET.iterparse(stream,events=("end",)):
            if element.tag!="timestep":continue
            t=float(element.get("time"));slot=int(t//chunk_seconds)
            if bucket is not None and slot!=bucket:flush()
            bucket=slot;positions=[];lookup={}
            for v in element:
                vid=v.get("id")
                if vid not in ids:
                    ids[vid]=len(agents)
                    m=metadata.get(vid,{})
                    agents.append(dict(id=vid,kind=v.tag,type=v.get("type","walker" if v.tag=="person" else "car"),
                        direction=m.get("direction",vid.split("_")[1] if v.tag=="person" else None),
                        source=m.get("source","pedestrian"),scheduled=m.get("scheduled"),measured=m.get("measured")))
                lane=v.get("lane","")
                if lane not in lane_ids:lane_ids[lane]=len(lanes);lanes.append(lane)
                point=[ids[vid],float(v.get("x")),float(v.get("y")),float(v.get("angle",0)),float(v.get("speed",0)),lane_ids[lane]]
                positions.append(point);lookup[vid]=point
            frame=[t,positions];frames.append(frame);total_frames+=1;total_positions+=len(positions)
            if round(t,6) in probe_map:
                probe=probe_map[round(t,6)]
                for point in probe["points"]:
                    actual=lookup.get(point["id"])
                    ok=actual is not None and abs(actual[1]-point["xy"][0])<=.011 and abs(actual[2]-point["xy"][1])<=.011 and abs(actual[4]-point["speed"])<=.011
                    item=dict(time=t,id=point["id"],matched=ok)
                    checks.append(item)
                    if not ok:errors.append(dict(**item,expected=point,actual=actual))
            element.clear()
    flush()
    index=dict(schema_version=2,source="SUMO FCD",source_hash=sha256(source),
        frames=total_frames,positions=total_positions,agents=agents,lane_ids=lanes,
        chunks=chunks,phases=phases,geometry=json.loads((network_folder/"geometry.json").read_text(encoding="utf-8")),
        signals=json.loads((network_folder/"network_info.json").read_text(encoding="utf-8")),
        time_convention="FCD timestamps matched against TraCI interval-start probes",
        interpolation="display interpolation only; do not infer unrecorded vehicles or traffic metrics")
    write_json(dest/"index.json",index)
    audit=dict(checks=len(checks),matched=sum(x["matched"] for x in checks),errors=errors,
        source_hash=index["source_hash"],frames=total_frames,positions=total_positions,
        tolerance_metres=.011,tolerance_speed=.011)
    write_json(folder/"replay_audit.json",audit)
    return audit

