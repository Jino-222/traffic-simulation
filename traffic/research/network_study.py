"""Reproducible turning and corridor experiments; explicit finite offset search."""
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor,as_completed
import argparse,json
from importlib.metadata import version
from ..io import write_json,sha256
from .networks import turning_network,corridor_network,turning_plan,corridor_plan,load_info
from .network_runner import create_demand,run,source_hash

ROOT=Path(__file__).resolve().parents[2]
SEEDS=[17,29,43];OFFSETS=[0,11,22,45,67];VALIDATION_SEEDS=[71,83,97]

def read(path):return json.loads(path.read_text(encoding='utf-8'))

def prepare(folder,kind,seed,separation=150,warmup=300,duration=1800):
    netfolder=folder/'networks'/f'{kind}_{separation}'
    info=load_info(netfolder) if (netfolder/'network_info.json').exists() else (turning_network(netfolder) if kind=='turning' else corridor_network(netfolder,separation))
    if kind=='turning':
        shares={'R':.2,'S':.6,'L':.2};extra={'N':150,'S':100,'E':50,'W':50}
        base={f:250*shares[r['turn']] for f,r in info['flows'].items()}
        additional={f:extra[r['direction']]*shares[r['turn']] for f,r in info['flows'].items()}
    else:
        base={'WE':500,'EW':250,'N0':120,'S0':120,'N1':120,'S1':120}
        additional={'WE':200,'EW':100}
    demand=folder/'demand'/f'{kind}_{separation}'/f'seed_{seed}'
    meta=create_demand(info,demand,base,additional,seed=seed,warmup=warmup,duration=duration)
    return dict(info=info,netfile=netfolder/'net.xml',metadata=meta,demand=demand,base=base,additional=additional)

def task(setup,plan,output,case,seed,before=False,record=False,warmup=300,duration=1800):
    return dict(info=setup['info'],netfile=setup['netfile'],routefile=setup['demand']/('before.rou.xml' if before else 'after.rou.xml'),
        metadata=setup['metadata'],plan=plan,folder=output,scenario='before' if before else 'after',seed=seed,
        warmup=warmup,duration=duration,drain=600,record=record)

def execute_jobs(jobs,folder,stage,workers=2):
    completed=0;results=[]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        pending={pool.submit(run,**kwargs):(family,case,seed,kwargs['folder']) for family,case,seed,kwargs in jobs}
        for future in as_completed(pending):
            family,case,seed,path=pending[future]
            r=future.result();completed+=1
            results.append(dict(family=family,case=case,seed=seed,path=str(path.relative_to(folder)),**r))
            write_json(folder/'status.json',dict(stage=stage,state='running',completed=completed,total=len(jobs),case=case,seed=seed))
            print(f'{stage}: {completed}/{len(jobs)} {family} {case} seed={seed} loss={r["mean_time_loss"]} remaining={r["pending"]+r["unfinished"]} integrity={r["integrity_passed"]}',flush=True)
    return sorted(results,key=lambda r:(r['family'],r['case'],r['seed']))

def aggregates(results):
    out=[]
    for family,case in sorted({(r['family'],r['case']) for r in results}):
        rows=[r for r in results if (r['family'],r['case'])==(family,case)]
        eligible=all(r['integrity_passed'] and r['pending']==r['unfinished']==0 for r in rows)
        values=[r['mean_time_loss'] for r in rows if r['mean_time_loss'] is not None]
        out.append(dict(family=family,case=case,seeds=[r['seed'] for r in rows],eligible=eligible,
            mean_time_loss=sum(values)/len(values) if values else None,
            pending=sum(r['pending'] for r in rows),unfinished=sum(r['unfinished'] for r in rows),
            link_E_mean_halting=sum(r['edge_stats'].get('link_E',{}).get('mean_halting',0) for r in rows)/len(rows),
            link_E_max_queue_m=max(r['edge_stats'].get('link_E',{}).get('max_geometric_queue_m',0) for r in rows),
            link_E_boundary_samples=sum(r['edge_stats'].get('link_E',{}).get('boundary_occupied_samples',0) for r in rows),
            W_in_mean_halting=sum(r['edge_stats'].get('W_in',{}).get('mean_halting',0) for r in rows)/len(rows)))
    return out

