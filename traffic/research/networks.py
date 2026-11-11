"""Explicit protected-turn and two-intersection synthetic research networks."""
from pathlib import Path
import math,os,subprocess,xml.etree.ElementTree as ET
from ..sumo.network import binary,write_xml
from ..io import write_json

DIRECTIONS=('N','E','S','W')
DEST={'N':{'R':'W','S':'S','L':'E'},'E':{'R':'N','S':'W','L':'S'},
      'S':{'R':'E','S':'N','L':'W'},'W':{'R':'S','S':'E','L':'N'}}

def load_info(folder):
    import json
    info=json.loads((Path(folder)/'network_info.json').read_text(encoding='utf-8'))
    for t in info['tls'].values():
        for key in ('links','requests','foes'):t[key]={int(k):v for k,v in t[key].items()}
    return info

def compile_network(folder,nodes,edges,connections,flow_routes,ped_routes):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    for name,root in [('nodes.xml',nodes),('edges.xml',edges),('connections.xml',connections)]:write_xml(folder/name,root)
    cmd=[binary('netconvert'),'--node-files',str(folder/'nodes.xml'),'--edge-files',str(folder/'edges.xml'),
         '--connection-files',str(folder/'connections.xml'),'--output-file',str(folder/'net.xml'),
         '--no-turnarounds','true','--walkingareas','true']
    p=subprocess.run(cmd,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=60,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    (folder/'netconvert.log').write_text(p.stdout+p.stderr,encoding='utf-8')
    if p.returncode:raise RuntimeError(p.stderr)
    root=ET.parse(folder/'net.xml').getroot()
    info=dict(tls={},crossings={},lanes={},flows=flow_routes,ped_routes=ped_routes,geometry=dict(lanes=[],junctions=[]))
    for e in root.findall('edge'):
        kind=e.get('function','road')
        for lane in e.findall('lane'):
            item=dict(id=lane.get('id'),edge=e.get('id'),kind=kind,pedestrian=lane.get('allow')=='pedestrian',
                length=float(lane.get('length')),width=float(lane.get('width','3.2')),
                shape=[[float(v) for v in pair.split(',')] for pair in lane.get('shape').split()])
            info['lanes'][item['id']]=item;info['geometry']['lanes'].append(item)
        if kind=='crossing':
            junction=e.get('id').split('_c')[0][1:]
            info['crossings'][e.get('id')]=dict(tls=junction,edges=e.get('crossingEdges').split(),
                length=float(e.find('lane').get('length')),lane=e.find('lane').get('id'))
    for j in root.findall('junction'):
        if j.get('type')=='internal':continue
        info['geometry']['junctions'].append(dict(id=j.get('id'),x=float(j.get('x')),y=float(j.get('y')),
            shape=[[float(v) for v in pair.split(',')] for pair in j.get('shape','').split()]))
        if j.get('type')!='traffic_light':continue
        lanes=j.get('intLanes').split();requests={int(r.get('index')):r.get('foes')[::-1] for r in j.findall('request')}
        info['tls'][j.get('id')]=dict(links={},requests=requests,internal_lanes=lanes)
    for c in root.findall('connection'):
        tls=c.get('tl')
        if tls not in info['tls']:continue
        t=info['tls'][tls];idx=int(c.get('linkIndex'));frm,to=c.get('from'),c.get('to')
        isped=to in info['crossings'];via=info['crossings'][to]['lane'] if isped else c.get('via')
        # Associate signal links with netconvert's independent junction conflict matrix.
        internal_chain=[via];terminal=via
        while terminal not in t['internal_lanes']:
            edge,index=terminal.rsplit('_',1)
            continuations=[x for x in root.findall('connection') if x.get('from')==edge and x.get('fromLane')==index and x.get('to')==to and x.get('via')]
            if len(continuations)!=1:raise ValueError(f'Cannot map split internal movement: {tls} {terminal}')
            terminal=continuations[0].get('via')
            if terminal in internal_chain:raise ValueError('Cycle in internal lane chain')
            internal_chain.append(terminal)
        request=t['internal_lanes'].index(terminal)
        if idx in t['links']:raise ValueError('Duplicate signal index requires explicit handling')
        t['links'][idx]=dict(index=idx,kind='pedestrian' if isped else 'vehicle',from_edge=frm,to_edge=to,
            via=via,internal_chain=internal_chain,request=request,turn=c.get('dir'),from_lane=c.get('fromLane'),to_lane=c.get('toLane'))
    for tls,t in info['tls'].items():
        if set(t['links'])!=set(range(len(t['links']))):raise ValueError('Non-contiguous signal links')
        t['signal_count']=len(t['links'])
        t['foes']={i:[j for j,other in t['links'].items() if t['requests'][link['request']][other['request']]=='1']
                   for i,link in t['links'].items()}
    for name,route in flow_routes.items():
        for frm,to in zip(route['edges'],route['edges'][1:]):
            matches=[(tls,i,link) for tls,t in info['tls'].items() for i,link in t['links'].items()
                     if link['kind']=='vehicle' and link['from_edge']==frm and link['to_edge']==to]
            if len(matches)!=1:raise ValueError(f'Flow connection missing or ambiguous: {name}, {frm}->{to}')
    for p in ped_routes:
        lane=root.find(f"edge[@id='{p['from']}']/lane[@allow='pedestrian']")
        if lane is None:raise ValueError('Missing sidewalk')
        p['depart_pos']=float(lane.get('length'))-1
    write_json(folder/'network_info.json',info);write_json(folder/'geometry.json',info['geometry'])
    return info

def turning_network(folder):
    nodes=ET.Element('nodes');edges=ET.Element('edges');cons=ET.Element('connections')
    ET.SubElement(nodes,'node',id='C',x='0',y='0',type='traffic_light')
    routes={};peds=[];coords={'N':(0,300),'E':(300,0),'S':(0,-300),'W':(-300,0)}
    for side,(x,y) in coords.items():
        ET.SubElement(nodes,'node',id=side,x=str(x),y=str(y),type='dead_end')
        for suffix,a,b in [('in',side,'C'),('out','C',side)]:
            ET.SubElement(edges,'edge',{'id':side+'_'+suffix,'from':a,'to':b,'numLanes':'3','speed':str(50/3.6),'width':'3.2','sidewalkWidth':'2'})
        for lane,turn in enumerate(('R','S','L'),1):
            dest=DEST[side][turn]
            ET.SubElement(cons,'connection',{'from':side+'_in','to':dest+'_out','fromLane':str(lane),'toLane':str(lane)})
            routes[side+'_'+turn]=dict(edges=[side+'_in',dest+'_out'],direction=side,turn=turn,depart_lane=lane)
        ET.SubElement(cons,'crossing',node='C',edges=f'{side}_in {side}_out',width='3',priority='true')
        peds.append(dict(id=side,tls='C',side=side,**{'from':side+'_in','to':side+'_out'}))
    info=compile_network(folder,nodes,edges,cons,routes,peds)
    for i,link in info['tls']['C']['links'].items():
        if link['kind']=='vehicle':
            expected=next(r['turn'].lower() for r in routes.values() if r['edges']==[link['from_edge'],link['to_edge']])
            if link['turn']!=expected:raise ValueError('Requested turn differs from generated turn geometry')
    return info

def corridor_network(folder,separation=150):
    nodes=ET.Element('nodes');edges=ET.Element('edges');cons=ET.Element('connections')
    for node,x,y,kind in [('J0',0,0,'traffic_light'),('J1',separation,0,'traffic_light'),('W',-300,0,'dead_end'),
        ('E',separation+300,0,'dead_end'),('N0',0,300,'dead_end'),('S0',0,-300,'dead_end'),
        ('N1',separation,300,'dead_end'),('S1',separation,-300,'dead_end')]:
        ET.SubElement(nodes,'node',id=node,x=str(x),y=str(y),type=kind)
    edge_specs=[('W_in','W','J0'),('W_out','J0','W'),('E_in','E','J1'),('E_out','J1','E'),
                ('link_E','J0','J1'),('link_W','J1','J0')]
    for n in ('0','1'):
        for side in ('N','S'):
            arm=side+n
            edge_specs.extend([(arm+'_in',arm,'J'+n),(arm+'_out','J'+n,arm)])
    for eid,a,b in edge_specs:
        ET.SubElement(edges,'edge',{'id':eid,'from':a,'to':b,'numLanes':'1','speed':str(50/3.6),'width':'3.2','sidewalkWidth':'2'})
    routes={'WE':dict(edges=['W_in','link_E','E_out'],direction='W',turn='S',depart_lane=1),
            'EW':dict(edges=['E_in','link_W','W_out'],direction='E',turn='S',depart_lane=1)}
    for n in ('0','1'):
        for side,other in [('N','S'),('S','N')]:
            routes[side+n]=dict(edges=[side+n+'_in',other+n+'_out'],direction=side,turn='S',depart_lane=1)
    for route in routes.values():
        for a,b in zip(route['edges'],route['edges'][1:]):
            ET.SubElement(cons,'connection',{'from':a,'to':b,'fromLane':'1','toLane':'1'})
    sides={'J0':{'N':('N0_in','N0_out'),'S':('S0_in','S0_out'),'W':('W_in','W_out'),'E':('link_W','link_E')},
           'J1':{'N':('N1_in','N1_out'),'S':('S1_in','S1_out'),'W':('link_E','link_W'),'E':('E_in','E_out')}}
    peds=[]
    for tls,arms in sides.items():
        for side,(a,b) in arms.items():
            ET.SubElement(cons,'crossing',node=tls,edges=f'{a} {b}',width='3',priority='true')
            peds.append(dict(id=tls+'_'+side,tls=tls,side=side,**{'from':a,'to':b}))
    return compile_network(folder,nodes,edges,cons,routes,peds)

def conflicts(info,tls,state):
    t=info['tls'][tls];active=[i for i in t['links'] if state[int(i)] in 'Gg']
    return [(i,j) for i in active for j in active if int(i)<int(j) and (j in t['foes'][i] or i in t['foes'][j])]

def turning_plan(info,greens=(18,18,18,18),walk=3,speed=1,yellow=3,allred=5):
    t=info['tls']['C'];phases=[]
    def phase(name,duration,indices,char):
        state=['r']*t['signal_count']
        for i in indices:state[int(i)]=char
        phases.append(dict(name=name,duration=duration,state=''.join(state)))
    # Four protected origin phases followed by exclusive pedestrian walk and clearance.
    for side,green in zip(DIRECTIONS,greens):
        indices=[i for i,l in t['links'].items() if l['kind']=='vehicle' and l['from_edge']==side+'_in']
        phase(side+'_protected',green,indices,'G');phase(side+'_yellow',yellow,indices,'y');phase(side+'_allred',allred,[],'r')
    length=max(c['length'] for c in info['crossings'].values())
    clearance=math.ceil((length/speed+2)*2)/2
    phase('ped_walk',walk,[i for i,l in t['links'].items() if l['kind']=='pedestrian'],'G')
    phase('ped_clearance',clearance,[],'r')
    plan={'C':dict(phases=phases,offset=0,cycle=sum(p['duration'] for p in phases))}
    validate_plan(info,plan)
    return plan

def corridor_plan(info,offset=0,downstream_ew=40,walk=3):
    plan={}
    side={p['tls']+':'+p['from']:p['side'] for p in info['ped_routes']}
    for tls,t in info['tls'].items():
        ew=downstream_ew if tls=='J1' else 40;phases=[]
        for axis,g in [('NS',80-ew),('EW',ew)]:
            carside=('N','S') if axis=='NS' else ('E','W')
            # Explicit crossed-arm test from junction metadata rather than string edge names.
            vehicles=[i for i,l in t['links'].items() if l['kind']=='vehicle' and side[tls+':'+l['from_edge']] in carside]
            pedestrians=[]
            for i,l in t['links'].items():
                if l['kind']!='pedestrian':continue
                crossing=info['crossings'][l['to_edge']]
                arm=next(p['side'] for p in info['ped_routes'] if p['tls']==tls and p['from'] in crossing['edges'])
                if arm not in carside:pedestrians.append(i)
            need=walk+max(c['length'] for c in info['crossings'].values() if c['tls']==tls)+2
            if g<need:raise ValueError('Insufficient pedestrian clearance in corridor green')
            for name,duration,char,walk_on in [('walk',walk,'G',True),('clear',g-walk,'G',False),('yellow',3,'y',False),('allred',2,'r',False)]:
                state=['r']*t['signal_count']
                for i in vehicles:state[int(i)]=char
                if walk_on:
                    for i in pedestrians:state[int(i)]='G'
                phases.append(dict(name=axis+'_'+name,duration=duration,state=''.join(state)))
        plan[tls]=dict(phases=phases,offset=offset if tls=='J1' else 0,cycle=90)
    validate_plan(info,plan);return plan

def validate_plan(info,plan):
    for tls,p in plan.items():
        if not p['phases'] or any(x['duration']<=0 for x in p['phases']):raise ValueError('Positive phase durations required')
        if abs(sum(x['duration'] for x in p['phases'])-p['cycle'])>1e-6:raise ValueError('Signal cycle mismatch')
        used=set()
        for phase in p['phases']:
            if len(phase['state'])!=info['tls'][tls]['signal_count']:raise ValueError('Signal length mismatch')
            if conflicts(info,tls,phase['state']):raise ValueError('Conflicting green movements according to generated junction matrix')
            used.update(i for i in info['tls'][tls]['links'] if phase['state'][int(i)]=='G')
        if used!=set(info['tls'][tls]['links']):raise ValueError('A movement is never served')

def write_plan(plan,path):
    root=ET.Element('additional')
    for tls,p in plan.items():
        # Offsets are initialized explicitly in TraCI using phase_position(t-offset).
        logic=ET.SubElement(root,'tlLogic',id=tls,type='static',programID='research',offset='0')
        for phase in p['phases']:ET.SubElement(logic,'phase',duration=str(phase['duration']),state=phase['state'],name=phase['name'])
    write_xml(path,root)

def phase_at(plan,t):
    at=(t-plan['offset'])%plan['cycle']
    for i,p in enumerate(plan['phases']):
        if at<p['duration']-1e-8:return i,p['state'],p['duration']-at
        at-=p['duration']
    return 0,plan['phases'][0]['state'],plan['phases'][0]['duration']
