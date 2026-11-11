from pathlib import Path
import os, subprocess, xml.etree.ElementTree as ET
from ..models import DIRECTIONS, OPPOSITE
from ..io import write_json

def binary(name):
    import sumo
    candidate=Path(sumo.SUMO_HOME)/"bin"/(name+(".exe" if os.name=="nt" else ""))
    if not candidate.exists():
        import sumolib
        candidate=Path(sumolib.checkBinary(name))
    return str(candidate)

def write_xml(path, element):
    ET.indent(element)
    ET.ElementTree(element).write(path,encoding="utf-8",xml_declaration=True)

def build(c, folder):
    folder=Path(folder); folder.mkdir(parents=True,exist_ok=True)
    nodes=ET.Element("nodes")
    ET.SubElement(nodes,"node",id="C",x="0",y="0",type="traffic_light")
    coords={"N":(0,c.road_length),"S":(0,-c.road_length),"E":(c.road_length,0),"W":(-c.road_length,0)}
    for d,(x,y) in coords.items(): ET.SubElement(nodes,"node",id=d,x=str(x),y=str(y),type="dead_end")
    edges=ET.Element("edges")
    connections=ET.Element("connections")
    for d in DIRECTIONS:
        for suffix,start,end,n in [("in",d,"C",c.approaches[d].lanes),("out","C",d,c.approaches[OPPOSITE[d]].lanes)]:
            ET.SubElement(edges,"edge",{"id":f"{d}_{suffix}","from":start,"to":end,
                                      "numLanes":str(n),"speed":str(c.speed_kmh/3.6),"width":"3.2",
                                      "sidewalkWidth":"2","priority":"1"})
        for lane in range(c.approaches[d].lanes):
            ET.SubElement(connections,"connection",{"from":f"{d}_in","to":f"{OPPOSITE[d]}_out",
                                                  "fromLane":str(lane+1),"toLane":str(lane+1)})
        ET.SubElement(connections,"crossing",node="C",edges=f"{d}_in {d}_out",width="3",priority="true")
    for name,root in [("nodes.nod.xml",nodes),("edges.edg.xml",edges),("connections.con.xml",connections)]:
        write_xml(folder/name,root)
    cmd=[binary("netconvert"),"--node-files",str(folder/"nodes.nod.xml"),"--edge-files",str(folder/"edges.edg.xml"),
         "--connection-files",str(folder/"connections.con.xml"),"--output-file",str(folder/"network.net.xml"),
         "--no-turnarounds","true","--walkingareas","true"]
    # netconvert's provisional signal plan is replaced by signals.add.xml.
    # Its --tls.allred.time accepts integers only; study phases support 0.5 s.
    p=subprocess.run(cmd,capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=60,
                     creationflags=subprocess.CREATE_NO_WINDOW if os.name=="nt" else 0)
    (folder/"netconvert.log").write_text(p.stdout+p.stderr,encoding="utf-8")
    if p.returncode: raise RuntimeError("도로망 생성 실패: "+p.stderr)
    root=ET.parse(folder/"network.net.xml").getroot()
    crossing_edges={e.get("id"):e for e in root.findall("edge") if e.get("function")=="crossing"}
    vehicle_links={}; ped_links={}; crossing_lengths={"ns":0,"ew":0}; lane_ids={}
    crossing_sides={}
    for eid,e in crossing_edges.items():
        side=e.get("crossingEdges","").split()[0][:1]
        if side not in DIRECTIONS: raise RuntimeError(f"횡단보도 방향 식별 실패: {eid}")
        axis="ew" if side in ("N","S") else "ns"
        crossing_sides[eid]=side
        crossing_lengths[axis]=max(crossing_lengths[axis],float(e.find("lane").get("length")))
    for con in root.findall("connection"):
        if con.get("tl")!="C": continue
        idx=int(con.get("linkIndex"))
        frm,to=con.get("from"),con.get("to")
        if frm in [f"{d}_in" for d in DIRECTIONS]:
            d=frm[0]
            if to!=f"{OPPOSITE[d]}_out": raise RuntimeError("직진 이외 차량 연결 발견")
            origin=root.find(f"edge[@id='{frm}']/lane[@index='{con.get('fromLane')}']")
            if origin is None or origin.get("allow")=="pedestrian":
                raise RuntimeError("차량 연결이 보행자 차로를 가리킵니다.")
            vehicle_links[idx]=d
        elif to in crossing_edges:
            ped_links[idx]=crossing_sides[to]
        else: raise RuntimeError(f"알 수 없는 신호 연결: {frm}->{to}")
    for d in DIRECTIONS:
        edge=root.find(f"edge[@id='{d}_in']")
        lane_ids[d]=[l.get("id") for l in edge.findall("lane") if l.get("allow")!="pedestrian"]
        if len(lane_ids[d])!=c.approaches[d].lanes: raise RuntimeError("차로 수 불일치")
    if len(crossing_edges)!=4 or set(ped_links.values())!=set(DIRECTIONS):
        raise RuntimeError("네 횡단보도 신호 연결 검증 실패")
    indices=set(vehicle_links)|set(ped_links)
    if indices!=set(range(max(indices)+1)): raise RuntimeError("신호 인덱스 누락")
    info=dict(vehicle_links=vehicle_links,ped_links=ped_links,crossing_lengths=crossing_lengths,
              crossing_sides=crossing_sides,lane_ids=lane_ids,signal_count=max(indices)+1)
    geometry=dict(lanes=[],junctions=[])
    for edge in root.findall("edge"):
        for lane in edge.findall("lane"):
            geometry["lanes"].append(dict(id=lane.get("id"),edge=edge.get("id"),
                kind=edge.get("function","road"),pedestrian=lane.get("allow")=="pedestrian",
                width=float(lane.get("width",3.2)),length=float(lane.get("length")),
                shape=[[float(v) for v in pair.split(",")] for pair in lane.get("shape").split()]))
    for junction in root.findall("junction"):
        if junction.get("type")=="internal":continue
        geometry["junctions"].append(dict(id=junction.get("id"),x=float(junction.get("x")),y=float(junction.get("y")),
            shape=[[float(v) for v in pair.split(",")] for pair in junction.get("shape","").split()]))
    write_json(folder/"geometry.json",geometry)
    write_json(folder/"network_info.json",info)
    return info