def study(folder=None,workers=2):
    folder=Path(folder or ROOT/'experiments/network_study_v1');folder.mkdir(parents=True,exist_ok=True)
    protocol=dict(version=1,engine_sha256=source_hash(),study_code_sha256=sha256(__file__),sumo_version=version('eclipse-sumo'),
        discovery_seeds=SEEDS,validation_seeds=VALIDATION_SEEDS,offsets=OFFSETS,warmup=300,duration=1800,drain=600,
        turning=dict(base_per_origin=250,extra=dict(N=150,S=100,E=50,W=50),shares=dict(R=.2,S=.6,L=.2),
            phase_order=['N','E','S','W'],equal_greens=[18,18,18,18],candidate_greens=[24,14,20,14],yellow=3,allred=5,exclusive_pedestrian_phase=True),
        corridor=dict(base=dict(WE=500,EW=250,N0=120,S0=120,N1=120,S1=120),extra=dict(WE=200,EW=100),
            separation_m=[150,75],cycle=90,normal_ew_green=40,bottleneck_ew_green=15,
            offset_definition='Delay J1 cycle start relative to J0; phase position=(simulation time-offset) mod cycle'),
        selection='Among fully processed and integrity-passing offset cases minimize equal-seed mean timeLoss; freeze then validate unseen seeds',
        synthetic=True,limitations=['Protected origin turns plus exclusive pedestrians are a simplified research layout, not an optimized field signal plan.',
            'Two straight-only intersections and fixed-speed pedestrians; no external network calibration.',
            'Boundary occupancy indicates a stopped group near the observation boundary. It alone does not establish spillback.',
            'Shorter connecting road also changes travel time and progression; the storage comparison is not a pure isolated storage experiment.'])
    if (folder/'protocol.json').exists() and read(folder/'protocol.json')!=protocol:raise ValueError('Study protocol changed; use a new output folder')
    write_json(folder/'protocol.json',protocol)
    jobs=[]
    for seed in SEEDS:
        turning=prepare(folder,'turning',seed)
        for case,before,greens in [('before',True,(18,18,18,18)),('after',False,(18,18,18,18)),('adjusted',False,(24,14,20,14))]:
            jobs.append(('turning',case,seed,task(turning,turning_plan(turning['info'],greens),folder/'turning'/f'seed_{seed}'/case,case,seed,before,record=seed==17)))
        normal=prepare(folder,'corridor',seed)
        jobs.append(('corridor','before',seed,task(normal,corridor_plan(normal['info']),folder/'corridor'/f'seed_{seed}'/'before','before',seed,True)))
        for offset in OFFSETS:
            case=f'offset_{offset:02d}'
            jobs.append(('corridor',case,seed,task(normal,corridor_plan(normal['info'],offset),folder/'corridor'/f'seed_{seed}'/case,case,seed)))
        for length in (150,75):
            setup=normal if length==150 else prepare(folder,'corridor',seed,separation=length)
            case=f'downstream_bottleneck_{length}'
            jobs.append(('corridor',case,seed,task(setup,corridor_plan(setup['info'],11,15),folder/'corridor'/f'seed_{seed}'/case,case,seed)))
    records=execute_jobs(jobs,folder,'discovery',workers);table=aggregates(records)
    write_json(folder/'discovery.json',dict(records=records,aggregates=table))
    eligible=[r for r in table if r['family']=='corridor' and r['case'].startswith('offset_') and r['eligible']]
    if not eligible:raise RuntimeError('No corridor offset is eligible; inspect incomplete or anomalous runs')
    selected=min(eligible,key=lambda r:(r['mean_time_loss'],r['case']))
    offset=int(selected['case'].split('_')[1]);frozen=dict(offset_seconds=offset,selected_case=selected['case'],
        criterion=protocol['selection'],discovery_sha256=sha256(folder/'discovery.json'),selected_before_validation=True)
    if (folder/'frozen_offset.json').exists() and read(folder/'frozen_offset.json')!=frozen:raise ValueError('Frozen selection changed')
    write_json(folder/'frozen_offset.json',frozen)
    validation_jobs=[]
    for seed in VALIDATION_SEEDS:
        setup=prepare(folder,'corridor',seed)
        for off in sorted({0,offset}):
            case=f'offset_{off:02d}'
            validation_jobs.append(('corridor',case,seed,task(setup,corridor_plan(setup['info'],off),folder/'validation'/f'seed_{seed}'/case,case,seed,record=seed==71)))
    validation=execute_jobs(validation_jobs,folder,'validation',workers)
    summary=dict(protocol=protocol,frozen=frozen,discovery=table,validation=aggregates(validation),
        discovery_runs=len(records),validation_runs=len(validation),all_integrity_passed=all(r['integrity_passed'] for r in records+validation),
        validation_records=validation,validation_used_for_selection=False)
    write_json(folder/'summary.json',summary)
    write_json(folder/'status.json',dict(stage='finished',state='completed' if summary['all_integrity_passed'] else 'needs_review'))
    print(json.dumps(dict(selected_offset=offset,discovery_runs=len(records),validation_runs=len(validation),all_integrity_passed=summary['all_integrity_passed'])),flush=True)
    return summary

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path);parser.add_argument('--workers',type=int,default=2)
    args=parser.parse_args();study(args.output,args.workers)
