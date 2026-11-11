"""Publish only generated replay JSON and mount a local Streamlit component."""
from pathlib import Path
import json,shutil,hashlib
import pandas as pd
import streamlit as st
from .dashboard import NAMES
ASSETS=Path(__file__).resolve().parents[1]/"frontend"
@st.cache_resource
def renderer(version):
    tag=hashlib.sha256(str(version).encode()).hexdigest()[:10]
    return st.components.v2.component("traffic_actual_replay_"+tag,
        html=(ASSETS/"replay.html").read_text(encoding="utf-8"),
        css=(ASSETS/"replay.css").read_text(encoding="utf-8"),
        js=(ASSETS/"replay.js").read_text(encoding="utf-8"))

@st.cache_data(show_spinner=False)
def prepare(folder,sids,version):
    folder=Path(folder);root=Path(__file__).resolve().parents[1]
    views=[];series=[]
    token=hashlib.sha256((str(folder)+str(version)).encode()).hexdigest()[:16]
    for sid in sids:
        source=folder/sid/"replay"
        if not (source/"index.json").exists():raise ValueError("이 실험에는 궤적 기록이 없습니다. 궤적 저장을 켜고 다시 실행하세요.")
        dest=root/"static"/"replays"/token/sid;dest.mkdir(parents=True,exist_ok=True)
        for f in source.glob("*.json"):shutil.copy2(f,dest/f.name)
        views.append(dict(title=NAMES[sid],base=f"/app/static/replays/{token}/{sid}/"))
        t=pd.read_csv(folder/sid/"telemetry.csv")
        agg=t.groupby("time",as_index=False).halting.sum().iloc[::5]
        series.append(agg[["time","halting"]].values.tolist())
    c=json.loads((folder/"inputs.json").read_text(encoding="utf-8"))
    return dict(views=views,series=series,start=c["warmup"]+30,observation_start=c['warmup'],observation_end=c['warmup']+c['duration'])

def show(folder,left="after",right="improved"):
    folder=Path(folder)
    try:data=prepare(str(folder),(left,right),(folder/"comparison.json").stat().st_mtime_ns)
    except (ValueError,FileNotFoundError) as e:st.info(str(e));return
    version=tuple((ASSETS/name).stat().st_mtime_ns for name in ('replay.html','replay.css','replay.js'))
    renderer(version)(data=data,key="actual_replay_"+folder.name+"_"+left+"_"+right)
    st.caption("재생은 저장된 궤적을 표시합니다. 궤적 구간이 바뀔 때 파일을 읽으며, 시간 손실 지표를 화면 움직임으로 추정하지 않습니다.")

