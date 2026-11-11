"""Generate advanced research notes directly from completed saved evidence."""
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def main():
    folder=ROOT/'experiments/public_calibration_v2';s=read(folder/'summary.json')
    a=s['calibration_best'];b=s['validation']['baseline'];v=s['validation']['calibrated'];p=s['protocol']
    lines=['# 공개 궤적 보정·보행 형상 연구','',
      '## 공개 자료 연구 질문','',
      '공개 NGSIM Lankershim의 연속 차량 추종 표본에서, SUMO Krauss 매개변수 조정이 관측 속도·간격과의 오차를 줄이는가?',
      '', '## 자료·실험 설계','',
      '원자료 26,905행·49대의 범위 제한 표본에서 같은 차로·구간·방향의 연속 추종 자료를 추출했다. 대상 뒤차 ID로 보정 11대와 검증 10대를 먼저 분리했다.',
      '차량 간 앞범퍼 거리에서 앞차 길이를 빼 차간격을 구했다. 피트→미터 변환계수는 0.3048이다. 앞차의 종방향 위치에서 뒤로 움직이는 측정 흔들림은 누적 최댓값으로 교정했다. 뒤차 관측값은 수정하지 않았다.',
      '독립된 직선 도로에 각 추종 쌍을 배치했다. 앞차만 관측 위치에 맞는 구간 속도로 제어하고, 뒤차는 최초 위치·속도를 설정한 뒤 자유롭게 계산되게 했다. 실제 원자료의 신호·차로 변경·주변 차량은 재현하지 않았다.',
      'tau 0.6/1.0/1.4/1.8초 × minGap 0.5/1.5/2.5m × accel 1.0/2.6m/s² = 24개 조합을 비교했다. sigma=0, decel=4.5m/s², 속도 상한 22.222222m/s, 시간 간격 0.1초를 고정했다.',
      '목적함수는 차량별 [속도 RMSE / 2m/s + 간격 RMSE / 10m]의 동일 가중 평균이다. 최초 상태를 맞춘 t=0은 점수에서 제외했다. 정규화 단위·후보·검증 분리는 protocol.json으로 먼저 고정했다.',
      '', '## 결과','',
      f"선택값: {s['frozen']['parameters']}. 보정 점수 {a['mean_score']:.6f}. 기준값과 같은 조합이 선택됐으므로 추가 보정 이익은 확인되지 않았다.",
      '', '| 자료 | 차량별 속도 RMSE 평균(m/s) | 차량별 간격 RMSE 평균(m) | 정규화 점수 |',
      '|---|---:|---:|---:|',
      f"| 보정·선택 조합 | {a['mean_speed_rmse_mps']:.6f} | {a['mean_gap_rmse_m']:.6f} | {a['mean_score']:.6f} |",
      f"| 검증·기준 | {b['mean_speed_rmse_mps']:.6f} | {b['mean_gap_rmse_m']:.6f} | {b['mean_score']:.6f} |",
      f"| 검증·선택 조합 | {v['mean_speed_rmse_mps']:.6f} | {v['mean_gap_rmse_m']:.6f} | {v['mean_score']:.6f} |",
      '', '검증 결과를 보고 후보를 다시 선택하지 않았다. 차량 전체 프레임을 합쳐 계산한 RMSE가 아니라 차량별 RMSE의 평균이다.',
      '', '| 검증 뒤차 ID | 속도 RMSE(m/s) | 간격 RMSE(m) | 평가 프레임 |','|---|---:|---:|---:|']
    for r in v['trajectories']:lines.append(f"| {r['follower']} | {r['speed_rmse_mps']:.4f} | {r['gap_rmse_m']:.4f} | {r['frames']} |")
    q=v['preprocessing']
    lines+=['','## 검증과 한계','',
      f"검증 앞차 위치 재생 최대 오차 {v['leader_position_max_error_m']:.3e}m. 위치 단조화 최대 수정량 {max(x['monotonic_adjustment_max_m'] for x in q.values()):.6f}m. 물리적 겹침 충돌·순간이동은 {v['collisions']}·{v['teleports']}건이었다.",
      f"관측 위치를 강제로 따르는 앞차에서 급제동 경고 {v['leader_emergency_warnings']}건, 자율 뒤차에서 {v['follower_emergency_warnings']}건이 기록됐다. 측정 잡음에 의한 비현실적 가속도는 제거되지 않았다. 경고 원문을 보존했다.",
      '검증 차량 중 ID 140은 다른 차량보다 차간격 오차가 컸다. 한두 개의 잘 맞는 그래프만 제시하지 않고 차량별 오차와 전체 선택기를 제공한다.',
      '동일 장소·겹치는 시간의 작은 편의 표본이며 일부 앞뒤 차량 관계가 연결된다. 대상 ID 분리가 완전한 통계적 독립성을 뜻하지 않는다. 다른 현장이나 아파트 통행발생량·교차로 개선 효과로 일반화하지 않는다.',
      '추가 후속 연구는 위치 평활화 규칙의 물리적 적합성, 새로운 시간대·장소 검증 자료, 더 다양한 차량 추종 모델 비교가 필요하다. 현재 기준값을 검증된 현장값으로 자동 적용하지 않는다.',
      '일차 실행에서 종료한 차량의 구독 해제를 빠뜨려 unknown vehicle 로그가 발생했다. 결과를 보존한 뒤 v2에서 구독을 해제하고 전체 실행을 반복했다. 보정 점수와 검증 결과는 같았으며 해당 오류는 사라졌다.',
      '', '## 보행 형상 연구','',
      '방향별 차로 수 1~4 × 보행속도 0.7/1.0m/s의 8개 조건을 검사했다. 생성 횡단길이는 각각 6.4/12.8/19.2/25.6m였다. 입력 가정 20m와 생성 길이 중 긴 값을 시간 검사에 사용한다.',
      '필요시간을 0.5초 단위로 올림한 배정은 통과하고, 그보다 0.5초 짧은 배정은 8개 조건에서 모두 차단됐다.',
      '입력 20m·생성 6.4m, 입력·생성 6.4m 일치, 입력 20m·생성 25.6m·느린 보행의 3개 사례를 각 3상황으로 실행했다. 매회 보행자 12명이 네 횡단보도를 이용해 이동을 완료했고 신호 진입·점유 검사 이상은 없었다.',
      '이는 고정 속도 보행과 합성 형상의 동작 검증이다. 실제 보행행태나 현장 안전을 검증한 것이 아니다.',
      '', '## 출처·재현','',
      '[US DOT/FHWA NGSIM](https://data.transportation.gov/d/8ect-6jqj) · [자료 사용 조건 CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/) · [SUMO TraCI 차량 제어](https://sumo.dlr.de/docs/TraCI/Change_Vehicle_State.html)',
      '원자료·질의·단위 변환은 data/public/ngsim, 보정 프로토콜·후보·고정 선택·검증 예측은 experiments/public_calibration_v2, 보행 원시 결과는 experiments/pedestrian_geometry에 저장했다.',
      '검증 CSV는 NGSIM 관측 자료와 SUMO 예측을 결합한 파생 자료이며 CC BY-SA 3.0 출처·변경·공유 조건을 따른다.',
      '', '```powershell','python -m traffic.research.public_calibration','python -m scripts.audit_pedestrian_geometry','python -m scripts.audit_completed_studies','python -m scripts.summarize_advanced','```']
    (ROOT/'docs/advanced_research.md').write_text('\n'.join(lines),encoding='utf-8')
    print('Advanced research report regenerated from completed outputs')

if __name__=='__main__':main()
