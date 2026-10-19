#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BOSS20_BALANCE_DESIGN.md ↔ boss20_config.json / SIM_RESULT.txt 일치 검사.
1) 문서를 다시 생성해 파일과 같은지(= 문서가 설정·시뮬 최신인지)
2) 보스 20·몬스터 60·아이템 20·강화·상한·공식 상수가 문서에 같은 서식으로 들어 있는지
3) §13 코드 블록이 SIM_RESULT.txt 원문과 같은지
4) §0 핵심 수치가 SIM 요약 줄과 같은지
5) 이전 설계안(B)의 낡은 수치 문구가 남아 있지 않은지
실행: python3 verify_doc_boss20.py  → 종료 코드 0 = 일치"""
import json, os, re, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
DOC = os.path.join(HERE, "BOSS20_BALANCE_DESIGN.md")
cfg = json.load(open(os.path.join(HERE, "boss20_config.json"), encoding="utf-8"))
SIM = open(os.path.join(HERE, "SIM_RESULT.txt"), encoding="utf-8").read()
doc = open(DOC, encoding="utf-8").read()
errors = []

def big(x):
    x = float(x)
    if x >= 1e12: return f"{x/1e12:.2f}조"
    if x >= 1e8: return f"{x/1e8:.2f}억"
    if x >= 1e4: return f"{x/1e4:.1f}만"
    return f"{int(round(x)):,}"
def pct(x, d=0): return f"{x*100:.{d}f}%"

def need(cond, msg):
    if not cond:
        errors.append(msg)

# 1) 재생성 == 파일
before = doc
r = subprocess.run([sys.executable, os.path.join(HERE, "doc_boss20.py")], capture_output=True, text=True)
need(r.returncode == 0, "doc_boss20.py 실행 실패: " + r.stderr[-500:])
after = open(DOC, encoding="utf-8").read()
need(before == after, "문서가 최신이 아님: doc_boss20.py 재실행 결과가 파일과 다르다")
doc = after

# §13 코드 블록 분리 (본문 검사에서 제외)
m = re.search(r"```\n(.*?)\n```", doc, re.S)
need(m is not None, "§13 코드 블록 없음")
sim_block = m.group(1) if m else ""
need(sim_block.strip() == SIM.strip(), "§13 블록이 SIM_RESULT.txt 원문과 다름")
body = doc.replace(sim_block, "")

# 2) 보스 카드
for bid, b in cfg["bosses"].items():
    card = re.search(r"#### " + bid + r"\. .*?(?=\n#### |\n---)", body, re.S)
    need(card is not None, f"{bid} 카드 없음")
    if not card: continue
    c = card.group(0)
    need(b["name_ko"] in c, f"{bid} 이름")
    if b["hp"]:
        need(f"체력 {big(b['hp'])}" in c, f"{bid} 체력 {big(b['hp'])}")
        need(f"공격 {big(b['atk'])}" in c, f"{bid} 공격 {big(b['atk'])}")
    need(f"경험치 {big(b['exp'])}" in c, f"{bid} 경험치")
    need(f"체력바 {b['phases']}개(전환 무적 {b['transition_s']}초)" in c, f"{bid} 체력바/전환")
    need(f"장갑 {pct(b['hit_cap'],1)} → 최소 {b['min_hits']}타" in c, f"{bid} 장갑/최소 타수")
    need(f"권장 도착 레벨 **{big(b['recommended_level'])}**" in c, f"{bid} 권장 레벨")
    need(f"목표 전투 시간 {b['target_secs_natural']}초" in c, f"{bid} 목표 초")
    need(f"보정 {b['anchor']['calibrated_secs_median']}초, 사망 {b['anchor']['calibrated_deaths_mean']}" in c, f"{bid} 보정 초/사망")
    need(cfg["items"][b["drop_item"]]["name_ko"] in c, f"{bid} 드롭 아이템")
    need(f"{b['stone_tier']}급 강화석" in c, f"{bid} 강화석 급")
    need(f"처치 에너지 +{b['energy_reward']}" in c, f"{bid} 에너지")
    if b["spawn_condition"]:
        need(b["spawn_condition"]["text_ko"] in c, f"{bid} 등장 조건")
    # 6.2 표 행
    row = [l for l in body.splitlines() if l.startswith(f"| {bid} | ")]
    need(len(row) == 1, f"{bid} 6.2 표 행")
    if row:
        need(f"| {big(b['exp'])} | {big(b['recommended_level'])} | {b['target_secs_natural']} |" in row[0], f"{bid} 6.2 경험치/권장/목표")

# 몬스터 표
for mid, mo in cfg["monsters"].items():
    rows = [l for l in body.splitlines() if f"| {mid} | {mo['name_ko']} |" in l]
    need(len(rows) == 1, f"몬스터 {mid} 행")
    if rows:
        need(f"| {big(mo['hp'])} | {big(mo['atk'])} | {mo['interval']} | {mo['speed']} | {mo['spawn']} | {big(mo['exp'])} |" in rows[0], f"몬스터 {mid} 수치")

# 아이템 표 (기본값 + 설명)
for iid, it in cfg["items"].items():
    rows = [l for l in body.splitlines() if l.startswith(f"| {iid} | {it['name_ko']} | {it['boss']} | {it['slot']} | {it['tier']} | {it['rank']} |")]
    need(len(rows) == 1, f"아이템 {iid} 행")
    if rows:
        for e in it["effects"]:
            if e["k"] != "var":
                need(f"{e['k']}={e['v']:.3g}" in rows[0], f"아이템 {iid} 효과 {e['k']}")
        need(it["desc_ko"] in rows[0], f"아이템 {iid} 설명")

# 강화 표
S = cfg["stones"]
for i in range(S["max_plus"]):
    need(f"| +{i} → +{i+1} | {S['cost'][i]} | {S['essence_cost'][i]} | {pct(S['success'][i])} | {S['expected_tries_per_step'][i]} |" in body, f"강화 +{i+1} 행")
need(f"강화석 **{S['expected_stones_to_plus10']}개**, 정수 **{S['expected_essence_to_plus10']}개**" in body, "기대 소모")

# 상한표
for k, name in cfg["caps"]["names_ko"].items():
    need(f"| {name} | caps.*.{k} |" in body, f"상한표 {k}")

# 공식 상수·판 규칙 (닫힌 식 문자열)
F, C, R, st = cfg["formulas"], cfg["combat"], cfg["run"], cfg["stats"]
checks = {
    f"need(L) = {cfg['exp_curve']['n0']} × (1 + L/{cfg['exp_curve']['K']})^{cfg['exp_curve']['a']}": "경험치 식",
    f"{pct(F['crit']['base'])} + {pct(F['crit']['span'])}×행운/(행운 + {F['crit']['lvl_coef']}×레벨 + {F['crit']['c']})": "치명 식",
    f"{pct(F['lifesteal']['max_from_pts'])}×P/(P + {F['lifesteal']['lvl_coef']}×레벨 + {F['lifesteal']['c']})": "흡혈 식",
    f"max({pct(F['lifesteal']['heal_per_s_cap_base'])} + 성배, {F['lifesteal']['heal_per_s_ls_coef']}×흡혈률)": "초당 회복 상한 식",
    f"1 + S/(1 + S/{F['aspd']['half']})": "공속 식",
    f"R = min({F['range']['cap']}, {F['range']['base']} + 장비)": "범위 식",
    f"p = min({pct(F['luck_bonus']['p_cap'])}, {F['luck_bonus']['p_coef']}×행운/(행운 + {F['luck_bonus']['lvl_coef']}×레벨 + {F['luck_bonus']['c']}))": "행운! 식",
    f"한 타 ≤ 최대 체력 {pct(F['damage_taken']['player_hit_cap'])}": "받는 한 타 상한",
    f"시작 {R['energy_start']}, 전투 −{R['energy_fight']}": "에너지",
    f"가운데 보스 +{R['energy_boss_main']}, 루프 보스 +{R['energy_boss_loop']}": "보스 에너지",
    f"{C['fever_hits']}콤보 = 피버 {C['fever_dur_s']:.0f}초(공속 ×{C['fever_aspd']})": "피버",
    f"탭 성공률 {pct(C['manual_combo_p'])}": "탭 성공률",
    f"1칸 = {R['encounter']['stud_per_bar']} stud": "조우 게이지",
    f"레벨 1당 포인트 {st['pts_per_level']}": "포인트",
    f"| 체력 | {st['hp']['base']} | +{st['hp']['per_pt']} | {st['hp']['auto_ratio']} |": "체력 스탯",
    f"| 힘 | {st['atk']['base']} | +{st['atk']['per_pt']} | {st['atk']['auto_ratio']} |": "힘 스탯",
    f"×{S['upgrade_mult_per_plus']}^p": "강화 배율",
    f"결투 레벨 {cfg['pvp']['duel_level']:,}": "PvP 레벨",
    f"×{cfg['pvp']['dmg_mult']}": "PvP 피해 보정",
    f"max({pct(cfg['pvp']['dodge_floor'])}, 치명 확률 × {cfg['pvp']['dodge_from_crit']}) ≤ {pct(cfg['pvp']['dodge_cap'])}": "PvP 회피",
}
for p in cfg["monetization"]["products"]:
    checks[f"| {p['name_ko']} | "] = f"상품 {p['id']}"
    checks[f"| {p['price_robux']} | "] = f"가격 {p['id']}"
for name, r_ in cfg["builds"].items():
    checks[f"| {name} | " + ":".join(f"{r_[k]:g}" for k in ("hp", "atk", "luk", "ls")) + " |"] = f"빌드 {name}"
for s_, msg in checks.items():
    need(s_ in body, f"{msg} 문자열 없음: {s_}")

# 4) §0 핵심 수치 ↔ SIM 요약
KEY = dict(re.findall(r"(\w+)=([^\s]+)", SIM.split("### 핵심 수치 요약")[1]))
sec0 = body.split("## 1. ")[0]
need(f"1보스전 {KEY['first_boss_secs']}초, 사망 {KEY['first_boss_deaths']}" in sec0, "§0 첫 보스")
need(f"{float(KEY['full_clear_20_minutes']):.1f}분" in sec0, "§0 20보스 분")
need(KEY["natural_secs"] + "초" in sec0, "§0 자연 초")
need(KEY["pvp_pair_range"] in sec0, "§0 PvP 범위")
need(f"{KEY['ls_deaths_20']} vs {KEY['bal_deaths_20']}" in sec0, "§0 흡혈")
need(f"중간값 최단 {KEY['plus10_min_secs']}초, 절대 최단 {KEY['plus10_abs_min_secs']}초" in sec0, "§0 +10 최단")

# 5) 낡은 문구(B 안·v8 설명 열 제외) — 본문 어디에도 없어야 함
stale = ["에너지 14", "heal_per_hit_cap", "12%×P", "0.4×레벨", "타격당 회복 ≤ 최대 체력 6%", "탭 성공률 85%", "0.3초 안에 탭",
         "3.5~6%", "최소 13타", "회피율 = 치명타 확률 × 0.8", "하급 3개 → 중급 1개", "약 38개", "k = 1 + floor(0.5×log2", "강화 보호 두루마리 | 49",
         "흡혈 ≤20%", "초당 회복 ≤최대 체력 4%", "×0.035 (PvE"]
for s_ in stale:
    need(s_ not in body, f"낡은 문구 남음: {s_}")

# 표 구조
lines = body.split("\n")
i = 0
while i < len(lines):
    if lines[i].startswith("|"):
        hdr = lines[i].count("|")
        need(i + 1 < len(lines) and lines[i + 1].startswith("|---"), f"표 구분선 없음 (줄 {i+1})")
        j = i
        while j < len(lines) and lines[j].startswith("|"):
            need(lines[j].count("|") == hdr, f"표 셀 수 불일치 (줄 {j+1})")
            j += 1
        i = j
    else:
        i += 1

print(f"검사 항목 통과, 오류 {len(errors)}건")
for e in errors:
    print(" -", e)
sys.exit(1 if errors else 0)
