"""Deterministic synthetic-demand SUMO study on OSM Beomeo geometry."""
from pathlib import Path
import os, json, math, random, subprocess, hashlib, xml.etree.ElementTree as ET
import sumolib

ROOT=Path(__file__).resolve().parent
HOME=Path(os.environ.get('SUMO_HOME',Path.home()/'AppData/Local/TrafficImpactLab/venv/Lib/site-packages/sumo'))
SUMO=HOME/'bin/sumo.exe'
N=sumolib.net.readNet(str(ROOT/'network/beomeo.net.xml'),withInternal=True,withPrograms=True)
C=N.convertLonLat2XY(128.6262151,35.8591365)
TLS=min(N.getTrafficLights(),key=lambda t: min(math.dist(c[0].getShape()[-1],C) for c in t.getConnections()))
ENTRY={'N':'55801221#1','S':'32499615#6','E':'374787080#2','W':'375783195#4'}
EXIT={'N':'32527752#6','S':'55801218#3','E':'374787071#12','W':'761764528#7'}
RATE={'N':400,'S':450,'E':900,'W':900}
EXTRA=600
START,DEMAND_END,END=300,1500,2100
SEED=2026

def save_xml(root,path):
    ET.indent(root); ET.ElementTree(root).write(path,encoding='utf-8',xml_declaration=True)

