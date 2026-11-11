"""Network-extension research report from audited SUMO output."""
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]
def read(p):return json.loads(p.read_text(encoding='utf-8'))

def main():
    folder=ROOT/'experiments/network_study_v1';s=read(folder/'summary.json');audit=read(ROOT/'docs/network_study_audit.json')
    rows={(r['family'],r['case']):r for r in s['discovery']};val={r['case']:r for r in s['validation']}
    turn_delta=rows['turning','adjusted']['mean_time_loss']-rows['turning','after']['mean_time_loss']
    lines=['# 회전·인접 교차로와 대기행렬 연구','',
      '## 연구 질문과 공통 조건','',
      '회전 경로·보행 상충을 포함했을 때 사전 지정 신호 조정안이 개선되는가? 두 교차로의 신호 시차와 하류 처리능력은 연결도로·상류 혼잡을 어떻게 바꾸는가?',
      '모든 도로·수요는 합성이다. 관측 1,800초, 준비 300초, 추가 종료 600초, 시간 간격 0.5초. 승용차 Krauss, 고정 동작 매개변수와 보행속도 1m/s를 사용했다. 도착 시각을 바꾸는 탐색 시드는 17/29/43, 별도 검증 시드는 71/83/97이다.',
      '이동류별·기존/추가별 차량 수는 진입 도로와 기간별 반올림 총량을 보존하도록 배정했다. 입주 전 차량의 ID·출발시각·차로·경로 속성은 입주 후에서도 같다. 같은 수요의 신호 비교는 같은 XML 파일을 공유한다.',
      '', '## 회전 교차로','',
      '각 진입 방향에 우회전·직진·좌회전 차로를 하나씩 두고, 한 방향씩 차량을 보내는 보호 현시 뒤에 보행 전용 현시를 배치했다. 우/직/좌 비율 20/60/20%, 기존 방향별 250대/시간, 추가 북150·남100·동50·서50대/시간이다.',
      '기준 녹색 북·동·남·서 18/18/18/18초와 후보 24/14/20/14초를 같은 주기 128.5초에서 비교했다. 황색 3초·전적색 5초, 보행 진입 3초·소거 21.5초다. 이는 보호 현시의 검증 사례이며 일반적인 현장 최적 운영을 주장하지 않는다.',
      '', '| 상황 | 완료 차량 평균 시간 손실(초) | 미진입+미완료 합계(3시드) |','|---|---:|---:|']
    for name,title in [('before','입주 전'),('after','입주 후'),('adjusted','사전 지정 조정')]:
        r=rows['turning',name];lines.append(f"| {title} | {r['mean_time_loss']:.4f} | {r['pending']+r['unfinished']} |")
    lines+=['',f'조정안은 입주 후 기준보다 평균 {turn_delta:+.4f}초 변했다. 평균이 악화되어 이 안을 개선안으로 추천하지 않는다. 세부 이동류와 시드에 따라 효과가 다르며 성공 사례만 고르지 않았다.',
      '', '## 두 교차로의 신호 시차','',
      '교차로 중심 간격 150m, 양방향 연결도로와 각 교차로 남북 진입로·횡단보도를 구성했다. 주기 90초, 정상 남북/동서 녹색 40/40초. 주방향 W→E는 기존500+추가200대/시간, 반대 방향은250+100, 남북 4개 흐름은 각각120대/시간이다.',
      '시차는 J1 주기의 시작 지연으로 정의했다. 현시 위치=(시각-시차) mod 주기다. 초기 현시와 남은 시간을 명시적으로 설정하고 모든 시간 단계에서 실제 신호를 대조했다.',
      '', '| 시차(초) | 3시드 평균 시간 손실(초) | 미처리 합계 |','|---|---:|---:|']
    for offset in s['protocol']['offsets']:
        r=rows['corridor',f'offset_{offset:02d}'];lines.append(f"| {offset} | {r['mean_time_loss']:.4f} | {r['pending']+r['unfinished']} |")
    lines+=['',f"탐색 범위에서 {s['frozen']['offset_seconds']}초를 선택하고, 탐색 결과 해시와 함께 고정한 뒤 새 시드를 실행했다. 검증 결과를 이용해 재선택하지 않았다.",
      '', '| 검증 시드 | 시차 0초 | 선택 시차 | 차이(초) |','|---|---:|---:|---:|']
    for p in audit['validation_pairs']:lines.append(f"| {p['seed']} | {p['reference_loss']:.4f} | {p['selected_loss']:.4f} | {p['delta']:+.4f} |")
    lines+=['',f"검증의 쌍별 평균 차이는 {audit['paired_delta_mean']:+.4f}초다. 제한된 합성 조건과 다섯 시차 범위의 결과이며 다른 수요·현장의 최적해를 뜻하지 않는다.",
      '', '## 하류 막힘과 도로 길이','',
      '선택 시차를 유지하고 J1 동서 녹색만 15초로 줄였다(남북65초, 주기 동일). 중심 간격150m와75m를 비교했다. 길이를 줄이면 저장공간 외에 주행시간·신호 도착 시각·보행 출발 위치도 바뀌므로 순수 저장공간 효과로 분리하지 않는다.',
      '', '| 조건 | 연결도로 평균 정지대수 | 연결도로 최장 정지군(m) | 상류 진입 평균 정지대수 | 미진입+미완료(3시드) |','|---|---:|---:|---:|---:|']
    for name,title in [('offset_11','정상150m'),('downstream_bottleneck_150','하류 제한150m'),('downstream_bottleneck_75','하류 제한75m')]:
        r=rows['corridor',name];lines.append(f"| {title} | {r['link_E_mean_halting']:.3f} | {r['link_E_max_queue_m']:.3f} | {r['W_in_mean_halting']:.3f} | {r['pending']+r['unfinished']} |")
    lines+=['','짧은 도로의 관측 행렬 길이가 작아도 전체 문제가 좋아졌다는 뜻은 아니다. 하류 제한에서 상류 정지 차량과 미처리 차량이 늘었다. 경계 점유 표본은 관측 구간의 잘림 가능성이며, 그 표지만으로 상류 전파를 확정하지 않는다.',
      '하류 제한 사례의 완료 차량 평균은 미처리 차량을 제외하므로 전체 수요 평균 또는 개선 순위로 사용하지 않는다. 미진입·미완료를 함께 보고한다.',
      '', '## 독립 경로·신호 검사','',
      f"총 {audit['runs']}회 실행의 수요·도로망 해시와 집계를 대조했다. 기록한 5개 실행의 완료 차량 경로 {audit['complete_path_checks']}건은 원시 FCD에서 확인한 외부 도로 순서와 입력 경로가 일치했다.",
      '신호 상충은 생성된 교차로 request/foes 행렬과 비교했다. 회전 경로의 내부 분할 차로를 연결해 신호 링크와 상충 행렬을 대응시켰다. 모든 이동류 사용, 네 개 또는 여덟 개 횡단보도 사용, 보행 이동 완료, 신호 진입·점유·경로 검사 이상 0건을 확인했다. 이는 모델 동작 검사이며 현장 안전 인증은 아니다.',
      '', '## 동적 대기행렬 검증','',
      '정지 속도<0.1m/s, 지속시간>1초, 차량 간 범퍼 간격≤10m로 연속 정지 차량군을 정의했다. 한 차로의 최대 길이를 구한 뒤 평행 차로 중 최댓값을 사용한다.',
      '알려진 배치를 SUMO에서 제어해 분리 차량군29m, 연결 차량군45m, 상류 경계에서 잘린42m, 재출발0m를 확인했다. 원시 FCD와 직접 관측 위치·속도 256건을 대조했다.',
      '분리 차량군에서 E2 원자료는 한 차로165m를 반환했다. 위치 기반 최장 연속 차량군과 정의·결과가 달라 E2 원자료를 검증된 최장 행렬로 표시하지 않는다. 원자료와 초기 실패 근거를 보존한다.',
      '기본 실험에서 궤적 저장을 켜면 geometric_queue.csv와 정의 파일을 자동 생성한다. 기록 주기·반올림·앞범퍼가 차로 안에 있는 차량만 포함하는 범위의 한계가 있다.',
      '', '## 재현·출처','',
      '```powershell','python -m traffic.research.network_study','python -m scripts.audit_network_study','python -m scripts.audit_queue_dynamic','python -m scripts.summarize_networks','```',
      '프로토콜이나 엔진 소스가 바뀌면 새 출력 폴더를 지정해야 한다. 완료한 동일 조건은 재사용하며 과거 다른 조건의 결과를 섞지 않는다.',
      '[SUMO 도로망·상충 행렬](https://sumo.dlr.de/docs/Networks/SUMO_Road_Networks.html) · [신호](https://sumo.dlr.de/docs/Simulation/Traffic_Lights.html) · [보행 모델](https://sumo.dlr.de/docs/Simulation/Pedestrians.html)']
    (ROOT/'docs/network_research.md').write_text('\n'.join(lines),encoding='utf-8');print('Network research report regenerated')

if __name__=='__main__':main()
