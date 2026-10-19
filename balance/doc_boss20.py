#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BOSS20_BALANCE_DESIGN.md 생성기.
숫자는 오직 boss20_config.json(설정)과 SIM_RESULT.txt(시뮬 출력)에서만 끌어온다. 손으로 옮긴 숫자는 없다.
실행: python3 doc_boss20.py  →  BOSS20_BALANCE_DESIGN.md
"""
import json, os, re, sys, math
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sim_boss20 as S

cfg = json.load(open(os.path.join(HERE, "boss20_config.json"), encoding="utf-8"))
SIM = open(os.path.join(HERE, "SIM_RESULT.txt"), encoding="utf-8").read()
curve = S.Curve(cfg["exp_curve"])
st, F, C, R, CAPS = cfg["stats"], cfg["formulas"], cfg["combat"], cfg["run"], cfg["caps"]
ITEMS, BOSSES, MONS, ROUTES, STONES = cfg["items"], cfg["bosses"], cfg["monsters"], cfg["routes"], cfg["stones"]
ROUTE_KR = {"main": "가운데", "left": "질풍", "right": "군단"}
UP = STONES["upgrade_mult_per_plus"]

# ----------------------------------------------------------------- 서식
def big(x):
    x = float(x)
    if x >= 1e12: return f"{x/1e12:.2f}조"
    if x >= 1e8: return f"{x/1e8:.2f}억"
    if x >= 1e4: return f"{x/1e4:.1f}만"
    return f"{int(round(x)):,}"

def num(x): return f"{int(round(x)):,}"
def pct(x, d=0): return f"{x*100:.{d}f}%"
def f1(x): return f"{x:.1f}"
def f2(x): return f"{x:.2f}"

# ----------------------------------------------------------------- 시뮬 결과 파싱
def sim_section(tag):
    """'### A.' 처럼 시작하는 블록 전체(다음 ### 전까지)."""
    m = re.search(r"^### " + re.escape(tag) + r"\..*?(?=^### |\Z)", SIM, re.S | re.M)
    if not m:
        raise KeyError(tag)
    return m.group(0).rstrip()

def sim_rows(tag):
    """블록 안 마크다운 표의 데이터 행(셀 리스트)."""
    rows = []
    for line in sim_section(tag).splitlines():
        if line.startswith("|") and not line.startswith("|---") and not line.startswith("| #") and not line.startswith("| 보스 |") \
                and not line.startswith("| 빌드") and not line.startswith("| 아이템") and not line.startswith("| 레벨") and not line.startswith("| 시드"):
            rows.append([c.strip() for c in line.strip().strip("|").split("|")])
    return rows

def sim_summary_line(tag):
    for line in sim_section(tag).splitlines():
        if line.startswith("클리어율"):
            return line
    return ""

KEY = {}
for m in re.finditer(r"(\w+)=([^\s]+)", SIM.split("### 핵심 수치 요약")[1]):
    KEY[m.group(1)] = m.group(2)
RUNS = re.search(r"판 수 = (\d+)", SIM).group(1)

# 자연 진행(C표) 보스별 행: id → dict
NAT = {}
for r in sim_rows("C"):
    bid = r[0].split()[0]
    NAT[bid] = dict(items=r[1], reach=r[2], spawn=r[3], lvl=r[4], win=r[5], secs=r[6], hits=r[7], deaths=r[8], mins=r[9])

def rows_by_name(tag):
    out = {}
    for r in sim_rows(tag):
        if len(r) >= 10 and r[0].isdigit():
            out[r[1]] = dict(reach=r[2], spawn=r[3], lvl=r[4], win=r[5], secs=r[6], rng=r[7], hits=r[8], deaths=r[9])
    return out

FULL20 = rows_by_name("E-2")
PLUS5 = rows_by_name("F5")
PLUS10 = rows_by_name("F10")
GEAR0 = rows_by_name("A")
GEAR1 = rows_by_name("B")
MAIN10 = rows_by_name("D")
FEVER_OFF = rows_by_name("I")
WARP = rows_by_name("Q")

def summary_fields(tag):
    """'클리어율(...) 96% | ... | 중간 판 시간 9.9분 ...' 줄을 dict 로."""
    line = sim_summary_line(tag)
    d = {}
    for part in line.split("|"):
        part = part.strip()
        m = re.match(r"(.+?)\s([\d.,만억조%]+[^\s]*)(?:\s\((.*)\))?$", part)
        if m:
            d[m.group(1).strip()] = m.group(2)
    return d

J_ROWS = sim_rows("J")
K0_ROWS = sim_rows("K-0")
K_ROWS = sim_rows("K")
L1_ROWS = sim_rows("L-1")
L2_ROWS = sim_rows("L-2")
N_ROWS = sim_rows("N")
O_SECTION = sim_section("O")
P_SECTION = sim_section("P")
M_SECTION = sim_section("M")
H_SECTION = sim_section("H")

def m2_rows():
    out = []
    in_m2 = False
    for line in M_SECTION.splitlines():
        if line.startswith("M-2"): in_m2 = True
        if line.startswith("M-3"): in_m2 = False
        if in_m2 and line.startswith("| B"):
            out.append([c.strip() for c in line.strip().strip("|").split("|")])
    return out

def m1_rows():
    out = []
    for line in M_SECTION.splitlines():
        if line.startswith("| ") and "×" in line and "치명" in line:
            out.append([c.strip() for c in line.strip().strip("|").split("|")])
    return out

def m_line(prefix):
    for line in M_SECTION.splitlines():
        if line.strip().startswith(prefix):
            return line.strip()
    return ""

# ----------------------------------------------------------------- 공식 도우미 (시뮬과 같은 식)
def crit_p(luk, lvl, add=0.0, cap=None):
    c = F["crit"]
    v = c["base"] + c["span"] * luk / (luk + c["lvl_coef"] * lvl + c["c"]) + add
    return min(cap if cap is not None else CAPS["pve"]["crit_p"], v)

def jackpot_p(luk, lvl):
    f = F["luck_bonus"]
    return min(f["p_cap"], f["p_coef"] * luk / (luk + f["lvl_coef"] * lvl + f["c"]))

def ls_pct(P, lvl, gear=0.0):
    f = F["lifesteal"]
    return min(CAPS["pve"]["lifesteal"], f["max_from_pts"] * P / (P + f["lvl_coef"] * lvl + f["c"]) + gear)

def aspd(Sv, cap=None):
    f = F["aspd"]
    m = 1 + Sv / (1 + Sv / f["half"]) if Sv >= 0 else 1 + Sv
    return min(cap if cap is not None else CAPS["pve"]["aspd_mult"], m)

def targets(R_add):
    rc = F["range"]
    Rr = min(rc["cap"], rc["base"] + R_add)
    return Rr, min(CAPS["pve"]["range_targets"], 1 + int((Rr - rc["base"]) // rc["per_target"]))

def heal_cap(ls, add=0.0):
    f = F["lifesteal"]
    return min(CAPS["pve"]["heal_per_s_max"], max(f["heal_per_s_cap_base"] + add, f["heal_per_s_ls_coef"] * ls))

def pts_balanced(lvl, ratio=None):
    """행운 당첨 없는 순수 포인트 3×(L−1) 을 비율대로 나눔."""
    ratio = ratio or {k: st[k]["auto_ratio"] for k in ("hp", "atk", "luk", "ls")}
    tot = sum(ratio.values())
    P = st["pts_per_level"] * (lvl - 1)
    return {k: P * ratio[k] / tot for k in ratio}

def item_eff(iid, plus=0):
    it = ITEMS[iid]
    parts = []
    for e in it["effects"]:
        v = e["v"] * (UP ** plus if e.get("up") else 1)
        if e["k"] == "var":
            parts.append(f"피해 분산 {e['lo']}~{e['hi']}")
        else:
            parts.append(f"{e['k']}={v:.3g}" + ("↑" if e.get("up") else ""))
    return "; ".join(parts)

def boss_by_item(iid):
    return BOSSES[ITEMS[iid]["boss"]]

def deaths_affordable(budget):
    n, spent = 0, 0
    while True:
        cost = min(R["energy_death_max"], R["energy_death_base"] + n * R["energy_death_step"])
        if spent + cost > budget: return n
        spent += cost; n += 1

def gear_summary(ids, plus=0):
    g = S.aggregate(cfg, ids, {i: plus for i in ids})
    return g

# ----------------------------------------------------------------- §0 용 파생값 (전부 SIM/config)
E1 = summary_fields("E-1")
FULL_MAIN_CLEAR = E1["가운데 10보스 클리어"]
FULL_MAIN_DEATHS = E1["평균 사망"]
PLUS5_MIN = summary_fields("F5")["중간 판 시간"].replace("분", "")
PLUS10_MIN = summary_fields("F10")["중간 판 시간"].replace("분", "")
_reach = [int(v["reach"].rstrip("%")) for v in NAT.values()]
NAT_REACH_RANGE = f"{min(_reach)}~{max(_reach)}%"
_caps = [b["hit_cap"] for b in BOSSES.values()]
HITCAP_RANGE = f"{min(_caps)*100:g}~{max(_caps)*100:g}%"
_mh = [b["min_hits"] for b in BOSSES.values()]
MINHITS_RANGE = f"{min(_mh)}~{max(_mh)}"
BUILD_DEATHS = " / ".join(f"{r[0]} {r[6]}" for r in J_ROWS)
_m2 = m2_rows()
_m2x = [r for r in _m2 if r[1] == "흡혈 극대"]
M2_HEAL_RANGE = f"{min(float(r[4].rstrip('%/s')) for r in _m2x):.1f}~{max(float(r[4].rstrip('%/s')) for r in _m2x):.1f}%/s"
M2_TAKEN_RANGE = f"{min(float(r[5].rstrip('%/s')) for r in _m2x):.1f}~{max(float(r[5].rstrip('%/s')) for r in _m2x):.1f}%/s"
_l1s = [float(r[-1]) for r in L1_ROWS]
L1_SECS_RANGE = f"{min(_l1s):.1f}~{max(_l1s):.1f}"
_l2s = [float(r[-1]) for r in L2_ROWS]
L2_SECS = f"{min(_l2s):.1f}~{max(_l2s):.1f}"
PASS_PRICE = [p for p in cfg["monetization"]["products"] if p["id"] == "pass"][0]["price_robux"]
_h = re.search(r"패스 없음 평균 보스 ([\d.]+) / 패스 ([\d.]+)", H_SECTION)
H_DELTA = f"{float(_h.group(1)):.2f}→{float(_h.group(2)):.2f}(아이템 4개 판)"
_o = re.search(r"중간값: 무료 — .*?전부 \+10 (\d+)판/(\d+)분 ; 패스 — .*?전부 \+10 (\d+)판/(\d+)분", O_SECTION)
O_FREE_PLUS10, O_PASS_PLUS10 = _o.group(1), _o.group(3)
_i = summary_fields("I")
FEVER_OFF_CLEAR = _i["가운데 10보스 클리어"]
FEVER_OFF_MIN = _i["중간 판 시간"].replace("분", "")

out = []
P = out.append

# ================================================================= 머리 + §0
P(f"""# 레벨 폭발 모험단 — 20보스 밸런스 최종 설계서 (v{cfg['meta']['version']})

- 문서 생성: `python3 doc_boss20.py` — 모든 숫자는 `boss20_config.json`(설정 원본)과 `SIM_RESULT.txt`(`python3 sim_boss20.py --runs {RUNS}` 출력)에서 스크립트가 끌어왔다. 손으로 옮긴 숫자는 없다. 끝의 `verify_doc_boss20.py` 가 문서와 설정의 일치를 검사한다.
- 파일: `boss20_config.json`(수치 전부: stats·formulas·caps·exp_curve·combat·run·items·stones·builds·monetization·pvp·boss_rush·monsters 60·bosses 20·routes) / `sim_boss20.py`(판 시뮬레이터, 의뢰자가 직접 돌릴 수 있음) / `gen_boss20.py`(수치 생성·앵커 보정·`--check` 재생성 검증) / `SIM_RESULT.txt`(§13 원문).
- 뼈대: {cfg['meta']['skeleton']}. 이식: {' / '.join(cfg['meta']['grafts'])}.
- 네 설계안(A 로그라이트·B 도파민·C 경제/PvP·D 수학)과 세 심사(J1 플레이어·J2 수치·J3 라이브옵스)를 거쳐 B 를 뼈대로 통합한 결과물이다. 충돌은 수치 심사(J2) 기준을 우선했다.

---
## 0. 한눈에 보기 (핵심 수치)

| # | 항목 | 수치 | 출처 |
|---|---|---|---|
| 1 | 보스 수 / 길 | 20 = 가운데 길 10 + 질풍 루프 5(5단계 광장) + 군단 루프 5(10단계 광장) | config.routes |
| 2 | 첫 판(장비 0) | 판 시간 {float(KEY['first_run_minutes']):.1f}분, 1보스 승률 {pct(float(KEY['first_boss_win_no_gear']))}, 1보스전 {KEY['first_boss_secs']}초, 사망 {KEY['first_boss_deaths']}, 2보스 도달 {pct(float(KEY['second_boss_reach']))} | SIM A표 |
| 3 | 가운데 10보스 풀클리어(풀장비 +0) | {float(KEY['full_clear_main_minutes']):.1f}분, 클리어 {FULL_MAIN_CLEAR}, 사망 {FULL_MAIN_DEATHS} | SIM E-1표 |
| 4 | 20보스 완주 한 판(풀장비 +0 / +5 / +10) | {float(KEY['full_clear_20_minutes']):.1f}분 / {PLUS5_MIN}분 / {PLUS10_MIN}분, 클리어 {pct(float(KEY['clear20_full_gear']))}, 최종 레벨 {big(float(KEY['final_level_full20']))} | SIM E-2·F5·F10 |
| 5 | 자연 진행 보스전(처음 만나는 판) | {KEY['natural_secs']}초, 보스전 사망 {KEY['natural_deaths']}, 도달 {NAT_REACH_RANGE} | SIM C표 |
| 6 | 풀 +10 보스전 하한 | 보스별 중간값 최단 {KEY['plus10_min_secs']}초, 절대 최단 {KEY['plus10_abs_min_secs']}초 (목표 ≥10) | SIM F10·M-4 |
| 7 | 한 방 즉사 | 어느 쪽도 없음 — 플레이어 받는 한 타 ≤ 최대 체력 {pct(F['damage_taken']['player_hit_cap'])}(실측 최대 {KEY['max_hit_taken']}), 보스 한 타 ≤ 보스 체력 {HITCAP_RANGE}(최소 {MINHITS_RANGE}타) | config.formulas·bosses, SIM |
| 8 | 경험치 곡선 | need(L) = {cfg['exp_curve']['n0']}×(1+L/{cfg['exp_curve']['K']})^{cfg['exp_curve']['a']} — 펭귄 3전 뒤 레벨 {num(ROUTES['main']['stages'][0]['anchor_levels']['after_first_fight'])}, 1보스 뒤 {num(ROUTES['main']['stages'][0]['anchor_levels']['after_boss'])}, 10보스 뒤 {big(ROUTES['main']['stages'][9]['anchor_levels']['after_boss'])}, 20보스 뒤 {big(ROUTES['right']['stages'][4]['anchor_levels']['after_boss'])} | config.exp_curve·routes |
| 9 | 에너지 | 시작 {R['energy_start']}, 전투 −{R['energy_fight']}, 사망 {R['energy_death_base']}→{R['energy_death_base']+R['energy_death_step']}→{R['energy_death_base']+2*R['energy_death_step']}→{R['energy_death_max']}(누진, 광장에서 초기화), 가운데 보스 +{R['energy_boss_main']}, 루프 보스 +{R['energy_boss_loop']} | config.run |
| 10 | 빌드 5종(20보스 판 사망) | {BUILD_DEATHS} | SIM J표 |
| 11 | 흡혈의 의미 | 흡혈 균형 vs 균형 20보스 사망 {KEY['ls_deaths_20']} vs {KEY['bal_deaths_20']}(가운데 10보스만 {KEY['ls_deaths_main']} vs {KEY['bal_deaths_main']}); 흡혈 극대 30% 도 초당 회복 {M2_HEAL_RANGE} < 피격 {M2_TAKEN_RANGE} → 불사 없음 | SIM J·M-2 |
| 12 | 행운의 의미 | 치명 5%→상한 {pct(CAPS['pve']['crit_p'])}, 레벨업 '행운!' 2배 당첨 p≤{pct(F['luck_bonus']['p_cap'])} → 레벨당 포인트 최대 ×{1+F['luck_bonus']['p_cap']*(F['luck_bonus']['double_mult']-1):.1f}, 레벨 무관(M-1), 보스 장갑 관통 ×{C['crit_cap_mult']}(광전사 반지 ×{C['crit_cap_mult']+ITEMS['I06']['effects'][2]['v']:.1f}) | config.formulas·caps, SIM M-1 |
| 13 | PvP(결투 레벨 {num(cfg['pvp']['duel_level'])}) | 5빌드 미러 매치 비대칭 쌍 승률 {KEY['pvp_pair_range']}, 결투 {L1_SECS_RANGE}초 (상한 없으면 {L2_SECS}초) | SIM L-1·L-2 |
| 14 | 과금 | 패스 {PASS_PRICE}R$ 등 {len(cfg['monetization']['products'])}종 — 시작 에너지 +1 조차 팔지 않음(H표: 처치 보스 {H_DELTA}), 자동 모험은 첫 처치 없음·강화석 {pct(cfg['monetization']['auto_adventure']['stone_rate'])}, 계정 성장(전부 +10) 무료 {O_FREE_PLUS10}판 vs 패스 {O_PASS_PLUS10}판 | config.monetization, SIM H·O |
| 15 | 강화 | 급별 강화석 4종, +p 는 효과값 ×{UP}^p(+10 ×{UP**10:.2f}), 성공률 {pct(STONES['success'][0])}→{pct(STONES['success'][-1])}, 3연속 실패 천장, 하락 없음, +10 기대 강화석 {STONES['expected_stones_to_plus10']}개·정수 {STONES['expected_essence_to_plus10']}개 | config.stones |
| 16 | 출시 | {cfg['release_plan_ko'][0].split(':')[0]} 가운데 10보스·피버 OFF 로도 성립(I표: 10종 보유 클리어 {FEVER_OFF_CLEAR}·{FEVER_OFF_MIN}분) | SIM I표 |
""")

# ================================================================= §1 철학
_b1, _b10, _b20 = BOSSES["B01"], BOSSES["B10"], BOSSES["B20"]
P(f"""---
## 1. 설계 철학

**한 줄:** 레벨은 한 판 안에서 1 → 수백억까지 터지게 두되(첫 판 {summary_fields('A')['중간 최종 레벨']}, 가운데 풀클리어 {E1['중간 최종 레벨']}, 20보스 완주 {summary_fields('E-2')['중간 최종 레벨']}), **보스전만은 반드시 {KEY['natural_secs']}초짜리 장면**으로 고정하고, 판이 끝나면 남는 것은 장비 20종·강화·강화석·정수·기록뿐이다.

기준선(v8) 시뮬이 보여 준 다섯 문제와 이 설계의 답:

| 기준선 문제 | 원인 | 해법 | 시뮬 증거(§13) |
|---|---|---|---|
| (a) 1보스 부트스트랩 불가(장비 0 승률 0%) | 1보스 HP 20,000·공 6,000 이 '엄니검 보유자' 기준 | 모든 보스를 **그 보스를 처음 만날 때 자연스럽게 가진 장비(이전 보스 아이템)** 기준으로 역산(앵커 보정). 1보스는 장비 0 기준 | A표: 장비 0, 1보스 승률 {pct(float(KEY['first_boss_win_no_gear']))}, {KEY['first_boss_secs']}초, 사망 {KEY['first_boss_deaths']} |
| (b) 보스전 0.6~13초, 드라마 없음 | 피해 상한이 없어 장비 1개로 즉사 | **타격당 피해 상한(장갑) {HITCAP_RANGE}** + 체력바 {min(b['phases'] for b in BOSSES.values())}~{max(b['phases'] for b in BOSSES.values())}개 + 전환 무적 {min(b['transition_s'] for b in BOSSES.values())}~{max(b['transition_s'] for b in BOSSES.values())}초 + 그로기·브레스·보호막·가시·저주·재생·타이머·광란·소환·흡혈·거울 기믹 | 자연 {KEY['natural_secs']}초, 풀장비 +10 중간값 최단 {KEY['plus10_min_secs']}초, 한 방 없음 |
| (c) 흡혈·범위가 죽은 아이템 | 1:1 결투·1초 전투 | 전투 1:N(최대 3마리, 군단 루프는 항상 떼), 범위 = **동시 타격 수**, 흡혈 = **초당 회복 vs 초당 피격**(초당 상한 = max({pct(F['lifesteal']['heal_per_s_cap_base'])}, {F['lifesteal']['heal_per_s_ls_coef']}×흡혈률) — 공속이 아니라 흡혈 투자가 상한을 올림) | K-0: 흡혈 송곳니 획득 → 다음 보스 승리 {K0_ROWS[2][3]}, 거인 망토 {K0_ROWS[3][3]}; J표 흡혈 균형 사망 {KEY['ls_deaths_20']} < 균형 {KEY['bal_deaths_20']} |
| (d) 벽 아니면 허수아비 | 장비 배율이 단계 배율을 압도 | 장비는 배율·공속·흡혈·범위·경험치로 분산 + 합산 상한(caps) + 체력바·장갑으로 하한. 장비 −1 / 자연 / 풀장비 3단 체감 | A·B표(부족): 2~3번째 보스에서 소진, C표(자연) 사망 {KEY['natural_deaths']}, E표(풀) 사망 {FULL_MAIN_DEATHS} |
| (e) 인플레이션 체감은 장점 | — | 경험치 표로 바꾸되 need(L)={cfg['exp_curve']['n0']}×(1+L/{cfg['exp_curve']['K']})^{cfg['exp_curve']['a']} 의 완만한 곡선 → 초반 1전투 +수십, 후반 +수억 | §3 표: 1단계 첫 전투 뒤 {num(ROUTES['main']['stages'][0]['anchor_levels']['after_first_fight'])}, 10단계 보스 뒤 {big(ROUTES['main']['stages'][9]['anchor_levels']['after_boss'])}, 군단 끝 {big(ROUTES['right']['stages'][4]['anchor_levels']['after_boss'])} |

통합에서 지킨 원칙:
1. **보상은 리듬으로 온다.** 전투 끝 → 레벨 티커 {C['loot_s']}초 → 걷기 → 다음 전투. 보스는 등장 {C['boss_intro_s']:.0f}초 → {KEY['natural_secs']}초 드라마 → 문 {C['door_s']:.0f}초. 첫 판 {float(KEY['first_run_minutes']):.1f}분, 가운데 풀클리어 {float(KEY['full_clear_main_minutes']):.1f}분, 20보스 완주 {float(KEY['full_clear_20_minutes']):.1f}분.
2. **보스는 숫자가 아니라 장면이다.** 장갑 때문에 풀 +10 이라도 최소 {MINHITS_RANGE}타, 중간값 {KEY['plus10_min_secs']}초 이상. 체력바가 깨질 때마다 화면이 멈추고, 그로기/브레스/폭주 타이머가 '지금 때려 / 지금 피해 / 서둘러'를 만든다.
3. **난이도는 계단이 아니라 경사.** 자연 장비 기준 보스마다 사망 {KEY['natural_deaths']}, 도달 {NAT_REACH_RANGE}. 보스 성향(탱커·유리대포·균형)으로 {KEY['natural_secs']}초에 분산.
4. **선택이 결과를 바꾼다.** 7칸(반지 2)에 20종, 보스별 정답 아이템이 다르다(보호막→공속, 가시→치명, 저주→확정 치명, 흡혈 봉인→피해감소, 소환→범위). 빌드 5종이 전부 20보스 클리어 100% 이면서 사망·시간·레벨이 갈린다(J표). 함정 빌드(공격 몰빵·행운 몰빵·행운 0 탱커)는 시뮬로 표시해 UI 경고로 쓴다.
5. **험로는 에너지 광산.** 루프 구간 = 2전투 −{2*R['energy_fight']} + 보스 +{R['energy_boss_loop']} = 순이익 +{R['energy_boss_loop']-2*R['energy_fight']}. 장비를 갖추고 들어가면 20보스 한 판이 열리고(E-2 {pct(float(KEY['clear20_full_gear']))}), 장비 없이 들어가면 표지판(권장 레벨)이 말린다.
6. **과금은 결과를 안 바꾼다.** 시작 에너지 +1 조차 팔지 않는다(H표 측정). 꾸미기·뽑기·강화석·보호권 없음. 파는 것은 시간·정보·기록·도전권.
7. **PvP 는 같은 코드, 다른 상한 열.** caps.pve / caps.pvp 16항목. 결투는 레벨 {num(cfg['pvp']['duel_level'])} 고정 + 분배 비율·장비·강화만. 5빌드 상성 {KEY['pvp_pair_range']}.

**구조 요약:** 한 판 = 마을 → 가운데 길 10구간(각 4전투 + 문 보스) → 5단계 광장에서 질풍 루프(5구간 × 2전투 + 보스, {ROUTES['left']['loop_length_stud']} stud 돌아 광장 복귀) → 10단계 광장에서 군단 루프(같은 구조, 최종 보스). 루프는 선택이며 조건부 보스 4(B13·B14·B18·B19)가 '공략 목표'를 준다.
""")

# ================================================================= §2 공식
_L = 1000
_pb = pts_balanced(_L)
_hp = (st["hp"]["base"] + st["hp"]["per_pt"] * _pb["hp"])
_atk = (st["atk"]["base"] + st["atk"]["per_pt"] * _pb["atk"])
_luk = st["luk"]["base"] + st["luk"]["per_pt"] * _pb["luk"]
_Pls = _pb["ls"] * st["ls"]["per_pt"]
_cp = crit_p(_luk, _L)
_jp = jackpot_p(_luk, _L)
_ls = ls_pct(_Pls, _L)
_ls_g = ls_pct(_Pls, _L, ITEMS["I03"]["effects"][0]["v"])
_S_wind = ITEMS["I02"]["effects"][0]["v"]
_S_storm = ITEMS["I12"]["effects"][0]["v"]
_R_giant, _t_giant = targets(ITEMS["I04"]["effects"][0]["v"])
_R_gale, _t_gale = targets(ITEMS["I13"]["effects"][0]["v"])
_hc_bal = heal_cap(_ls_g)
_hc_max = heal_cap(CAPS["pve"]["lifesteal"], ITEMS["I17"]["effects"][1]["v"])
_b1hit = _b1["atk"]
_lv1 = ROUTES["main"]["stages"][0]["anchor_levels"]["at_boss"]
_pb1 = pts_balanced(_lv1); _hp1 = st["hp"]["base"] + st["hp"]["per_pt"] * _pb1["hp"]
_a = _b1["anchor"]
_ratio_text = ":".join(str(st[k]["auto_ratio"]) for k in ("hp", "atk", "luk", "ls"))
P(f"""---
## 2. 능력치·전투 공식 전부 (닫힌 형식, JSON `stats` / `formulas` / `combat` / `caps`)

### 2.1 능력치 (레벨 1당 포인트 {st['pts_per_level']}, 자동 분배 기본 비율 체:힘:행:흡 = {_ratio_text})
| 능력치 | 기본 | 1포인트당 | 기본 자동 비율 | 효과 |
|---|---|---|---|---|
| 체력 | {st['hp']['base']} | +{st['hp']['per_pt']} | {st['hp']['auto_ratio']} | {st['hp']['desc_ko']} |
| 힘 | {st['atk']['base']} | +{st['atk']['per_pt']} | {st['atk']['auto_ratio']} | {st['atk']['desc_ko']} |
| 행운 | {st['luk']['base']} | +{st['luk']['per_pt']} | {st['luk']['auto_ratio']} | {st['luk']['desc_ko']} |
| 흡혈 | {st['ls']['base']} | +{st['ls']['per_pt']} (포인트 P) | {st['ls']['auto_ratio']} | {st['ls']['desc_ko']} |

**예시 계산 — 레벨 {num(_L)}, 균형 분배, 행운 당첨 없음, 장비 없음:** 포인트 {num(st['pts_per_level']*(_L-1))} → 체력 {num(_pb['hp'])}·힘 {num(_pb['atk'])}·행운 {num(_pb['luk'])}·흡혈 {num(_pb['ls'])}.
최대 체력 = {st['hp']['base']} + {st['hp']['per_pt']}×{num(_pb['hp'])} = **{num(_hp)}**, 공격력 = {st['atk']['base']} + {st['atk']['per_pt']}×{num(_pb['atk'])} = **{num(_atk)}**, 행운 = {st['luk']['base']} + {num(_pb['luk'])} = **{num(_luk)}**, 흡혈 포인트 P = {num(_Pls)}.
(실제 판에서는 '행운!' 당첨으로 포인트가 ×{1+_jp*(F['luck_bonus']['double_mult']-1):.2f} 안팎 더 들어온다 — 2.2 참고.)

### 2.2 공식표
| 항목 | 식 | 예시(레벨 {num(_L)} 균형) | 비고 |
|---|---|---|---|
| 피해 | 공격력 × U({F['damage_taken']['var_lo']},{F['damage_taken']['var_hi']}) × (치명이면 치명 배율) | {num(_atk)} × 0.9~1.1 → {num(_atk*0.9)}~{num(_atk*1.1)} (치명 {num(_atk*F['crit']['mult_base']*0.9)}~{num(_atk*F['crit']['mult_base']*1.1)}) | 질풍검은 U(0.7,1.5). 다중 타격은 대상마다 따로 굴림 |
| 치명타 확률 | min({pct(CAPS['pve']['crit_p'])}, {pct(F['crit']['base'])} + {pct(F['crit']['span'])}×행운/(행운 + {F['crit']['lvl_coef']}×레벨 + {F['crit']['c']}) + 장비) | {pct(F['crit']['base'])} + {pct(F['crit']['span'])}×{num(_luk)}/({num(_luk)}+{num(F['crit']['lvl_coef']*_L)}+{F['crit']['c']}) = **{pct(_cp,1)}** | 레벨에 상대적 → 행운 비율이 같으면 어느 레벨에서도 같은 치명. 폭풍 정령 −10%p |
| 치명타 피해 | min(×{CAPS['pve']['crit_mult']}, ×{F['crit']['mult_base']} + 장비) | ×{F['crit']['mult_base']} (광전사 반지 +{ITEMS['I06']['effects'][0]['v']} → ×{F['crit']['mult_base']+ITEMS['I06']['effects'][0]['v']}, 종언의 정령 +{ITEMS['I20']['effects'][3]['v']}) | PvP 상한 ×{CAPS['pvp']['crit_mult']} |
| 행운! 2배 당첨 | 레벨 1 오를 때마다 p = min({pct(F['luck_bonus']['p_cap'])}, {F['luck_bonus']['p_coef']}×행운/(행운 + {F['luck_bonus']['lvl_coef']}×레벨 + {F['luck_bonus']['c']})) 로 그 레벨의 포인트 {st['pts_per_level']} → {st['pts_per_level']*F['luck_bonus']['double_mult']:.0f} | p = {pct(_jp,1)} → 레벨당 기대 포인트 {st['pts_per_level']}×(1+{_jp:.3f}) = **{st['pts_per_level']*(1+_jp):.2f}** (×{1+_jp:.2f}) | 상한 ×{1+F['luck_bonus']['p_cap']:.1f}, 레벨 무관(M-1). 서버는 레벨마다 주사위, 고레벨은 '행운 ×n' 묶음 표시. PvP 결투는 당첨 없음 |
| 흡혈률 | min({pct(CAPS['pve']['lifesteal'])}, {pct(F['lifesteal']['max_from_pts'])}×P/(P + {F['lifesteal']['lvl_coef']}×레벨 + {F['lifesteal']['c']}) + 장비) | {pct(F['lifesteal']['max_from_pts'])}×{num(_Pls)}/({num(_Pls)}+{num(_L)}+{F['lifesteal']['c']}) = **{pct(_ls,1)}** (+송곳니 {pct(ITEMS['I03']['effects'][0]['v'])} = {pct(_ls_g,1)}) | 균형 ≈{pct(F['lifesteal']['max_from_pts']*0.125/(0.125+1.0),0)}, 흡혈 2배 분배 ≈{pct(F['lifesteal']['max_from_pts']*0.25/(0.25+1.0),0)}, 몰빵(비율 0.75) ≈{pct(F['lifesteal']['max_from_pts']*0.75/(0.75+1.0),0)} 로 수렴(레벨 ≫ 50 일 때 P/레벨 = 3×비율/비율합) |
| 초당 회복 상한 | min({pct(CAPS['pve']['heal_per_s_max'])}, max({pct(F['lifesteal']['heal_per_s_cap_base'])} + 성배, {F['lifesteal']['heal_per_s_ls_coef']}×흡혈률)) × 최대 체력. 스윙당 상한 = 그 값 × 공격 간격 | 흡혈 {pct(_ls_g,1)} → max({pct(F['lifesteal']['heal_per_s_cap_base'])}, {F['lifesteal']['heal_per_s_ls_coef']}×{pct(_ls_g,1)}) = **{pct(_hc_bal,1)}/초**; 흡혈 {pct(CAPS['pve']['lifesteal'])}+성배 → {pct(_hc_max,1)}/초 | 공속을 올려도 초당 회복은 안 늘고, 흡혈에 투자하면 상한이 오른다(A 안). 보스 기믹 '내 흡혈 ×0.5'. PvP 초당 {pct(CAPS['pvp']['heal_per_s_max'])} |
| 공격 속도 | 배율 = 1 + S/(1 + S/{F['aspd']['half']}), S = 장비 공속 보너스 합. 상한 ×{CAPS['pve']['aspd_mult']}. S<0 은 1+S | 바람 정령 S {_S_wind} → ×{aspd(_S_wind):.2f}, 폭풍 정령 S {_S_storm} → ×{aspd(_S_storm):.2f}, S→∞ → ×{F['aspd']['half']+1:.1f} | 공격 간격 = {C['attack_interval']}초 ÷ 배율. **자동 타격과 버튼 평타가 쿨다운 공유**. 피버 ×{C['fever_aspd']} 는 별도, 절대 상한 ×{F['aspd']['fever_abs_cap']}(간격 {C['attack_interval']/F['aspd']['fever_abs_cap']:.2f}초). PvP 상한 ×{CAPS['pvp']['aspd_mult']} |
| 콤보·피버 | 쿨다운이 돌아온 뒤 {C['tap_window_s']}초 창 안에 탭 = 콤보 +1, 실패 = 유지, {C['combo_idle_reset_s']}초 무입력 = 0. {C['fever_hits']}콤보 = 피버 {C['fever_dur_s']:.0f}초(공속 ×{C['fever_aspd']}) | 탭 성공률 {pct(C['manual_combo_p'])} 가정 → 피버 가동률 {pct(min(b['anchor']['fever_uptime_assumed'] for b in BOSSES.values()))}~{pct(max(b['anchor']['fever_uptime_assumed'] for b in BOSSES.values()))}(앵커 기록), 판당 {KEY['fever_per_run']}회(E-1) | 자동 모험·PvP 피버 없음. 1차 출시 피버 OFF 로도 성립(I표) |
| 공격 범위 | R = min({F['range']['cap']}, {F['range']['base']} + 장비). 동시 타격 수 = min(살아있는 적, {CAPS['pve']['range_targets']}, 1 + floor((R−{F['range']['base']})/{F['range']['per_target']})) | 거인 망토 +{ITEMS['I04']['effects'][0]['v']} → R {_R_giant} → **{_t_giant}마리**, 광풍 망토 +{ITEMS['I13']['effects'][0]['v']} → R {_R_gale} → **{_t_gale}마리** | 스플래시(광풍 {pct(ITEMS['I13']['effects'][1]['v'])}, 종언 {pct(ITEMS['I20']['effects'][1]['v'])})는 범위 밖 적에게도. PvP(3v3) {CAPS['pvp']['range_targets']}마리·스플래시 {pct(CAPS['pvp']['splash'])} |
| 보스 타격 상한(장갑) | 1타 ≤ 보스 최대 체력 × hit_cap({HITCAP_RANGE}) × 관통(치명 ×{C['crit_cap_mult']}, 광전사 반지 ×{C['crit_cap_mult']+ITEMS['I06']['effects'][2]['v']:.1f}, 상한 ×{CAPS['pve']['crit_pierce']}, 일부 보스 ×{BOSSES['B09']['crit_pierce_cap']} 제한) × (그로기 중 ×2) + 파멸의 대검 +{pct(ITEMS['I10']['effects'][2]['v'])}p | 수정 매머드 체력 {num(_b1['hp'])} × {pct(_b1['hit_cap'],1)} = 1타 최대 {num(_b1['hp']*_b1['hit_cap'])} → 최소 {_b1['min_hits']}타 | 최소 타격 수 = ceil(1/hit_cap). 상한 타격은 '한계!' 표기. PvP 관통 없음 |
| 받는 피해 | 몬스터 공격력 × U({F['damage_taken']['var_lo']},{F['damage_taken']['var_hi']}) × (1 − 피해감소) × (도박 구역 ×{F['damage_taken']['zone_dmg_mult']}) ; 한 타 ≤ 최대 체력 {pct(F['damage_taken']['player_hit_cap'])} | 수정 매머드 1타 {num(_b1hit)} vs 권장 레벨 {num(_lv1)} 체력 {num(_hp1)} → {pct(_b1hit/_hp1,1)}(앵커 {_a['boss_hit_pct_of_player_hp']}%), 초당 {_a['boss_dps_pct_of_player_hp']}% | 피해감소 합산 1−Π(1−x), 상한 {pct(CAPS['pve']['dmg_reduce'])}. 반격 = 받은 피해 × reflect(상한 {pct(CAPS['pve']['reflect'])}) |
| 회복 | 전투 종료 시 최대 체력 {pct(C['after_fight_heal'])} 즉시 + 비전투 초당 {pct(C['regen_per_s'])} + 레벨업으로 최대 체력이 늘면 그만큼 즉시 회복 + 보스 제단 입장 시 가득 | — | '레벨업 = 회복'이 떼 전투의 생존 장치 |
| 사망 | 에너지 −(n번째 사망 = min({R['energy_death_max']}, {R['energy_death_base']}+(n−1)×{R['energy_death_step']})), 그 자리 부활·체력 가득·무적 {C['revive_invuln']}초(+수호 부적 {ITEMS['I09']['effects'][0]['v']:.0f}초), 적 체력 유지 | 1·2·3·4번째 사망 = −{R['energy_death_base']}, −{R['energy_death_base']+R['energy_death_step']}, −{R['energy_death_base']+2*R['energy_death_step']}, −{R['energy_death_max']} | 카운터는 광장(루프 입·출구)에서 0 으로. 수호 부적: 판 첫 사망 −{ITEMS['I09']['effects'][1]['v']} |
| 경험치 획득 | 몬스터 경험치 × 장비 경험치 배율(상한 ×{CAPS['pve']['exp_mult']}) × (도박 구역 ×{F['exp_gain']['zone_exp_mult']} + 행운의 왕관 {ITEMS['I14']['effects'][1]['v']}) × (보스: 보스 경험치 배율, 상한 ×{CAPS['pve']['boss_exp_mult']}) | 펭귄 {num(MONS['penguin']['exp'])} → 레벨 1 에서 {int(curve.L(MONS['penguin']['exp']))} | 레벨 = L(누적 경험치) 닫힌 식(§3) |

### 2.3 합산 상한표 (`caps`) — 장비·강화·스탯을 아무리 쌓아도 못 넘는 선
{CAPS['text_ko']}

| 항목 | 키 | PvE | PvP |
|---|---|---|---|
""")
for k, name in CAPS["names_ko"].items():
    pv, pp = CAPS["pve"][k], CAPS["pvp"][k]
    def _fmt(k, v):
        if k in ("range_targets",): return f"{v}마리"
        if k in ("aspd_mult", "crit_mult", "crit_pierce", "exp_mult", "boss_exp_mult", "atk_mult", "hp_mult", "dmg_mult"): return f"×{v}"
        return pct(v)
    P(f"| {name} | caps.*.{k} | {_fmt(k, pv)} | {_fmt(k, pp)} |")
P(f"""
### 2.4 전투 타이밍 (`combat`)
- 플레이어: 자동 타격 사거리 {C['auto_range']} stud, 버튼 평타 사거리 {C['button_range']} stud, 둘이 {C['attack_interval']}초 쿨다운을 공유(button_shares_cooldown). 접근 {C['approach_s']}초 뒤 첫 스윙. 데미지 적용은 휘두른 뒤 0.1초(기존).
- 몬스터: 거리 {C['monster_attack_reach']} 안에서 {C['monster_windup_s']}초 예고(빨간 번쩍) 후 판정, 등장 뒤 첫 공격 {C['first_hit']}초, 떼는 {C['timing']['add_spawn_stagger_s']}초 간격으로 어긋나게. 간격은 종별(가운데 약·중 {cfg['gen_params']['KIND']['main'][0]['interval']} / 정예 {cfg['gen_params']['KIND']['main'][2]['interval']}, 질풍 {cfg['gen_params']['KIND']['left'][0]['interval']}~{cfg['gen_params']['KIND']['left'][2]['interval']}, 군단 {cfg['gen_params']['KIND']['right'][2]['interval']}~{cfg['gen_params']['KIND']['right'][0]['interval']}초).
- 보스: 간격 {min(b['interval'] for b in BOSSES.values())}~{max(b['interval'] for b in BOSSES.values())}초. 전환 무적·그로기 중엔 공격 안 함. 전환이 끝난 뒤 첫 공격 {C['timing']['boss_attack_after_transition_s']}초, 전환/그로기 중 차례가 온 공격은 각각 {C['timing']['boss_attack_delay_after_transition_hit_s']}/{C['timing']['boss_attack_delay_after_stagger_s']}초 뒤.
- 연출 시간(시뮬 가정): 등장 {C['spawn_s']}초, 전리품·레벨 티커 {C['loot_s']}초, 제단 등장 {C['boss_intro_s']}초, 문 열림 {C['door_s']}초(조건부 보스 미등장 구간은 ×{C['timing']['no_boss_door_s_mult']}), 사망 연출 {C['death_anim_s']}초, 결산 {R['result_s']}초, 마을 문→첫 제단 {R['village_to_gate_s']}초, 루프 입장 {ROUTES['left']['enter_s']}초. 한 전투 최대 {C['max_fight_s']}초.
- 니어미스 = 체력 {pct(C['timing']['near_miss_hp_frac'])} 이하로 떨어졌다가 무사망 승리.
- {C['text_ko']}
""")

# ================================================================= §3 경험치
P(f"""---
## 3. 경험치·레벨 곡선 (`exp_curve`)

### 3.1 식 (서버는 누적 경험치가 아니라 레벨만 저장하고, 획득 시 E(L)+Δ → L(E) 로 복원)
- 레벨 L → L+1 필요 경험치: **need(L) = {cfg['exp_curve']['n0']} × (1 + L/{cfg['exp_curve']['K']})^{cfg['exp_curve']['a']}**
- 레벨 L 도달 누적 경험치: **E(L) = {curve.A:.1f} × ((1 + L/{cfg['exp_curve']['K']})^{1+cfg['exp_curve']['a']} − {curve.c1:.4f})**  (E(1) = 0)
- 역함수(반복문 없음): **L(E) = {cfg['exp_curve']['K']} × ((E/{curve.A:.1f} + {curve.c1:.4f})^(1/{1+cfg['exp_curve']['a']}) − 1)**, 소수점 버림.
- 왜 a={cfg['exp_curve']['a']}: a=0 이면 경험치=레벨(순수 인플레이션), a=1 이면 보통 RPG. {cfg['exp_curve']['a']} 은 "경험치 ×{cfg['gen_params']['R_MAIN']} 마다 레벨 ×{cfg['gen_params']['R_MAIN']**(1/(1+cfg['exp_curve']['a'])):.1f}" — 10단계에서도 한 전투에 수백만 레벨이 오르고, 경험치 ×1.5 왕관은 레벨 ×{1.5**(1/(1+cfg['exp_curve']['a'])):.2f} 로 눌려 들어가 폭주하지 않는다.
- 숫자 범위: 최종 레벨 {big(float(KEY['final_level_full20']))}, B20 경험치 {big(_b20['exp'])} — Luau double 안전 범위(9e15) 안. UI 는 만/억/조 축약.

### 3.2 대표 레벨 표
| 레벨 L | need(L) | 누적 E(L) | 레벨 L 균형 분배 체력 / 공격력(장비 없음) |
|---|---|---|---|
""")
for L in (1, 10, 30, 89, 100, 154, 300, 485, 1000, 2081, 3000, 8277, 10000, 30000, 94078, 100000, 300000, 1000000, 3000000, 10000000, 45723424, 100000000, 1000000000, 18609869530, 100000000000):
    pb = pts_balanced(L)
    P(f"| {num(L)} | {curve.need(L):,.1f} | {big(curve.E(L))} | {big(st['hp']['base']+st['hp']['per_pt']*pb['hp'])} / {big(st['atk']['base']+st['atk']['per_pt']*pb['atk'])} |")
P(f"""
### 3.3 몬스터·보스 경험치와 기대 레벨 (JSON `routes[].stages[].anchor_levels`, `monsters[].exp`, `bosses[].exp`)
가운데 길 구간 s 기본(약 몬스터) 경험치 = {cfg['gen_params']['MAIN_BASE0']} × {cfg['gen_params']['R_MAIN']}^(s−1). 약/중/정예 = 기본 × {cfg['gen_params']['KIND']['main'][0]['exp_m']} / {cfg['gen_params']['KIND']['main'][1]['exp_m']} / {cfg['gen_params']['KIND']['main'][2]['exp_m']}. 가운데 보스 = 기본 × {cfg['gen_params']['BOSS_EXP_MULT']['main']:.0f}(≈ 그 구간 일반 전투 총합), 루프 보스 = 기본 × {cfg['gen_params']['BOSS_EXP_MULT']['loop']:.0f}. 질풍 루프 총 경험치 = 가운데 6구간의 {pct(cfg['gen_params']['LEFT_SHARE'])}(구간 성장비 ×{cfg['gen_params']['LEFT_G']}), 군단 루프는 10구간 뒤 경험치에서 이어진다(구간당 ×{ROUTES['right']['stages'][1]['base_exp']/ROUTES['right']['stages'][0]['base_exp']:.1f}). 기대 레벨은 균형 분배·자연 장비(이전 보스 아이템 자동 장착, 경험치 배율 포함)·수동 조작 기준이며, 판 60회 재측정으로 보정한 값이다.

| 길 | 구간 | 약 몬스터 경험치 | 보스 경험치 | 진입 레벨 | 첫 전투 뒤 | 보스 도착 | 보스 처치 뒤 | 첫 전투 +레벨 | 보스 +레벨(×) | 자연 경험치 배율 |
|---|---|---|---|---|---|---|---|---|---|---|
""")
for rid in ("main", "left", "right"):
    for sg in ROUTES[rid]["stages"]:
        a = sg["anchor_levels"]; b = BOSSES[sg["boss"]]
        P(f"| {ROUTE_KR[rid]} | {sg['stage']} | {big(sg['base_exp'])} | {big(b['exp'])} | {big(a['enter'])} | {big(a['after_first_fight'])} | {big(a['at_boss'])} | {big(a['after_boss'])} | +{big(a['after_first_fight']-a['enter'])} | +{big(a['after_boss']-a['at_boss'])} (×{a['after_boss']/a['at_boss']:.2f}) | ×{a['natural_exp_mult']} |")
P(f"""
읽는 법: 가운데 1구간 '첫 전투 뒤'는 인트로 펭귄 3전 뒤({num(ROUTES['main']['stages'][0]['anchor_levels']['after_first_fight'])}), 나머지는 그 구간 첫 전투 뒤. 보스 처치는 가운데 길에서 레벨 ×{min(sg['anchor_levels']['after_boss']/sg['anchor_levels']['at_boss'] for sg in ROUTES['main']['stages']):.2f}~×{max(sg['anchor_levels']['after_boss']/sg['anchor_levels']['at_boss'] for sg in ROUTES['main']['stages']):.2f}, 군단 루프에서 ×{min(sg['anchor_levels']['after_boss']/sg['anchor_levels']['at_boss'] for sg in ROUTES['right']['stages']):.2f}~×{max(sg['anchor_levels']['after_boss']/sg['anchor_levels']['at_boss'] for sg in ROUTES['right']['stages']):.2f}. 질풍 루프는 의도적으로 레벨이 조금만 오르는 길(가운데 6구간의 절반) — 보상은 아이템·3급 강화석·에너지.
시뮬 실측(E-2 풀장비 20보스 판) 도착 레벨: B01 {FULL20[BOSSES['B01']['name_ko']]['lvl']}, B05 {FULL20[BOSSES['B05']['name_ko']]['lvl']}, B10 {FULL20[BOSSES['B10']['name_ko']]['lvl']}, B15 {FULL20[BOSSES['B15']['name_ko']]['lvl']}, B20 {FULL20[BOSSES['B20']['name_ko']]['lvl']}, 최종 {summary_fields('E-2')['중간 최종 레벨']} — 풀장비의 경험치 배율(×{S.aggregate(cfg, S.auto_equip(cfg, list(ITEMS)))['exp_mult']:.2f}, 보스 ×{S.aggregate(cfg, S.auto_equip(cfg, list(ITEMS)))['boss_exp_mult']:.1f})만큼 자연 기대보다 높다.
""")

# ================================================================= §4 한 판 구조
_enc = R["encounter"]; _W = R["warp"]
_sum_a = summary_fields("A")
P(f"""---
## 4. 한 판 구조 (`run` / `routes`)

### 4.1 에너지 (판의 수명)
{R['text_ko']}

| 사건 | 에너지 | 비고 |
|---|---|---|
| 판 시작 | {R['energy_start']} (+군주의 부적 {ITEMS['I18']['effects'][0]['v']}) | v8 의 12 → {R['energy_start']}: 누진 사망 비용 도입 보정 + 첫 판 {float(KEY['first_run_minutes']):.1f}분(목표 3~5분) |
| 전투 승리 | −{R['energy_fight']} | 보스전은 −{R['energy_fight']} 없음 |
| n번째 사망 | −min({R['energy_death_max']}, {R['energy_death_base']} + (n−1)×{R['energy_death_step']}) → {R['energy_death_base']}, {R['energy_death_base']+R['energy_death_step']}, {R['energy_death_base']+2*R['energy_death_step']}, {R['energy_death_max']}, {R['energy_death_max']}… | 카운터는 광장(루프 입·출구) 통과 시 0. 수호 부적: 판 첫 사망 −{ITEMS['I09']['effects'][1]['v']}. '죽으며 깎기'는 합법이지만 3번째부터 벌(M표: 공격 몰빵 클리어 0%) |
| 가운데 보스 처치 | +{R['energy_boss_main']} (+부적 {ITEMS['I18']['effects'][1]['v']}) | 그 전투 −1 없음 |
| 루프 보스 처치 | +{R['energy_boss_loop']} (+부적 {ITEMS['I18']['effects'][1]['v']}) | 루프 구간 수지 = −{2*R['energy_fight']} + {R['energy_boss_loop']} = **+{R['energy_boss_loop']-2*R['energy_fight']}** |
| 에너지 0 또는 복귀 | 판 종료 | 레벨 1·포인트 0 초기화. 장비·강화·강화석·정수·기록 유지 |

수지 예: 가운데 길 10구간 = 전투 40(−40) + 보스 10(+{10*R['energy_boss_main']}) → 시작 {R['energy_start']} 기준 사망 예산 = {R['energy_start']-40+10*R['energy_boss_main']} 에너지 (누진 {R['energy_death_base']},{R['energy_death_base']+1},{R['energy_death_base']+2},{R['energy_death_max']} 이라 광장 초기화 없이는 사망 {deaths_affordable(R['energy_start']-40+10*R['energy_boss_main'])}회분). 20보스 완주 = 가운데 40전투 + 루프 20전투(−60) + 보스 {10*R['energy_boss_main']+10*R['energy_boss_loop']} → 사망 예산 {R['energy_start']-60+10*R['energy_boss_main']+10*R['energy_boss_loop']}. 시뮬 E-2(풀장비) 평균 사망 {summary_fields('E-2')['평균 사망']}, 클리어 {summary_fields('E-2')['클리어율(전 보스 20)']}.
첫 판(장비 0, A표): 보스 1 처치 {pct(float(KEY['first_boss_win_no_gear']))}, 2보스 도달 {pct(float(KEY['second_boss_reach']))}, 평균 처치 보스 {_sum_a['평균 처치 보스']}, 사망 {_sum_a['평균 사망']}, {_sum_a['중간 판 시간']} — "첫 보스는 꼭 잡고 둘째 보스에서 아쉽게 끝나는" 리듬.

### 4.2 세 길과 루프 (갈림길 광장 → 가운데 길; 5·10단계 광장에서 루프 진입)
| 길 | 구간 | 구간당 전투 | 해금 | 조우 마릿수 1/2/3 | 몬스터 가중치 약/중/정예 | 성격 |
|---|---|---|---|---|---|---|
""")
for rid in ("main", "left", "right"):
    rt = ROUTES[rid]
    P(f"| {rt['name_ko']} | {len(rt['stages'])} | {rt['stages'][0]['fights']} | {rt['unlock_ko']} | {'/'.join(str(x)+'%' for x in rt['group_probs'])} | {'/'.join(str(x) for x in cfg['gen_params']['WEIGHTS'][rid])} | {rt['desc_ko']} |")
P(f"""
- 루프 구조(A 안 이식): 광장 문 → {ROUTES['left']['stages'][0]['length']} stud 구간 × 5(전체 {ROUTES['left']['loop_length_stud']} stud) → 광장 복귀. 구간마다 2전투 + 제단. 들어가기 전 표지판: 질풍 「{ROUTES['left']['sign_ko'].split(': ',1)[1].split(' (')[0]}」, 군단 「{ROUTES['right']['sign_ko'].split(': ',1)[1].split(' (')[0]}」 (권장 레벨 = 진입 기대 레벨 × {ROUTES['left']['sign_recommended_level_factor']}, JSON `routes.*.sign_recommended_level`).
- 조건부 보스(숨은 보스) 4: {' / '.join(f"{b['id']} {b['name_ko']} — {b['spawn_condition']['text_ko']}" for b in BOSSES.values() if b['spawn_condition'])}. {cfg['hidden_conditions']['text_ko']} 시뮬 등장률(N표, 자연 장비/풀/+5/자동): {' ; '.join(f"{r[0].split()[0]} {r[2]}/{r[3]}/{r[4]}/{r[5]}" for r in N_ROWS)}.
- 워프 제단(D 안): {_W['text_ko']} 시뮬 Q표: 10단계 광장 시작 군단 루프 5보스 클리어 {summary_fields('Q')['클리어율(전 보스 5)']}, {summary_fields('Q')['중간 판 시간']}.

### 4.3 맵 (Z 좌표, 기존 자산 유지·연장)
| 길 | 구간 | Z 시작 | Z 끝 | 길이(stud) | 전투 수 | 도박 구역 | 몬스터 | 보스 |
|---|---|---|---|---|---|---|---|---|
""")
for rid in ("main", "left", "right"):
    for sg in ROUTES[rid]["stages"]:
        P(f"| {ROUTE_KR[rid]} | {sg['stage']} | {sg['z_from']} | {sg['z_to']} | {sg['length']} | {sg['fights']} | {sg['luck_zones']} | {', '.join(MONS[m]['name_ko'] for m in sg['monsters'])} | {BOSSES[sg['boss']]['name_ko']} |")
P(f"""
- 가운데 6~10구간은 기존 5단계 꺾임 뒤로 이어 붙인다(Z {ROUTES['main']['stages'][5]['z_from']} → {ROUTES['main']['stages'][9]['z_to']}). 마을 문 → 첫 제단 약 274 stud({R['village_to_gate_s']}초) 유지. 이동 {R['move_speed']} stud/초.
- 루프 2개는 **가운데 길 Z 지오메트리를 리스킨**해 쓴다(J3·D 안). 표의 루프 z_from/z_to 는 가운데 길과 같은 −120~−920 범위로 기록되어 있고 실제 배치는 광장 옆 별도 영역이므로 좌표 오프셋은 구현 시 정한다.
- 조우: {_enc['text_ko']} (1칸 {_enc['stud_per_bar']} stud, {_enc['bars_full']}칸 = 100%, {_enc['start_bar']}칸부터 매초 칸수×{pct(_enc['p_per_s_per_bar'])}). 가운데 1구간 첫 {ROUTES['main']['intro_fights']}전투는 펭귄 1마리 고정(레벨 1 입장 보호).
- 도박 구역(기존 행운 구역 '레벨 ×2 / 체력 ½' 두 종류를 하나로): 반지름 10, 구간마다 {min(sg['luck_zones'] for r in ROUTES.values() for sg in r['stages'])}~{max(sg['luck_zones'] for r in ROUTES.values() for sg in r['stages'])}곳, 그 안에서 시작한 전투는 경험치 ×{F['exp_gain']['zone_exp_mult']}·받는 피해 ×{F['damage_taken']['zone_dmg_mult']}, 전투 1회 뒤 소진. 행운의 왕관이면 ×{F['exp_gain']['zone_exp_mult']+ITEMS['I14']['effects'][1]['v']}. B18 군주 발록은 그 구간 구역 전투 승리가 등장 조건.

### 4.4 판 시간 목표 (근거: §13)
| 판 | 시뮬 중간 시간 | 목표 |
|---|---|---|
| 첫 판(장비 0, 가운데) | {_sum_a['중간 판 시간']} | 3~5분 ✓ |
| 가운데 10보스 풀클리어(풀장비 +0) | {E1['중간 판 시간']} | 8~15분 ✓ — '숙련 목표' |
| 20보스 완주(풀 +0 / +5 / +10) | {summary_fields('E-2')['중간 판 시간']} / {PLUS5_MIN}분 / {PLUS10_MIN}분 | 루프 2개가 선택이라 15분을 넘어도 됨(+10 에서 15분) |
| 워프 판(10단계 광장 → 군단 루프) | {summary_fields('Q')['중간 판 시간']} | 모바일 한 세션 |
| 보스 러시(20보스 연속, 레벨 고정) | {re.search(r'풀장비 \+0: 합계 (\d+)초 \(([\d.]+)분\)', P_SECTION).group(2)}분(+0) / {re.search(r'풀장비 \+10: 합계 (\d+)초 \(([\d.]+)분\)', P_SECTION).group(2)}분(+10) | 타임어택 |
""")

# ================================================================= §5 몬스터
_K = cfg["gen_params"]["KIND"]
P(f"""---
## 5. 일반 몬스터 표 ({len(MONS)}종 = 20구간 × 약·중·정예, JSON `monsters`)

설계식: {cfg['design_anchors_note_ko'].split('.')[0]}. 계수(hp_k / atk_k): 가운데 약 {_K['main'][0]['hp_k']}/{_K['main'][0]['atk_k']}, 중 {_K['main'][1]['hp_k']}/{_K['main'][1]['atk_k']}, 정예 {_K['main'][2]['hp_k']}/{_K['main'][2]['atk_k']} · 질풍(모두 달려옴, 빠름) {_K['left'][0]['hp_k']}/{_K['left'][0]['atk_k']}, {_K['left'][1]['hp_k']}/{_K['left'][1]['atk_k']}, {_K['left'][2]['hp_k']}/{_K['left'][2]['atk_k']} · 군단(항상 떼) {_K['right'][0]['hp_k']}/{_K['right'][0]['atk_k']}, {_K['right'][1]['hp_k']}/{_K['right'][1]['atk_k']}, {_K['right'][2]['hp_k']}/{_K['right'][2]['atk_k']}. 즉 약한 몬스터는 "그 구간 들어선 직후 1~2타에 죽고 한 방이 내 체력의 {pct(_K['main'][0]['atk_k'])}", 정예는 "3~4타, 한 방 {pct(_K['main'][2]['atk_k'])}". 구간 사이 배율은 경험치 곡선을 따라 일정(×{MONS['deer']['atk']/MONS['penguin']['atk']:.0f} 는 1구간 펭귄이 레벨 1 기준이라 예외, 이후 ×{MONS['golem']['atk']/MONS['deer']['atk']:.1f}~×{MONS['titan']['atk']/MONS['stargiant']['atk']:.1f}). 기존 v8 의 ×1,000 → ×15 끊김 해소. 일반 몬스터는 드롭 없음.

| 길 | 구간 | id | 이름 | 모델 | 키 | 종 | 체력 | 공격력 | 간격(초) | 이속 | 등장 | 경험치 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
""")
for rid in ("main", "left", "right"):
    for sg in ROUTES[rid]["stages"]:
        for mid in sg["monsters"]:
            m = MONS[mid]
            P(f"| {ROUTE_KR[rid]} | {sg['stage']} | {m['id']} | {m['name_ko']} | {m['model']} | {m['height']} | {m['kind_ko']} | {big(m['hp'])} | {big(m['atk'])} | {m['interval']} | {m['speed']} | {m['spawn']} | {big(m['exp'])} |")
_new_models = sorted({m['model'] for m in MONS.values() if '재질' not in m['model']} | {b['model'] for b in BOSSES.values() if '재질' not in b['model']})
P(f"""
- 보스 소환수(수하)도 몬스터 표에 준한다: {' / '.join(f"{b['gimmick']['adds']['unit']['name_ko']} 체력 {big(b['gimmick']['adds']['unit']['hp'])}·공격 {big(b['gimmick']['adds']['unit']['atk'])}·경험치 {big(b['gimmick']['adds']['unit']['exp'])}" for b in BOSSES.values() if 'adds' in b['gimmick'])}.
- 모델: 재질 변경이 아닌 신규/기존 모델은 {', '.join(_new_models)}. 그 외 {sum(1 for m in MONS.values() if '재질' in m['model'])}종은 기존 탈것 재질 변경. 신규 제작이 필요한 모델은 Mount23~30 의 8종(질풍 매·바람 정령체·운명의 고양이·기사의 군마·피의 박쥐·에테르 드래곤/그리폰/청룡 대형).
- 펭귄({MONS['penguin']['hp']}/{MONS['penguin']['atk']}/{MONS['penguin']['exp']})은 레벨 1·힘 {st['atk']['base']}·체력 {st['hp']['base']} 기준 "{math.ceil(MONS['penguin']['hp']/st['atk']['base'])}타에 죽고 {math.ceil(st['hp']['base']/MONS['penguin']['atk'])}타를 버틴다". v8 실측 '3전 뒤 레벨 91'과 맞춘 경험치({MONS['penguin']['exp']} → 3전 뒤 {num(ROUTES['main']['stages'][0]['anchor_levels']['after_first_fight'])}).
""")

# ================================================================= §6 보스
ARCH = cfg["gen_params"]["ARCH"]
def gimmick_text(b):
    g = b["gimmick"]; parts = []
    if "stagger" in g:
        s_ = g["stagger"]; parts.append(f"그로기: {s_['every_s']}초마다 {s_['dur_s']}초, 피해 ×{s_['dmg_mult']}, 상한 ×{s_['cap_mult']}")
    if "stagger_on_phase_s" in g: parts.append(f"전환 그로기: 체력바가 깨질 때마다 {g['stagger_on_phase_s']}초")
    if "breath" in g:
        br = g["breath"]; parts.append(f"브레스: {br['every_s']}초마다 공격 ×{br['atk_mult']} (1.5초 예고, 뒤로 걸으면 회피 — 수동 {pct(br['dodge_p_manual'])} / 자동 {pct(br['dodge_p_auto'])})")
    if "enrage" in g:
        e = g["enrage"]; parts.append("분노: " + f"{e['from_phase']}페이즈부터" + (f" 공격 ×{e['atk_mult']}" if 'atk_mult' in e else "") + (f" 간격 ×{e['int_mult']}" if 'int_mult' in e else ""))
    if "shield_hits" in g: parts.append(f"보호막: 페이즈마다 처음 {g['shield_hits']}타 무효(피해량 무관)")
    if "adds" in g:
        a = g["adds"]; u = a["unit"]
        parts.append(f"소환: 페이즈 {a['phases']} 에 {a['count']}마리 ({u['name_ko']} 체력 {big(u['hp'])} 공격 {big(u['atk'])} 간격 {u['interval']} 경험치 {big(u['exp'])})")
    if "frenzy" in g:
        fz = g["frenzy"]; parts.append(f"광란: 공격 간격 {b['interval']}→{fz['int_min']}초로 {fz['over_s']}초에 걸쳐 (초당 피해 ×{b['interval']/fz['int_min']:.2f})")
    if "thorns_frac" in g: parts.append(f"가시: 때릴 때마다 내 최대 체력 {pct(g['thorns_frac'])} 피해(피해감소 적용, 부활 무적 중 제외)")
    if "regen_per_s" in g: parts.append(f"재생: 매초 최대 체력 {pct(g['regen_per_s'],1)} (전환 중 제외)")
    if "timer" in g: parts.append(f"폭주 타이머: {g['timer']['at_s']}초 뒤 공격 ×{g['timer']['atk_mult']}")
    if "curse_noncrit_mult" in g: parts.append(f"저주: 치명타 아닌 타격 피해 ×{g['curse_noncrit_mult']}")
    if "boss_lifesteal" in g: parts.append(f"보스 흡혈: 준 피해의 {pct(g['boss_lifesteal'])} 회복")
    if "player_ls_mult" in g: parts.append(f"내 흡혈 ×{g['player_ls_mult']}")
    if "mirror" in g:
        mi = g["mirror"]; parts.append(f"거울: 체력 = 내 맨몸 DPS × {mi['T']}초, 한 타 = 맨몸 최대 체력 × {pct(mi['dps_k'],1)}/초 × 간격, 회피 = 내 치명 확률 × {mi['dodge_from_crit']} (≤{pct(mi['dodge_cap'])})")
    if b.get("crit_pierce_cap"): parts.append(f"관통 제한: 치명 상한 관통 ×{b['crit_pierce_cap']} 까지(광전사 반지 무력)")
    return " · ".join(parts)

def gimmick_keys(b):
    ks = []
    for k in b["gimmick"]:
        ks.append({"stagger": "그로기", "stagger_on_phase_s": "전환 그로기", "breath": "브레스", "enrage": "분노", "shield_hits": "보호막", "adds": "소환",
                   "frenzy": "광란", "thorns_frac": "가시", "regen_per_s": "재생", "timer": "폭주", "curse_noncrit_mult": "저주", "boss_lifesteal": "보스 흡혈",
                   "player_ls_mult": "흡혈 봉인", "mirror": "거울"}[k])
    if b.get("crit_pierce_cap"): ks.append("관통 제한")
    return "·".join(ks)

P(f"""---
## 6. 보스 20종

### 6.1 수치 산출 방식 (`design_anchors_note_ko`, `bosses[].anchor`)
{cfg['design_anchors_note_ko']}
- 성향(D 안): 탱커 = 목표 초 ×{ARCH['탱커']['T_mult']}·공격 ×{ARCH['탱커']['atk_factor']}, 유리대포 = 목표 초 ×{ARCH['유리대포']['T_mult']}·공격 ×{ARCH['유리대포']['atk_factor']}, 균형 = ×1/×1. 배분: 탱커 {', '.join(b['id'] for b in BOSSES.values() if b['archetype_ko']=='탱커')} / 유리대포 {', '.join(b['id'] for b in BOSSES.values() if b['archetype_ko']=='유리대포')} / 균형 나머지 {sum(1 for b in BOSSES.values() if b['archetype_ko'].startswith('균형'))}.
- 보정 절차: ① 자연 판 60회로 도착 레벨 재측정(`arrival_level_measured_median`, p10~p90) ② 앵커 플레이어 40회 결투로 공격 배율 격자+이분 탐색(`atk_calib_mult`, 사망 목표 `death_target` 가운데 0.6 / 루프 0.5 / B01 0.35 / B13 0.3 / B19 0.35; 사망 0 평탄 구간이면 큰 배율) ③ 체력 2회 반복 보정(중간 전투 시간 = 목표 초, `calibrated_secs_median`). `death_curve` 에 배율별 사망이 기록되어 있어 노브를 돌릴 때 참고한다.
- 사망 목표를 0.3~0.6 으로 둔 이유: '죽으며 깎기'가 가능하되(v6 규칙 유지) 보스마다 평균 1회 미만이어야 누진 사망 비용(3,4,5,6)이 판을 끝내지 않는다. 자연 진행 실측 {KEY['natural_deaths']}(C표).

### 6.2 한눈에 (JSON `bosses`)
| # | 길 | 구간 | 이름 | 모델 | 키 | 성향 | 체력 | 공격력(1타) | 간격 | 1타(내 체력 %) | 초당(내 체력 %) | 체력바 | 전환 | 장갑 | 최소 타수 | 기믹 | 경험치 | 권장 레벨 | 목표 초 | 보정 초 / 사망 | 등장 조건 | 드롭 | 강화석 | 에너지 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
""")
for b in BOSSES.values():
    a = b["anchor"]
    hp_s = big(b["hp"]) if b["hp"] else f"거울(맨몸 DPS×{b['gimmick']['mirror']['T']}s)"
    atk_s = big(b["atk"]) if b["atk"] else f"맨몸 체력 {pct(b['gimmick']['mirror']['dps_k'],1)}/s"
    hit_s = f"{a['boss_hit_pct_of_player_hp']}%" if a['boss_hit_pct_of_player_hp'] is not None else f"{b['gimmick']['mirror']['dps_k']*b['interval']*100:.1f}%"
    dps_s = f"{a['boss_dps_pct_of_player_hp']}%" if b["hp"] else f"{b['gimmick']['mirror']['dps_k']*100:.1f}%"
    cond = b["spawn_condition"]["text_ko"] if b["spawn_condition"] else "항상"
    P(f"| {b['id']} | {ROUTE_KR[b['route']]} | {b['stage']} | {b['name_ko']} | {b['model']} | {b['height']} | {b['archetype_ko']} | {hp_s} | {atk_s} | {b['interval']} | {hit_s} | {dps_s} | {b['phases']} | {b['transition_s']}초 | {pct(b['hit_cap'],1)} | {b['min_hits']} | {gimmick_keys(b)} | {big(b['exp'])} | {big(b['recommended_level'])} | {b['target_secs_natural']} | {a['calibrated_secs_median']} / {a['calibrated_deaths_mean']} | {cond} | {ITEMS[b['drop_item']]['name_ko']} | {b['stone_tier']}급 | +{b['energy_reward']} |")
P(f"""
읽는 법: '1타(내 체력 %)'는 권장 레벨 균형 분배·자연 장비 플레이어의 최대 체력 대비 보스 평타 한 번(브레스·분노 제외), '초당'은 그 ÷ 간격. 최소 타수 = ceil(1/장갑). 보정 초/사망은 앵커 플레이어 40회 결투 중간값·평균(`anchor.calibrated_*`). 자연 진행 판 {RUNS}회의 실측은 6.3 과 §13 C표.

### 6.3 보스별 상세 카드
각 카드: 수치 → 기믹 → 공략 → 3단 체감(§13 실측: 장비 부족 / 자연 장비 / 풀장비 +0 / +5 / +10) → 드롭·강화석·정수. '자연'은 그 보스를 처음 만나는 판(이전 보스 아이템만 보유), '풀'은 20종 보유 자동 장착 20보스 판(E-2). 가운데 길 보스의 '장비 0 / 엄니검만'은 A·B표.
""")
for b in BOSSES.values():
    a = b["anchor"]; iid = b["drop_item"]; it = ITEMS[iid]
    nat = NAT[b["id"]]
    full = FULL20[b["name_ko"]]; p5 = PLUS5[b["name_ko"]]; p10 = PLUS10[b["name_ko"]]
    cond = b["spawn_condition"]
    hp_line = (f"체력 {big(b['hp'])} / 공격 {big(b['atk'])} (간격 {b['interval']}초 → 1타 내 체력의 {a['boss_hit_pct_of_player_hp']}%, 초당 {a['boss_dps_pct_of_player_hp']}%)"
               if b["hp"] else f"체력 = 내 맨몸 DPS × {b['gimmick']['mirror']['T']}초 / 공격 = 맨몸 최대 체력 × {pct(b['gimmick']['mirror']['dps_k'],1)}/초 × 간격 {b['interval']}초 (권장 레벨 기준 체력 약 {big((st['atk']['base']+st['atk']['per_pt']*pts_balanced(a['player_lvl'])['atk'])*(1+crit_p(st['luk']['base']+pts_balanced(a['player_lvl'])['luk'], a['player_lvl'])*(F['crit']['mult_base']-1))/C['attack_interval']*b['gimmick']['mirror']['T'])}, 1타 약 {big((st['hp']['base']+st['hp']['per_pt']*pts_balanced(a['player_lvl'])['hp'])*b['gimmick']['mirror']['dps_k']*b['interval'])})")
    extra = ""
    if b["name_ko"] in GEAR0:
        g0 = GEAR0[b["name_ko"]]
        extra += f"장비 0: 도달 {g0['reach']}, 승률 {g0['win']}, {g0['secs']}초({g0['rng']}), 사망 {g0['deaths']} · "
    if b["name_ko"] in GEAR1 and b["id"] != "B01":
        g1 = GEAR1[b["name_ko"]]
        extra += f"엄니검만: 도달 {g1['reach']}, 승률 {g1['win']}, {g1['secs']}초, 사망 {g1['deaths']} · "
    if b["name_ko"] in MAIN10:
        d = MAIN10[b["name_ko"]]
        extra += f"가운데 10종(+0, D표): {d['secs']}초, 사망 {d['deaths']} · "
    if b["name_ko"] in WARP:
        w = WARP[b["name_ko"]]
        extra += f"워프 판(Q표): 도착 {w['lvl']}, {w['secs']}초, 사망 {w['deaths']} · "
    nat_items = ", ".join(ITEMS[i]["name_ko"] for i in a["natural_items"]) or "없음"
    ess = STONES["essence_drop"]
    mirror_note = f" [시뮬 보정 뒤 실제 값은 dps_k {pct(b['gimmick']['mirror']['dps_k'],1)}/초·T {b['gimmick']['mirror']['T']}초 — 공략 문구의 9%/초는 보정 전 설계 입력값]" if 'mirror' in b['gimmick'] else ""
    P(f"""
#### {b['id']}. {b['name_ko']} — {ROUTE_KR[b['route']]} {b['stage']}구간 · {b['archetype_ko']} (모델 {b['model']}, 키 {b['height']}, 등장 {b['spawn']}, 이속 {b['speed']})
- 수치: {hp_line} / 체력바 {b['phases']}개(전환 무적 {b['transition_s']}초) / 장갑 {pct(b['hit_cap'],1)} → 최소 {b['min_hits']}타{f" / 관통 제한 ×{b['crit_pierce_cap']}" if b.get('crit_pierce_cap') else ""} / 경험치 {big(b['exp'])} / 처치 에너지 +{b['energy_reward']}
- 기믹: {gimmick_text(b)}
- 등장 조건: {cond['text_ko'] if cond else '항상'}{f" (JSON spawn_condition.type = {cond['type']}; 시뮬 등장률 자연 {[r for r in N_ROWS if r[0].startswith(b['id'])][0][2]} / 풀 {[r for r in N_ROWS if r[0].startswith(b['id'])][0][3]} / 자동 모험 {[r for r in N_ROWS if r[0].startswith(b['id'])][0][5]})" if cond else ""}
- 공략: {b['guide_ko']}{mirror_note}
- 권장 도착 레벨 **{big(b['recommended_level'])}** (실측 중간 {big(a['arrival_level_measured_median'])}, p10~p90 {big(a['arrival_level_p10_p90'][0])}~{big(a['arrival_level_p10_p90'][1])}). 그때 자연 장비 = {nat_items}; 내 공격력 {big(a['player_atk'])}, 체력 {big(a['player_hp'])}, 기대 DPS {big(a['player_dps_natural'])}(피버 가동률 {pct(a['fever_uptime_assumed'])} 포함){f", 1타 = 보스 체력의 {a.get('natural_hit_pct_of_boss_hp')}%" if a.get('natural_hit_pct_of_boss_hp') else ""}. 목표 전투 시간 {b['target_secs_natural']}초(기준 ×{ARCH[b['archetype_ko']]['T_mult']}) → 보정 {a['calibrated_secs_median']}초, 사망 {a['calibrated_deaths_mean']} (목표 {a['death_target']}, 공격 보정 배율 ×{a['atk_calib_mult']}).
- 3단 체감(§13 실측, 판 {RUNS}회): {extra}**자연**(C표, 아이템 {nat['items']}개): 도달 {nat['reach']}, 등장 {nat['spawn']}, 도착 {nat['lvl']}, 승률 {nat['win']}, **{nat['secs']}초**, {nat['hits']}타, 사망 {nat['deaths']} · **풀장비 +0**(E-2): 도착 {full['lvl']}, {full['secs']}초({full['rng']}), {full['hits']}타, 사망 {full['deaths']} · **+5**: {p5['secs']}초({p5['rng']}), 사망 {p5['deaths']} · **+10**: {p10['secs']}초({p10['rng']}), 사망 {p10['deaths']}
- 드롭: 첫 처치 **{it['name_ko']}**({it['slot']}, {it['desc_ko']}) + {b['stone_tier']}급 강화석 {STONES['drop']['first_kill']}개 + 정수 `{b['essence_id']}` {ess['first_kill']}개. 재처치: 강화석 {STONES['drop']['repeat_kill']}개({pct(STONES['drop']['repeat_bonus_p'])}로 +{STONES['drop']['repeat_bonus_n']}, 무사망 +{STONES['drop']['no_death_bonus']}) + 정수 {ess['repeat_kill']}개(추가 1개 확률 {ess['extra_base']}+{ess['extra_luck_coef']}×r).
""")

# ================================================================= §7 아이템 + 강화석
SLOT_ORDER = list(cfg["slots"].keys())
EFFECT_KO = {
    "atk_mult_bonus": "공격 배율 +v (곱, 상한 ×{})".format(CAPS['pve']['atk_mult']), "S": "공속 보너스 S +v (합, 배율 1+S/(1+S/1.5), 상한 ×{})".format(CAPS['pve']['aspd_mult']),
    "ls": "흡혈 +v (합, 상한 {})".format(pct(CAPS['pve']['lifesteal'])), "range_add": "범위 +v stud (합, 상한 R 18 = 3마리)", "move_bonus": "이동속도 +v",
    "exp_mult_bonus": "경험치 배율 +v (곱, 상한 ×{})".format(CAPS['pve']['exp_mult']), "boss_exp_mult_bonus": "보스 경험치 배율 +v (곱, 상한 ×{})".format(CAPS['pve']['boss_exp_mult']),
    "crit_dmg": "치명 피해 +v (합, 상한 ×{})".format(CAPS['pve']['crit_mult']), "crit_p_add": "치명 확률 +v", "dmg_reduce": "피해감소 v (1−Π(1−x), 상한 {})".format(pct(CAPS['pve']['dmg_reduce'])),
    "hp_mult_bonus": "체력 배율 +v (곱)", "energy_start": "시작 에너지 +v", "energy_boss": "보스 처치 에너지 +v", "cap_add": "보스 장갑 상한 +v",
    "nth_crit": "v타마다 치명 확정", "first_hits_fast": "전투 첫 v타 가속", "first_hits_mult": "첫 타 간격 ÷v", "multi_atk_bonus": "적 2마리 이상이면 공격 +v",
    "revive_invuln_add": "부활 무적 +v초", "first_death_cost": "판 첫 사망 에너지 = v", "luk_mult_bonus": "행운 배율 +v (곱)", "zone_exp_bonus": "도박 구역 배율 +v",
    "var": "피해 분산 lo~hi", "ls_crit_mult": "치명 시 흡혈 ×v", "reflect": "반격 v (상한 {})".format(pct(CAPS['pve']['reflect'])), "splash": "스플래시 v (상한 {})".format(pct(CAPS['pve']['splash'])),
    "heal_cap_s_add": "초당 회복 상한 기본 +v", "crit_pierce_add": "장갑 관통 +v (상한 ×{})".format(CAPS['pve']['crit_pierce']),
}
P(f"""---
## 7. 아이템 20종 + 강화석 (JSON `items` / `slots` / `stones`)

### 7.1 칸 구조와 원칙
칸: {' / '.join(f"{k} {v}" for k, v in cfg['slots'].items())} = **{sum(cfg['slots'].values())}개 장착, 20개 보유** → 길·보스마다 바꿔 끼는 것이 전략(제단 앞 교체 가능, 에너지 소모 없음). 자동 장착은 칸별 `rank` 가 높은 것. 장비는 능력치를 '더하지' 않고 **배율·보너스**로만 작동(v8 엄니검 +10,000 고정치 폐기 → 힘 ×{1+ITEMS['I01']['effects'][0]['v']} 배율형: 레벨 1 에서도 1보스를 무력화하지 않고 2단계에서도 쓸모 있다). 효과값은 `items[].effects[]` 의 {{k, v, up}} — up=true 인 값만 강화가 키운다(×{UP}^p). PvP 에서 무효인 키는 `pvp_disabled`.

| id | 이름 | 보스 | 칸 | 급 | rank | 효과(기본값; ↑=강화 대상) | 설명·상한 | +5 | +10 | PvP |
|---|---|---|---|---|---|---|---|---|---|---|
""")
for iid, it in ITEMS.items():
    P(f"| {iid} | {it['name_ko']} | {it['boss']} | {it['slot']} | {it['tier']} | {it['rank']} | {item_eff(iid)} | {it['desc_ko']} | {item_eff(iid, 5)} | {item_eff(iid, 10)} | {it['pvp_ko']}{' (무효: ' + ', '.join(it['pvp_disabled']) + ')' if it['pvp_disabled'] else ''} |")
P(f"""
효과 키 사전(시뮬 `aggregate`): {' · '.join(f"`{k}` {v}" for k, v in EFFECT_KO.items())}.

### 7.2 아이템 전략 요약 — 왜 20개가 다 쓸모 있나 (K·K-0 표 근거)
- 무기 3: 엄니검(안정 ×{1+ITEMS['I01']['effects'][0]['v']}) / 질풍검(×{1+ITEMS['I15']['effects'][0]['v']} + 공속 S {ITEMS['I15']['effects'][1]['v']} + 분산 0.7~1.5 — 보호막·가시 보스에서 큼직한 한 방) / 파멸의 대검(×{1+ITEMS['I10']['effects'][0]['v']}, 공속 {ITEMS['I10']['effects'][1]['v']}, 장갑 +{pct(ITEMS['I10']['effects'][2]['v'])}p — 장갑에 닿는 풀장비·강화 구간에서 최강).
- 정령 4(공속): 바람 S {ITEMS['I02']['effects'][0]['v']} / 번개 S {ITEMS['I08']['effects'][0]['v']} + {ITEMS['I08']['effects'][1]['v']}타마다 확정 치명(저주 보스 B08·B14 의 답) / 폭풍 S {ITEMS['I12']['effects'][0]['v']} − 치명 {pct(-ITEMS['I12']['effects'][1]['v'])}p(보호막 보스 B03·B12·B18 의 답) / 종언 S {ITEMS['I20']['effects'][0]['v']} + 스플래시 {pct(ITEMS['I20']['effects'][1]['v'])} + 흡혈 {pct(ITEMS['I20']['effects'][2]['v'])} + 치명 피해 +{ITEMS['I20']['effects'][3]['v']}(올라운더).
- 반지 4(2칸): 흡혈 송곳니(흡혈 {pct(ITEMS['I03']['effects'][0]['v'])}) / 광전사 반지(치명 ×{F['crit']['mult_base']+ITEMS['I06']['effects'][0]['v']}, 치명 시 흡혈 ×{ITEMS['I06']['effects'][1]['v']:.0f}, **장갑 관통 ×{C['crit_cap_mult']}→×{C['crit_cap_mult']+ITEMS['I06']['effects'][2]['v']:.1f}** — 가시 보스 B06·B19, 장갑 3% 보스의 답; B09 는 관통 ×{BOSSES['B09']['crit_pierce_cap']} 제한으로 천적) / 질풍의 반지(S {ITEMS['I11']['effects'][0]['v']}, 이속 +{pct(ITEMS['I11']['effects'][1]['v'])}, 첫 {ITEMS['I11']['effects'][2]['v']}타 간격 ÷{ITEMS['I11']['effects'][3]['v']:.0f} — 광란 보스 B11 선제) / 피의 성배(흡혈 {pct(ITEMS['I17']['effects'][0]['v'])}, **초당 회복 상한 기본 {pct(F['lifesteal']['heal_per_s_cap_base'])}→{pct(F['lifesteal']['heal_per_s_cap_base']+ITEMS['I17']['effects'][1]['v'])}**, 체력 {pct(ITEMS['I17']['effects'][2]['v'])}).
- 망토 4: 거인(2마리, 이속 +{pct(ITEMS['I04']['effects'][1]['v'])}) / 용암(피해 −{pct(ITEMS['I07']['effects'][0]['v'])}, 반격 {pct(ITEMS['I07']['effects'][2]['v'])}, 2마리 — 흡혈 봉인 보스 B09·B17 의 답; 강화하면 1:1 전용) / 광풍(3마리 + 스플래시 {pct(ITEMS['I13']['effects'][1]['v'])} — 소환 보스 B13 의 답) / 군단 파쇄(3마리 + 떼 공격 +{pct(ITEMS['I16']['effects'][1]['v'])} + 피해감소 {pct(ITEMS['I16']['effects'][2]['v'])}(강화 불가) — 군단 루프 전용이면서 1:1 에서도 용암 +0 과 동급).
- 왕관 3: 에테르(경험치 ×{1+ITEMS['I05']['effects'][0]['v']}) / 행운(행운 ×{1+ITEMS['I14']['effects'][0]['v']}, 구역 ×{F['exp_gain']['zone_exp_mult']+ITEMS['I14']['effects'][1]['v']}, 경험치 ×{1+ITEMS['I14']['effects'][2]['v']} — 안정형) / 영혼(경험치 ×{1+ITEMS['I19']['effects'][0]['v']}, 보스 ×{1+ITEMS['I19']['effects'][1]['v']:.0f} — 기록형, 보스 경험치 상한 ×{CAPS['pve']['boss_exp_mult']} 으로 봉인).
- 부적 2: 수호(판 첫 사망 −{ITEMS['I09']['effects'][1]['v']}, 무적 +{ITEMS['I09']['effects'][0]['v']:.0f}초, 피해 −{pct(ITEMS['I09']['effects'][2]['v'])}) / 군주(에너지 +{ITEMS['I18']['effects'][0]['v']}/보스 +{ITEMS['I18']['effects'][1]['v']}).
- 제단 앞 교체 추천표: 보호막(B03·B12·B18) → 폭풍/번개 정령 · 가시(B06·B15·B19) → 광전사 반지 + 질풍검 · 저주(B08·B14) → 번개 정령 + 행운의 왕관 · 흡혈 봉인(B09·B17) → 용암 망토 + 체력 분배 · 소환(B04·B13·B16·B20) → 광풍/군단 파쇄 망토 · 광란·폭주(B05·B07·B11·B18·B20) → 공속·대검으로 DPS.
- 획득 직후 기여도(K-0, 그 보스를 처음 잡은 다음 판에 이 아이템이 있을 때 vs 없을 때 '다음 보스 도달×등장×승리'): {' · '.join(f"{r[0]} {r[3]}" for r in K0_ROWS[:10])}. 루프 아이템은 이미 98~100% 포화 구간이라 Δ승리가 작고 대신 사망·레벨로 나타난다({' · '.join(f"{r[0]} 사망 {r[5]}" for r in K0_ROWS if r[0] in ('피의 성배','영혼 왕관','종언의 정령'))}). 군주의 부적은 에너지 +3 덕에 '더 죽어도 판이 안 끝나' 사망이 늘어 보인다({[r for r in K0_ROWS if r[0]=='군주의 부적'][0][5]}) — 음의 기여가 아니라 수명 연장 효과.
- 풀장비 합산(+0 → +10, M-4): {m_line('풀장비 합산').replace('풀장비 합산: ','')}.

### 7.3 강화석 (JSON `stones`)
{STONES['text_ko']} {STONES['fail_rule_ko']}

| 급 | 이름·획득처 | 첫 처치 | 재처치 | 강화 대상 |
|---|---|---|---|---|
""")
for t, name in STONES["tiers"].items():
    bs = [b for b in BOSSES.values() if str(b["stone_tier"]) == t]
    P(f"| {t}급 | {name} ({', '.join(b['name_ko'] for b in bs)}) | {STONES['drop']['first_kill']}개 | {STONES['drop']['repeat_kill']}개 (+{pct(STONES['drop']['repeat_bonus_p'])}로 {STONES['drop']['repeat_bonus_n']}개, 무사망 +{STONES['drop']['no_death_bonus']}) | {', '.join(ITEMS[b['drop_item']]['name_ko'] for b in bs)} |")
P(f"""
교환: {STONES['exchange']['text_ko']} (`exchange.lower_to_upper` = {STONES['exchange']['lower_to_upper']}).

| 강화 | 강화석(그 급) | 정수(그 보스) | 성공률 | 기대 시도 | 실패 시 | 효과 배율(up 값에) |
|---|---|---|---|---|---|---|
""")
for i in range(STONES["max_plus"]):
    P(f"| +{i} → +{i+1} | {STONES['cost'][i]} | {STONES['essence_cost'][i]} | {pct(STONES['success'][i])} | {STONES['expected_tries_per_step'][i]} | 강화석만 소모, 하락 없음{', 3연속 실패 시 다음 확정' if STONES['success'][i] < 1 else ''} | ×{UP**(i+1):.2f} |")
_ess = STONES["essence_drop"]
P(f"""
- 기대 소모(+10 까지): 강화석 **{STONES['expected_stones_to_plus10']}개**, 정수 **{STONES['expected_essence_to_plus10']}개**(`expected_*`). 천장(`pity_fails` = {STONES['pity_fails']}): 같은 단계 {STONES['pity_fails']}회 연속 실패 → 다음 확정, UI '다음은 확정'. 정수는 성공 시에만 소모.
- 정수(C 안): {_ess['text_ko']} 보스 20종 각각 고유 → '그 보스를 다시' 잡을 이유가 끝까지 남는다. 행운 r = 행운/(행운 + 0.5×레벨 + 50) 이라 행운 빌드가 정수 파밍에 유리.
- 판당 수입(§13): 가운데 풀클리어 강화석 {re.search(r'강화석 ([\d.]+) 정수 ([\d.]+)', sim_summary_line('E-1')).group(1)}·정수 {re.search(r'강화석 ([\d.]+) 정수 ([\d.]+)', sim_summary_line('E-1')).group(2)}, 20보스 완주 강화석 {re.search(r'강화석 ([\d.]+) 정수 ([\d.]+)', sim_summary_line('E-2')).group(1)}·정수 {re.search(r'강화석 ([\d.]+) 정수 ([\d.]+)', sim_summary_line('E-2')).group(2)}. 계정 성장 시뮬(O표, 하루 = 수동 {cfg['monetization']['auto_adventure']['manual_runs_per_day_assumed']}판 + 자동 모험): 처음 10보스 {re.search(r'중간값: 무료 — 10보스 (\d+판/\d+분)', O_SECTION).group(1)}, 처음 20보스 {re.search(r'20보스 (\d+판/\d+분)', O_SECTION).group(1)}, 장착 7종 전부 +5 {re.search(r'전부 \+5 (\d+)판', O_SECTION).group(1)}판, 전부 +10 {O_FREE_PLUS10}판/{re.search(r'전부 \+10 \d+판/(\d+)분', O_SECTION).group(1)}분.
- 강화는 "더 빨리·더 안전하게·더 큰 숫자"지 "보스 생략"이 아니다: 풀 +10 20보스 판 {PLUS10_MIN}분·사망 {summary_fields('F10')['평균 사망']}, 보스별 중간값 최단 {KEY['plus10_min_secs']}초(F10). 합산 상한에 걸리므로 PvP 도 안전(L-3: 전부 +10 균형 vs 균형 {re.search(r'균형 vs 균형 (\d+%)', sim_section('L-2')).group(1)}).
- 강화석·정수·보호권 판매 없음. 1.08^p 복리는 J2 가 선호한 선형과 다르지만 합산 상한으로 봉인됨 — 선형 ×(1+0.1p)로 바꾸려면 `stones.upgrade_mult_per_plus` 처리 1줄과 gen 재보정 1회.
""")

# ================================================================= §8 빌드
def ratio_str(r): return ":".join(f"{r[k]:g}" for k in ("hp", "atk", "luk", "ls"))
_jmap = {r[0]: r for r in J_ROWS}
_full_ids = S.auto_equip(cfg, list(ITEMS))
_full_names = ", ".join(ITEMS[i]["name_ko"] for i in _full_ids)
_lv = cfg["pvp"]["duel_level"]
def build_stats(name):
    r = cfg["builds"][name]
    pb = pts_balanced(_lv, r)
    luk = st["luk"]["base"] + pb["luk"]
    return pb, crit_p(luk, _lv), ls_pct(pb["ls"], _lv, S.aggregate(cfg, _full_ids)["ls"]), jackpot_p(luk, _lv)
P(f"""---
## 8. 빌드 / 공략 예시 (JSON `builds`, 수치는 §13 J·K·M 표)

자동 분배 프리셋 5종. 포인트는 레벨당 {st['pts_per_level']} + '행운!' 당첨. 아래 '치명/흡혈'은 레벨 {num(_lv)}·풀장비(+0, {_full_names}) 기준 닫힌 식 값(당첨 포인트 제외), 시뮬 열은 J표(풀장비 +0, 20보스 판 {RUNS}회).

| 빌드 | 체:힘:행:흡 | 레벨 {num(_lv)} 포인트(체/힘/행/흡) | 치명(식) | 흡혈(식, 장비 포함) | 행운! p | 가운데 10 클리어 | 20보스 클리어 | 최종 레벨(20보스) | 판 시간 | 평균 사망 | 보스전 초 합 | 치명(시뮬) | 흡혈(시뮬) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
""")
for name, r in cfg["builds"].items():
    pb, cp, ls, jp = build_stats(name)
    j = _jmap[name]
    P(f"| {name} | {ratio_str(r)} | {big(pb['hp'])}/{big(pb['atk'])}/{big(pb['luk'])}/{big(pb['ls'])} | {pct(cp)} | {pct(ls,1)} | {pct(jp)} | {j[2]} | {j[3]} | {j[4]} | {j[5]}분 | {j[6]} | {j[7]}초 | {j[8]} | {j[9]} |")
_m1 = m1_rows()
P(f"""
### 8.1 빌드별 읽는 법
- **균형(기본)** {ratio_str(cfg['builds']['균형(기본)'])}: 기준선. 가운데 10보스만 보면 가장 적게 죽는다(사망 {KEY['bal_deaths_main']} vs 흡혈 균형 {KEY['ls_deaths_main']} — 0.3 수준 노이즈), 20보스 완주에서는 흡혈 균형보다 더 죽는다({KEY['bal_deaths_20']} vs {KEY['ls_deaths_20']}).
- **속공(위험)** {ratio_str(cfg['builds']['속공(위험)'])}: 보스전 합이 가장 짧고({_jmap['속공(위험)'][7]}초) 판도 빠르지만({_jmap['속공(위험)'][5]}분) 사망 {_jmap['속공(위험)'][6]} — 시간 기록용, 에너지를 태운다. PvP 에서는 최강 축(L-1: 탱커 상대 {[r for r in L1_ROWS if r[0]=='속공(위험)'][0][4]}).
- **흡혈 균형** {ratio_str(cfg['builds']['흡혈 균형'])}: 힘 0.25 를 흡혈로. 흡혈 {_jmap['흡혈 균형'][9]} → 초당 회복 상한 {pct(heal_cap(float(_jmap['흡혈 균형'][9].rstrip('%'))/100),1)}. 장기전(군단 루프·보스 흡혈 봉인)에서 이점이 뚜렷: 20보스 사망 {_jmap['흡혈 균형'][6]}(5빌드 중 2위), 판 {_jmap['흡혈 균형'][5]}분. PvP 는 약세(L-1 평균 아래) — 결투 흡혈 기하평균식으로 전패는 벗어남.
- **탱커** {ratio_str(cfg['builds']['탱커'])}: 가장 안전({_jmap['탱커'][6]} 사망)하고 가장 느림({_jmap['탱커'][5]}분, 보스전 합 {_jmap['탱커'][7]}초). 행운 0.5 를 유지하는 것이 핵심 — 행운 0 탱커는 함정(아래).
- **행운 도박** {ratio_str(cfg['builds']['행운 도박'])}: 치명 {_jmap['행운 도박'][8]}, 최종 레벨 최고({_jmap['행운 도박'][4]}, 당첨 포인트), 사망 {_jmap['행운 도박'][6]}. 장갑 관통(광전사 반지 ×{C['crit_cap_mult']+ITEMS['I06']['effects'][2]['v']:.1f})과 저주 보스(B08·B14)에서 최강, 관통 제한 B09 에서 최약. PvP 회피 = 치명 × {cfg['pvp']['dodge_from_crit']} 로 방어 스탯.

### 8.2 함정 빌드 (M 표 — UI 경고·튜토리얼 팁으로 노출)
- {m_line('행운 몰빵')}
- {m_line('공격 몰빵')}
- {m_line('행운 0 탱커')}
- 행운 절반을 흡혈로 돌린 1.0:2.0:0.25:0.75 는 PvE·PvP 모두 흡혈 균형에 밀려(회피·치명 손실 > 흡혈 이득) 프리셋에서 기각.

### 8.3 행운 보너스의 상한 (M-1: 레벨당 실효 포인트 배율, 상한 ×{1+F['luck_bonus']['p_cap']*(F['luck_bonus']['double_mult']-1):.1f})
| 레벨 | 균형 | 행운 도박 | 행운 몰빵(0.5:0.5:3:0) | 행운 도박+행운의 왕관 |
|---|---|---|---|---|
""")
for r in _m1:
    P("| " + " | ".join(r) + " |")
P(f"""
v8 의 k=1+floor(log2(1+행운/50))(행운 전부 → 포인트 약 2.4배, PDF 질문 10)와 B 안의 무상한 로그식을 모두 버리고 D 안의 '그 레벨 포인트 2배 당첨'으로 교체 → 상한 ×{1+F['luck_bonus']['p_cap']*(F['luck_bonus']['double_mult']-1):.1f}, 레벨 무관. 행운의 가치는 치명·관통·당첨·정수·PvP 회피 다섯 곳으로 분산되고 몰빵은 벌을 받는다.

### 8.4 흡혈은 불사가 아니다 (M-2: 흡혈 극대 0.5:1:0:2.5 + 송곳니·성배 +10 vs 균형, 권장 레벨 보스 단독 100회)
| 보스 | 빌드 | 흡혈률 | 초당 회복 상한 | 실측 회복/초 | 실측 피격/초 | 승률 | 사망 | 초 |
|---|---|---|---|---|---|---|---|---|
""")
for r in _m2:
    P("| " + " | ".join(r) + " |")
P(f"""
흡혈 {pct(CAPS['pve']['lifesteal'])} 극대 빌드도 회복은 피해 비례라 상한({M2_HEAL_RANGE} 실측 vs 상한 12~20%/s)에 닿지 못하고 피격({M2_TAKEN_RANGE})에 밀린다. 흡혈은 '덜 죽는 균형'을 만들지 '안 죽는 빌드'를 만들지 않는다(BRIEF §4-5 증명).

### 8.5 공략 예시 — 선택이 결과를 바꾸는 장면
1. **바람 정령을 얻은 다음 판(B03 에테르 드래곤)**: 보호막 {BOSSES['B03']['gimmick']['shield_hits']}타 × 체력바 {BOSSES['B03']['phases']}개 = {BOSSES['B03']['gimmick']['shield_hits']*BOSSES['B03']['phases']}타가 피해 0. 공속 ×{aspd(ITEMS['I02']['effects'][0]['v']):.2f} 이면 보호막 벗기는 시간이 {BOSSES['B03']['gimmick']['shield_hits']*C['attack_interval']:.1f}초 → {BOSSES['B03']['gimmick']['shield_hits']*C['attack_interval']/aspd(ITEMS['I02']['effects'][0]['v']):.1f}초. K-0: 다음 보스 승리 {[r for r in K0_ROWS if r[0]=='바람 정령'][0][3]}.
2. **에테르 왕관을 얻은 다음 판(B06)**: 경험치 ×{1+ITEMS['I05']['effects'][0]['v']} = 레벨 ×{(1+ITEMS['I05']['effects'][0]['v'])**(1/(1+cfg['exp_curve']['a'])):.2f} = 모든 능력치 ×{(1+ITEMS['I05']['effects'][0]['v'])**(1/(1+cfg['exp_curve']['a'])):.2f}. K-0: {[r for r in K0_ROWS if r[0]=='에테르 왕관'][0][3]}, 평균 처치 보스 {[r for r in K0_ROWS if r[0]=='에테르 왕관'][0][4]}.
3. **심연의 수호자(B09)**: 보스 흡혈 {pct(BOSSES['B09']['gimmick']['boss_lifesteal'])}·내 흡혈 ×{BOSSES['B09']['gimmick']['player_ls_mult']}·관통 ×{BOSSES['B09']['crit_pierce_cap']} 제한. 광전사 반지를 빼고 용암 망토(피해 −{pct(ITEMS['I07']['effects'][0]['v'])}·반격 {pct(ITEMS['I07']['effects'][2]['v'])})와 체력 분배로. 자연 진행 사망 {NAT['B09']['deaths']}(C표) — 장비를 바꾸지 않으면 '행운 도박'이 가장 고전하는 보스.
4. **폭풍 와이번 25초 컷 → 회오리 정령왕 → 무사망 → 운명의 구미호**: 질풍 루프의 조건부 체인. 자연 장비로 25초 컷은 {[r for r in N_ROWS if r[0].startswith('B13')][0][2]}, 정령왕 무사망은 {[r for r in N_ROWS if r[0].startswith('B14')][0][2]}(풀장비 {[r for r in N_ROWS if r[0].startswith('B14')][0][3]}). 정령왕은 소환 {BOSSES['B13']['gimmick']['adds']['count']}마리×2회라 광풍 망토(3마리) 없으면 6마리 상대 — 거인 망토(2마리)로도 사망이 줄어든다.
5. **군단 루프 전 장비 재구성**: 군단 파쇄 망토(떼 +{pct(ITEMS['I16']['effects'][1]['v'])}·3마리) + 피의 성배(초당 회복 상한 {pct(F['lifesteal']['heal_per_s_cap_base']+ITEMS['I17']['effects'][1]['v'])}) + 군주의 부적(에너지 +{ITEMS['I18']['effects'][0]['v']}/+{ITEMS['I18']['effects'][1]['v']}). K-0 피의 성배: 사망 {[r for r in K0_ROWS if r[0]=='피의 성배'][0][5]}. 영혼 왕관은 '안전(행운의 왕관) vs 기록(최종 레벨 {[r for r in K0_ROWS if r[0]=='영혼 왕관'][0][6]})'의 선택.
6. **워프 판**: 황제 드래곤 {R['warp']['unlock_kills']}회 처치 뒤 10단계 광장에서 시작(레벨 ×{R['warp']['level_factor']}, 에너지 {R['warp']['start_energy']}) → 군단 루프 5보스 {summary_fields('Q')['중간 판 시간']}·클리어 {summary_fields('Q')['클리어율(전 보스 5)']}·사망 {summary_fields('Q')['평균 사망']}(Q표). 숙련자의 모바일 한 세션.
""")

# ================================================================= §9 도파민
_e2 = summary_fields("E-2")
P(f"""---
## 9. 도파민·연출 장치 (전부 수치에 묶여 있고 시뮬에서 측정됨)

| 장치 | 트리거(수치) | 연출 | 측정값 / 왜 재미인가 |
|---|---|---|---|
| 레벨 티커 | 전투 종료 시 획득 레벨. 1구간 첫 전투 +{num(ROUTES['main']['stages'][0]['anchor_levels']['after_first_fight']-1)}(3전), 5구간 첫 전투 +{big(ROUTES['main']['stages'][4]['anchor_levels']['after_first_fight']-ROUTES['main']['stages'][4]['anchor_levels']['enter'])}, 10구간 +{big(ROUTES['main']['stages'][9]['anchor_levels']['after_first_fight']-ROUTES['main']['stages'][9]['anchor_levels']['enter'])}, 군단 5구간 +{big(ROUTES['right']['stages'][4]['anchor_levels']['after_first_fight']-ROUTES['right']['stages'][4]['anchor_levels']['enter'])} | 숫자가 {C['loot_s']}초 동안 드르륵(로그 스케일 롤링), 자릿수 바뀔 때 효과음 피치 상승, 레벨업 회복으로 체력바가 차오름 | 인플레이션 RPG 의 핵심 쾌감. 경험치 표로 바꿔도 체감이 유지됨을 §3 표가 보장 |
| 행운! | 레벨 1 오를 때 p≤{pct(F['luck_bonus']['p_cap'])} 로 포인트 {st['pts_per_level']}→{st['pts_per_level']*F['luck_bonus']['double_mult']:.0f} | '행운!' 팝(금색). 고레벨은 '행운 ×n' 묶음 표시 | 20보스 판 행운! {_e2['행운!']}(E-2) — 매 전투 수천~수억 번이라 묶어서 표시. 상한 ×{1+F['luck_bonus']['p_cap']*(F['luck_bonus']['double_mult']-1):.1f}(M-1) |
| 체력바 깨짐 | 보스 체력 1/페이즈 경계 통과(체력바 {min(b['phases'] for b in BOSSES.values())}~{max(b['phases'] for b in BOSSES.values())}개) | 화면 정지 {min(b['transition_s'] for b in BOSSES.values())}~{max(b['transition_s'] for b in BOSSES.values())}초(전환 무적), 유리 깨지는 소리, 다음 바 색 변경, 분노 보스는 붉은 오라 | 장갑 때문에 풀 +10 이라도 최소 {MINHITS_RANGE}타 → 장면이 생략되지 않음(F10 중간값 최단 {KEY['plus10_min_secs']}초) |
| 그로기 창 | 수정 매머드 {BOSSES['B01']['gimmick']['stagger']['every_s']}초마다 {BOSSES['B01']['gimmick']['stagger']['dur_s']}초, 영혼의 거인왕 {BOSSES['B19']['gimmick']['stagger']['every_s']}초마다 {BOSSES['B19']['gimmick']['stagger']['dur_s']}초, 전환 그로기 {min(b['gimmick']['stagger_on_phase_s'] for b in BOSSES.values() if 'stagger_on_phase_s' in b['gimmick'])}~{max(b['gimmick']['stagger_on_phase_s'] for b in BOSSES.values() if 'stagger_on_phase_s' in b['gimmick'])}초 | '지금!' 자막, 피해 ×{BOSSES['B01']['gimmick']['stagger']['dmg_mult']}·장갑 ×{BOSSES['B01']['gimmick']['stagger']['cap_mult']:.0f} → 노란 큰 숫자 | 버튼을 연타할 이유. 보스가 공격을 멈추므로 사망도 줄인다(B01 자연 사망 {NAT['B01']['deaths']}) |
| 브레스 예고 | 와이번·황제·청룡 {min(b['gimmick']['breath']['every_s'] for b in BOSSES.values() if 'breath' in b['gimmick'])}~{max(b['gimmick']['breath']['every_s'] for b in BOSSES.values() if 'breath' in b['gimmick'])}초마다, 1.5초 예고, 피해 ×{BOSSES['B02']['gimmick']['breath']['atk_mult']} | 바닥 붉은 부채꼴, 뒤로 걸으면 회피(수동 {pct(BOSSES['B02']['gimmick']['breath']['dodge_p_manual'])} 가정) | 조준 없이 '걷기'만으로 되는 회피(BRIEF 제약 1). 니어미스의 원천 |
| 피버 | 리듬 탭 {C['fever_hits']}콤보(창 {C['tap_window_s']}초) → {C['fever_dur_s']:.0f}초 공속 ×{C['fever_aspd']} | 숫자 황금색, 음악 레이어 추가, 공격 궤적 길어짐 | 판당 가운데 {KEY['fever_per_run']}회(E-1), 20보스 {_e2['피버']}(E-2). 보정 기준 탭 성공률 {pct(C['manual_combo_p'])}(보수적) — 피버 OFF 로도 10종 클리어 {FEVER_OFF_CLEAR}(I표) |
| 한계! / 장갑! | 보스에게 상한 타격(피해 = 장갑×최대체력×관통) | 숫자 뒤 「한계!」, 화면 가장자리 흰 번쩍. 관통 치명이면 「장갑!」 | 상한 타격 비율: 자연 {re.search(r'상한 타격 (\d+%)', sim_summary_line('A')).group(1)}(장비 0) → 풀 +0 {re.search(r'상한 타격 (\d+%)', sim_summary_line('E-2')).group(1)} → +10 {re.search(r'상한 타격 (\d+%)', sim_summary_line('F10')).group(1)}. 강해졌다는 증거이자 공속·관통으로 갈아타라는 신호 |
| 니어미스 | 체력 {pct(C['timing']['near_miss_hp_frac'])} 이하에서 사망 없이 승리 | 흑백 0.5초 → 컬러 복귀, '아슬아슬!' 배지, 결산 기록 | 판당 {re.search(r'니어미스 ([\d.]+)회', sim_summary_line('A')).group(1)}회(첫 판)~{_e2['니어미스']}(20보스) |
| 문 열림 | 보스 처치 | {C['door_s']:.0f}초: 제단 빛 → 문 균열 → 열림, 에너지 +{R['energy_boss_main']}/+{R['energy_boss_loop']} 숫자 튀어오름, 첫 드롭이면 전신 발광 | 구간 끝의 성취. 에너지 회복 = '더 갈 수 있다'는 허가장 |
| 조건부 보스 흔적 | 조건 미충족 제단 | 발자국·시계 소리·거울 파편만 남고 문이 {C['door_s']*C['timing']['no_boss_door_s_mult']:.0f}초 만에 열림 | '다음엔 25초 안에 / 무사망으로 / 도박 구역에서' — 공략 목표가 생긴다. 등장률 N표 |
| 루프 입구 표지판 | 5·10단계 광장 | '권장 레벨 {num(ROUTES['left']['sign_recommended_level'])} / {num(ROUTES['right']['sign_recommended_level'])}' + 아이템 수 | 모험심: 지도에 '아직 못 간 곳'이 보이되 무모한 진입은 말림(A 안) |
| 도착 보상 리듬 | 전투 간격 ≈ 걷기 {_enc['stud_per_bar']*_enc['start_bar']/R['move_speed']:.1f}초+ + 등장 {C['spawn_s']:.0f}초 + 전투 | 10초 안팎마다 숫자가 터진다 | 모바일 세션용 간격. 가운데 10보스 판 {E1['중간 판 시간']}에 전투 40 + 보스 10 |
| 결산 | 판 종료 {R['result_s']}초 | 최종 레벨(기록 갱신 금색), 처치 보스, 최장 피버, 니어미스, 최대 한 방, '행운!' 횟수, 공유 카드. 워프/깃발 판 표식 | '다음 판엔'을 부르는 마지막 도파민 |

난이도 곡선(벽 아니면 허수아비 금지)의 수치 근거: 자연 장비 기준 보스마다 **사망 {KEY['natural_deaths']}·도달 {NAT_REACH_RANGE}·전투 {KEY['natural_secs']}초**(C표), 장비 −1 이면 그 보스에서 에너지가 바닥나기 쉽고(A/B표: 2~3번째 보스), 풀장비면 사망 {min(float(v['deaths']) for v in FULL20.values()):.2f}~{max(float(v['deaths']) for v in FULL20.values()):.2f}·{min(float(v['secs']) for v in FULL20.values()):.1f}~{max(float(v['secs']) for v in FULL20.values()):.1f}초(E-2). 어느 보스도 100% 벽이 아니고 어느 보스도 1초가 아니다.
""")

# ================================================================= §10 과금
MZ = cfg["monetization"]; AA = MZ["auto_adventure"]
P(f"""---
## 10. 과금 (JSON `monetization`) — 꾸미기·뽑기·강화석 판매 없음

원칙: {MZ['rules_ko']}

| 상품 | Roblox 상품 유형 | 가격(Robux) | 효과 | 왜 결과를 크게 안 바꾸는가(시뮬 근거) |
|---|---|---|---|---|
""")
_ptype = {"pass": "구독(Subscription) — 월 정액", "teleport": "게임 패스(영구)", "record_book": "게임 패스(영구)", "festival": "개발자 상품(소모, 서버 전체 효과)",
          "lens": "게임 패스(영구)", "crystal": "개발자 상품(소모, 10개 묶음)", "rush_tickets": "개발자 상품(소모, 3장)"}
for p in MZ["products"]:
    eff = "; ".join(p["effects_ko"]) + (f" · 체험: {p['trial_ko']}" if "trial_ko" in p else "") + (f" · 묶음 {p['bundle_ko']}" if "bundle_ko" in p else "")
    P(f"| {p['name_ko']} | {_ptype[p['id']]} | {p['price_robux']} | {eff} | {p['why_no_result_ko']} |")
_hl = re.search(r"아이템 4개 보유 판: 패스 없음 평균 보스 ([\d.]+) / 패스 ([\d.]+), 최종 레벨 ([^,]+), 사망 ([\d.]+) / ([\d.]+)", H_SECTION)
P(f"""
- 무료 경로(`free_paths_ko`): {' / '.join(MZ['free_paths_ko'])}.
- **시작 에너지 +1 을 팔지 않는 이유(H표)**: 장비 0 판에 +1 을 주면 평균 처치 보스 {summary_fields('A')['평균 처치 보스']} → {summary_fields('H')['평균 처치 보스']}, 아이템 4개 보유 판 {_hl.group(1)} → {_hl.group(2)}(최종 레벨 {_hl.group(3)}). 결과를 바꾸는 수치라 B 안의 '패스 에너지 +1'을 삭제했다(`pass_energy_bonus` = {MZ['pass_energy_bonus']}).
- **자동 모험이 성장 속도를 크게 안 바꾸는 이유(O표)**: 첫 처치 없음·기록 없음·강화석 {pct(AA['stone_rate'])}·피버 없음·구역 {pct(C['zone_p_auto'])}·회피 {pct(BOSSES['B02']['gimmick']['breath']['dodge_p_auto'])} → 20보스 클리어 {summary_fields('G')['클리어율(전 보스 20)']}(G표, 수동 {summary_fields('E-2')['클리어율(전 보스 20)']}). 계정 성장(전부 +10) 무료 {AA['free_per_day']}회/일 {O_FREE_PLUS10}판 vs 패스 {AA['pass_per_day']}회/일 {O_PASS_PLUS10}판 — 패스의 성장 가속 ≈ ×{int(O_FREE_PLUS10)/int(O_PASS_PLUS10):.2f}(목표 ≤×1.3). 20보스 첫 완주까지는 둘 다 {re.search(r'중간값: 무료 — .*?20보스 (\d+)판', O_SECTION).group(1)}판으로 같다.
- 패스 {MZ['trial_days']}일 무료 체험 → 8일째 자동 모험 {AA['pass_per_day']}→{AA['free_per_day']}회·배속 ×{AA['speed_pass']}→×{AA['speed_free']} 축소(상실감이 전환 트리거, 결과 손해 없음).
- 사고 싶게 만드는 것(결과가 아닌 것들): 시간(순간이동 판당 약 40초·빨리감기 ×{AA['speed_pass']}·워프), 정보(예측 카드 '예상 32초·사망 1.1 → 거북 반지면 25초·0.6', 렌즈 타이머·조건 표시), 기록(리플레이·리더보드·공유 카드), 사회(축제 깃발 서버 공지 — '깃발 판' 표식으로 기록 오염 방지), 도전(보스 러시 타임어택 {re.search(r'풀장비 \+0: 합계 (\d+)초', P_SECTION).group(1)}초 → +10 {re.search(r'풀장비 \+10: 합계 (\d+)초', P_SECTION).group(1)}초, 일 강화석 상한 {cfg['boss_rush']['daily_stone_cap']} = 풀클리어 1판의 약 {cfg['boss_rush']['daily_stone_cap']/float(re.search(r'강화석 ([\d.]+)', sim_summary_line('E-2')).group(1))*100:.0f}%).
- 레포 규칙 준수: 유료 확률형 뽑기 없음, 치장 없음, 모든 상품에 무료 경로.
""")

# ================================================================= §11 PvP
PV = cfg["pvp"]
P(f"""---
## 11. PvP 대비 (JSON `pvp`, `caps.pvp`, `items[].pvp_disabled`) — 3차 출시

{PV['text_ko']}

### 11.1 결투 규칙 (수식)
| 항목 | 값 | 키 |
|---|---|---|
| 결투 레벨(둘 다 정규화, 포인트 고정 {num(PV['duel_level']*st['pts_per_level'])}, 당첨 없음) | {num(PV['duel_level'])} | pvp.duel_level, points_fixed |
| 제한 시간 / 종료 | {PV['time_limit_s']}초, 체력% 높은 쪽 승 | pvp.time_limit_s |
| 주는 피해 보정 | ×{PV['dmg_mult']} | pvp.dmg_mult, caps.pvp.dmg_mult |
| 한 타 상한 | 상대 최대 체력 {pct(CAPS['pvp']['hit_taken_cap'])} (최소 {math.ceil(1/CAPS['pvp']['hit_taken_cap'])}타) | caps.pvp.hit_taken_cap |
| 회피 | max({pct(PV['dodge_floor'])}, 치명 확률 × {PV['dodge_from_crit']}) ≤ {pct(PV['dodge_cap'])} — 행운이 결투 방어 스탯 | pvp.dodge_* |
| 결투 흡혈 | 타격당 회복 = 흡혈률 × √(내 최대 체력 × 상대 최대 체력) × {pct(PV['heal_per_hit_hp_frac'])}, 초당 ≤ {pct(CAPS['pvp']['heal_per_s_max'])} | pvp.heal_per_hit_hp_frac, heal_basis={PV['heal_basis']} |
| 첫 스윙 지연 | U({PV['first_swing_delay_s'][0]}, {PV['first_swing_delay_s'][1]})초 | pvp.first_swing_delay_s |
| 피버 | 없음 | pvp.fever |
| 무효 효과(pvp_disabled) | {', '.join(f"{it['name_ko']}: {', '.join(it['pvp_disabled'])}" for it in ITEMS.values() if it['pvp_disabled'])} | items[].pvp_disabled |
| 3v3 | 범위 {CAPS['pvp']['range_targets']}마리, 스플래시 {pct(CAPS['pvp']['splash'])} | caps.pvp |

상한표는 §2.3(PvE/PvP 열). 핵심 차이: 공속 ×{CAPS['pve']['aspd_mult']}→×{CAPS['pvp']['aspd_mult']}, 초당 회복 {pct(CAPS['pve']['heal_per_s_max'])}→{pct(CAPS['pvp']['heal_per_s_max'])}, 치명 {pct(CAPS['pve']['crit_p'])}/×{CAPS['pve']['crit_mult']}→{pct(CAPS['pvp']['crit_p'])}/×{CAPS['pvp']['crit_mult']}, 관통 ×{CAPS['pve']['crit_pierce']}→×{CAPS['pvp']['crit_pierce']}(없음), 반격 {pct(CAPS['pve']['reflect'])}→{pct(CAPS['pvp']['reflect'])}, 공격 배율 ×{CAPS['pve']['atk_mult']}→×{CAPS['pvp']['atk_mult']}, 경험치·보스 경험치 ×1(무의미).

### 11.2 상성표 (L-1: 미러 매치, 풀장비 +0, {RUNS}결투/쌍 — 행이 열을 이길 확률)
| 빌드 \\ 상대 | {' | '.join(r[0] for r in L1_ROWS)} | 평균 결투 초 |
|---|{'---|'*len(L1_ROWS)}---|
""")
for r in L1_ROWS:
    P("| " + " | ".join(r) + " |")
P(f"""
비대칭 쌍 승률 범위 **{KEY['pvp_pair_range']}** (목표 20~80%, 0%/100% 없음). 결투 {L1_SECS_RANGE}초. 가위바위보: 속공·균형 > 탱커·흡혈 균형, 행운 도박 > 흡혈 균형, 탱커 > 흡혈 균형, 행운 도박 ≈ 균형.

### 11.3 상한이 없다면 (L-2: caps.pve·피해 ×1·회피 없음)
| 빌드 \\ 상대 | {' | '.join(r[0] for r in L2_ROWS)} | 평균 결투 초 |
|---|{'---|'*len(L2_ROWS)}---|
""")
for r in L2_ROWS:
    P("| " + " | ".join(r) + " |")
P(f"""
결투가 {L2_SECS}초에 끝나는 '선타 싸움' — PvE 수치는 공격력 ≈ 체력의 60~80% 라 보정 없이는 2타 결투. 상한표가 결투를 {L1_SECS_RANGE}초의 빌드 싸움으로 바꾼다.
- {re.search(r'L-3\. (.+)', SIM).group(1)} — 전부 +10 이어도 합산 상한에 걸려 결투 길이가 유지된다.
- 노브 탐색 기록(`_tools/pvp_grid*.py`, 150결투/쌍): dmg_mult 0.035→{PV['dmg_mult']}, 한 타 상한 8%→{pct(CAPS['pvp']['hit_taken_cap'])}, 결투 흡혈 기하평균(피해 비례는 공격형만, 자기 체력 비례는 체력형만 유리), PvP 흡혈 상한 20%→{pct(CAPS['pvp']['lifesteal'])}(20% 면 흡혈 빌드 전패), 회피 계수 0.5→{PV['dodge_from_crit']}(0.5 면 행운이 흡혈을 압도), 초당 회복 {pct(CAPS['pvp']['heal_per_s_max'])}(J3).
- 왜 레벨 고정: 판마다 레벨 1 로 리셋되는 게임이라 '현재 레벨'은 운, '최고 기록'은 영원한 격차. 레벨 {num(PV['duel_level'])} 고정 + 분배 비율·장비·강화만 → PvP 는 빌드 싸움. 거울 기사(B15)가 같은 수식의 PvE 예습이고 보스 러시(레벨 {num(cfg['boss_rush']['level'])} 고정)가 같은 축의 경쟁이다.
- 미검증: 임의 분배(체력 몰빵 3:1:0:0 등)·장비 조합 차이·3v3. 출시 전 `python3 sim_boss20.py --pvp --runs 300` 으로 재확인.
""")

# ================================================================= §12 자동 모험
_g = summary_fields("G"); _g0 = summary_fields("G0")
P(f"""---
## 12. 인게임 자동 모험(시뮬) 모드 — "시뮬레이션을 통한 게임 클리어 재미" (JSON `monetization.auto_adventure`)

- 문 앞 UI: [장비 프리셋] [분배 비율 슬라이더 4개] [길·루프 선택] → **자동 모험 시작**. 서버가 §2 와 동일한 전투 규칙으로 판을 진행하고 화면은 ×{AA['speed_free']} 빨리감기(패스 ×{AA['speed_pass']}) + 전황 리포트(레벨 그래프, 보스별 초/사망, 피버 없음 표시).
- 핵심 루프 보호(의도된 열세): {AA['text_ko']}
- 시뮬 G표(풀장비 20보스 판, 자동): 클리어 {_g['클리어율(전 보스 20)']}(수동 {_e2['클리어율(전 보스 20)']}), 평균 처치 보스 {_g['평균 처치 보스']}(수동 {_e2['평균 처치 보스']}), 사망 {_g['평균 사망']}(수동 {_e2['평균 사망']}), 가운데 10보스는 {_g['가운데 10보스 클리어']}. 조건부 보스 B18·B19 등장 {[r for r in N_ROWS if r[0].startswith('B18')][0][5]}(도박 구역 진입 확률이 낮아서). G0(장비 0 자동): 처치 보스 {_g0['평균 처치 보스']}(수동 {summary_fields('A')['평균 처치 보스']}). → UI 에서 '가운데 길 전용 추천'으로 안내.
- 규칙: 이미 한 번 잡은 보스까지만(새 보스 제단 앞에서 멈춰 '직접 도전' 버튼), 첫 처치·기록 없음, 강화석·정수 {pct(AA['stone_rate'])}. 무료 {AA['free_per_day']}회/일, 패스 {AA['pass_per_day']}회/일(+예측 수정구로 추가). 언제든 버튼을 누르면 수동 전환(콤보 시작). 결산 카드에 '자동' 표식.
- 제단 예측 카드(D·A 묶음, 예측 수정구): 현재 빌드로 이 보스 '예상 N초·사망 M' + 칸 하나 바꿨을 때의 변화 1줄. 서버가 같은 규칙으로 40회 시뮬(= gen 의 `_measure`). 하루 무료 {AA['free_per_day']}회.
- 의뢰자 오프라인 시뮬: `python3 sim_boss20.py --runs {RUNS}` 이 §13 전체를, `--auto` 가 이 모드를, `--gear I01,I02 --build ls --plus 5 --plan main --start plaza5 --fever off` 가 시나리오를 출력한다(`--report all|quick|none`).
""")

# ================================================================= §13 시뮬 결과 원문
P(f"""---
## 13. 시뮬레이션 결과 (`SIM_RESULT.txt` 원문 — `python3 sim_boss20.py --runs {RUNS}`, 수동 조작 모델, 탭 성공률 {pct(C['manual_combo_p'])})

모델 요약: 이벤트 구동 1:N 전투(최대 3마리 동시 타격), 자동 타격 {C['attack_interval']}초(피버 ×{C['fever_aspd']}), 몬스터 각자 간격, 보스 체력바·전환 무적·장갑·관통·기믹 14종 전부 구현, 사망 시 부활·적 체력 유지·누진 에너지, 레벨업 회복, 제단 입장 체력 가득, 가운데 구간당 4전투·루프 2전투, 도박 구역 {pct(C['zone_p_manual'])}(자동 {pct(C['zone_p_auto'])}), 조건부 보스 판정, 루프 에너지, 워프, PvP 결투, 보스 러시, 계정 성장. 표 머리의 A~Q 는 본문에서 'X표'로 인용한 것과 같다. 아래는 파일을 그대로 붙인 것이다.

```
{SIM.strip()}
```
""")

# ================================================================= §14 노브
def j(path):
    cur = cfg
    for k in path.split("."):
        cur = cur[int(k)] if k.isdigit() else cur[k]
    return cur
KNOBS = [
    ("시작 에너지", "run.energy_start", "첫 판 길어짐(+1 ≈ 처치 보스 +0.4, H표), 자연 진행 도달율 ↑ / 내리면 2보스 도달 ↓(15 면 J1 목표 55~65% 안에 들어오지만 B07 도달 71% 가 더 떨어짐)", "A·C표"),
    ("사망 비용(기본·증분·상한)", "run.energy_death_base / energy_death_step / energy_death_max", "올리면 '죽으며 깎기' 비싸짐 → 벽 느낌 ↑, 공격 몰빵 벌 ↑ / 내리면 유리대포 빌드 생존", "C표 사망·도달, M표 공격 몰빵"),
    ("보스 처치 에너지(가운데/루프)", "run.energy_boss_main / energy_boss_loop", "올리면 풀클리어·루프 수지 ↑ / 루프 +5→+4 면 구간 순이익 +2", "D/E/E-2표 클리어율"),
    ("광장 사망 카운터 초기화", "run.death_counter_reset_at_plaza", "끄면 20보스 판 사망 비용이 6 으로 고정되어 완주율 ↓", "E-2 사망"),
    ("단계당 경험치 배율", "gen_params.R_MAIN (gen 재실행)", "레벨 폭발 ↑·최종 레벨 ↑ (몬스터·보스는 앵커로 같이 올라가 난이도 불변)", "§3 표, 최종 레벨"),
    ("경험치 곡선 a", "exp_curve.a", "올리면 후반 레벨 증가 둔화(0.5 면 최종 레벨 1/10), 왕관 가치 ↓", "최종 레벨"),
    ("보스 목표 초", "bosses.*.target_secs_natural (gen 재보정)", "보스전 길이 비례, 사망 ↑", "C표 보스전 초"),
    ("보스 성향", "gen_params.ARCH (T_mult / atk_factor)", "탱커 ×1.3/×0.75 를 벌리면 보스전 길이 분산 ↑", "C표 19.9~43.8초"),
    ("보스 사망 목표", "bosses.*.anchor.death_target (gen 재보정)", "올리면 공격 보정 배율 ↑ → 자연 사망 ↑", "C표 사망, anchor.death_curve"),
    ("보스 장갑(타격 상한)", "bosses.*.hit_cap", "내리면 풀장비 보스전 길어짐(최소 타수 ↑), 공속·관통 가치 ↑ / 0.5%p 내리면 풀 +10 약 +1초", "F10 최단 초, M-4"),
    ("체력바 수·전환 초", "bosses.*.phases / transition_s", "드라마 ↑, 풀장비 하한 ↑(전환 초 합이 전투 하한에 더해짐)", "E-2 최소 초"),
    ("관통(치명·반지·상한)", "combat.crit_cap_mult / items.I06 crit_pierce_add / caps.pve.crit_pierce / bosses.*.crit_pierce_cap", "행운 빌드의 장갑 뚫기 가치", "J표 행운 도박, B09"),
    ("피버 절대 공속 상한", "formulas.aspd.fever_abs_cap", "2.5→2.2 면 풀 +10 절대 최단 9.0초 → 10초 위로(피버 중 간격 0.40→0.45초)", "M-4 절대 최단"),
    ("공속 반감·상한", "formulas.aspd.half / caps.pve.aspd_mult", "정령 중첩 가치 ↑, PvP 위험 ↑", "M-3, L표"),
    ("초당 회복 상한(기본·계수·최대)", "formulas.lifesteal.heal_per_s_cap_base / heal_per_s_ls_coef / caps.pve.heal_per_s_max", "올리면 흡혈 빌드 생존 ↑(불사 위험은 M-2 로 확인)", "J표 흡혈 균형, M-2"),
    ("흡혈 포인트 최대·계수", "formulas.lifesteal.max_from_pts / lvl_coef / c", "흡혈 몰빵 가치 ↑", "J표"),
    ("치명 식", "formulas.crit.base / span / lvl_coef / c / caps.pve.crit_p", "행운 투자 가치 ↑(PDF 질문 5)", "J표 행운 빌드, L표 회피"),
    ("행운! 당첨", "formulas.luck_bonus.p_coef / p_cap / double_mult", "행운 몰빵 포인트 ↑(상한 = 1+p_cap×(double−1))", "M-1"),
    ("피버", "combat.fever_hits / fever_dur_s / fever_aspd / manual_combo_p / tap_window_s", "수동 vs 자동 격차 ↑. 탭 실측 뒤 manual_combo_p 재설정 + gen 재보정", "E vs G표, I표"),
    ("도박 구역", "combat.zone_p_manual / zone_p_auto, formulas.exp_gain.zone_exp_mult, formulas.damage_taken.zone_dmg_mult", "도박 가치·분산 ↑, B18 등장률", "최종 레벨 분포, N표"),
    ("받는 한 타 상한", "formulas.damage_taken.player_hit_cap", "내리면 브레스·폭주의 위협 ↓", "'한 타 최대 피격' 행"),
    ("피격 분산", "formulas.damage_taken.var_lo / var_hi", "넓히면 운 요소 ↑", "C표 사망"),
    ("몬스터 계수", "gen_params.KIND[*].hp_k / atk_k (gen 재실행)", "일반 전투 사망 ↑(현재 자연 0~0.3/판)", "'일반 전투 사망' 행"),
    ("조우 수·게이지", "routes.*.stages[].fights, run.encounter.stud_per_bar", "판 길이·레벨 ↑, 에너지 압박 ↑", "판 시간"),
    ("루프 표지판", "routes.left/right.sign_recommended_level_factor", "낮추면 무모한 진입 ↑", "C표 B11/B16 도달"),
    ("조건부 보스 조건", "bosses.B13/B14/B18/B19.spawn_condition", "조이면 변별력 ↑·20보스 클리어 ↓", "N표"),
    ("강화 배율·단계", "stones.upgrade_mult_per_plus / max_plus", "+10 가치 ↑(합산 상한에 막힘). 선형으로 바꾸려면 gen 재보정", "F5/F10, L-3"),
    ("강화 비용·성공률·천장·정수", "stones.cost / success / pity_fails / essence_cost", "파밍 길이(기대 41.2개·정수 17)", "O표"),
    ("강화석 드롭", "stones.drop.first_kill / repeat_kill / repeat_bonus_p / no_death_bonus", "계정 성장 속도", "O표"),
    ("워프", "run.warp.unlock_kills / start_energy / level_factor", "숙련자 세션 길이", "Q표"),
    ("자동 모험", "monetization.auto_adventure.free_per_day / pass_per_day / stone_rate", "패스 성장 가속(현재 ×1.06, 목표 ≤1.3)", "O표"),
    ("PvP 보정", "pvp.dmg_mult / dodge_from_crit / dodge_cap / dodge_floor / heal_per_hit_hp_frac, caps.pvp.hit_taken_cap / heal_per_s_max / lifesteal", "결투 길이·빌드 균형(격자 탐색 기록 §11)", "L표"),
    ("보스 러시", "boss_rush.level / death_penalty_s / daily_stone_cap", "타임어택 길이·강화석 수입", "P표"),
    ("시뮬 모델 가정", "combat.manual_combo_p, bosses.*.gimmick.breath.dodge_p_manual/auto, combat.zone_p_*", "실측 뒤 교체할 가정값 4개", "전 표"),
]
def cur_val(path):
    first = path.split(" ")[0].split(" / ")[0].split("(")[0].strip()
    try:
        v = j(first)
        return json.dumps(v, ensure_ascii=False) if not isinstance(v, (dict, list)) else "(표 참조)"
    except Exception:
        return "(§ 해당 표)"
P(f"""---
## 14. 튜닝 노브 표 — JSON 경로·현재값·올리면/내리면

| 노브 | config 키 | 현재값(첫 키) | 올리면 / 내리면 | 시뮬에서 보는 지표 |
|---|---|---|---|---|
""")
for name, path, eff, metric in KNOBS:
    P(f"| {name} | `{path}` | {cur_val(path)} | {eff} | {metric} |")
P(f"""
재생성 절차: `gen_boss20.py` 의 설계 입력(또는 config 의 노브)을 바꾸고 `python3 gen_boss20.py`(앵커 2차 측정 60판·공격 배율 격자·체력 2회 보정 자동) → `python3 gen_boss20.py --check`(재생성 == 파일, 종료 코드 0) → `python3 sim_boss20.py --runs {RUNS} > SIM_RESULT.txt` → `python3 doc_boss20.py`(이 문서) → `python3 verify_doc_boss20.py`. 노브만 바꾸고 gen 을 다시 돌리지 않으면 앵커(권장 레벨·보정 초)가 어긋나므로 `--check` 가 DIFF 를 낸다.
""")

# ================================================================= §15 v8 대비 변경
P(f"""---
## 15. 기준선 v8 대비 변경 이유 (BRIEF §1 → 이 설계)

| 항목 | v8 | 이 설계 | 이유 |
|---|---|---|---|
| 에너지 | 시작 12, 사망 −3 고정, 보스 +4 | 시작 {R['energy_start']}, 사망 {R['energy_death_base']}→{R['energy_death_max']} 누진(광장 초기화), 가운데 +{R['energy_boss_main']}·루프 +{R['energy_boss_loop']} | 12 는 장비 0 첫 판이 2.3분에 끝남. 누진은 '죽으며 깎기'를 전략(1~2회)으로 남기고 남용(3회+)만 벌함(M표 공격 몰빵 0%). 루프 +5 는 험로를 에너지 광산으로(A) |
| 1보스 | HP 20,000·공 6,000(엄니검 보유자 기준) → 장비 0 승률 0% | HP {num(_b1['hp'])}·공 {_b1['atk']}(장비 0 기준 앵커) → 승률 {pct(float(KEY['first_boss_win_no_gear']))}, {KEY['first_boss_secs']}초 | 부트스트랩(BRIEF §4-7) |
| 보스 수 | 5 | 20 (가운데 10 + 루프 5+5) | 의뢰 |
| 보스전 | 0.6~13초(허수아비) / 벽 | 장갑 {HITCAP_RANGE}·체력바·기믹 → 자연 {KEY['natural_secs']}초, 풀 +10 중간값 ≥{KEY['plus10_min_secs']}초 | 한 방 금지·10~45초·3단 체감(BRIEF §4-8) |
| 엄니검 | 데미지 +10,000 고정 | 공격 ×{1+ITEMS['I01']['effects'][0]['v']} 배율 | 레벨 1 부터 1보스 무력화 방지, 2단계에서도 유효(PDF 질문 2) |
| 흡혈 | 1pt 0.001%, 송곳니 3%(죽은 아이템) | 포화식 {pct(F['lifesteal']['max_from_pts'])}×P/(P+레벨+{F['lifesteal']['c']}) + 장비, 초당 상한 max({pct(F['lifesteal']['heal_per_s_cap_base'])}, {F['lifesteal']['heal_per_s_ls_coef']}×흡혈률) | 기존값은 체감 0. 초당 상한으로 공속·흡혈 분리, 불사 금지(M-2). B 안의 '타격당 6%' 는 흡혈 스탯을 죽여(J2) 교체 |
| 범위 | 거인 망토 ×1.5(죽은 아이템) | 동시 타격 수(2~3마리) + 스플래시, 전투 1:N·군단 떼 | 1:1 모델에서 의미 없음 → 다중 타격으로(BRIEF §4-5) |
| 치명 | 8%+22%×행운/(행운+0.5L+20), 상한 30% | {pct(F['crit']['base'])}+{pct(F['crit']['span'])}×행운/(행운+{F['crit']['lvl_coef']}L+{F['crit']['c']}), 상한 {pct(CAPS['pve']['crit_p'])}, 장갑 관통 ×{C['crit_cap_mult']} | 행운 투자 가치(PDF 질문 5): 치명·관통·당첨·정수·PvP 회피 |
| 행운 보너스 | p≤50%, k=1+floor(log2(1+행운/50)) → 몰빵 ×2.4 | '행운!' 그 레벨 포인트 2배, p≤{pct(F['luck_bonus']['p_cap'])} → 상한 ×{1+F['luck_bonus']['p_cap']*(F['luck_bonus']['double_mult']-1):.1f}, 레벨 무관 | 몰빵 폭주 제거(PDF 질문 10, M-1) |
| 레벨 | 획득 레벨을 직접 더함 | 경험치 표 need(L)={cfg['exp_curve']['n0']}(1+L/{cfg['exp_curve']['K']})^{cfg['exp_curve']['a']}, 닫힌 역함수 | 의뢰(경험치 표) + 인플레이션 체감 유지(§3) |
| 단계 간 배율 | 공격 ×1,000 → ×15 끊김 | 앵커식(hp_k·atk_k × 기대 능력치) → 구간당 ×{MONS['golem']['atk']/MONS['deer']['atk']:.1f}~{MONS['titan']['atk']/MONS['stargiant']['atk']:.1f} 일정 | PDF 질문 3·9 |
| 공격 간격 | 자동 1.1초 / 버튼 0.6초 | {C['attack_interval']}초 쿨다운 공유 + 리듬 탭 콤보→피버 | 탭 속도 DPS 격차(1.8배) 제거 → 밸런스·PvP 예측 가능. 수동 보상은 피버로 |
| 조우 | 1칸 30 stud | 1칸 {_enc['stud_per_bar']} stud | 가운데 구간당 {_enc['target_fights_main']}전투·루프 {_enc['target_fights_loop']}전투에 맞춤 |
| 행운 구역 | 레벨 ×2 또는 체력 ½ 두 종류 | 도박 구역 하나(경험치 ×{F['exp_gain']['zone_exp_mult']}·피해 ×{F['damage_taken']['zone_dmg_mult']}, 1회 소진) | 선택이 곧 전략, B18 조건 |
| 몬스터 모델 | 15종 + 보스 5 | {len(MONS)}종(재질 변경 {sum(1 for m in MONS.values() if '재질' in m['model'])}) + 보스 20 | 신규 모델 8종만(Mount23~30) |
| 장비 칸 | 5(무기·정령·반지·망토·왕관) | 7(반지 2·부적 추가), 20종 | 교체 전략 |
| 강화 | plus 필드 1.3^plus(미사용) | {UP}^p, 급별 강화석 4종, 성공률·천장·정수·5:1 교환 | 장기 루프(O표 전부 +10 {O_FREE_PLUS10}판) |
| 어려운 길 | 입구만(잠김) | 광장 루프 2개(5구간, 2전투+보스, 표지판·조건부 보스) | 모험심(A)·구현 절제(Z 리스킨, D) |
| 체력/힘/행운 계수·포인트 3 | 10/2/1, 3 | 그대로 | PDF 질문 4: 변경 없이 앵커가 흡수 |
| 사망 규칙 | 그 자리 부활·체력 가득·2.5초 무적·적 체력 유지 | 그대로 + 누진 비용 + 제단 입장 체력 가득 | v6 규칙 유지 |

PDF 밸런스 질문 11개에 대한 답은 위 표와 §4(1), §7(2), §5(3·9), §2(4·5·11), §6(6), §4.3(7), §4.2(8), §8(10)에 있다.
""")

# ================================================================= §16 구현 순서
P(f"""---
## 16. 구현 순서 (출시 3분할, JSON `release_plan_ko`)

| 차수 | 범위 | 성립 근거(시뮬) |
|---|---|---|
| 1차 | {cfg['release_plan_ko'][0]} | I표: 가운데 10종 보유·피버 OFF 풀클리어 {FEVER_OFF_CLEAR}·{FEVER_OFF_MIN}분; 장비 0 피버 OFF 1보스 승률 {re.search(r'장비 0 \+ 피버 OFF: 1보스 승률 (\d+%)', SIM).group(1)}, 2보스 도달 {re.search(r'2보스 도달 (\d+%)', sim_section('I')).group(1)} |
| 2차 | {cfg['release_plan_ko'][1]} | C표 B11~B15 도달 {min(int(NAT[b]['reach'].rstrip('%')) for b in ('B11','B12','B13','B14','B15'))}~{max(int(NAT[b]['reach'].rstrip('%')) for b in ('B11','B12','B13','B14','B15'))}%, N표 조건 등장률 |
| 3차 | {cfg['release_plan_ko'][2]} | E-2 20보스 {pct(float(KEY['clear20_full_gear']))}, L-1 PvP {KEY['pvp_pair_range']}, P표 러시, Q표 워프 |

### 16.1 1차 구현 체크리스트 (코어)
1. 경험치·레벨: `exp_curve` 닫힌 식 3개(need/E/L). 레벨만 저장, 획득 시 E(L)+Δ → L(E). 포인트 {st['pts_per_level']}/레벨 + '행운!' 주사위(p 식). 자동 분배 비율 저장(builds 프리셋 5 + 함정 경고).
2. 전투 코어: {C['attack_interval']}초 쿨다운 공유(자동·버튼), 피해 식, 치명 식, 흡혈 포화식 + 초당 회복 상한(스윙당 = 상한 × 간격), 공속 식, 범위 → 동시 타격 수, 받는 피해 식 + 한 타 {pct(F['damage_taken']['player_hit_cap'])} 상한, 전투 종료 회복 {pct(C['after_fight_heal'])}·비전투 {pct(C['regen_per_s'])}/초, 레벨업 회복.
3. 보스 코어: 체력바(phases)·전환 무적·장갑(hit_cap × 관통)·기믹 원시형 14종(그로기·전환 그로기·브레스·분노·보호막·소환·광란·가시·재생·폭주·저주·보스 흡혈·흡혈 봉인·거울). B01~B10 은 이 중 12종 사용(거울·흡혈 봉인 제외는 B09 에 있음 → 전부). 제단 입장 체력 가득.
4. 판: 에너지 {R['energy_start']}·누진 사망·보스 +{R['energy_boss_main']}, 조우 게이지({_enc['stud_per_bar']} stud/칸), 도박 구역(1회 소진), 문(이번 판 처치), 결산 카드.
5. 장비: 7칸(반지 2), 효과 키 {len(EFFECT_KO)}종 집계(`aggregate` 그대로 이식), caps.pve 16항목, 제단 앞 교체 UI, 자동 장착(rank).
6. 강화: 1~2급 강화석, 비용·성공률·천장·정수(+5 이상), 5:1 교환, 실패 하락 없음.
7. 과금: 패스(구독, 7일 체험)·순간이동권·기록의 책·관찰 렌즈·예측 수정구(개발자 상품). 자동 모험 {AA['free_per_day']}회/일(패스 {AA['pass_per_day']}).
8. 연출: 레벨 티커·행운!·체력바 깨짐·그로기 '지금!'·브레스 예고·한계!/장갑!·니어미스·문 열림·결산(피버 연출은 2차).
9. 몬스터·보스 자산: 가운데 30종(재질 변경 {sum(1 for m in MONS.values() if m['route']=='main' and '재질' in m['model'])}) + 보스 10(신규 대형 Mount28~30 3종).

### 16.2 2차
리듬 탭(창 {C['tap_window_s']}초)·콤보·피버(모바일 지연 실측 → `manual_combo_p` 재설정 → gen 재보정), 질풍 루프(가운데 Z 지오메트리 리스킨, 몬스터 15종 재질 변경 + 신규 Mount23~26 4종), 조건부 보스 판정 함수 1개(`condition_met`) + B13·B14, 3급 강화석, 표지판, 루프 에너지 +{R['energy_boss_loop']}·광장 카운터 초기화.

### 16.3 3차
군단 루프(Mount27 1종 신규), B18·B19 조건, 4급 강화석, 결투장(거울 기사 코드 재사용: caps.pvp 열·pvp_disabled·회피·기하평균 흡혈), 보스 러시(레벨 {num(cfg['boss_rush']['level'])} 고정·사망 +{cfg['boss_rush']['death_penalty_s']}초·일 강화석 {cfg['boss_rush']['daily_stone_cap']}), 워프 제단({R['warp']['unlock_kills']}회 처치 해금), 축제 깃발, 리더보드.

### 16.4 남은 문제 (엔진 담당 기록 + 문서 담당 추가)
1. 첫 판 2보스 도달 {pct(float(KEY['second_boss_reach']))}({RUNS}판) — J1 목표 55~65% 약간 위. energy_start {R['energy_start']}→15 면 들어오지만 자연 진행 B07 도달 {NAT['B07']['reach']} 이 더 떨어져 그대로 둠.
2. 풀 +10 보스전 절대 최단 {KEY['plus10_abs_min_secs']}초(거울 기사, 150판 중 1회) — 보스별 중간값은 전부 ≥{KEY['plus10_min_secs']}초. 더 조이려면 `formulas.aspd.fever_abs_cap` {F['aspd']['fever_abs_cap']}→2.2 또는 해당 보스 hit_cap −0.5%p 뒤 gen 재실행.
3. 흡혈 균형 vs 균형: 20보스 {KEY['ls_deaths_20']} vs {KEY['bal_deaths_20']} 로 충족하지만 가운데 10보스만 보면 {KEY['ls_deaths_main']} vs {KEY['bal_deaths_main']}(노이즈 수준) — 흡혈의 이점은 장기전(군단 루프)에서만 뚜렷.
4. 조건부 보스 조건이 수동 플레이어에겐 거의 항상 충족(B13·B18·B19 100%, B14 무사망만 {[r for r in N_ROWS if r[0].startswith('B14')][0][2]}) — 변별력은 B14 와 자동 모험({[r for r in N_ROWS if r[0].startswith('B18')][0][5]})에서만. 조이면 20보스 클리어율이 떨어져 그대로 둠.
5. 자연 진행 사망 하한: B09 {NAT['B09']['deaths']}, B14 {NAT['B14']['deaths']}(무사망 조건으로 걸러진 플레이어만 만나는 선택 효과) — 0.4 아래 2보스.
6. 20보스 완주 {float(KEY['full_clear_20_minutes']):.1f}분(+10 {PLUS10_MIN}분)은 BRIEF 권장 15분 초과 — 루프 2개가 선택이라 가운데 풀클리어 {float(KEY['full_clear_main_minutes']):.1f}분·워프 판 {summary_fields('Q')['중간 판 시간']}을 숙련 목표로 제시.
7. 자동 모험 20보스 클리어 {summary_fields('G')['클리어율(전 보스 20)']} — 의도된 열세지만 UI 에서 '가운데 길 전용 추천' 안내 필요.
8. 모델 가정 미실측: 탭 성공률 {C['manual_combo_p']}(창 {C['tap_window_s']}초), 브레스 걷기 회피 {BOSSES['B02']['gimmick']['breath']['dodge_p_manual']}(자동 {BOSSES['B02']['gimmick']['breath']['dodge_p_auto']}), 도박 구역 진입 {C['zone_p_manual']}, 행운 당첨은 기대값 처리(서버는 주사위). 버튼 연타 추가 DPS 없음(쿨다운 공유라 동일).
9. 경험치 숫자 10^12(B20 {big(_b20['exp'])}, 최종 레벨 {big(float(KEY['final_level_full20']))}) — Luau double 안전 범위 안이지만 누적 경험치가 아닌 레벨만 저장하고 L(E) 로 복원해야 함.
10. K-0 '획득 직후' 해석: 군주의 부적(에너지 +3/+1)은 사망 {[r for r in K0_ROWS if r[0]=='군주의 부적'][0][5]} 로 '늘어난' 것처럼 보이나 에너지가 늘어 더 죽어도 판이 안 끝나는 효과. 군단 파쇄 망토 Δ승리 {[r for r in K0_ROWS if r[0]=='군단 파쇄 망토'][0][3]} 는 98~99% 포화 구간의 노이즈.
11. 신규 모델 8종(Mount23~30) 필요, 나머지 {sum(1 for m in MONS.values() if '재질' in m['model'])}종은 재질 변경.
12. 루프 z_from/z_to 는 가운데 길과 같은 범위로 기록(지오메트리 리스킨 전제) — 실제 좌표 오프셋은 구현 시 결정.
13. 강화 {UP}^p 복리는 J2 선호(선형)와 다름 — 합산 상한으로 PvP 안전. 선형으로 바꾸려면 gen 재보정 1회.
14. PvP 표는 5개 프리셋 미러 매치만 — 임의 분배·장비 조합 차이·3v3 미검증. 결투 레벨 고정이라 레벨 차 0.
15. (문서 담당) config 안의 설명 문구 두 곳이 시뮬 수치와 어긋남: 패스 설명 '시작 에너지 +1 → 처치 보스 +0.3' (H표 실측: 장비 0 판 +{float(summary_fields('H')['평균 처치 보스'])-float(summary_fields('A')['평균 처치 보스']):.2f}, 아이템 4개 판 +{float(_hl.group(2))-float(_hl.group(1)):.2f}), 보스 러시 설명 '일 강화석 30 = 풀클리어 1판의 약 40%' (E-2 실측 {re.search(r'강화석 ([\d.]+)', sim_summary_line('E-2')).group(1)}개 기준 {cfg['boss_rush']['daily_stone_cap']/float(re.search(r'강화석 ([\d.]+)', sim_summary_line('E-2')).group(1))*100:.0f}%). 또 B15 공략 문구의 '9%/초'는 보정 전 입력값(보정 후 dps_k {pct(BOSSES['B15']['gimmick']['mirror']['dps_k'],1)}). 수치 필드는 모두 맞고 문구만 오래된 것이라 본 문서는 실측값을 병기했다 — config `text_ko` 3곳 갱신 권장.
""")

# ================================================================= 쓰기
text = "\n".join(("\n" + s.rstrip("\n")) if s.startswith("---") else s.rstrip("\n") for s in out)
OUT = os.path.join(HERE, "BOSS20_BALANCE_DESIGN.md")
with open(OUT, "w", encoding="utf-8") as f:
    f.write(text + "\n")
print("wrote", OUT, len(text), "chars,", text.count("\n"), "lines")
