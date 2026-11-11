대구 범어네거리 SUMO 시각화 실험실
====================================

1. 바로 보기

현재 컴퓨터: http://127.0.0.1:8504/web/
서버가 꺼져 있으면 '갤러리_실행.cmd'를 실행하세요.
다른 컴퓨터에서도 Python 3가 있다면 아래 명령으로 볼 수 있습니다.
    python launch_gallery.py --open
웹 갤러리에는 추가 Python 패키지나 인터넷 연결이 필요하지 않습니다.
HTML을 더블클릭하면 브라우저의 로컬 파일 제한으로 JSON이 로드되지 않을 수 있습니다.

2. 볼 수 있는 자료

figures/01_network_atlas             실제 OSM 도로망과 가상 유입 위치
figures/02_speed_comparison          3개 시나리오 평균속도 비교 지도
figures/03_congestion_and_tradeoff   누적 정지 시간과 도로별 속도 변화
figures/04_junction_closeup          동일 시각 차량/신호 확대 장면
figures/05_isometric_city            별도 렌더러의 2.5D 도시 조감도
figures/06_metrics_and_completion    완료/미완료/미진입과 지표 비교
figures/07_time_space_trajectories    동→서 이동 차량의 시간-공간 궤적
figures/08_signal_plan               90초 주기 신호 현시 비교
figures/09_native_sumo_overview      SUMO GUI 자체 렌더링 전경
figures/10_native_sumo_closeup       SUMO GUI 자체 렌더링 확대 장면

01~08은 PNG 및 벡터 PDF, 09~10은 원본 PNG입니다.
output/daegu_comparison_replay.mp4: 1600×740, 25초, 12fps.
관측 구간 300~1,496초를 4초 간격으로 재생하므로 약 48배속이며 위치 보간은 없습니다.
output/scenario_metrics.csv: 시나리오 지표
output/edge_metrics.csv: 도로별 속도/체류/정지 집계
output/validation.json 및 output/audit.json: 검증 결과
web/: 시나리오·2D/입체/속도/정체 전환, 재생, 확대, 차량 선택, 궤적, PNG 저장

3. 실험 조건

대상: 범어네거리 주변. OSM 중심점 35.8591365N, 128.6262151E.
원자료 bbox: 128.6167151,35.8516365,128.6357151,35.8666365.
OSM에서 참조하는 완전한 도로가 bbox 밖으로 연장되어 SUMO 네트워크 경계는 더 넓습니다.
지도 전경은 중심 주변 약 1.7km 범위를 보여줍니다.

기본 수요 목표: 북400/남450/동900/서900대/시.
입주 추가 수요: 남측600대/시. 실제 특정 아파트의 사업/교통량과 무관합니다.
직진60%, 좌/우 목적지 각20% 확률. 난수로 경로를 배정하므로 실제 구성은 정확히 그 비율이 아닙니다.
도착 시간은 일정 간격에 무작위 흔들림을 주었습니다. 전체 수요는 25분 동안 출발 요청합니다.
승용92%, 버스형4%, 트럭형4% 확률. 후자의 형상/길이는 다르지만 통행 권한은 passenger입니다.
실제 시내버스 노선/정류장이나 물류 OD를 구현한 것은 아닙니다.

SUMO1.28.0, seed2026, 시간 간격0.5초, FCD2초, 웹/영상4초.
준비0~300초, 관측300~1,500초, 잔여 통행 관측1,500~2,100초.
충돌 처리 warn, 순간이동(time-to-teleport) 비활성화 -1.
도착하지 못한 차량도 tripinfo에 기록합니다.
입주 후와 조정안은 정확히 같은 after.rou.xml을 사용합니다.
기본 신호는 netconvert 자동 생성입니다. 실제 대구 신호운영계획이 아닙니다.
중앙 신호만 현시 순서/신호 상태/황색6초를 보존하여 15/17/17/17초 → 16/12/21/17초로 변경했습니다.
수요 가중치와 최소녹색10초로 만든 단일 휴리스틱 후보입니다. 최적화나 AI 제어 모델이 아닙니다.
보행자, 보행신호 및 횡단시간 검증은 이 도시 확장 버전에 포함하지 않았습니다.
이전 단일 교차로 연구의 보행 제약 검사를 도시 모델에서 완료한 것처럼 해석하면 안 됩니다.

4. 관측된 결과와 해석

                     입주 전     입주 후     신호 조정안
출발 요청             1105        1355          1355
종료 시 통행 완료     1058        1086          1173
종료 시 통행 중         47         146           143
종료 시 미진입           0         123            39
평균 정지 차량        89.42      135.04        119.47
완료 차량 timeLoss    163.04      193.62        197.76 초
충돌 / 순간이동        0/0         0/0           0/0

