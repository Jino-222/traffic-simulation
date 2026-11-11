"""Native SUMO GUI render via the supported TraCI GUI API (isolated outputs)."""
from pathlib import Path
import subprocess,os,socket,json,sys
import traci
ROOT=Path(__file__).resolve().parent
HOME=Path(os.environ.get('SUMO_HOME',Path.home()/'AppData/Local/TrafficImpactLab/venv/Lib/site-packages/sumo'))
os.environ['SUMO_HOME']=str(HOME)
center=json.loads((ROOT/'data/experiment.json').read_text(encoding='utf-8'))['center_xy']
captures=[]
views={'overview':('09_native_sumo_overview',850),'closeup':('10_native_sumo_closeup',150)}
# Capture one view per process: GUI shutdown/reconnection in the same Python process
# can leave TraCI waiting on a stale view in some Windows sessions.
for title,radius in [views[sys.argv[1] if len(sys.argv)>1 else 'closeup']]:
    sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1];sock.close()
    startup=subprocess.STARTUPINFO();startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=0
    log=open(ROOT/f'output/{title}.log','w',encoding='utf-8')
    p=subprocess.Popen([str(HOME/'bin/sumo-gui.exe'),'--start','--net-file',str(ROOT/'network/beomeo.net.xml'),'--route-files',str(ROOT/'data/after.rou.xml'),'--additional-files',str(ROOT/'network/beomeo.poly.xml'),'--remote-port',str(port),'--step-length','0.5','--seed','2026','--time-to-teleport','-1','--no-step-log','true','--quit-on-end','true','--window-size','1500,1000'],stdout=log,stderr=log,startupinfo=startup)
    try:
        conn=traci.connect(port=port,numRetries=15,proc=p)
        conn.simulationStep(900)
        view=conn.gui.getIDList()[0]
        conn.gui.setSchema(view,'real world')
        cx,cy=center;conn.gui.setBoundary(view,cx-radius,cy-radius,cx+radius,cy+radius)
        conn.gui.screenshot(view,str(ROOT/f'figures/{title}.png'),width=1500,height=1000)
        conn.simulationStep()
        captures.append({'file':f'figures/{title}.png','simulation_time_s':conn.simulation.getTime(),'boundary_radius_m':radius,'schema':'real world','note':'Native SUMO GUI screenshot; vehicle colors are scheme defaults, not speed colors.'})
        conn.close()
    finally:
        try:p.wait(timeout=10)
        except subprocess.TimeoutExpired:p.terminate()
        log.close()
(ROOT/f'output/{title}_manifest.json').write_text(json.dumps(captures,indent=2),encoding='utf-8')
print('Native SUMO screenshot capture finished.')
