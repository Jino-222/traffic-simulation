from dataclasses import dataclass, asdict, field
from typing import Any
import hashlib
import json

DIRECTIONS = ("N", "S", "E", "W")
LABELS = {"N": "북측", "S": "남측", "E": "동측", "W": "서측"}
OPPOSITE = {"N": "S", "S": "N", "E": "W", "W": "E"}
MODEL_VERSION = "2.0.0-dev"

@dataclass
class Approach:
    lanes: int = 1
    base: float = 0
    extra: float = 0

@dataclass
class Config:
    approaches: dict[str, Approach] = field(default_factory=lambda: {
        d: Approach(1, q, a) for d,q,a in zip(DIRECTIONS,(650,550,450,350),(250,150,100,100))
    })
    cycle: float = 90
    yellow: float = 3
    all_red: float = 2
    before_ns: float = 40
    before_ew: float = 40
    improved_ns: float = 50
    improved_ew: float = 30
    saturation: float = 1800
    start_loss: float = 2
    crossing_length_ns: float = 20
    crossing_length_ew: float = 20
    pedestrian_speed: float = 1
    pedestrian_walk: float = 3
    pedestrian_margin: float = 2
    pedestrian_budget_ns: float = 25
    pedestrian_budget_ew: float = 25
    pedestrian_rate: float = 60
    road_length: float = 300
    speed_kmh: float = 50
    warmup: int = 900
    duration: int = 3600
    drain: int = 900
    seed: int = 42
    stochastic: bool = False
    step_length: float = 0.5
    demand_profile: list[float] = field(default_factory=lambda:[1.0])
    vehicle_mix: dict[str,float] = field(default_factory=lambda:{"car":1.0,"bus":0.0,"truck":0.0})
    car_tau: float = 1.0
    car_sigma: float = 0.0
    record_trajectories: bool = False
    trajectory_period: float = 0.5
    telemetry_period: float = 1.0
    e2_enabled: bool = True
    e2_speed_threshold: float = 0.1
    e2_time_threshold: float = 1.0
    e2_jam_gap: float = 10.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw):
        values = dict(raw)
        values["approaches"] = {d: Approach(**raw["approaches"][d]) for d in DIRECTIONS}
        return cls(**values)

    def fingerprint(self):
        def normalize(x):
            if isinstance(x,dict): return {k:normalize(v) for k,v in x.items()}
            if isinstance(x,(list,tuple)):return [normalize(v) for v in x]
            if isinstance(x,(int,float)) and not isinstance(x,bool): return float(x)
            return x
        return hashlib.sha256(json.dumps(normalize(self.to_dict()),sort_keys=True,allow_nan=False).encode()).hexdigest()[:16]

def scenario_specs(c):
    return [
        ("before","입주 전", c.before_ns,c.before_ew,False),
        ("after","입주 후", c.before_ns,c.before_ew,True),
        ("improved","신호 개선 후보", c.improved_ns,c.improved_ew,True),
    ]

