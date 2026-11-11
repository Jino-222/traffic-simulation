from dataclasses import replace
from pathlib import Path
from traffic.models import Config
from traffic.experiment import execute
if __name__=="__main__":
    c=replace(Config(),warmup=0,duration=180,drain=120)
    result=execute(c,Path("experiments/smoke_run"),lambda x:print(x,flush=True))
    for run in result["sumo"]:
        print({k:run[k] for k in ("scenario","anomaly_count","pedestrian_departed","pedestrian_completed","crossings_used","elapsed_seconds")},flush=True)
