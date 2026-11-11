"""Audit an explicitly bounded public NGSIM subset; never mix with synthetic demand."""
from pathlib import Path
import json,hashlib
import pandas as pd
from traffic.io import write_json,sha256

def main():
    root=Path(__file__).resolve().parents[1];folder=root/"data/public/ngsim"
    raw=folder/"lankershim_raw.json"
    d=pd.DataFrame(json.loads(raw.read_text(encoding="utf-8")))
    for k in d.columns:
        if k!="location":d[k]=pd.to_numeric(d[k],errors="coerce")
    required=["vehicle_id","global_time","v_vel","local_x","local_y","v_length","lane_id","preceding","space_headway"]
    missing={k:int(d[k].isna().sum()) for k in required}
    duplicates=int(d.duplicated(["vehicle_id","global_time"]).sum())
    if any(missing.values()) or duplicates:raise ValueError("Missing values or duplicated timestamp keys require review")
    if (d.v_vel<0).any():raise ValueError("Negative reported speed requires review")
    d=d.sort_values(["vehicle_id","global_time"])
    for key in ["local_x","local_y","global_x","global_y","v_length","v_width","space_headway"]:
        d[key+"_m"]=d[key]*.3048
    d["speed_mps"]=d.v_vel*.3048;d["acceleration_mps2"]=d.v_acc*.3048
    d["time_s"]=(d.global_time-d.global_time.min())/1000
    d.to_csv(folder/"trajectories_si.csv",index=False,encoding="utf-8-sig")
    # Same-lane, same-section, same-direction paired measurements, uninterrupted at 10 Hz.
    a=d.merge(d,left_on=["preceding","global_time"],right_on=["vehicle_id","global_time"],suffixes=("","_lead"))
    a=a[(a.section_id==a.section_id_lead)&(a.lane_id==a.lane_id_lead)&(a.direction==a.direction_lead)&
        (a.section_id>0)&(a.v_class==2)&(a.space_headway>a.v_length_lead)]
    a=a.sort_values(["vehicle_id","global_time"])
    cut=(a.vehicle_id.ne(a.vehicle_id.shift())|a.preceding.ne(a.preceding.shift())|
         a.section_id.ne(a.section_id.shift())|a.lane_id.ne(a.lane_id.shift())|a.global_time.diff().ne(100))
    a["segment"]=cut.cumsum()
    summary=a.groupby("segment").agg(follower=("vehicle_id","first"),leader=("preceding","first"),
        frames=("frame_id","count"),start_ms=("global_time","min"),end_ms=("global_time","max"),
        section=("section_id","first"),lane=("lane_id","first"),direction=("direction","first"))
    eligible=summary[summary.frames>=100].sort_values("frames",ascending=False).drop_duplicates("follower").sort_values("follower")
    # Deterministic split chosen before fitting; target followers do not overlap.
    eligible["split"]=["calibration" if v<=134 else "validation" for v in eligible.follower]
    segments=[]
    out=folder/"segments";out.mkdir(exist_ok=True)
    for sid,row in eligible.iterrows():
        trace=a[a.segment==sid].copy()
        name=f"follower_{int(row.follower)}_leader_{int(row.leader)}.csv"
        cols=["global_time","vehicle_id","preceding","speed_mps","speed_mps_lead","space_headway_m",
              "v_length_m","v_length_m_lead","global_x_m","global_y_m","global_x_m_lead","global_y_m_lead",
              "local_y_m","local_y_m_lead","lane_id","section_id","direction"]
        trace[cols].to_csv(out/name,index=False,encoding="utf-8-sig")
        segments.append(dict(file="segments/"+name,sha256=sha256(out/name),**{k:(v.item() if hasattr(v,"item") else v) for k,v in row.items()}))
    observed_duration=d.groupby("vehicle_id").global_time.diff().dropna()
    audit=dict(source="US DOT / FHWA NGSIM Lankershim Boulevard",synthetic=False,
        source_url="https://data.transportation.gov/d/8ect-6jqj",
        license="Creative Commons Attribution-ShareAlike 3.0 Unported",
        license_url="https://creativecommons.org/licenses/by-sa/3.0/",
        raw_sha256=sha256(raw),rows=len(d),vehicles=int(d.vehicle_id.nunique()),
        time_min_ms=int(d.global_time.min()),time_max_ms=int(d.global_time.max()),
        missing=missing,duplicate_vehicle_time=duplicates,
        intervals_ms={str(k):int(v) for k,v in observed_duration.value_counts().items()},
        conversion="feet to metres and feet/second to metres/second: multiply by 0.3048",
        selection=json.loads((folder/"request.json").read_text(encoding="utf-8-sig")),
        segments=segments,calibration_followers=[s["follower"] for s in segments if s["split"]=="calibration"],
        validation_followers=[s["follower"] for s in segments if s["split"]=="validation"],
        limitations=["Vehicle-ID bounded convenience subset, not representative flow counts.",
          "Split by target follower, same place and overlapping times; not external site validation.",
          "Raw video-derived positions/speeds may contain measurement noise; no smoothing yet.",
          "Pair extraction and import only. SUMO parameter calibration and held-out comparison not yet performed.",
          "Do not claim this validates synthetic apartment demand or four-arm signal optimization."])
    write_json(folder/"audit.json",audit)
    print(json.dumps({k:audit[k] for k in ["rows","vehicles","duplicate_vehicle_time","calibration_followers","validation_followers"]}))
if __name__=="__main__":main()

