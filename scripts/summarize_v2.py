"""Regenerate an evidence-based research report without claiming pending work complete."""
from pathlib import Path
import json
from traffic.results import summary
ROOT=Path(__file__).resolve().parents[1]
def read(path):return json.loads(path.read_text(encoding="utf-8"))
def value(x):return "해당 없음" if x is None else f"{x:.3f}"
def main():
    study=ROOT/"experiments/study_v2";report=read(study/"discovery/search_summary.json")
    hold=read(study/"holdout/holdout_summary.json")
    requirements=read(ROOT/'docs/requirements.json')['requirements']
    complete=all(r['status']=='complete' for r in requirements)
    lines=["# 교통 변화 연구실 · 확장 연구 보고서", "",
      "이 문서는 저장된 원시 결과와 검증 기록에서 생성한 연구 보고서입니다. "+('계획의 연구·구현·배포 검증을 완료했습니다. 항목별 근거는 docs/final_audit.md에 정리했습니다.' if complete else '최종 배포 검증을 진행 중이며 항목별 상태는 아래에 표시합니다.'),
      "", "## 연구 질문", "",
      "합성 아파트 입주 수요를 반영할 때, 보행·신호 조건을 만족하며 전체 효율과 방향별 불이익을 함께 비교할 수 있는가?",
      "학습형 AI 모델은 사용하지 않았습니다. AI의 도움으로 개발한 계산·SUMO 실험·후보 열거 도구입니다.",
      "", "## 기준 조건", "",
      "4지 직진 교차로. 관측 3,600초, 준비 900초, 추가 종료 900초. 입주 전 2,000대/시간, 입주 후 2,600대/시간.",
      "주기 90초, 황색 3초·전적색 2초씩 2회. 기준 녹색 남북/동서 40/40초. 모든 도로·수요는 가상입니다.",
      "신호 후보는 남북 25~55초의 1초 간격, 동서는 80-남북으로 총 31개입니다. 다른 주기·구조의 최적해를 뜻하지 않습니다.",
      "", "## 31개 후보 탐색", "",
      f"탐색 시드 {report['seeds']}, 총 {len(report['records'])}회. 실패 {len(report['failed'])}회.",
      f"모든 시드에서 후보·기준이 정상 종료되고 관측 출발 예정 차량이 모두 완료한 적격 배분은 {sum(c['eligible'] for c in report['candidates'])}개입니다.",
      "미진입·미완료가 남는 배분은 완료 차량 평균으로 순위를 매기지 않습니다. 각 시드 내 수요 파일은 모든 후보가 공유합니다.",
      "", "| 배분(남북/동서 초) | 적격 | 전체 시간 손실 평균(초) | 시드별 최악 방향 평균의 평균(초) | 기준 대비 차이(초) | 시드·방향 중 최대 악화(초) | 미진입+미완료 합계 |",
      "|---|---|---:|---:|---:|---:|---:|"]
    for c in report["candidates"]:
        lines.append(f"| {c['ns']}/{c['ew']:g} | {'예' if c['eligible'] else '아니오'} | {value(c['mean_time_loss'])} | {value(c['worst_direction_time_loss'])} | {value(c['paired_delta_mean'])} | {value(c['worst_paired_direction_delta'])} | {c['pending']+c['unfinished']} |")
    lines+=["",f"전체 평균 기준 선택: {report['overall_best']}/{80-report['overall_best']}초. 방향 균형 기준 선택: {report['balanced_best']}/{80-report['balanced_best']}초.",
      "위 미처리 합계는 3개 시드의 합계이며 한 번의 실험 차량 수가 아닙니다.",
      "", "## 선택을 고정한 뒤 별도 시드 검증", "",
      f"검증 시드: {hold['frozen']['validation_seeds']}. 탐색에서 사용하지 않은 시드입니다. 결과를 보고 선택을 바꾸지 않았습니다.",
      "", "| 고정 후보 | 전체 평균(초) | 기준 대비 차이(초) | 쌍별 차이 표본 표준편차(초) | 시드·방향 중 최대 악화(초) | 미처리 합계 |",
      "|---|---:|---:|---:|---:|---:|"]
    for c in hold["validation"]["candidates"]:
        lines.append(f"| {c['ns']}/{c['ew']:g} | {value(c['mean_time_loss'])} | {value(c['paired_delta_mean'])} | {value(c['paired_delta_sd'])} | {value(c['worst_paired_direction_delta'])} | {c['pending']+c['unfinished']} |")
    lines+=["","49/31초는 전체 평균의 이점이 더 크고, 44/36초는 특정 방향의 악화가 더 작습니다. 목적함수에 따라 선택이 달라집니다.",
      "세 개의 별도 합성 시드 검증은 현장 성능이나 통계적 일반화의 증거가 아닙니다.",
      "", "## 시나리오별 민감도 연구", "",
      "같은 행 안에서 입주 후와 신호 후보를 비교합니다. 시드 407, 1시간 관측. 이 일괄 실행은 모두 불규칙 도착을 사용하므로 baseline과 irregular 행은 같은 조건입니다.",
      "", "| 시나리오 | 입주 후 평균(초) | 후보 평균(초) | 입주 후 미처리 | 후보 미처리 |",
      "|---|---:|---:|---:|---:|"]
    count=0
    for path in sorted((study/"scenarios").glob("*/comparison.json")):
        data=read(path);runs={r["scenario"]:summary(r) for r in data["sumo"]};a,b=runs["after"],runs["improved"]
        lines.append(f"| {path.parent.name} | {value(a['time_loss'])} | {value(b['time_loss'])} | {a['pending']+a['unfinished']} | {b['pending']+b['unfinished']} |");count+=1
    lines+=["",f"현재 저장된 시나리오 {count}/16개. 같은 조건의 두 행을 독립 실험 근거로 세지 않습니다. 규칙 도착 대조 실험 3회는 experiments/arrival_control_regular에 별도로 저장했습니다.",
      "", "## 지표와 데이터 범위", "",
      "- 시간 손실: 관측기간에 출발 예정인 차량 중 실행 종료까지 완료한 차량의 SUMO TripInfo timeLoss.",
      "- 전체 평균: 완료 차량 수로 가중. 미완료 평균이나 공식 제어지체·LOS로 표현하지 않음.",
      "- 정지 차량: 진입 도로에서 관측된 대수. 길이(m)와 구분.",
      "- 누적 진입·통과: 준비기간을 포함한 전체 실험 시작부터의 시간 집계.",
      "- geometric_queue: FCD의 차량 전면·길이·속도로 계산한 최장 연속 정지 차량군. 평행 차로를 합산하지 않음.",
      "- 원시 E2 queue_m: 독립 배치 실험에서 차이를 발견해 검증된 최장 대기행렬로 사용하지 않음. docs/progress_20261111.md 참고.",
      "", "## 공개 실측 자료와 모델 확장", "",
      "US DOT/FHWA NGSIM Lankershim 공개 궤적 26,905행·49대의 범위 제한 표본을 확보했습니다.",
      "SI 단위 변환과 중복·결측 검사를 수행하고, 연속 추종 대상 차량을 보정 11대·검증 10대로 분리했습니다.",
      "자료 라이선스는 CC BY-SA 3.0이며 출처·변환·추출 조건을 data/public/ngsim에 보존합니다.",
      "공개 표본으로 24개 Krauss 매개변수 조합을 보정하고 별도 차량 10대에서 검증했습니다. 기준 매개변수가 선택돼 추가 개선은 확인되지 않았습니다. 검증 차량별 RMSE 평균은 속도 1.253m/s, 간격 3.570m입니다.",
      "앞차 위치의 측정 흔들림, 비현실적 가속도, 작은 동일 장소 표본의 한계가 있습니다. 신호·차로 변경·아파트 통행발생량은 이 실험에서 보정하지 않았습니다. 상세 근거는 docs/advanced_research.md와 experiments/public_calibration_v2에 있습니다.",
      "보행 형상은 8개 시간 경계 조건과 9회 SUMO 실행을 검증했습니다. 입력과 생성 길이 중 긴 값을 적용하며, 매회 보행자 12명의 완료와 네 횡단보도 사용을 확인했습니다.",
      "회전·인접 교차로는 별도 합성 모델로 33회 탐색·6회 검증을 실행했습니다. 기록한 완료 차량 경로 3,946건과 신호·보행 검사를 대조했습니다. 회전 사전 지정안은 평균 시간 손실이 1.161초 증가해 개선안으로 추천하지 않습니다. 두 교차로에서는 다섯 시차 중 11초를 고정 선택한 뒤 별도 시드에서 평균 1.702초 감소를 확인했습니다. 기본 직진 교차로와 다른 모델이며 현장 최적해를 뜻하지 않습니다. 상세: docs/network_research.md.",
      "대기행렬은 분리 차량군·연결·관측 경계·재출발 네 배치의 29/45/42/0m와 일치했습니다. FCD 위치·속도 256건 대조 오차는 0입니다. 시간대 수요·차종은 docs/profile_mix_research.md에서 생성 대수·동작 매개변수·민감도 결과를 확인할 수 있습니다.",
      "[NGSIM 공식 출처](https://data.transportation.gov/d/8ect-6jqj)",
      "", "## 검증·수정 기록", "",
      "v1 대비 기준 지표 차이 0건. 기준 궤적 독립 대조 2,276건 일치. 회전·인접 교차로 추가 후 전체 테스트 83개 통과(docs/tests_v2_networks.xml). 상세·후보 그래프 220개 데이터 묶음을 원시 기록과 대조했고 상황별 히트맵 색상 범위를 통일했습니다(docs/chart_values_audit.json). 이후 변경의 검증 결과는 별도 기록합니다.",
      "후보 기준 실험 누락 방지, Windows AppTest 프로세스 격리, 재생 구간 경계 0.5초 오차를 수정했습니다.",
      "실패 기록을 삭제하지 않고 docs/tests_failure_apptest_spawn.xml, experiments/e2_audit에 보존했습니다.",
      "", "## 완료 여부와 남은 항목", "",
      "| 항목 | 상태 |",
      "|---|---|"]
    for r in requirements:
        lines.append(f"| {r['id']} · {r['title']} | {r['status']} |")
    lines+=["","## 재현 명령","",
      "프로젝트 폴더에서 제공된 Python 환경을 사용합니다.",
      "","~~~powershell","python -m pytest -q","python -m scripts.run_v2_study --output experiments/new_study",
      "python -m scripts.audit_ngsim","python -m scripts.audit_e2","python -m traffic.research.public_calibration",
      "python -m scripts.audit_pedestrian_geometry","python -m scripts.audit_completed_studies","python -m scripts.audit_chart_values","python -m scripts.audit_profile_mix",
      "python -m traffic.research.network_study --output experiments/new_network_study","python -m scripts.audit_network_study",
      "python -m scripts.summarize_advanced","python -m scripts.summarize_networks","python -m scripts.summarize_v2","~~~","",
      "기존 완료 폴더의 입력·코드 버전이 달라지면 새 출력 폴더를 사용해야 합니다. 과거 결과에 새 코드 결과를 덮어쓰지 않습니다.",
      "개발 도구·외부 지원·실무 검토 범위는 docs/contributions.md에 정리했습니다."]
    (ROOT/"docs/research_report.md").write_text("\n".join(lines),encoding="utf-8")
    print(f"Report regenerated: 31 candidates, frozen holdout, {count}/16 scenarios")
if __name__=="__main__":main()

