"""Regular arrivals matched to the seed-407 stochastic scenario study."""
from pathlib import Path
from dataclasses import replace
import json
from traffic.models import Config
from traffic.experiment import execute
from traffic.search import core_hash
from traffic.io import write_json

def main():
    root=Path(__file__).resolve().parents[1]
    folder=root/'experiments/arrival_control_regular'
    config=replace(Config(),seed=407,stochastic=False)
    path=folder/'comparison.json';source=folder/'control_source.json'
    if path.exists():
        if json.loads(path.read_text(encoding='utf-8'))['config']!=config.to_dict():raise ValueError('Control settings changed; use a new experiment folder')
        if source.exists() and json.loads(source.read_text(encoding='utf-8'))['core_hash']!=core_hash():raise ValueError('Simulation core changed; use a new experiment folder')
    else:execute(config,folder)
    write_json(source,dict(core_hash=core_hash(),comparison='study_v2/scenarios/baseline',changed_fields=['stochastic']))
    print('Regular-arrival control available; only arrival-time randomization differs from stochastic reference')

if __name__=='__main__':main()
