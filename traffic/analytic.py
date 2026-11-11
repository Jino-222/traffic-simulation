from dataclasses import replace
from .models import DIRECTIONS, LABELS, scenario_specs
from .validation import validate

def calculate(c):
    errors=validate(c)
    result=[]
    for sid,title,ns,ew,added in scenario_specs(c):
        rows=[]
        if not errors[sid]:
            for d in DIRECTIONS:
                a=c.approaches[d]
                green=ns if d in ("N","S") else ew
                capacity=a.lanes*c.saturation*(green-c.start_loss)/c.cycle
                volume=a.base+(a.extra if added else 0)
                rows.append(dict(direction=d,label=LABELS[d],volume=volume,capacity=capacity,
                                 vc=volume/capacity,green=green,effective_green=green-c.start_loss))
        result.append(dict(id=sid,title=title,errors=errors[sid],rows=rows))
    return result

def candidates(c, limit=5):
    budget=c.cycle-2*(c.yellow+c.all_red)
    choices=[]
    for ns in range(1,int(budget)):
        candidate=replace(c,improved_ns=float(ns),improved_ew=budget-ns)
        r=calculate(candidate)[2]
        if not r["errors"]:
            choices.append(dict(ns=ns,ew=budget-ns,max_vc=max(x["vc"] for x in r["rows"])))
    return sorted(choices,key=lambda x:(x["max_vc"],abs(x["ns"]-c.before_ns)))[:limit]

