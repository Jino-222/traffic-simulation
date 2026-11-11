"""Create a short, deterministic video from actual stored SUMO records."""
from pathlib import Path
import json,math,bisect
import pandas as pd
from PIL import Image,ImageDraw,ImageFont
import imageio_ffmpeg
from traffic.io import write_json,sha256
ROOT=Path(__file__).resolve().parents[1]
W,H=1600,960
COLORS={"before":"#778b86","after":"#c57930","improved":"#087f79"}
NAMES={"before":"입주 전","after":"입주 후","improved":"선택한 신호 후보"}
def font(size):return ImageFont.truetype("C:/Windows/Fonts/malgun.ttf",size)

def read_view(folder,sid,start,end):
    base=folder/sid/"replay"
    index=json.loads((base/"index.json").read_text(encoding="utf-8"))
    frames=[]
    for c in index["chunks"]:
        if c["end"]>=start-1 and c["start"]<=end+1:
            frames.extend(json.loads((base/c["file"]).read_text(encoding="utf-8")))
    telemetry=pd.read_csv(folder/sid/"telemetry.csv")
    totals=telemetry.groupby("time")[["halting","inserted","crossed","completed"]].sum()
    return dict(sid=sid,index=index,frames=frames,times=[f[0] for f in frames],totals=totals)

def panel(image,draw,view,t,box):
    x0,y0,x1,y1=box;width=x1-x0;height=y1-y0
    draw.rounded_rectangle(box,radius=15,fill="#ffffff",outline="#d4dfd6",width=2)
    draw.text((x0+20,y0+15),NAMES[view["sid"]],font=font(25),fill=COLORS[view["sid"]])
    canvas=(x0+10,y0+65,x1-10,y0+65+470);cx=(x0+x1)/2;cy=y0+65+235
    scale=(width-20)/150
    def xy(x,y):return (cx+(x-300)*scale,cy-(y-300)*scale)
    # Render in a clipped local image so roads cannot cross the info panels.
    layer=Image.new("RGB",(int(width-20),470),"#edf2ed");ld=ImageDraw.Draw(layer)
    def local(pt):
        x,y=xy(*pt);return (x-(x0+10),y-(y0+65))
    for lane in view["index"]["geometry"]["lanes"]:
        pts=[local(pt) for pt in lane["shape"]]
        if len(pts)<2:continue
        color="#fbfbf2" if lane["kind"]=="crossing" else ("#d0d9cd" if lane["pedestrian"] else "#586862")
        ld.line(pts,fill=color,width=max(1,round(lane["width"]*scale)),joint="curve")
    idx=max(0,bisect.bisect_right(view["times"],t)-1)
    frame=view["frames"][idx];nextframe=view["frames"][idx+1] if idx+1<len(view["frames"]) else None
    lookup={p[0]:p for p in nextframe[1]} if nextframe else {}
    alpha=(t-frame[0])/(nextframe[0]-frame[0]) if nextframe else 0
    phase=view["index"]["phases"][0]
    for ph in view["index"]["phases"]:
        if ph["time"]>t:break
        phase=ph
    signals=view["index"]["signals"]
    for link,d in signals["vehicle_links"].items():
        lane=next(l for l in view["index"]["geometry"]["lanes"] if l["id"]==signals["lane_ids"][d][0])
        px,py=local(lane["shape"][-1]);state=phase["state"][int(link)]
        color="#1bb58b" if state in "Gg" else "#dbb43a" if state in "yY" else "#c34b4d"
        ld.ellipse((px-5,py-5,px+5,py+5),fill=color,outline="white",width=1)
    for p in frame[1]:
        a=view["index"]["agents"][p[0]];n=lookup.get(p[0]);x=p[1]+(n[1]-p[1])*alpha if n else p[1];y=p[2]+(n[2]-p[2])*alpha if n else p[2]
        px,py=local([x,y])
        if a["kind"]=="person":
            ld.ellipse((px-3,py-3,px+3,py+3),fill="#80569b");continue
        length=(5 if a["type"]=="car" else 12)*scale;half=scale
        angle=math.radians(p[3]-90);dx,dy=math.cos(angle),math.sin(angle)
        corners=[(px+dx*along-dy*side,py+dy*along+dx*side) for along,side in [(0,-half),(0,half),(-length,half),(-length,-half)]]
        ld.polygon(corners,fill="#efa950" if a["source"]=="extra" else "#6bd1bc")
    ld.text((10,8),"북 ↑",font=font(15),fill="#193b33")
    image.paste(layer,(int(x0+10),int(y0+65)))
    signal_text=" · ".join({"N":"북","S":"남","E":"동","W":"서"}[d]+phase["state"][int(k)] for k,d in signals["vehicle_links"].items())
    draw.text((x0+20,y0+550),"실제 신호  "+signal_text,font=font(17),fill="#36574b")
    time_idx=view["totals"].index[view["totals"].index<=t]
    stats=view["totals"].loc[time_idx[-1]]
    draw.text((x0+20,y0+586),f"정지 차량 {int(stats.halting)}대  |  누적 통과 {int(stats.crossed)}대",font=font(21),fill="#193b33")
    draw.text((x0+20,y0+624),f"궤적 기록 {frame[0]:.1f}초 · 동일 시각 재생",font=font(17),fill="#61776e")

