"""Cross-check model invariants and artifacts rather than mirroring implementation."""
from pathlib import Path
import json,math,hashlib,csv,xml.etree.ElementTree as ET,subprocess
from PIL import Image
import sumolib
ROOT=Path(__file__).resolve().parent
def read(p):return json.loads(p.read_text(encoding='utf-8'))
meta=read(ROOT/'data/experiment.json'); results=read(ROOT/'web/results.json');G=read(ROOT/'web/geometry.json')
checks=[]
def ok(name,value):
    assert value,name
    checks.append({'check':name,'passed':True})
before=ET.parse(ROOT/'data/before.rou.xml').getroot();after=ET.parse(ROOT/'data/after.rou.xml').getroot()
bv={e.get('id'):e.attrib for e in before.findall('vehicle')};av={e.get('id'):e.attrib for e in after.findall('vehicle')}
ok('Existing demand vehicles exactly preserved after occupancy',all(av[k]==v for k,v in bv.items()))
ok('Exactly 250 added departure requests over 25 minutes',len(av)-len(bv)==250)
cfgs={s:ET.parse(ROOT/f'runs/{s}/scenario.sumocfg').getroot() for s in ['before','after','adjusted']}
ok('After and adjusted reference identical demand file',cfgs['after'].find('input/route-files').get('value')==cfgs['adjusted'].find('input/route-files').get('value'))
net=ET.parse(ROOT/'network/beomeo.net.xml').getroot()
base=next(e for e in net.findall('tlLogic') if e.get('id')==meta['tls_id'])
adjust=ET.parse(ROOT/'runs/adjusted/measurements.add.xml').find('tlLogic')
bp=base.findall('phase');ap=adjust.findall('phase')
ok('Signal phase states and order preserved',[p.get('state') for p in bp]==[p.get('state') for p in ap])
ok('Both signal cycles equal 90 seconds',sum(float(p.get('duration')) for p in bp)==sum(float(p.get('duration')) for p in ap)==90)
ok('Yellow durations unchanged',all(a.get('duration')==b.get('duration') for a,b in zip(ap,bp) if 'y' in b.get('state').lower()))
ok('Candidate green durations at least 10 seconds',all(float(ap[i].get('duration'))>=10 for i in meta['phase_green_indices']))
replays={s:read(ROOT/f'web/{s}.json') for s in cfgs}
for s,rep in replays.items():
    r=results['results'][s];c=r['counts']
    ok(s+' requested = completed + running + waiting',c['requested']==c['completed']+c['running']+c['waiting'])
    ok(s+' replay timestamps are 300..1496 step4',[f['t'] for f in rep['frames']]==list(range(300,1500,4)))
    ok(s+' finite vehicle coordinates / nonnegative speeds',all(all(math.isfinite(v) for v in row[1:]) and row[3]>=0 and row[0]<len(rep['vehicles']) for f in rep['frames'] for row in f['v']))
    ok(s+' correct active signal program',all(f['tls'][meta['tls_id']][2]==('candidate' if s=='adjusted' else '0') for f in rep['frames']))
ok('All noncentral TLS states unchanged',all(a['tls'][k]==b['tls'][k] for a,b in zip(replays['after']['frames'],replays['adjusted']['frames']) for k in a['tls'] if k!=meta['tls_id']))
ok('Before and after have identical signals',all(a['tls']==b['tls'] for a,b in zip(replays['before']['frames'],replays['after']['frames'])))
for p in (ROOT/'figures').glob('*.png'):
    with Image.open(p) as im: im.verify()
ok('Ten visual outputs exist',len(list((ROOT/'figures').glob('[0-9][0-9]_*.png')))==10)
ok('Native overview and closeup are different renders',(ROOT/'figures/09_native_sumo_overview.png').read_bytes()!=(ROOT/'figures/10_native_sumo_closeup.png').read_bytes())
roadnames={r['id']:r['name'] for r in G['roads']}
with open(ROOT/'output/edge_metrics.csv','w',newline='',encoding='utf-8-sig') as f:
    w=csv.writer(f);w.writerow(['scenario','edge_id','road_name','sampled_vehicle_seconds','mean_speed_kmh','waiting_vehicle_seconds','entered'])
    for s,r in results['results'].items():
        for e,v in r['edges'].items():w.writerow([s,e,roadnames.get(e,''),v['seconds'],v['speed_kmh'],v['waiting'],v['entered']])
n=sumolib.net.readNet(str(ROOT/'network/beomeo.net.xml'),withInternal=True,withPrograms=True)
summary={'external_edges':len(n.getEdges(withInternal=False)),'edges_with_internal':len(n.getEdges()),'nodes':len(n.getNodes()),'tls':len(n.getTrafficLights()),'center_xy':meta['center_xy'],'selected_central_tls':meta['tls_id'],'osm_buildings':len(G['buildings']),'building_height_assumed':results['building_height_assumed']}
(ROOT/'network/network_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
report={'passed':len(checks),'checks':checks,'important_limit':'No field calibration, pedestrian clearance validation, multiple demand seeds, or safety certification.'}
(ROOT/'output/audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))
