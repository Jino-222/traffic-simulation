from pathlib import Path
from traffic.models import Config
from traffic.sumo.network import build
from traffic.sumo.signals import create
import json
if __name__=="__main__":
    folder=Path("experiments/network_smoke")
    c=Config()
    info=build(c,folder)
    create(c,c.before_ns,c.before_ew,info,folder/"signals.add.xml")
    print(json.dumps(info,ensure_ascii=False,indent=2))

