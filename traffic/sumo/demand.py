from pathlib import Path
import math, random, hashlib, bisect, xml.etree.ElementTree as ET
from ..models import DIRECTIONS, OPPOSITE
from ..io import write_json, sha256
from .network import write_xml

def departures(rate, start, duration, rng, randomize, step, profile=(1.0,)):
    n=int(math.floor(rate*duration/3600+0.5))
    if not n: return []
    times=sorted(rng.random()*duration for _ in range(n)) if randomize else [(i+0.5)*duration/n for i in range(n)]
    if len(profile)>1:
        cumulative=[];total=sum(profile);acc=0.0
        for weight in profile:
            acc+=weight/total;cumulative.append(acc)
        shaped=[]
        for t in times:
            u=t/duration
            j=min(bisect.bisect_right(cumulative,u),len(profile)-1)
            previous=cumulative[j-1] if j else 0.0
            local=(u-previous)/(cumulative[j]-previous)
            shaped.append((j+local)*duration/len(profile))
        times=shaped
    return [round((start+min(duration-step,math.floor(t/step)*step))/step)*step for t in times]

def vehicle_type(vid,seed,mix):
    draw=int.from_bytes(hashlib.sha256(f"{seed}:{vid}:vehicle_type".encode()).digest()[:8],"big")/2**64
    cumulative=0.0
    for kind in ("car","bus","truck"):
        cumulative+=mix[kind]
        if draw<cumulative:return kind
    return "truck"

def create(c, folder, network_path):
    folder=Path(folder); folder.mkdir(parents=True,exist_ok=True)
    net=ET.parse(network_path).getroot()
    base=[]; extra=[]; people=[]; metadata={}
    periods=[("warmup",0,c.warmup),("measure",c.warmup,c.duration)]
    for i,d in enumerate(DIRECTIONS):
        for j,kind in enumerate(("base","extra")):
            rng=random.Random(c.seed+100*i+10*j)
            for period,start,duration in periods:
                profile=c.demand_profile if period=="measure" else (1.0,)
                for k,t in enumerate(departures(getattr(c.approaches[d],kind),start,duration,rng,c.stochastic,c.step_length,profile)):
                    vid=f"v_{d}_{kind}_{period}_{k}"
                    vtype=vehicle_type(vid,c.seed,c.vehicle_mix)
                    el=ET.Element("vehicle",id=vid,type=vtype,route=d,depart=f"{t:.2f}",departLane="free",departSpeed="max")
                    (base if kind=="base" else extra).append((t,el))
                    metadata[vid]=dict(direction=d,source=kind,scheduled=t,measured=period=="measure",vehicle_type=vtype)
        # Start on the inbound sidewalk close to the junction, finish on the opposite sidewalk of the same arm.
        edge=net.find(f"edge[@id='{d}_in']")
        sidewalk=edge.find("lane[@allow='pedestrian']")
        depart_pos=float(sidewalk.get("length"))-1
        rng=random.Random(c.seed+1000+i)
        for period,start,duration in periods:
            for k,t in enumerate(departures(c.pedestrian_rate,start,duration,rng,c.stochastic,c.step_length)):
                person=ET.Element("person",id=f"p_{d}_{period}_{k}",type="walker",depart=f"{t:.2f}",departPos=f"{depart_pos:.2f}")
                ET.SubElement(person,"walk",edges=f"{d}_in {d}_out",arrivalPos="1",speed=str(c.pedestrian_speed))
                people.append((t,person))
    for scenario,items in [("before",base),("after",base+extra)]:
        routes=ET.Element("routes")
        ET.SubElement(routes,"vType",id="car",vClass="passenger",carFollowModel="Krauss",
                      length="5",minGap="2.5",accel="2.6",decel="4.5",tau=str(c.car_tau),sigma=str(c.car_sigma),speedFactor="1",speedDev="0")
        for kind,length,accel,tau in [("bus",12,1.2,1.5),("truck",12,1.0,1.5)]:
            ET.SubElement(routes,"vType",id=kind,vClass=kind,carFollowModel="Krauss",length=str(length),
                minGap="2.5",accel=str(accel),decel="4",tau=str(max(tau,c.car_tau)),sigma=str(c.car_sigma),speedFactor="1",speedDev="0")
        ET.SubElement(routes,"vType",id="walker",vClass="pedestrian",maxSpeed=str(c.pedestrian_speed),
                      speedFactor="1",speedDev="0",impatience="0")
        for d in DIRECTIONS: ET.SubElement(routes,"route",id=d,edges=f"{d}_in {OPPOSITE[d]}_out")
        for _,el in sorted(items+people,key=lambda row:(row[0],row[1].get("id"))): routes.append(el)
        write_xml(folder/f"{scenario}.rou.xml",routes)
    write_json(folder/"vehicles.json",metadata)
    hashes={name:sha256(folder/f"{name}.rou.xml") for name in ("before","after")}
    write_json(folder/"hashes.json",hashes)
    return metadata,hashes

