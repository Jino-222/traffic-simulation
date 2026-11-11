"""Metrics derived from raw SUMO records with explicit cohorts."""
import csv, math, xml.etree.ElementTree as ET
from pathlib import Path

def quantile(values,p):
    values=sorted(values)
    if not values:return None
    i=(len(values)-1)*p;lo=int(math.floor(i));hi=int(math.ceil(i))
    return values[lo]+(values[hi]-values[lo])*(i-lo)

def vehicle_table(tripfile,metadata,scenario):
    trips={v.get("id"):v.attrib for v in ET.parse(tripfile).getroot().findall("tripinfo")}
    rows=[]
    for vid,m in metadata.items():
        if scenario=="before" and m["source"]!="base":continue
        trip=trips.get(vid,{})
        departed=float(trip.get("depart",-1))
        arrived=float(trip.get("arrival",-1))
        status="completed" if arrived>=0 else ("unfinished" if departed>=0 else "pending")
        row=dict(id=vid,direction=m["direction"],source=m["source"],vehicle_type=m.get("vehicle_type","car"),
                 measured=m["measured"],scheduled=m["scheduled"],status=status,
                 depart=departed if departed>=0 else None,arrival=arrived if arrived>=0 else None)
        for out,key in [("time_loss","timeLoss"),("waiting_time","waitingTime"),("depart_delay","departDelay"),("travel_time","duration")]:
            row[out]=float(trip[key]) if status=="completed" and key in trip else None
        rows.append(row)
    return rows

def write_csv(path,rows,fields=None):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("w",newline="",encoding="utf-8-sig") as stream:
        writer=csv.DictWriter(stream,fieldnames=fields or list(rows[0]) if rows else fields or ["empty"])
        writer.writeheader()
        writer.writerows(rows)

def summary(result):
    rows=result["rows"]
    n=sum(r["completed"] for r in rows);requested=sum(r["requested"] for r in rows)
    return dict(requested=requested,completed=n,
        completion_rate=n/requested if requested else None,
        pending=sum(r["pending"] for r in rows),unfinished=sum(r["unfinished"] for r in rows),
        time_loss=sum((r["time_loss"] or 0)*r["completed"] for r in rows)/n if n else None,
        waiting_time=sum((r["waiting_time"] or 0)*r["completed"] for r in rows)/n if n else None,
        depart_delay=sum((r["depart_delay"] or 0)*r["completed"] for r in rows)/n if n else None,
        worst_direction_time_loss=max((r["time_loss"] for r in rows if r["time_loss"] is not None),default=None),
        anomaly_count=result["anomaly_count"],collisions=result["collisions"],teleports=result["teleports"])

