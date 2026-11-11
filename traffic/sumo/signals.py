from pathlib import Path
import xml.etree.ElementTree as ET
from .network import write_xml

def create(c, ns, ew, info, path):
    phases=[]
    for axis,green in [("ns",ns),("ew",ew)]:
        vehicle_dirs=("N","S") if axis=="ns" else ("E","W")
        crossed_sides=("E","W") if axis=="ns" else ("N","S")
        for name,duration,car,ped in [
            (axis+"_walk",c.pedestrian_walk,"G",True),
            (axis+"_clear",green-c.pedestrian_walk,"G",False),
            (axis+"_yellow",c.yellow,"y",False),
            (axis+"_all_red",c.all_red,"r",False)
        ]:
            if duration<=0: continue
            state=["r"]*info["signal_count"]
            for index,d in info["vehicle_links"].items():
                if d in vehicle_dirs: state[int(index)]=car
            for index,d in info["ped_links"].items():
                if ped and d in crossed_sides: state[int(index)]="G"
            phases.append(dict(name=name,duration=duration,state="".join(state)))
    if abs(sum(p["duration"] for p in phases)-c.cycle)>1e-6: raise ValueError("신호 주기 불일치")
    root=ET.Element("additional")
    tls=ET.SubElement(root,"tlLogic",id="C",type="static",programID="study",offset="0")
    for phase in phases: ET.SubElement(tls,"phase",**{k:str(v) for k,v in phase.items()})
    write_xml(Path(path),root)
    return phases

