from pathlib import Path
import urllib.request, json, subprocess, hashlib, datetime, os
import xml.etree.ElementTree as ET
import sumolib

ROOT=Path(__file__).resolve().parent
DATA=ROOT/'data'; NET=ROOT/'network'; OUT=ROOT/'output'
for p in [DATA,NET,OUT,ROOT/'runs',ROOT/'web',ROOT/'figures']:
    p.mkdir(parents=True,exist_ok=True)
SUMO_HOME=Path(os.environ.get('SUMO_HOME',Path.home()/'AppData/Local/TrafficImpactLab/venv/Lib/site-packages/sumo'))
def binary(name):
    p=SUMO_HOME/'bin'/f'{name}.exe'
    return str(p if p.exists() else sumolib.checkBinary(name))
def run(args,log):
    p=subprocess.run(args,capture_output=True,timeout=180)
    (NET/log).write_bytes(p.stdout+p.stderr)
    if p.returncode: raise RuntimeError(p.stderr.decode('utf-8','replace')[-4000:])

center=[128.6262151,35.8591365]
bbox=[center[0]-.0095,center[1]-.0075,center[0]+.0095,center[1]+.0075]
url='https://api.openstreetmap.org/api/0.6/map?bbox='+','.join(f'{v:.7f}' for v in bbox)
osm=DATA/'beomeo.osm.xml'
if not osm.exists():
    req=urllib.request.Request(url,headers={'User-Agent':'TrafficChangeLab-Research/1.0'})
    osm.write_bytes(urllib.request.urlopen(req,timeout=60).read())
source=ET.parse(osm).getroot()
tags=lambda e:{t.get('k'):t.get('v') for t in e.findall('tag')}
roads=[tags(w) for w in source.findall('way') if 'highway' in tags(w)]
buildings=[w for w in source.findall('way') if 'building' in tags(w)]
meta={'name':'대구 범어네거리 주변','center_lon_lat':center,'bbox_lon_lat':bbox,'source_url':url,
 'geocoder_source':'https://nominatim.openstreetmap.org/search?q=범어네거리&format=json&limit=3&countrycodes=kr',
 'center_osm_node':7119325165,'downloaded_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'osm_sha256':hashlib.sha256(osm.read_bytes()).hexdigest(),
 'osm_ways':len(source.findall('way')),'osm_road_ways':len(roads),'osm_building_ways':len(buildings),
 'license':'© OpenStreetMap contributors, ODbL 1.0; https://www.openstreetmap.org/copyright',
 'scope':'Road/building geometry from OSM. Demand, signal plans, missing road attributes and default building heights are assumptions. No field calibration.'}
(DATA/'source.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
net=NET/'beomeo.net.xml'
cmd=[binary('netconvert'),'--osm-files',str(osm),'--output-file',str(net),
 '--geometry.remove','true','--junctions.join','true','--tls.guess-signals','true',
 '--tls.guess','true','--tls.join','true','--tls.default-type','static','--tls.cycle.time','90',
 '--osm.turn-lanes','true','--no-turnarounds','true','--keep-edges.by-vclass','passenger',
 '--keep-edges.components','1','--keep-edges.in-geo-boundary',','.join(map(str,bbox)),
 '--output.street-names','true','--output.original-names','true',
 '--default.speed','13.89','--default.lanenumber','1']
run(cmd,'netconvert.log')
run([binary('polyconvert'),'--net-file',str(net),'--osm-files',str(osm),
 '--type-file',str(SUMO_HOME/'data/typemap/osmPolyconvert.typ.xml'),'--output-file',str(NET/'beomeo.poly.xml')],'polyconvert.log')
n=sumolib.net.readNet(str(net),withInternal=True,withPrograms=True)
cx,cy=n.convertLonLat2XY(*center)
tls=sorted(n.getTrafficLights(),key=lambda t:min(sum((a-b)**2 for a,b in zip(c[0].getShape()[-1],(cx,cy))) for c in t.getConnections()))
summary={'edges_with_internal':len(n.getEdges()),'external_edges':len(n.getEdges(withInternal=False)),'lanes_with_internal':sum(e.getLaneNumber() for e in n.getEdges()),
 'nodes':len(n.getNodes()),'tls':len(tls),'center_xy':[cx,cy],
 'nearby_tls':[{'id':t.getID(),'node':n.getNode(t.getID()).getCoord() if n.hasNode(t.getID()) else None,
 'programs':{k:[{'duration':p.duration,'state':p.state} for p in v.getPhases()] for k,v in t.getPrograms().items()}} for t in tls[:6]],
 'buildings':len(buildings)}
(NET/'network_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'source':meta,'network':summary},ensure_ascii=False,indent=2))