def main():
    folder=ROOT/"experiments/selected_replay_701"
    data=json.loads((folder/"comparison.json").read_text(encoding="utf-8"))
    choice=json.loads((folder/"selection.json").read_text(encoding="utf-8"))
    out=ROOT/"docs/demo";out.mkdir(exist_ok=True)
    start=900;seconds=30;fps=20;speed=6
    views=[read_view(folder,s,start,start+seconds*speed) for s in NAMES]
    movie=out/"traffic_comparison.mp4"
    writer=imageio_ffmpeg.write_frames(str(movie),(W,H),fps=fps,codec="libx264",quality=7,
        macro_block_size=16,output_params=["-movflags","+faststart"])
    writer.send(None)
    try:
        for frame in range(seconds*fps):
            t=start+frame/fps*speed
            im=Image.new("RGB",(W,H),"#f5f7f2");draw=ImageDraw.Draw(im)
            draw.text((38,24),"교통 변화 연구실",font=font(35),fill="#173e34")
            draw.text((38,80),f"아파트 입주 전·후와 선택 후보 {choice['candidate']}/ {80-choice['candidate']}초 · 실제 SUMO 기록",font=font(23),fill="#456257")
            draw.text((38,120),f"검증 시드 701 | 실험 {t:.1f}초 | 관측 시작 후 {t-start:.1f}초 | {speed}배 재생",font=font(19),fill="#456257")
            for i,view in enumerate(views):panel(im,draw,view,t,(38+i*514,170,538+i*514,850))
            draw.text((38,876),"청록: 기존 차량   주황: 입주 추가 차량   보라: 보행자   ·   중간 위치는 표시용 보간",font=font(18),fill="#456257")
            draw.text((38,913),"누적 통과: 준비 900초 포함 · 합성 실험이며 현장 효과·안전·공식 LOS를 증명하지 않습니다.",font=font(18),fill="#456257")
            if frame in (0,300,599):im.save(out/f"frame_{frame:04d}.png")
            writer.send(im.tobytes())
    finally:writer.close()
    reader=imageio_ffmpeg.read_frames(str(movie))
    metadata=next(reader);decoded=sum(1 for _ in reader)
    audit=dict(source_experiment=folder.name,comparison_hash=sha256(folder/"comparison.json"),
        candidate=choice["candidate"],seed=701,synthetic=True,start=start,simulation_seconds=seconds*speed,
        playback_seconds=seconds,fps=fps,frames_written=seconds*fps,frames_decoded=decoded,
        dimensions=[W,H],metadata=metadata,video_sha256=sha256(movie),
        interpretation="Actual FCD geometry and phases; display-only interpolation. Counts are raw telemetry including warmup.",
        matched=decoded==seconds*fps and list(metadata["size"])==[W,H])
    write_json(out/"video_audit.json",audit)
    print(json.dumps(audit,ensure_ascii=False))
if __name__=="__main__":main()

