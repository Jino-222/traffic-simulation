import math
from .models import DIRECTIONS, LABELS, scenario_specs

def finite(v):
    return isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v)

def validate(c, crossing_lengths=None):
    common=[]
    def check(v,low,high,label,integer=False):
        if not finite(v) or not low <= v <= high or (integer and int(v)!=v):
            common.append(f"{label}: {low}~{high} 범위의 {'정수' if integer else '숫자'}가 필요합니다.")
    for d in DIRECTIONS:
        a=c.approaches[d]
        check(a.lanes,1,4,LABELS[d]+" 차로 수",True)
        check(a.base,0,10000,LABELS[d]+" 기존 수요")
        check(a.extra,0,10000,LABELS[d]+" 추가 수요")
    for key,low,high,label in [
        ("cycle",30,300,"주기"),("yellow",0,10,"황색"),("all_red",0,10,"전적색"),
        ("saturation",600,2400,"포화교통류율"),("start_loss",0,10,"출발 손실"),
        ("crossing_length_ns",1,100,"남북 보행 횡단길이"),("crossing_length_ew",1,100,"동서 보행 횡단길이"),
        ("pedestrian_speed",0.3,2,"보행속도"),("pedestrian_walk",1,30,"보행 진입 허용시간"),
        ("pedestrian_margin",0,15,"보행 소거 여유"),("pedestrian_budget_ns",1,300,"남북 보행 배정"),
        ("pedestrian_budget_ew",1,300,"동서 보행 배정"),("pedestrian_rate",0,600,"횡단보도당 보행 수요"),
        ("road_length",100,1000,"도로 길이"),("speed_kmh",10,80,"제한속도"),
        ("step_length",0.1,1,"시뮬레이션 시간 간격"),
        ("car_tau",0.1,3,"차량 반응시간"),("car_sigma",0,1,"차량 동작 변동"),
        ("trajectory_period",0.1,5,"궤적 기록 간격"),("telemetry_period",0.1,10,"시간별 집계 간격"),
        ("e2_speed_threshold",0.01,5,"정체 판정 속도"),("e2_time_threshold",0,30,"정체 판정 지속시간"),
        ("e2_jam_gap",1,30,"정체 차량 연결 간격")
    ]: check(getattr(c,key),low,high,label)
    for key,low,high,label in [("warmup",0,3600,"준비시간"),("duration",60,7200,"관측시간"),
                               ("drain",0,3600,"추가 종료시간"),("seed",0,2147483647,"시드")]:
        check(getattr(c,key),low,high,label,True)
    if finite(c.step_length) and c.step_length > 0:
        for key in ["cycle","yellow","all_red","before_ns","before_ew","improved_ns","improved_ew","pedestrian_walk","trajectory_period","telemetry_period"]:
            value=getattr(c,key)
            if finite(value) and abs(value/c.step_length-round(value/c.step_length))>1e-6:
                common.append(f"{key}: 시간 간격 {c.step_length}초의 배수로 설정하세요.")
        if finite(c.car_tau) and c.car_tau<c.step_length:
            common.append("차량 반응시간은 시뮬레이션 시간 간격 이상이어야 합니다.")
    profile=c.demand_profile
    if not isinstance(profile,(list,tuple)) or not 1<=len(profile)<=24 or any(not finite(v) or not 0<=v<=10 for v in profile):
        common.append("시간대 수요 배율은 0~10 범위 숫자 1~24개가 필요합니다.")
    elif abs(sum(profile)/len(profile)-1)>1e-6:
        common.append("총수요 보존을 위해 시간대 수요 배율의 평균은 1이어야 합니다.")
    if not isinstance(c.vehicle_mix,dict) or set(c.vehicle_mix)!={"car","bus","truck"} or any(not finite(v) or not 0<=v<=1 for v in c.vehicle_mix.values()) or abs(sum(c.vehicle_mix.values())-1)>1e-6:
        common.append("승용차·버스·트럭 비율은 0~1이고 합계가 1이어야 합니다.")
    for key in ("record_trajectories","e2_enabled","stochastic"):
        if not isinstance(getattr(c,key),bool):common.append(f"{key}: 참/거짓 값이 필요합니다.")
    for axis in ("ns","ew"):
        length=getattr(c,"crossing_length_"+axis)
        if crossing_lengths:
            length=max(length,crossing_lengths.get(axis,0)) if finite(length) else length
        if finite(length) and finite(c.pedestrian_speed) and c.pedestrian_speed>0:
            need=c.pedestrian_walk+length/c.pedestrian_speed+c.pedestrian_margin
            budget=getattr(c,"pedestrian_budget_"+axis)
            if finite(need) and finite(budget) and budget+1e-6<need:
                common.append(f"{'남북' if axis=='ns' else '동서'} 보행 배정 {budget:g}초 < 필요 {need:.2f}초 (입력·생성 길이 중 긴 값 적용).")
    results={}
    for sid,title,ns,ew,_ in scenario_specs(c):
        errors=list(common)
        for name,g,budget in [("남북",ns,c.pedestrian_budget_ns),("동서",ew,c.pedestrian_budget_ew)]:
            if not finite(g) or g<=0 or g>300:
                errors.append(f"{name} 녹색시간은 0보다 크고 300초 이하여야 합니다.")
            elif g<=c.start_loss:
                errors.append(f"{name} 녹색시간은 출발 손실시간보다 길어야 합니다.")
            if finite(g) and finite(budget) and g+1e-6<budget:
                errors.append(f"{name} 녹색 {g:g}초 안에 보행 배정 {budget:g}초가 들어가야 합니다.")
        if all(finite(v) for v in (ns,ew,c.yellow,c.all_red,c.cycle)):
            total=ns+ew+2*(c.yellow+c.all_red)
            if abs(total-c.cycle)>1e-6:
                errors.append(f"신호 합계 {total:g}초 ≠ 주기 {c.cycle:g}초.")
        results[sid]=errors
    return results

