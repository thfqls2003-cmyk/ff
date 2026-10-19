# balance/ — 레벨 폭발 모험단 20보스 밸런스 설계 (시뮬레이션 포함)

| 파일 | 내용 |
|---|---|
| `BOSS20_BALANCE_DESIGN.md` | 최종 설계서 (능력치 공식, 경험치 곡선, 보스 20종, 아이템 20종 + 강화석, 빌드 예시, 도파민 장치, 과금, PvP 상한, 자동 모험 모드, 시뮬 결과, 튜닝 노브, 변경 이유, 출시 순서) |
| `boss20_config.json` | 설계서의 모든 수치 (설정 원본). 시뮬레이터와 문서 생성기는 이 파일만 읽는다 |
| `sim_boss20.py` | 판 시뮬레이터. `python3 sim_boss20.py --quick` (핵심 표, ~30초) / `python3 sim_boss20.py --runs 300` (전체 보고서, ~2~3분) |
| `gen_boss20.py` | 앵커 보정으로 config 를 생성. `python3 gen_boss20.py --check` 로 "재생성 == config 파일" 검증 |
| `doc_boss20.py` | config + SIM_RESULT.txt 에서 설계서를 자동 생성 (손으로 옮긴 숫자 없음) |
| `SIM_RESULT.txt` | `python3 sim_boss20.py --runs 300` 출력 원문 (설계서 §13) |
| `baseline_v8_sim.py` | 비교용: PDF v8 수치를 그대로 돌린 기준선 시뮬 (1보스 부트스트랩 불가 등 문제 재현) |

표준 라이브러리만 사용 (Python 3.10+). 수치를 바꾸려면 `boss20_config.json` 을 고치고 `sim_boss20.py` 를 다시 돌리면 된다.
설계서 §14 "튜닝 노브 표"에 어떤 키를 올리고 내리면 무엇이 변하는지 적혀 있다.

사용 예:
```
python3 sim_boss20.py --gear none --runs 300          # 첫 판(장비 0) 부트스트랩 검증
python3 sim_boss20.py --gear full --build ls           # 풀장비 + 흡혈 빌드
python3 sim_boss20.py --gear full --plus 10 --plan full # 전부 +10 강화, 20보스 완주 판
python3 sim_boss20.py --gear I01,I02,I03 --build luck  # 특정 아이템 조합
```
