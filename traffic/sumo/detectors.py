"""Explicit E2 definitions; keep queue metres separate from halting counts."""
from pathlib import Path
import xml.etree.ElementTree as ET
from .network import write_xml
from ..io import write_json

def create(c,netfile,folder):
    folder=Path(folder)
    net=ET.parse(netfile).getroot()
    root=ET.Element("additional");meta=[]
    if c.e2_enabled:
        for edge in net.findall("edge"):
            if not edge.get("id","").endswith("_in"):continue
            for lane in edge.findall("lane"):
                if lane.get("allow")=="pedestrian":continue
                detector="e2_"+lane.get("id")
                length=float(lane.get("length"))
                ET.SubElement(root,"laneAreaDetector",id=detector,lane=lane.get("id"),pos="0",
                    endPos=str(length),period=str(c.telemetry_period),file=str(folder/"e2.xml"),
                    speedThreshold=str(c.e2_speed_threshold),timeThreshold=str(c.e2_time_threshold),
                    jamThreshold=str(c.e2_jam_gap))
                meta.append(dict(id=detector,lane=lane.get("id"),direction=edge.get("id")[0],length=length))
    path=folder/"detectors.add.xml";write_xml(path,root)
    write_json(folder/"detectors.json",dict(detectors=meta,definition=dict(
        speed_threshold=c.e2_speed_threshold,time_threshold=c.e2_time_threshold,jam_gap=c.e2_jam_gap,
        directional_metres="maximum lane jam length, never sum parallel lane lengths")))
    return path,meta

