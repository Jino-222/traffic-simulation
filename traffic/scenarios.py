"""Named, deterministic experimental configurations (all synthetic)."""
from dataclasses import dataclass, replace
from copy import deepcopy
from .models import Config, Approach, DIRECTIONS

@dataclass
class Scenario:
    id: str
    title: str
    question: str
    config: Config
    changed: list[str]
    synthetic: bool = True

def library(base=None):
    base=deepcopy(base or Config())
    out=[]
    def add(sid,title,question,changed,**changes):
        out.append(Scenario(sid,title,question,replace(deepcopy(base),**changes),changed))
    add("baseline","기본 입주","같은 수요에서 신호 배분의 이익·불이익은?",[])
    for scale,label in [(0,"추가 없음"),(.5,"추가 수요 50%"),(1.5,"추가 수요 150%"),(2,"추가 수요 200%")]:
        add("extra_"+str(scale).replace(".","p"),label,"입주 규모 변화에 따라 부담이 어떻게 변하는가?",["extra"],
            approaches={d:replace(a,extra=a.extra*scale) for d,a in base.approaches.items()})
    total=sum(a.extra for a in base.approaches.values())
    for sid,title,shares in [("ns_focus","남북 집중",[.5,.3,.1,.1]),("ew_focus","동서 집중",[.1,.1,.5,.3])]:
        add(sid,title,"추가 수요 총량이 같아도 방향 분배에 따라 결과가 달라지는가?",["extra distribution"],
            approaches={d:replace(base.approaches[d],extra=total*x) for d,x in zip(DIRECTIONS,shares)})
    for scale in [1.25,1.5]:
        add("high_"+str(scale).replace(".","p"),f"전체 수요 {scale:g}배","신호 변경으로 대응하기 어려운 수요 수준은?",["base","extra"],
            approaches={d:replace(a,base=a.base*scale,extra=a.extra*scale) for d,a in base.approaches.items()})
    add("slow_pedestrian","느린 보행 0.7m/s","보행시간 확보로 신호 선택 범위가 얼마나 줄어드는가?",
        ["pedestrian_speed","pedestrian_budget_ns","pedestrian_budget_ew","improved_ns","improved_ew"],
        pedestrian_speed=.7,pedestrian_budget_ns=34,pedestrian_budget_ew=34,improved_ns=46,improved_ew=34)
    add("fast_pedestrian","보행속도 1.2m/s","속도 가정 민감도는?",["pedestrian_speed"],pedestrian_speed=1.2)
    lanes=deepcopy(base.approaches);lanes["N"].lanes=2
    add("north_two_lanes","북측 2차로","차로 변화와 신호 배분의 효과는?",["N lanes"],approaches=lanes)
    add("irregular","불규칙 도착","고정 총수요 안에서 도착 시각 변동의 영향은?",["stochastic"],stochastic=True)
    add("peak_profile","중간 구간 집중","관측기간 총량이 같아도 순간 집중은 어떤 영향을 주는가?",
        ["demand_profile"],demand_profile=[.8,1.0,1.4,.8])
    add("mixed_fleet","승용차·버스·트럭 혼합","차종 동작 차이에 따른 영향은?",["vehicle_mix"],
        vehicle_mix={"car":.85,"bus":.05,"truck":.10})
    add("zero_demand","차량 0대 경계","분모가 0인 결과를 올바르게 표시하는가?",["base","extra"],
        approaches={d:Approach(a.lanes,0,0) for d,a in base.approaches.items()})
    return {s.id:s for s in out}

def metadata(scenario):
    return dict(id=scenario.id,title=scenario.title,question=scenario.question,
                changed=scenario.changed,synthetic=scenario.synthetic,config=scenario.config.to_dict())