def main():
    routes={}; lengths={}
    for a in ENTRY:
        for b in EXIT:
            if a==b: continue
            edges,cost=N.getShortestPath(N.getEdge(ENTRY[a]),N.getEdge(EXIT[b]),vClass='passenger')
            if not edges: raise ValueError(f'No route {a}-{b}')
            routes[a+b]=[e.getID() for e in edges]; lengths[a+b]=cost
    rng=random.Random(SEED); vehicles=[]
    opposite={'N':'S','S':'N','E':'W','W':'E'}
    def demand(group,a,rate):
        count=round(rate*DEMAND_END/3600)
        destinations=[b for b in EXIT if b!=a]
        for i in range(count):
            t=(i+rng.random())*DEMAND_END/count
            b=rng.choices(destinations,[.6 if b==opposite[a] else .2 for b in destinations])[0]
            typ=rng.choices(['car','bus','truck'],[.92,.04,.04])[0]
            vehicles.append({'id':f'{group}_{a}_{i:04d}','depart':round(t,2),'route':a+b,'type':typ,'group':group})
    for a,rate in RATE.items(): demand('base',a,rate)
    demand('extra','S',EXTRA)
    vehicles.sort(key=lambda v:(v['depart'],v['id']))
    for name in ['before','after']:
        rr=ET.Element('routes')
        for typ,ln,wd,vc in [('car',4.6,1.8,'passenger'),('bus',11.5,2.5,'passenger'),('truck',7.5,2.4,'passenger')]:
            # Bus/truck are visual/physical examples, passenger permissions intentionally retained.
            ET.SubElement(rr,'vType',id=typ,vClass=vc,length=str(ln),width=str(wd),maxSpeed='16.67',accel='2.0',decel='4.5',sigma='0',speedFactor='1',minGap='2.5',tau='1.2',guiShape=('passenger' if typ=='car' else typ))
        for rid,edges in routes.items(): ET.SubElement(rr,'route',id=rid,edges=' '.join(edges))
        for v in vehicles:
            if name=='before' and v['group']=='extra': continue
            ET.SubElement(rr,'vehicle',**{k:str(v[k]) for k in ['id','depart','route','type']},departLane='best',departSpeed='max')
        save_xml(rr,ROOT/f'data/{name}.rou.xml')
    phases=TLS.getPrograms()['0'].getPhases()
    greens=[i for i,p in enumerate(phases) if 'y' not in p.state.lower() and 'g' in p.state.lower()]
    weights=[0.0 for _ in greens]
    for rid,route in routes.items():
        rate=(RATE[rid[0]]+(EXTRA if rid[0]=='S' else 0))*(.6 if rid[1]==opposite[rid[0]] else .2)
        for ine,out,index in TLS.getConnections():
            if ine.getEdge().isSpecial(): continue
            pair=(ine.getEdge().getID(),out.getEdge().getID())
            if not any(pair==(x,y) for x,y in zip(route,route[1:])): continue
            eligible=[j for j,i in enumerate(greens) if phases[i].state[index] in 'Gg']
            for j in eligible: weights[j]+=rate/max(1,len(eligible))/ine.getEdge().getLaneNumber()
    available=round(sum(phases[i].duration for i in greens)); minimum=10
    alloc=[minimum+int((available-minimum*len(greens))*w/sum(weights)) for w in weights]
    for j in sorted(range(len(weights)),key=lambda j:weights[j],reverse=True)[:available-sum(alloc)]: alloc[j]+=1
    plan={i:alloc[j] for j,i in enumerate(greens)}
    runmeta={}
    for name,label in [('before','입주 전'),('after','입주 후'),('adjusted','신호 조정안')]:
        out=ROOT/'runs'/name; out.mkdir(parents=True,exist_ok=True)
        add=ET.Element('additional')
        if name=='adjusted':
            tl=ET.SubElement(add,'tlLogic',id=TLS.getID(),type='static',programID='candidate',offset='0')
            for i,p in enumerate(phases): ET.SubElement(tl,'phase',duration=str(plan.get(i,p.duration)),state=p.state)
        ET.SubElement(add,'edgeData',id='edges',file='edges.xml',period='60',begin=str(START),end=str(DEMAND_END),excludeEmpty='true')
        ET.SubElement(add,'timedEvent',type='SaveTLSStates',dest='tls.xml.gz')
        save_xml(add,out/'measurements.add.xml')
        cfg=ET.Element('configuration'); inp=ET.SubElement(cfg,'input')
        ET.SubElement(inp,'net-file',value='../../network/beomeo.net.xml')
        ET.SubElement(inp,'route-files',value=f'../../data/{"before" if name=="before" else "after"}.rou.xml')
        ET.SubElement(inp,'additional-files',value='measurements.add.xml,../../network/beomeo.poly.xml')
        time=ET.SubElement(cfg,'time')
        for k,v in [('begin',0),('end',END),('step-length',.5)]: ET.SubElement(time,k,value=str(v))
        process=ET.SubElement(cfg,'processing')
        ET.SubElement(process,'time-to-teleport',value='-1')
        ET.SubElement(process,'collision.action',value='warn')
        report=ET.SubElement(cfg,'report'); ET.SubElement(report,'no-step-log',value='true')
        ET.SubElement(report,'duration-log.statistics',value='true')
        output=ET.SubElement(cfg,'output')
        for k,v in [('fcd-output','fcd.xml.gz'),('tripinfo-output','tripinfo.xml'),('tripinfo-output.write-unfinished','true'),('summary-output','summary.xml'),('statistic-output','statistics.xml')]: ET.SubElement(output,k,value=v)
        dev=ET.SubElement(cfg,'fcd_device'); ET.SubElement(dev,'device.fcd.period',value='2')
        randomblock=ET.SubElement(cfg,'random_number'); ET.SubElement(randomblock,'seed',value=str(SEED))
        save_xml(cfg,out/'scenario.sumocfg')
        runmeta[name]={'label':label,'requested':sum(name!='before' or v['group']=='base' for v in vehicles),'green_seconds':[plan[i] if name=='adjusted' else phases[i].duration for i in greens]}
        proc=subprocess.run([str(SUMO),'-c','scenario.sumocfg'],cwd=out,capture_output=True,timeout=180,env={**os.environ,'SUMO_HOME':str(HOME)})
        (out/'run.log').write_bytes(proc.stdout+proc.stderr)
        if proc.returncode: raise RuntimeError(proc.stderr.decode('utf-8','replace'))
        print(name,proc.stdout.decode('utf-8','replace')[-1200:],flush=True)
    meta={'source':'OpenStreetMap geometry / synthetic demand / generated signal plans','center_xy':C,'seed':SEED,
      'base_rate_veh_h':RATE,'extra_rate_veh_h':EXTRA,'extra_entry':'S','warmup_s':START,'observation_end_s':DEMAND_END,'simulation_end_s':END,
      'tls_id':TLS.getID(),'phase_weights':weights,'phase_green_indices':greens,'scenarios':runmeta,'entries':ENTRY,'exits':EXIT,'routes':routes,'route_lengths_m':lengths,
      'signal_method':'One demand-weighted green split candidate. Same 90-second cycle, phase states/order and yellow durations; minimum green 10 s. Not an optimum or a field-safe plan.',
      'vehicle_types':'92% car, 4% bus-shaped, 4% truck-shaped. All passenger class permissions; no scheduled transit service.',
      'scope':'No pedestrian simulation or pedestrian clearance validation. OSM lane attributes and signal topology not field verified. Teleport disabled. One-seed visualization experiment.'}
    (ROOT/'data/experiment.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
    (ROOT/'data/vehicles.json').write_text(json.dumps(vehicles,separators=(',',':')),encoding='utf-8')

if __name__=='__main__': main()
