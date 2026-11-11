"""Export auditable SUMO outputs and compact browser replay data."""
from pathlib import Path
import xml.etree.ElementTree as ET
import json,gzip,math,statistics,collections,csv,hashlib
import sumolib

ROOT=Path(__file__).resolve().parent
def read(p): return json.loads(p.read_text(encoding='utf-8'))
def dump(p,x): p.write_text(json.dumps(x,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
def elements(path,tag):
    with (gzip.open(path,'rb') if path.suffix=='.gz' else open(path,'rb')) as f:
        for _,e in ET.iterparse(f,events=['end']):
            if e.tag==tag:
                yield e
                e.clear()

def main():
    meta=read(ROOT/'data/experiment.json'); source=read(ROOT/'data/source.json')
    net=sumolib.net.readNet(str(ROOT/'network/beomeo.net.xml'),withInternal=True,withPrograms=True)
    cx,cy=meta['center_xy']; shape=lambda pts:[[round(x-cx,2),round(y-cy,2)] for x,y in pts]
    roads=[{'id':e.getID(),'name':e.getName(),'lanes':e.getLaneNumber(),'width':round(sum(l.getWidth() for l in e.getLanes()),2),'shape':shape(e.getShape()),'internal':e.isSpecial()} for e in net.getEdges()]
    lanes=[{'id':l.getID(),'shape':shape(l.getShape()),'width':l.getWidth()} for e in net.getEdges(withInternal=False) for l in e.getLanes()]
    junctions=[shape(n.getShape()) for n in net.getNodes() if len(n.getShape())>2]
    raw=ET.parse(ROOT/'data/beomeo.osm.xml').getroot(); nodes={n.get('id'):net.convertLonLat2XY(float(n.get('lon')),float(n.get('lat'))) for n in raw.findall('node')}
    buildings=[]; parks=[]
    for w in raw.findall('way'):
        t={x.get('k'):x.get('v') for x in w.findall('tag')}; pts=[nodes[x.get('ref')] for x in w.findall('nd') if x.get('ref') in nodes]
        if len(pts)<3: continue
        if 'building' in t:
            h=12.0; origin='assumed'
            try:
                if 'height' in t: h=float(t['height'].replace('m','').strip()); origin='OSM height'
                elif 'building:levels' in t: h=3*float(t['building:levels']); origin='OSM levels x assumed 3 m'
            except ValueError: pass
            buildings.append({'id':w.get('id'),'shape':shape(pts),'height':max(3,min(150,h)),'height_source':origin})
        elif t.get('leisure') in ['park','garden','pitch'] or t.get('landuse') in ['grass','forest','recreation_ground']:
            parks.append(shape(pts))
    signals=[]
    for tls in net.getTrafficLights():
        for ine,out,idx in tls.getConnections():
            for conn in ine.getOutgoing():
                if conn.getToLane()==out and conn.getTLLinkIndex()==idx and conn.getTLSID()==tls.getID():
                    via=conn.getViaLaneID(); pts=net.getLane(via).getShape() if via else [ine.getShape()[-1],out.getShape()[0]]
                    signals.append({'tls':tls.getID(),'index':idx,'shape':shape(pts)})
                    break
    entries={k:shape(net.getEdge(v).getShape())[0] for k,v in meta['entries'].items()}
    geo={'roads':roads,'lanes':lanes,'junctions':junctions,'buildings':buildings,'parks':parks,'signals':signals,'entries':entries,'bounds':[-850,850,-850,850]}
    dump(ROOT/'web/geometry.json',geo)
    results={}; validations=[]
    for name in ['before','after','adjusted']:
        folder=ROOT/'runs'/name; stats=ET.parse(folder/'statistics.xml').getroot()
        vs={k:int(v) for k,v in stats.find('vehicles').attrib.items()}; vs['completed']=vs['inserted']-vs['running']; vs['requested']=meta['scenarios'][name]['requested']
        assert vs['requested']==vs['completed']+vs['running']+vs['waiting']
        edges={}; timebins=[]
        for interval in elements(folder/'edges.xml','interval'):
            for e in interval.findall('edge'):
                a=e.attrib; seconds=float(a['sampledSeconds']); rec=edges.setdefault(a['id'],{'seconds':0.,'speed_sum':0.,'waiting':0.,'entered':0})
                rec['seconds']+=seconds; rec['speed_sum']+=seconds*float(a.get('speed',0)); rec['waiting']+=float(a.get('waitingTime',0)); rec['entered']+=int(a.get('entered',0))
        for e in edges.values(): e['speed_kmh']=round(e['speed_sum']/e['seconds']*3.6,3) if e['seconds'] else None
        trips=[dict(e.attrib) for e in elements(folder/'tripinfo.xml','tripinfo')]
        completed=[t for t in trips if float(t['arrival'])>=0]; incomplete=[t for t in trips if float(t['arrival'])<0]
        assert len(completed)==vs['completed'] and len(incomplete)==vs['running']
        identifiers={}; vehiclemeta=[]; frames=[]
        for step in elements(folder/'fcd.xml.gz','timestep'):
            t=float(step.get('time'))
            if not 300<=t<1500: continue
            cars=[]
            for v in step.findall('vehicle'):
                a=v.attrib; vid=a['id']
                if vid not in identifiers:
                    identifiers[vid]=len(vehiclemeta); vehiclemeta.append({'id':vid,'type':a['type'],'extra':vid.startswith('extra')})
                cars.append([identifiers[vid],round(float(a['x'])-cx,2),round(float(a['y'])-cy,2),float(a['speed']),float(a['angle'])])
            stopped=sum(v[3]<.1 for v in cars)
            timebins.append([t,len(cars),stopped,round(statistics.mean(v[3] for v in cars)*3.6,3) if cars else 0])
            if t%4==0: frames.append({'t':t,'v':cars})
        signalstates={}
        for e in elements(folder/'tls.xml.gz','tlsState'):
            t=float(e.get('time'))
            if 300<=t<1500 and t%4==0: signalstates.setdefault(t,{})[e.get('id')]=[int(e.get('phase')),e.get('state'),e.get('programID')]
        for f in frames: f['tls']=signalstates[f['t']]
        expected='candidate' if name=='adjusted' else '0'
        assert all(f['tls'][meta['tls_id']][2]==expected for f in frames)
        loss=[float(t['timeLoss']) for t in completed]
        res={'label':meta['scenarios'][name]['label'],'counts':vs,'collisions':int(stats.find('safety').get('collisions')),
          'teleports':int(stats.find('teleports').get('total')),'completed_time_loss_mean_s':round(statistics.mean(loss),2),
          'completed_time_loss_s':loss,'mean_stopped_vehicles':round(statistics.mean(x[2] for x in timebins),2),
          'mean_running_vehicles':round(statistics.mean(x[1] for x in timebins),2),'series':timebins,'edges':edges,
          'green_seconds':meta['scenarios'][name]['green_seconds']}
        results[name]=res
        dump(ROOT/f'web/{name}.json',{'vehicles':vehiclemeta,'frames':frames})
        validations.append({'scenario':name,'vehicle_conservation':True,'tripinfo_matches_statistics':True,'signal_program_verified':expected,'replay_frames':len(frames),'collisions':res['collisions'],'teleports':res['teleports']})
    assert (ROOT/'runs/after/scenario.sumocfg').exists()
    # Identical after/adjusted route file is referenced by both configurations.
    routes=[ET.parse(ROOT/f'runs/{s}/scenario.sumocfg').find('input/route-files').get('value') for s in ['after','adjusted']]
    assert routes[0]==routes[1]
    dump(ROOT/'web/results.json',{'experiment':meta,'source':source,'results':results,'building_height_assumed':sum(b['height_source']=='assumed' for b in buildings),'building_count':len(buildings)})
    dump(ROOT/'output/validation.json',{'checks':validations,'after_adjusted_identical_route_file':True,'route_sha256':hashlib.sha256((ROOT/'data/after.rou.xml').read_bytes()).hexdigest()})
    with open(ROOT/'output/scenario_metrics.csv','w',newline='',encoding='utf-8-sig') as f:
        writer=csv.DictWriter(f,fieldnames=['scenario','requested','inserted','completed','running','waiting','mean_stopped','completed_time_loss_s','collisions','teleports']); writer.writeheader()
        for k,r in results.items(): writer.writerow({'scenario':k,**{a:r['counts'][a] for a in ['requested','inserted','completed','running','waiting']},'mean_stopped':r['mean_stopped_vehicles'],'completed_time_loss_s':r['completed_time_loss_mean_s'],'collisions':r['collisions'],'teleports':r['teleports']})
    print(json.dumps({k:{'counts':r['counts'],'mean_stopped':r['mean_stopped_vehicles'],'completed_loss':r['completed_time_loss_mean_s']} for k,r in results.items()},indent=2))

if __name__=='__main__': main()