입주 후 대비 완료87대 증가, 평균 정지 약11.5% 감소, 미진입84대 감소.
반면 완료 차량 평균 timeLoss는 약2.1% 증가했습니다.
완료 차량 구성과 완료율이 달라지므로 평균 timeLoss만으로 전체 차량의 개선을 단정할 수 없습니다.
지표는 다른 모집단/시간 범위를 갖습니다. 완료 지표는 종료시점까지, 평균 정지는 관측구간에 한정됩니다.
충돌0은 이 모델에서 발생하지 않았다는 뜻이며 실제 도로의 안전성을 입증하지 않습니다.
순간이동은 비활성화했으므로 0이며, 정체 차량을 임의 제거해서 개선을 만든 것은 아닙니다.
공식 LOS, 교통영향평가 판정 또는 현장 신호설계 결과가 아닙니다.

5. 재실행

Python3.11 이상과 SUMO1.28.0을 준비합니다.
    pip install -r requirements.txt
SUMO_HOME은 SUMO 배포 폴더(bin/netconvert.exe, bin/sumo.exe가 있는 폴더)로 지정합니다.
현재 컴퓨터의 기존 TrafficImpactLab SUMO 설치 경로는 자동 탐색합니다.

    python prepare_network.py     # 캐시된 OSM에서 네트워크/폴리곤 재생성
    python simulate.py            # 3개 SUMO 시나리오, 기존 runs 출력 갱신
    python analyze.py             # 지표/웹 재생 데이터
    python render_figures.py --movie
    python capture_sumo_gui.py overview
    python capture_sumo_gui.py closeup
    python validate.py
    python launch_gallery.py --open

SUMO GUI에서 각 runs/<scenario>/scenario.sumocfg를 열어 재생할 수도 있습니다.
이 경우 설정에 포함된 출력 파일이 갱신됩니다. 원래 결과 보존을 원하면 프로젝트 사본에서 실행하세요.
자동 캡처는 출력 파일을 덮어쓰지 않는 별도 GUI 실행을 사용합니다.
SUMO GUI 캡처는 Windows 그래픽 세션이 필요합니다.
플롯 한국어 글꼴은 Windows 맑은 고딕을 사용합니다. 글꼴 파일은 배포하지 않습니다.

6. 데이터와 라이선스

OSM 데이터: © OpenStreetMap contributors, ODbL1.0.
https://www.openstreetmap.org/copyright
https://opendatacommons.org/licenses/odbl/1-0/
원본과 파생 지리 데이터는 ODbL 조건을 따릅니다. 공개 재배포 시 출처와 라이선스를 유지하세요.
원본 다운로드 URL, 시각 및 SHA256은 data/source.json에 저장했습니다.
898개 건물 중 699개는 높이 자료가 없어12m를 가정했습니다.
나머지는 OSM height 또는 building:levels×3m이며, 렌더링 높이는3~150m로 제한했습니다.
모두 현장 미검증 높이이며 사진이나 실측3D 자료가 아닙니다.
SUMO 소프트웨어는 패키지에 포함하지 않았습니다.

참고한 공식 문서:
https://sumo.dlr.de/docs/Networks/Import/OpenStreetMap.html
https://sumo.dlr.de/docs/Simulation/Output/FCDOutput.html
https://sumo.dlr.de/docs/Simulation/Output/Lane-_or_Edge-based_Traffic_Measures.html
https://sumo.dlr.de/docs/Simulation/Output/Traffic_Lights.html
https://sumo.dlr.de/docs/Simulation/Output/StatisticOutput.html
https://sumo.dlr.de/docs/TraCI/Change_GUI_State.html

7. 포트폴리오에 사용하기 전 동생이 할 일

[직접 확인] 과거 업무에서 다루었던 범위와 이 합성 도시 실험의 차이를 설명하기.
[직접 수행] 시나리오/보기/시간을 바꾸고 차량 선택과 정체를 확인한 화면을 저장하기.
[직접 설명] 완료 차량은 늘었는데 평균 timeLoss도 증가한 이유와 선택 편향 설명하기.
[추가 연구] 현장 차로/회전/보행/신호 확인, 관측 교통량 보정, 다중 시드, 후보 탐색 및 미완료 패널티 비교.
[기여 확인] 이번 구현은 AI의 개발 보조로 제작되었습니다. 동생이 직접 코딩·검증했다고 소급해 쓰지 말고 실제 수행한 내용만 기록하세요.
이 자료를 기존 포트폴리오 PDF/Overleaf에 자동으로 반영하거나 제출하지는 않았습니다.
