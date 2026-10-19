#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
boss20_config.json 생성기 (최종 통합 설계). 설계 입력(철학 수치) → 앵커(기대 도착 레벨·자연 장비) → 몬스터/보스 수치 → 보정 → JSON.
실행:  python3 gen_boss20.py            # boss20_config.json 생성 (앵커·40회 보정 포함, 약 20~40초)
       python3 gen_boss20.py --check    # 다시 생성한 결과가 파일과 완전히 같은지 검증 (D_math 식 규율). 다르면 종료 코드 1
의뢰자는 JSON 만 읽어도 된다. 이 파일은 "왜 그 숫자인가"의 기록이다.
"""
import json, os, sys, math, random, statistics, copy
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sim_boss20 as S

OUT = os.path.join(HERE, "boss20_config.json")


def nice(x, sig=3):
    if x <= 0:
        return 0
    e = math.floor(math.log10(x))
    m = 10 ** (e - sig + 1)
    return int(round(x / m) * m) if e >= sig - 1 else round(x, sig - 1 - e)


def build_config():
    cfg = {}
    cfg["meta"] = {
        "id": "boss20_final", "title": "레벨 폭발 모험단 — 20보스 최종 통합 설계 (B_dopamine 뼈대 + A/C/D 이식)", "version": "1.1",
        "units": "체력/공격력/경험치 정수, 시간 초, 거리 stud",
        "skeleton": "B_dopamine (앵커 보정·체력바·타격 상한·피버·need(L)=10(1+L/1000)^0.3·3길)",
        "grafts": ["A: 흡혈 초당 상한 max(5%, 0.8×흡혈률), 험로 루프 에너지(2전투 −2 + 보스 +5), 숨은 보스 조건 4종, 치명 관통/장갑 보스, 도박 구역 1회 소진",
                   "C: PvE/PvP 상한표 + pvp_disabled, 누진 사망 비용 3·4·5·6, 보스 고유 정수(+5 이상), 3연속 실패 천장, 7일 무료 체험·순간이동권·기록의 책·보스 러시",
                   "D: 보스 성향(목표 초 ×, 공격 ×), 행운 보너스 '포인트 2배 당첨 p≤0.5', 제단 입장 체력 가득, 하위 5→상위 1 교환, 워프 제단, --check 재생성 검증, 재처치 무사망 +1 강화석"],
        "notes": [
            "자동 타격과 버튼 평타는 1.0초 쿨다운을 공유한다 (v7 1.1/0.6 → 변경: 탭 속도 우위 제거, PvP 예측 가능).",
            "리듬 탭(쿨다운 뒤 0.5초 창) 성공 = 콤보 +1, 실패 = 유지, 1.5초 무입력 = 0. 10콤보 = 피버 5초(공속 ×1.5). 보정 기준 탭 성공률 0.6(보수적).",
            "보스 타격당 피해 상한(hit_cap, 장갑) 3~5%. 치명타는 상한 ×1.5(관통), 광전사 반지로 ×2.0, 일부 보스는 관통 ×1.2 제한. 풀 +10 에서도 보스전 ≥10초가 되게 빠른 보스 9종의 상한을 0.5%p 낮췄다(v1.1).",
            "플레이어가 받는 한 타격 상한 = 최대 체력 75%. 어느 쪽도 한 방 즉사 없음.",
            "한 판 = 가운데 길 10단계 + (5단계 광장) 질풍 루프 5구간 + (10단계 광장) 군단 루프 5구간 = 보스 20. 루프는 선택.",
        ],
    }
    cfg["stats"] = {
        "hp":  {"name_ko": "체력", "base": 100, "per_pt": 10, "auto_ratio": 1.0, "desc_ko": "최대 체력 = (100 + 10×체력pt) × 장비 체력 배율"},
        "atk": {"name_ko": "힘",   "base": 10,  "per_pt": 2,  "auto_ratio": 2.0, "desc_ko": "공격력 = (10 + 2×힘pt) × 장비 공격 배율. 피해 = 공격력 × U(0.9,1.1) × 치명 배율"},
        "luk": {"name_ko": "행운", "base": 1,   "per_pt": 1,  "auto_ratio": 0.5, "desc_ko": "치명타 확률, 레벨업 '행운! 2배 당첨' 확률, 정수 추가 드롭, (PvP) 회피"},
        "ls":  {"name_ko": "흡혈", "base": 0,   "per_pt": 1,  "auto_ratio": 0.5, "desc_ko": "포인트 P → 흡혈% = 30%×P/(P + 1.0×레벨 + 50) (장비와 합산; 균형 분배 ≈9%, 흡혈 2배 분배 ≈13%, 몰빵 ≈20%). 초당 회복 상한(0.8×흡혈률)을 함께 올린다"},
        "pts_per_level": 3,
    }
    cfg["formulas"] = {
        "crit": {"base": 0.05, "span": 0.60, "lvl_coef": 0.5, "c": 40, "mult_base": 2.0,
                 "text_ko": "치명타 확률 = min(상한, 5% + 60%×행운/(행운 + 0.5×레벨 + 40) + 장비). 치명타 피해 = min(상한, ×2.0 + 장비). 보스 상한 관통 ×1.5(기본)."},
        "luck_bonus": {"p_coef": 0.5, "lvl_coef": 0.5, "c": 50, "p_cap": 0.5, "double_mult": 2.0,
                       "text_ko": "레벨 1 오를 때마다 확률 p = min(50%, 0.5×행운/(행운 + 0.5×레벨 + 50)) 로 그 레벨의 포인트 3 → 6 ('행운!' 팝). 기대 포인트 = 3×(1+p) ≤ 4.5 (상한 ×1.5). 고레벨은 '행운 ×n' 묶음 표시."},
        "lifesteal": {"max_from_pts": 0.30, "lvl_coef": 1.0, "c": 50, "heal_per_s_cap_base": 0.05, "heal_per_s_ls_coef": 0.8,
                      "text_ko": "흡혈% = min(상한, 30%×P/(P + 1.0×레벨 + 50) + 장비). 초당 회복 상한 = max(5% + 성배, 0.8×흡혈률) × 최대 체력 (스윙당 상한 = 그 값 × 공격 간격) → 공속을 올려도 회복은 늘지 않고, 흡혈에 투자하면 상한이 오른다. 보스 기믹으로 흡혈 ×0.5."},
        "aspd": {"half": 1.5, "fever_abs_cap": 2.5,
                 "text_ko": "공속 배율 = 1 + S/(1 + S/1.5), S = 장비 공속 보너스 합. S 0.6→1.43, 0.9→1.56, 1.2→1.67, ∞→2.5(상한). 음수는 1+S. 피버 ×1.5 는 별도, 절대 상한 ×2.5(간격 0.40초 — 풀 +10 보스전 10초 하한을 지키는 선)."},
        "range": {"base": 9, "cap": 18, "per_target": 3,
                  "text_ko": "공격 범위 R = min(18, 9 + 장비). 동시 타격 수 = min(살아있는 적, 상한, 1 + floor((R−9)/3)). 13.5 → 2마리, 15+ → 3마리."},
        "damage_taken": {"player_hit_cap": 0.75, "zone_dmg_mult": 1.5, "var_lo": 0.9, "var_hi": 1.1,
                         "text_ko": "받는 피해 = 몬스터 공격력 × U(0.9,1.1) × (1−피해감소) × (도박 구역 1.5). 한 타격 상한 = 최대 체력 75%. 사망 시 그 자리 부활·체력 가득·무적 2.5초(+수호 부적), 적 체력 유지."},
        "exp_gain": {"zone_exp_mult": 2.0,
                     "text_ko": "획득 경험치 = 몬스터 경험치 × 장비 경험치 배율 × (도박 구역 ×2, 행운의 왕관 +0.5) × (보스: 영혼 왕관 ×2)."},
    }
    cfg["caps"] = {
        "text_ko": "장비·강화·스탯을 아무리 쌓아도 못 넘는 선. PvE 열은 판에서, PvP 열은 마을 결투장에서. 같은 코드가 열만 바꿔 읽는다.",
        "pve": {"aspd_mult": 2.5, "lifesteal": 0.30, "heal_per_s_max": 0.20, "crit_p": 0.60, "crit_mult": 4.0, "crit_pierce": 2.0,
                "dmg_reduce": 0.40, "reflect": 0.30, "splash": 0.50, "range_targets": 3, "exp_mult": 3.5, "boss_exp_mult": 2.0,
                "atk_mult": 3.5, "hp_mult": 2.0, "hit_taken_cap": 0.75, "dmg_mult": 1.0},
        "pvp": {"aspd_mult": 2.2, "lifesteal": 0.30, "heal_per_s_max": 0.06, "crit_p": 0.50, "crit_mult": 3.0, "crit_pierce": 1.0,
                "dmg_reduce": 0.40, "reflect": 0.10, "splash": 0.15, "range_targets": 2, "exp_mult": 1.0, "boss_exp_mult": 1.0,
                "atk_mult": 2.5, "hp_mult": 2.0, "hit_taken_cap": 0.12, "dmg_mult": 0.08},
        "names_ko": {"aspd_mult": "공속 배율", "lifesteal": "흡혈률", "heal_per_s_max": "초당 회복 상한 최대", "crit_p": "치명 확률", "crit_mult": "치명 피해",
                     "crit_pierce": "상한 관통", "dmg_reduce": "피해감소", "reflect": "반격", "splash": "스플래시", "range_targets": "동시 타격 수",
                     "exp_mult": "경험치 배율", "boss_exp_mult": "보스 경험치 배율", "atk_mult": "공격 배율", "hp_mult": "체력 배율",
                     "hit_taken_cap": "받는 한 타 상한(최대 체력 비율)", "dmg_mult": "피해 보정"},
    }
    cfg["exp_curve"] = {"n0": 10, "K": 1000, "a": 0.30,
                        "text_ko": "need(L) = 10×(1+L/1000)^0.3. 누적 E(L) = 7692.3×((1+L/1000)^1.3 − 1.0013). 역함수 L(E) = 1000×((E/7692.3 + 1.0013)^(1/1.3) − 1). need(1)=10, need(1만)=20.5, need(100만)=79, need(1억)=316."}
    cfg["combat"] = {
        "attack_interval": 1.0, "button_shares_cooldown": True, "button_range": 11, "auto_range": 9,
        "first_hit": 1.2, "approach_s": 0.5, "crit_cap_mult": 1.5,
        "zone_p_manual": 0.35, "zone_p_auto": 0.22, "zone_once_per_zone": True,
        "max_fight_s": 240, "revive_invuln": 2.5, "death_anim_s": 1.5, "spawn_s": 2.0, "loot_s": 0.8,
        "boss_intro_s": 3.0, "door_s": 4.0, "after_fight_heal": 0.5, "regen_per_s": 0.06,
        "fever_hits": 10, "fever_dur_s": 5.0, "fever_aspd": 1.5, "manual_combo_p": 0.6, "tap_window_s": 0.5, "combo_idle_reset_s": 1.5,
        "monster_attack_reach": "3.2 + 반지름", "monster_windup_s": 0.45,
        "timing": {"add_spawn_stagger_s": 0.3, "boss_attack_after_transition_s": 0.8, "boss_attack_delay_after_transition_hit_s": 0.6, "boss_attack_delay_after_stagger_s": 0.4,
                   "near_miss_hp_frac": 0.15, "no_boss_door_s_mult": 0.5,
                   "text_ko": "소환수는 0.3초 간격으로 순차 등장. 체력바 전환이 끝난 뒤 보스 첫 공격 0.8초. 전환/그로기 중 공격 차례가 돌아온 보스는 각각 0.6/0.4초 뒤에 공격. 니어미스 = 체력 15% 이하로 떨어졌다가 무사망 승리. 조건부 보스가 안 나온 구간의 문 열림 연출 = 4초×0.5."},
        "text_ko": "도박 구역: 반지름 10, 구간마다 2~3곳, 그 안에서 시작한 전투는 경험치 ×2·받는 피해 ×1.5, 전투 1회 뒤 그 구역은 이번 판 소진. 수동 35%/자동 22% 의 전투가 구역에서 시작. 전투 종료 시 최대 체력 50% 즉시 회복 + 비전투 초당 6%. 보스 제단 입장 시 체력 가득.",
    }
    cfg["run"] = {
        "energy_start": 16, "energy_fight": 1, "energy_death_base": 3, "energy_death_step": 1, "energy_death_max": 6,
        "energy_boss_main": 4, "energy_boss_loop": 5, "boss_altar_full_heal": True, "death_counter_reset_at_plaza": True,
        "move_speed": 20, "village_to_gate_s": 14, "result_s": 5,
        "encounter": {"stud_per_bar": 25, "bars_full": 6, "start_bar": 3, "p_per_s_per_bar": 0.15, "target_fights_main": 4, "target_fights_loop": 2,
                      "text_ko": "조우 게이지 1칸 = 25 stud. 3칸부터 매초 칸수×15%. 가운데 길 구간당 4전투, 루프 구간당 2전투가 되도록 길이를 맞춤."},
        "warp": {"unlock_kills": 3, "start_energy": 12, "level_factor": 0.9, "warp_s": 5,
                 "text_ko": "워프 제단: 광장 문 보스(청색의 드래곤/황제 드래곤)를 3회 처치하면 그 광장에서 판 시작 가능(레벨 = 그 광장 기준 진입 레벨 ×0.9, 에너지 12). 워프 판은 기록판에 '워프' 표식, 20보스 기록 제외."},
        "text_ko": "시작 에너지 16, 전투 승리 −1, 사망 n번째 = min(6, 3+(n−1)) → 3,4,5,6,6…(1~2번은 전략, 3번부터 벌), 가운데 보스 +4, 루프 보스 +5(그 전투는 −1 없음). 루프 구간 = 2전투 −2 + 보스 +5 = 순이익 +3 → '장비 갖춘 뒤 들어가는 에너지 광산'. 사망 누진 카운터는 광장(루프 입·출구)을 지날 때 0 으로 초기화('광장 휴식': 한 장(章) 안에서 3번부터 벌). 에너지 0 또는 복귀 = 판 종료(레벨 1·포인트 0, 장비·강화·강화석·정수·기록 유지). 문은 이번 판에 그 보스를 잡아야 열림. 조건부 보스가 등장하지 않은 구간은 문이 바로 열린다(보상 없음).",
    }
    cfg["slots"] = {"무기": 1, "정령": 1, "반지": 2, "망토": 1, "왕관": 1, "부적": 1}

    def E(k, v, up=True, **kw):
        d = {"k": k, "v": v, "up": up}
        d.update(kw)
        return d

    cfg["items"] = {
        "I01": dict(name_ko="엄니검", boss="B01", slot="무기", tier=1, rank=1, effects=[E("atk_mult_bonus", 0.35)], pvp_disabled=[],
                    desc_ko="공격력 ×1.35 (힘 기반 배율 — 레벨과 함께 자란다). +10강 ×1.76.", pvp_ko="허용"),
        "I02": dict(name_ko="바람 정령", boss="B02", slot="정령", tier=1, rank=1, effects=[E("S", 0.60)], pvp_disabled=[],
                    desc_ko="공속 보너스 S +0.6 → 배율 1.43(단독). +10강 S 1.30 → 1.70.", pvp_ko="허용(공속 상한 2.2)"),
        "I03": dict(name_ko="흡혈 송곳니", boss="B03", slot="반지", tier=1, rank=2, effects=[E("ls", 0.05)], pvp_disabled=[],
                    desc_ko="흡혈 +5%p (총 30% 상한, 초당 회복 상한도 0.8×흡혈률로 오름). +10강 +10.8%p.", pvp_ko="허용(흡혈 상한 30%·초당 회복 6%)"),
        "I04": dict(name_ko="거인 망토", boss="B04", slot="망토", tier=1, rank=1, effects=[E("range_add", 4.5), E("move_bonus", 0.10, up=False)], pvp_disabled=[],
                    desc_ko="공격 범위 9→13.5 stud = 동시에 2마리. 이동속도 +10%. +10강 범위 +9.7 → 3마리.", pvp_ko="3v3 에서만 의미(2마리 상한)"),
        "I05": dict(name_ko="에테르 왕관", boss="B05", slot="왕관", tier=1, rank=1, effects=[E("exp_mult_bonus", 0.50)], pvp_disabled=["exp_mult_bonus"],
                    desc_ko="얻는 경험치 ×1.5 (레벨 ×1.37). +10강 ×2.08 (총 ×3.5 상한).", pvp_ko="무효(결투는 레벨 고정)"),
        "I06": dict(name_ko="광전사 반지", boss="B06", slot="반지", tier=2, rank=3, effects=[E("crit_dmg", 0.50), E("ls_crit_mult", 2.0, up=False), E("crit_pierce_add", 0.5, up=False)], pvp_disabled=["crit_pierce_add"],
                    desc_ko="치명타 피해 ×2 → ×2.5, 치명타 시 흡혈 2배, 보스 장갑 관통 ×1.5 → ×2.0(행운에 '장갑 뚫기' 역할). +10강 ×3.08.", pvp_ko="허용(치명 ×3 상한, 관통 무효)"),
        "I07": dict(name_ko="용암 망토", boss="B07", slot="망토", tier=2, rank=3, effects=[E("dmg_reduce", 0.15), E("range_add", 3.0, up=False), E("reflect", 0.10)], pvp_disabled=[],
                    desc_ko="받는 피해 −15%(총 40% 상한), 받은 피해의 10% 반격, 범위 +3(2마리). +10강 −32%/22%.", pvp_ko="허용(반격 10% 상한)"),
        "I08": dict(name_ko="번개 정령", boss="B08", slot="정령", tier=2, rank=2, effects=[E("S", 0.70), E("nth_crit", 5, up=False)], pvp_disabled=[],
                    desc_ko="공속 S +0.7, 매 5번째 타격은 치명타 확정(번개) — 저주 보스의 답. +10강 S 1.51.", pvp_ko="허용"),
        "I09": dict(name_ko="수호 부적", boss="B09", slot="부적", tier=2, rank=1, effects=[E("revive_invuln_add", 2.0), E("first_death_cost", 1, up=False), E("dmg_reduce", 0.05, up=False)], pvp_disabled=["revive_invuln_add", "first_death_cost"],
                    desc_ko="부활 무적 2.5→4.5초, 판마다 첫 사망의 에너지 −3 → −1, 받는 피해 −5%. +10강 무적 +4.3초.", pvp_ko="피해감소 5%만 허용"),
        "I10": dict(name_ko="파멸의 대검", boss="B10", slot="무기", tier=2, rank=3, effects=[E("atk_mult_bonus", 0.60), E("S", -0.15, up=False), E("cap_add", 0.01, up=False)], pvp_disabled=["cap_add"],
                    desc_ko="공격력 ×1.6, 공속 −15%, 보스 타격 상한 +1%p(한계 돌파). +10강 ×2.30.", pvp_ko="허용(상한 보너스 무효)"),
        "I11": dict(name_ko="질풍의 반지", boss="B11", slot="반지", tier=3, rank=1, effects=[E("S", 0.15), E("move_bonus", 0.25, up=False), E("first_hits_fast", 3, up=False), E("first_hits_mult", 2.0, up=False)], pvp_disabled=[],
                    desc_ko="공속 S +0.15, 이동속도 +25%, 전투 시작 첫 3타 간격 절반(선제 러시). +10강 S 0.32.", pvp_ko="허용"),
        "I12": dict(name_ko="폭풍 정령", boss="B12", slot="정령", tier=3, rank=3, effects=[E("S", 0.90), E("crit_p_add", -0.10, up=False)], pvp_disabled=[],
                    desc_ko="공속 S +0.9(배율 1.56 단독), 치명타 확률 −10%p. 보호막 보스의 답. +10강 S 1.94.", pvp_ko="허용"),
        "I13": dict(name_ko="광풍 망토", boss="B13", slot="망토", tier=3, rank=2, effects=[E("range_add", 7.5), E("splash", 0.30)], pvp_disabled=[],
                    desc_ko="범위 9→16.5(3마리), 범위 밖 적에게도 피해의 30% 스플래시. +10강 스플래시 50%(상한).", pvp_ko="3v3: 스플래시 15%"),
        "I14": dict(name_ko="행운의 왕관", boss="B14", slot="왕관", tier=3, rank=2, effects=[E("luk_mult_bonus", 0.50), E("zone_exp_bonus", 0.5, up=False), E("exp_mult_bonus", 0.40)], pvp_disabled=["zone_exp_bonus", "exp_mult_bonus"],
                    desc_ko="행운 ×1.5(치명·당첨·정수 공식에 적용), 도박 구역 ×2→×2.5, 경험치 ×1.4. +10강 행운 ×2.08.", pvp_ko="행운 배율만 허용(회피 ↑)"),
        "I15": dict(name_ko="질풍검", boss="B15", slot="무기", tier=3, rank=2, effects=[E("atk_mult_bonus", 0.25), E("S", 0.30), E("var", 0, up=False, lo=0.7, hi=1.5)], pvp_disabled=[],
                    desc_ko="공격력 ×1.25, 공속 S +0.3, 피해 분산 0.9~1.1 → 0.7~1.5(평균 +10%, 큰 숫자가 자주 뜬다). +10강 ×1.54.", pvp_ko="허용"),
        "I16": dict(name_ko="군단 파쇄 망토", boss="B16", slot="망토", tier=4, rank=4, effects=[E("range_add", 6.0), E("multi_atk_bonus", 0.25), E("dmg_reduce", 0.15, up=False)], pvp_disabled=["multi_atk_bonus"],
                    desc_ko="범위 9→15(3마리), 적이 2마리 이상이면 공격력 +25%, 받는 피해 −15%(군단 갑주, 강화 안 됨 — 1:1 보스에서 용암 망토 +0 대신 껴도 손해가 아니게; 용암 망토는 강화하면 −32%·반격으로 1:1 전용). +10강 범위 +13(상한 18), +54%.", pvp_ko="3v3 에서만 의미(피해감소 15% 는 허용)"),
        "I17": dict(name_ko="피의 성배", boss="B17", slot="반지", tier=4, rank=4, effects=[E("ls", 0.07), E("heal_cap_s_add", 0.03), E("hp_mult_bonus", -0.05, up=False)], pvp_disabled=["heal_cap_s_add"],
                    desc_ko="흡혈 +7%p, 초당 회복 상한 기본 5%→8%(유일한 상한 해제 아이템), 최대 체력 −5%(피의 대가). +10강 +15%p / 상한 +6.5%p.", pvp_ko="허용(흡혈 상한 30%, 회복 상한 해제 무효)"),
        "I18": dict(name_ko="군주의 부적", boss="B18", slot="부적", tier=4, rank=2, effects=[E("energy_start", 3, up=False), E("energy_boss", 1, up=False)], pvp_disabled=["energy_start", "energy_boss"],
                    desc_ko="시작 에너지 +3, 보스 처치 에너지 +1. 강화 불가(판 길이 자원은 고정).", pvp_ko="무효"),
        "I19": dict(name_ko="영혼 왕관", boss="B19", slot="왕관", tier=4, rank=3, effects=[E("exp_mult_bonus", 0.50), E("boss_exp_mult_bonus", 1.0, up=False)], pvp_disabled=["exp_mult_bonus", "boss_exp_mult_bonus"],
                    desc_ko="경험치 ×1.5, 보스 경험치 추가 ×2(상한 ×2 — 기록용 왕관). +10강 경험치 ×2.08.", pvp_ko="무효"),
        "I20": dict(name_ko="종언의 정령", boss="B20", slot="정령", tier=4, rank=4, effects=[E("S", 0.80), E("splash", 0.15, up=False), E("ls", 0.03), E("crit_dmg", 0.30)], pvp_disabled=[],
                    desc_ko="공속 S +0.8, 스플래시 15%, 흡혈 +3%p, 치명타 피해 +0.3. 최종 올라운더. +10강 S 1.73/흡혈 6.5%p/치명 +0.65.", pvp_ko="허용"),
    }
    cost = [1, 1, 2, 2, 3, 3, 4, 4, 5, 5]
    success = [1.0, 1.0, 1.0, 1.0, 1.0, 0.85, 0.75, 0.65, 0.55, 0.45]
    essence_cost = [0, 0, 0, 0, 1, 1, 2, 3, 4, 6]
    pity = 3
    exp_tries = [sum((1 - s) ** k for k in range(pity)) for s in success]   # 천장 3: 기대 시도 = 1 + (1−p) + (1−p)²
    cfg["stones"] = {
        "upgrade_mult_per_plus": 1.08, "max_plus": 10,
        "tiers": {"1": "하급 강화석(수정) — 가운데 길 1~5", "2": "중급 강화석(강철) — 가운데 길 6~10", "3": "상급 강화석(질풍) — 질풍 루프", "4": "최상급 강화석(종언) — 군단 루프"},
        "drop": {"first_kill": 2, "repeat_kill": 1, "repeat_bonus_p": 0.25, "repeat_bonus_n": 1, "no_death_bonus": 1,
                 "text_ko": "보스 첫 처치: 아이템 + 그 급 강화석 2개 + 정수 2개. 재처치: 강화석 1개(25% 로 2개) + 정수 1개(+추가 확률). 그 보스전 무사망이면 강화석 +1. 일반 몬스터는 드롭 없음."},
        "cost": cost, "success": success, "pity_fails": pity, "essence_cost": essence_cost,
        "essence_drop": {"first_kill": 2, "repeat_kill": 1, "extra_base": 0.10, "extra_luck_coef": 0.30,
                         "text_ko": "정수(보스 고유 ess_Bxx) 추가 1개 확률 = 0.10 + 0.30×r, r = 행운/(행운 + 0.5×레벨 + 50). +5 이상 강화에만 들며 성공 시에만 소모."},
        "exchange": {"lower_to_upper": 5, "text_ko": "하위 강화석 5개 → 상위 1개(역방향 불가). 하위 급이 +10 뒤 죽은 통화가 되지 않게."},
        "fail_rule_ko": "실패 시 강화석만 소모, 단계 하락·파괴 없음. 같은 단계 3회 연속 실패 시 다음은 확정 성공(천장, UI '다음은 확정'). 정수는 성공 시에만 소모.",
        "expected_tries_per_step": [round(x, 3) for x in exp_tries],
        "expected_stones_to_plus10": round(sum(c * t for c, t in zip(cost, exp_tries)), 1),
        "expected_essence_to_plus10": sum(essence_cost),
        "text_ko": "강화 +p 는 up:true 효과값에 1.08^p (+5 ×1.47, +10 ×2.16). 합산 상한(caps)에 걸리므로 강화가 PvP 를 망가뜨리지 않는다. 강화석·정수 판매 없음.",
    }
    cfg["builds"] = {
        "균형(기본)": {"hp": 1.0, "atk": 2.0, "luk": 0.5, "ls": 0.5},
        "속공(위험)": {"hp": 1.0, "atk": 2.25, "luk": 0.5, "ls": 0.25},
        "흡혈 균형": {"hp": 1.0, "atk": 1.75, "luk": 0.5, "ls": 0.75},
        "탱커": {"hp": 1.5, "atk": 1.5, "luk": 0.5, "ls": 0.5},
        "행운 도박": {"hp": 1.0, "atk": 1.75, "luk": 1.0, "ls": 0.25},
    }
    cfg["monetization"] = {
        "pass_energy_bonus": 0,
        "trial_days": 7,
        "auto_adventure": {"free_per_day": 3, "pass_per_day": 6, "stone_rate": 0.5, "manual_runs_per_day_assumed": 5, "first_kill": False, "records": False, "speed_free": 2, "speed_pass": 8,
                           "text_ko": "자동 모험: 피버 없음·구역 22%·브레스 회피 35%·조건 보스는 운에 맡김 → 항상 수동보다 손해. 이미 잡은 보스까지만, 강화석·정수 50%, 첫 처치·기록 없음. 무료 3회/일, 패스 6회/일."},
        "rules_ko": "꾸미기·치장 상품 없음. 확률형 유료 뽑기 없음. 강화석·정수·에너지·강화 보호권·레벨 직접 판매 없음(B의 강화 보호 두루마리 삭제). 결과(레벨·클리어·PvP 전력)를 크게 바꾸지 않는 시간·정보·사회·도전권 상품만. 계정 성장 속도 영향 ≤ ×1.3(시뮬 O표).",
        "products": [
            {"id": "pass", "name_ko": "모험 패스 (월 정액)", "price_robux": 399, "trial_ko": "첫 7일 무료 체험 → 8일째 자동 모험 6→3회·배속 8→2 로 축소(상실감이 전환 트리거, 결과 손해 없음)",
             "effects_ko": ["자동 모험 3→6회/일, 빨리감기 ×8(무료 ×2)", "장비 프리셋 3개(무료 1개) — 제단 앞 교체가 한 번에", "리플레이 30개·공유 카드", "상세 통계(DPS·상한 타격 비율·피버·행운! 횟수)", "에너지 보너스 없음 — B 안의 '시작 에너지 +1' 은 시뮬 H표에서 처치 보스 +0.3 으로 측정되어 삭제"],
             "why_no_result_ko": "판의 전투·보상 규칙은 무료와 동일. 자동 모험은 첫 처치 없음·50% → 계정 성장 ≤×1.3(O표). H표가 '+1 에너지를 팔면 어떻게 되는가'를 기록."},
            {"id": "teleport", "name_ko": "순간이동권 (영구)", "price_robux": 149,
             "effects_ko": ["마을 ↔ 갈림길 광장 ↔ 루프 입구 순간이동(루프 입출 6초×4 + 마을 문 14초 = 판당 약 40초 절약)", "판 종료 결산 즉시 스킵"],
             "why_no_result_ko": "전투·조우·보상 동일. 20보스 판 18분 중 이동 약 2.2분의 일부만 줄인다."},
            {"id": "record_book", "name_ko": "기록의 책", "price_robux": 99,
             "effects_ko": ["보스별 최단 처치 기록·빌드 저장", "판 리플레이 공유 코드(시드 기록 → 같은 빌드·시드 = 같은 결과)", "서버 리더보드 등록"],
             "why_no_result_ko": "기록·공유만."},
            {"id": "festival", "name_ko": "축제 깃발 (서버 전체)", "price_robux": 99,
             "effects_ko": ["구매자 이름 서버 공지 + 10분간 서버 모두의 도박 구역 ×2 → ×2.5, 구역 1곳 추가", "결산·공유 카드·기록판에 '깃발 판' 표식 강제(기록 오염 방지)"],
             "why_no_result_ko": "서버 전원 대칭. 레벨 기록 +약 10%(구역 전투 35% × 1.25) 이지만 표식으로 분리."},
            {"id": "lens", "name_ko": "관찰 렌즈 (영구)", "price_robux": 149,
             "effects_ko": ["보스 체력바에 페이즈 경계·그로기/브레스/폭주 타이머 표시, 숫자에 '한계!'·'장갑!' 표기", "제단 앞 조건부 보스 조건 표시"],
             "why_no_result_ko": "정보 상품. 보스는 결정적이라 숙련자는 외운다."},
            {"id": "crystal", "name_ko": "예측 수정구", "price_robux": 49, "bundle_ko": "10개",
             "effects_ko": ["제단 앞 예측 카드: 현재 빌드로 이 보스 '예상 32초·사망 1.1 → 거북 반지면 25초·0.6' (서버가 같은 규칙으로 40회 시뮬)", "자동 모험(시뮬) 추가 실행권. 하루 무료 3회"],
             "why_no_result_ko": "정보만. 실제 판은 조우가 랜덤이라 공략 계획 도구."},
            {"id": "rush_tickets", "name_ko": "보스 러시 도전권 3장", "price_robux": 49,
             "effects_ko": ["20보스 연속 타임어택(결투 레벨 100,000 고정·장비·강화만, 에너지 없음). 보상 기록 + 강화석(일 상한 30). 무료 1장/일"],
             "why_no_result_ko": "PvP 와 같은 축(장비·강화만)에서 경쟁을 미리 학습. 강화석 일 30 = 풀클리어 1판의 약 40%."},
        ],
        "free_paths_ko": ["워프 제단: 광장 문 보스 3회 처치로 무료 해금(유료 즉시 해금 없음)", "자동 모험 3회/일", "예측 수정구 3회/일", "보스 러시 1장/일", "리플레이 5개"],
    }
    cfg["pvp"] = {
        "duel_level": 100000, "time_limit_s": 60, "dmg_mult": 0.08, "dodge_from_crit": 0.35, "dodge_cap": 0.25, "dodge_floor": 0.10, "fever": False, "first_swing_delay_s": [0.3, 0.7],
        "points_fixed": True, "heal_per_hit_hp_frac": 0.12, "heal_basis": "geomean",
        "caps_ref": "caps.pvp",
        "text_ko": "마을 결투장: 두 플레이어 모두 결투 레벨 100,000 으로 정규화(각자 저장된 분배 비율대로 포인트), 장착 장비·강화만 그대로. 주는 피해 ×0.08, 한 타 ≤ 상대 최대 체력 12%(최소 9타), 공속 ≤2.2, 흡혈 ≤30%(PvE 와 같음 — 20% 로 자르면 흡혈 빌드의 유일한 결투 장점이 사라져 전패했다), 초당 회복 ≤6%, 치명 ≤50%·×3, 피해감소 ≤40%, 반격 ≤10%, 관통 없음, 피버 없음. 회피 = max(10%, 치명 확률 ×0.35) ≤25% (행운 = 결투 방어 스탯, 행운 0 도 하한 10%; 0.5 면 행운이 흡혈을 압도해 흡혈 균형이 전패). 결투 포인트는 레벨 100,000 분량(300,000)으로 고정(행운 당첨 없음 — 당첨은 PvE 전용). 결투 흡혈: 타격당 회복 = 흡혈률 × √(내 최대 체력 × 상대 최대 체력) × 12% (PvE 의 '피해 비례' 회복은 공격형만, '내 체력 비례'는 체력형만 유리해져 승률이 0/100 으로 갈림 — 기하평균이 둘을 중립화, 시뮬 L표로 확인), 초당 ≤6%. 60초 후 체력% 높은 쪽 승. pvp_disabled 효과(경험치·에너지·상한 돌파·부활·보스 경험치) 무효. 3v3 에서 범위 2마리·스플래시 15%.",
    }
    cfg["boss_rush"] = {"level": 100000, "death_penalty_s": 10, "daily_stone_cap": 30, "free_tickets_per_day": 1,
                        "text_ko": "보스 러시: 결투 레벨 100,000 고정·장비·강화만, 20보스 연속(조건 무시), 사망 = +10초 페널티·체력 가득 부활, 합계 초 기록. 결투장 공간·UI 재사용."}
    cfg["hidden_conditions"] = {
        "prev_boss_secs_max": "직전 보스를 N초 안에 처치 (피버·그로기·공속의 보상)",
        "zone_fight_this_stage": "이 구간의 도박 구역에서 전투 1회 승리 (선택이 곧 조건)",
        "no_death_prev_boss": "직전 보스전 무사망 (숙련)",
        "all_prev_loop_bosses": "이 루프의 앞 보스 전부 이번 판 처치 (험로 전부)",
        "text_ko": "조건 미충족 시 제단에 흔적(발자국·시계 소리·거울 파편)만 남고 문이 바로 열린다. 조건은 전부 JSON(bosses[].spawn_condition), 코드에는 판정 함수 1개.",
    }
    cfg["release_plan_ko"] = [
        "1차(2~3주): 가운데 길 10보스·10아이템·1~2급 강화석·정수·패스·피버 OFF(쿨다운 공유만) — 시뮬 I표 성립",
        "2차: 질풍 루프 5보스(가운데 길 Z 지오메트리 리스킨, 몬스터 재질 변경) + 피버 ON(탭 창 0.5초 실측 뒤 재보정) + 조건부 보스 2(B13·B14)",
        "3차: 군단 루프 5보스 + 조건부 보스 2(B18·B19) + 거울 기사 코드 재사용한 PvP 결투장 + 보스 러시 + 워프 제단",
    ]
    return cfg


# ---------------------------------------------------------------------------
# 몬스터/보스 설계 입력
# ---------------------------------------------------------------------------
MAIN_MONS = [
    [("penguin", "펭귄", "Mount01", 5.5), ("jelly", "젤리말", "Mount02", 5), ("firewolf", "불늑대", "Mount03", 6)],
    [("deer", "은빛 사슴", "Mount04", 7), ("unicorn", "유니콘", "Mount05", 7), ("icewolf", "얼음 늑대", "Mount06", 7)],
    [("golem", "숲 골렘", "Mount08", 9), ("lavagolem", "용암 골렘", "Mount09", 9), ("hellhound", "지옥견", "Mount11", 8)],
    [("hellboar", "지옥 군단 멧돼지", "Mount12", 10), ("balrog", "고대 발록", "Mount13", 11), ("cerberus", "케르베로스", "Mount14", 10)],
    [("giant", "에테르 거인", "Mount15", 12), ("sage", "육중한 신선", "Mount16", 12), ("gumiho", "에테르 구미호", "Mount17", 11)],
    [("steelrhino", "강철 코뿔소", "Mount10 재질 변경", 9), ("darkunicorn", "검은 유니콘", "Mount05 재질", 8), ("stormwolf", "폭풍 늑대", "Mount06 재질", 8)],
    [("crystalgolem", "수정 골렘", "Mount08 재질", 10), ("lavaturtle", "화산 거북", "Mount18", 9), ("shadowleopard", "그림자 표범", "Mount19", 9)],
    [("abyssboar", "심연 멧돼지", "Mount12 재질", 11), ("fallenangel", "타락 천사상", "Mount20", 12), ("tricerberus", "지옥 삼두견", "Mount14 재질", 11)],
    [("stargiant", "별빛 거인", "Mount15 재질", 13), ("dragonkin", "고대 용아병", "Mount21", 12), ("goldgumiho", "황금 구미호", "Mount17 재질", 12)],
    [("titan", "에테르 타이탄", "Mount22", 14), ("voidsage", "공허 신선", "Mount16 재질", 13), ("doomwolf", "종말의 늑대", "Mount03 재질", 12)],
]
LEFT_MONS = [
    [("galewolf", "질풍 늑대", "Mount03 재질", 6), ("galehorse", "질풍 말", "Mount02 재질", 6), ("galefalcon", "질풍 매", "Mount23", 5)],
    [("stormhorse", "폭풍 말", "Mount04 재질", 7), ("stormleopard", "폭풍 표범", "Mount19 재질", 8), ("stormfalcon", "폭풍 매", "Mount23 재질", 6)],
    [("windspirit", "바람 정령체", "Mount24", 8), ("galegumiho", "질풍 구미호", "Mount17 재질", 9), ("thunderhound", "번개 사냥개", "Mount11 재질", 8)],
    [("fatecat", "운명의 고양이", "Mount25", 8), ("fatedeer", "운명의 사슴", "Mount04 재질", 9), ("fatefalcon", "운명의 매", "Mount23 재질", 7)],
    [("knightsteed", "기사의 군마", "Mount26", 10), ("galeknight", "질풍 기사", "Mount21 재질", 11), ("galedragon", "질풍 비룡", "Mount07 재질", 10)],
]
RIGHT_MONS = [
    [("legionboar", "군단 멧돼지", "Mount12 재질", 7), ("legionhound", "군단 사냥개", "Mount11 재질", 7), ("legionbrute", "군단 거구", "Mount13 재질", 8)],
    [("bloodhound", "피의 사냥개", "Mount14 재질", 9), ("bloodbat", "피의 박쥐", "Mount27", 7), ("bloodknight", "피의 기사", "Mount21 재질", 10)],
    [("lordguard", "군주 근위병", "Mount13 재질", 11), ("lordgolem", "군주 골렘", "Mount09 재질", 11), ("lordwyvern", "군주 비룡", "Mount07 재질", 11)],
    [("soulgiant", "영혼 거인", "Mount15 재질", 13), ("soulsage", "영혼 신선", "Mount16 재질", 12), ("soulgumiho", "영혼 구미호", "Mount17 재질", 12)],
    [("endtitan", "종언 타이탄", "Mount22 재질", 15), ("enddragon", "종언 용아병", "Mount21 재질", 13), ("endwolf", "종언 늑대", "Mount03 재질", 13)],
]
# 종별 계수: 몬스터 체력 = hp_k × 플레이어 공격력(앵커), 공격력 = atk_k × 플레이어 최대체력(앵커)
KIND = {
    "main":  [dict(hp_k=0.85, atk_k=0.07, interval=1.3, speed=10, spawn="rise", exp_m=1.0),
              dict(hp_k=1.80, atk_k=0.10, interval=1.3, speed=10, spawn="rise", exp_m=1.5),
              dict(hp_k=3.20, atk_k=0.15, interval=1.1, speed=19, spawn="rush", exp_m=2.5)],
    "left":  [dict(hp_k=0.70, atk_k=0.09, interval=1.0, speed=20, spawn="rush", exp_m=1.0),
              dict(hp_k=1.50, atk_k=0.13, interval=1.0, speed=21, spawn="rush", exp_m=1.5),
              dict(hp_k=2.60, atk_k=0.18, interval=0.9, speed=23, spawn="rush", exp_m=2.5)],
    "right": [dict(hp_k=1.00, atk_k=0.06, interval=1.3, speed=10, spawn="rise", exp_m=1.0),
              dict(hp_k=2.00, atk_k=0.085, interval=1.3, speed=10, spawn="rise", exp_m=1.5),
              dict(hp_k=3.50, atk_k=0.12, interval=1.2, speed=19, spawn="rush", exp_m=2.5)],
}
WEIGHTS = {"main": [45, 35, 20], "left": [40, 35, 25], "right": [35, 35, 30]}
GROUP = {"main": [35, 45, 20], "left": [25, 45, 30], "right": [0, 30, 70]}
# 보스 성향(D): 목표 초 배율, 공격 배율
ARCH = {"균형": (1.0, 1.0), "탱커": (1.3, 0.75), "유리대포": (0.7, 1.25), "균형(최종)": (1.0, 1.0)}
DPS_K_SCALE = 0.75  # 전 보스 공통 치명도 배율 (누진 사망 비용·초당 회복 상한 도입 보정)
BR = {"every_s": 9, "atk_mult": 2.2, "dodge_p_manual": 0.70, "dodge_p_auto": 0.35}

# (id, 이름, 모델, 키, 페이즈, 전환초, 상한, dps_k, 간격, 기준 목표 초, 성향, 기믹, 공략, 등장 조건, 관통 제한)
BOSSES = {
 "main": [
  ("B01", "수정 매머드", "Mount10 구슬 코뿔소(수정 재질)", 8, 3, 1.5, 0.035, 0.095, 2.1, 26, "균형",
   {"stagger": {"every_s": 10, "dur_s": 3, "dmg_mult": 1.5, "cap_mult": 2.0}},
   "10초마다 돌진 뒤 엄니가 땅에 박혀 3초 그로기(피해 ×1.5, 상한 ×2). 장비 없이도 그로기 3번이면 체력바 1개가 통째로 날아간다. 첫 보스 = 튜토리얼: 체력바·그로기·상한을 몸으로 배운다.", None, None),
  ("B02", "화염 와이번", "Mount07", 9, 3, 1.2, 0.035, 0.070, 1.9, 26, "유리대포",
   {"breath": dict(BR), "enrage": {"from_phase": 2, "atk_mult": 1.3, "int_mult": 0.9}},
   "유리대포: 짧지만 아프다. 9초마다 1.5초 예고 후 화염 브레스(일반 타의 2.2배) — 예고 중 뒤로 걸으면 피함(수동 70%). 2페이즈 분노(공격 ×1.3, 간격 ×0.9). 브레스 직후 다시 붙기, 흡혈·체력 분배가 안정.", None, None),
  ("B03", "에테르 드래곤", "Mount28(v8 키 14 → 12)", 12, 3, 1.0, 0.05, 0.120, 1.9, 26, "탱커",
   {"shield_hits": 5},
   "탱커: 길고 무디다. 페이즈마다 에테르 보호막 5타 무효(피해량 무관) → 공속이 정답, 바람 정령이 보호막 벗기는 시간을 5초→3.5초로. 큰 한 방 빌드는 손해.", None, None),
  ("B04", "에테르 그리폰", "Mount29", 14, 3, 1.0, 0.03, 0.090, 1.9, 26, "균형",
   {"adds": {"phases": [2], "count": 2, "unit_k": {"hp_k": 1.5, "atk_k": 0.07, "interval": 1.3, "exp_m": 0.5}}},
   "2페이즈 진입 시 새끼 그리폰 2마리 소환(각자 공격). 범위(거인 망토)면 보스와 새끼를 한 번에 → 소환이 보너스 경험치. 범위 없으면 새끼 처리 동안 보스 공격을 더 맞는다.", None, None),
  ("B05", "청색의 드래곤", "Mount30", 16, 4, 1.2, 0.035, 0.160, 1.9, 28, "유리대포",
   {"frenzy": {"int_min": 1.1, "over_s": 40}, "stagger_on_phase_s": 2.0},
   "광란: 공격 간격이 30초에 걸쳐 1.9→1.1초로(DPS 체크). 체력바가 깨질 때마다 2초 그로기. 빨리 깨면 쉬운 보스, 끌면 지옥. 5단계 문 = 에테르 왕관 + 질풍 루프 입구.", None, None),
  ("B06", "강철 기간테스", "Mount13 재질(강철)", 15, 3, 1.0, 0.03, 0.110, 2.0, 28, "탱커",
   {"thorns_frac": 0.02, "enrage": {"from_phase": 3, "atk_mult": 1.4}},
   "가시 갑주: 때릴 때마다 내 최대 체력 2% 피해 → 공속 몰빵의 천적, 큼직한 치명타(광전사 반지, 관통 ×2)가 유리. 3페이즈 분노 ×1.4.", None, None),
  ("B07", "용암 군주", "Mount09 재질(용암, 크게)", 13, 3, 1.0, 0.03, 0.125, 1.9, 28, "균형",
   {"regen_per_s": 0.008, "timer": {"at_s": 56, "atk_mult": 2.5}},
   "매초 최대 체력 0.8% 재생 + 56초(목표 초의 2배) 뒤 폭주(공격 ×2.5). 순수 DPS 체크. 장비 없으면 재생이 DPS 의 1/3을 먹는다.", None, None),
  ("B08", "뇌전 와이번", "Mount07 재질(번개)", 10, 3, 1.4, 0.03, 0.160, 1.8, 30, "유리대포",
   {"curse_noncrit_mult": 0.7, "stagger_on_phase_s": 2.5, "enrage": {"from_phase": 3, "int_mult": 0.8}},
   "정전기 갑옷: 치명타가 아닌 타격은 70% 피해. 행운·광전사 반지·번개 정령(5타마다 확정 치명)의 가치. 페이즈 전환 시 2.5초 감전 그로기.", None, None),
  ("B09", "심연의 수호자", "Mount20 재질(심연)", 14, 4, 1.0, 0.03, 0.150, 1.8, 28, "탱커",
   {"boss_lifesteal": 0.35, "player_ls_mult": 0.5},
   "장갑 3%(최소 34타) + 치명 관통 ×1.2 제한 → 행운의 천적, 공속의 놀이터. 심연의 계약: 보스가 준 피해의 35%를 회복하고 내 흡혈은 절반 → 체력·피해감소(용암 망토)로 갈아탄다.", None, 1.2),
  ("B10", "에테르 황제 드래곤", "Mount30 재질(황금, 크게)", 20, 5, 1.2, 0.04, 0.150, 1.9, 36, "균형(최종)",
   {"breath": {"every_s": 10, "atk_mult": 2.2, "dodge_p_manual": 0.70, "dodge_p_auto": 0.35},
    "adds": {"phases": [3], "count": 2, "unit_k": {"hp_k": 2.0, "atk_k": 0.08, "interval": 1.3, "exp_m": 0.5}},
    "enrage": {"from_phase": 5, "atk_mult": 1.5, "int_mult": 0.85}, "stagger_on_phase_s": 1.5},
   "가운데 길 최종. 체력바 5개, 상한 4%(최소 25타). 브레스 10초, 3페이즈 용아병 2마리, 5페이즈 분노. 전환마다 1.5초 그로기. 처치 = 군단 루프 입구.", None, None),
 ],
 "left": [
  ("B11", "질풍 표범", "Mount19 재질(바람)", 9, 3, 0.8, 0.03, 0.140, 1.5, 24, "균형",
   {"frenzy": {"int_min": 0.9, "over_s": 30}},
   "30초에 걸쳐 공격 간격 1.5→0.9초. 빨리 잡지 않으면 초당 피해 1.7배. 질풍 루프 입문: 선제 러시(첫 3타 가속)의 가치.", None, None),
  ("B12", "폭풍 와이번", "Mount07 재질(폭풍)", 11, 3, 0.8, 0.04, 0.100, 1.6, 24, "유리대포",
   {"shield_hits": 4, "breath": {"every_s": 7, "atk_mult": 1.8, "dodge_p_manual": 0.70, "dodge_p_auto": 0.35}},
   "페이즈마다 폭풍 보호막 4타 + 7초마다 돌풍 브레스(×1.8). 공속이 모든 것. 25초 안에 잡으면 다음 구간에 회오리 정령왕이 깨어난다.", None, None),
  ("B13", "회오리 정령왕", "Mount24 재질(크게)", 12, 3, 1.0, 0.03, 0.190, 1.6, 28, "탱커",
   {"adds": {"phases": [1, 3], "count": 2, "unit_k": {"hp_k": 1.2, "atk_k": 0.08, "interval": 1.0, "exp_m": 0.4}}},
   "조건부(폭풍 와이번 25초 컷). 장갑 3% + 시작과 3페이즈에 바람 정령체 2마리씩 → 범위·스플래시 없으면 6마리 상대. 무사망으로 잡으면 다음 구간에 운명의 구미호가 나타난다. 광풍 망토의 관문.",
   {"type": "prev_boss_secs_max", "value": 25, "text_ko": "직전 보스(폭풍 와이번)를 25초 안에 처치"}, None),
  ("B14", "운명의 구미호", "Mount17 재질(은빛)", 11, 4, 0.8, 0.04, 0.150, 1.6, 28, "균형",
   {"curse_noncrit_mult": 0.65, "boss_lifesteal": 0.25},
   "조건부(회오리 정령왕 무사망). 운명의 저주: 치명타 아닌 타격 65%, 보스는 준 피해의 25% 회복. 행운·확정 치명이 없으면 체력 레이스에서 밀린다. 행운의 왕관의 관문.",
   {"type": "no_death_prev_boss", "text_ko": "직전 보스(회오리 정령왕) 전투 무사망"}, None),
  ("B15", "질풍의 거울 기사", "Mount21 재질(은갑, 거울)", 13, 4, 0.8, 0.05, 0.0, 1.6, 26, "균형",
   {"mirror": {"T": 55.0, "dps_k": 0.09, "dodge_from_crit": 0.6, "dodge_cap": 0.30}, "thorns_frac": 0.01},
   "거울 기사 = 내 레벨의 '장비 없는' 복사(체력 = 맨몸 DPS×T, 한 타 = 맨몸 체력의 9%/초 × 간격, 내 치명 확률×0.6 만큼 회피(≤30%)). 장비·강화만이 차이 = PvP 예습. 가시 1%.", None, None),
 ],
 "right": [
  ("B16", "군단장 멧돼지왕", "Mount12 재질(황금, 크게)", 13, 3, 1.2, 0.035, 0.210, 1.8, 26, "균형",
   {"adds": {"phases": [1, 2, 3], "count": 3, "unit_k": {"hp_k": 1.0, "atk_k": 0.06, "interval": 1.3, "exp_m": 0.3}}},
   "페이즈마다 군단 멧돼지 3마리. 항상 4마리 상대. 범위 3마리 + 스플래시로 '군단을 갈아 경험치로' — 군단 파쇄 망토의 관문.", None, None),
  ("B17", "피의 케르베로스", "Mount14 재질(붉은, 크게)", 14, 3, 1.0, 0.045, 0.095, 1.7, 30, "탱커",
   {"boss_lifesteal": 0.5, "player_ls_mult": 0.5, "enrage": {"from_phase": 2, "atk_mult": 1.3}},
   "피의 계약: 보스 흡혈 50%, 내 흡혈 절반, 2페이즈 분노. 체력 레이스. 피의 성배의 관문.", None, None),
  ("B18", "군주 발록", "Mount13 재질(검은 금, 크게)", 16, 4, 1.0, 0.045, 0.125, 1.8, 30, "균형",
   {"regen_per_s": 0.01, "timer": {"at_s": 60, "atk_mult": 3.0}, "shield_hits": 4},
   "조건부(이 구간 도박 구역에서 전투 승리 — 군주는 도박꾼만 만난다). 재생 1%/초 + 보호막 4타 + 60초 폭주 ×3. DPS 체크의 완성형. 군주의 부적(에너지 +3/+1)의 관문.",
   {"type": "zone_fight_this_stage", "text_ko": "이 구간의 도박 구역 안에서 전투 1회 승리"}, None),
  ("B19", "영혼의 거인왕", "Mount15 재질(투명, 크게)", 18, 4, 1.0, 0.04, 0.135, 2.0, 34, "탱커",
   {"stagger": {"every_s": 12, "dur_s": 3, "dmg_mult": 1.5, "cap_mult": 2.0}, "thorns_frac": 0.02},
   "조건부(군단 루프 앞 3보스 이번 판 전부 처치). 12초마다 3초 그로기(상한 ×2) + 가시 2%. 그로기 창에 한 방을 몰아넣는 리듬 보스. 영혼 왕관의 관문.",
   {"type": "all_prev_loop_bosses", "text_ko": "군단 루프 앞 3보스(B16~B18) 이번 판 전부 처치"}, None),
  ("B20", "종언의 청룡", "Mount30 재질(검은 청색, 최대 크기)", 24, 5, 1.2, 0.035, 0.105, 1.9, 40, "균형(최종)",
   {"breath": {"every_s": 8, "atk_mult": 2.2, "dodge_p_manual": 0.70, "dodge_p_auto": 0.35},
    "adds": {"phases": [2, 4], "count": 2, "unit_k": {"hp_k": 1.5, "atk_k": 0.08, "interval": 1.3, "exp_m": 0.4}},
    "enrage": {"from_phase": 5, "atk_mult": 1.5, "int_mult": 0.8}, "frenzy": {"int_min": 1.3, "over_s": 40},
    "timer": {"at_s": 80, "atk_mult": 2.0}, "stagger_on_phase_s": 1.5},
   "최종 보스. 체력바 5개·상한 3.5%(최소 29타)·브레스 8초·소환 2회·광란·5페이즈 분노·80초 폭주. 종언의 정령의 관문. 풀장비+강화에서 25~35초의 '처형'이 목표.", None, None),
 ],
}

R_MAIN = 4.6
MAIN_BASE = [300 * R_MAIN ** i for i in range(10)]
BOSS_EXP_MULT = {"main": 12.0, "loop": 8.0}
LEFT_SHARE = 0.5      # 질풍 루프 총 경험치 = 가운데 6단계 총 경험치 × 0.5
LEFT_G = 1.5          # 질풍 구간 기본 경험치 성장비
INTRO_MAIN = 3
STAGE_LEN = {"main": [265, 270, 280, 280, 290, 300, 300, 310, 320, 330], "left": [160] * 5, "right": [160] * 5}
FIGHTS = {"main": 4, "left": 2, "right": 2}
ENTRY = {"left": 5, "right": 10}
SIGN_FACTOR = 0.8   # 험로 입구 표지판 권장 레벨 = 진입 기대 레벨 × 0.8 (A)
ROUTE_META = {
    "main": dict(name_ko="가운데 길 (에테르 평원 → 황제의 둥지)", unlock_ko="항상", enter_s=0,
                 desc_ko="10구간 10보스. 구간당 4전투(1구간은 인트로 3 + 1). 한 판 풀클리어가 '숙련 목표'(8~10분)."),
    "left": dict(name_ko="질풍 루프 (5단계 광장 왼쪽 험로)", unlock_ko="청색의 드래곤(B05)을 이번 판에 처치 → 5단계 광장 왼쭉 문. 입구 표지판 '권장: 가운데 길 아이템 5개'", enter_s=6,
                 desc_ko="5구간 × (2전투 + 보스), 300 stud 루프 → 광장 복귀. 모두 달려오는 빠른 적, 레벨은 조금만 오르고(가운데 6단계의 절반) 보상은 아이템·3급 강화석·에너지(+3/구간). 공속·행운·범위의 길. 조건부 보스 2."),
    "right": dict(name_ko="군단 루프 (10단계 광장 오른쪽 험로)", unlock_ko="에테르 황제 드래곤(B10)을 이번 판에 처치 → 10단계 광장 오른쪽 문", enter_s=6,
                  desc_ko="5구간 × (2전투 + 보스). 항상 떼(2~3마리). 11~15단계에 해당하는 레벨 폭발(구간당 ×3.2). 범위·흡혈·에너지의 길, 최종 보스. 조건부 보스 2."),
}


def owned_for(route_id, k):
    main_ids = [b[0] for b in BOSSES["main"]]
    if route_id == "main":
        bosses = main_ids[:k]
    elif route_id == "left":
        bosses = main_ids[:ENTRY["left"]] + [b[0] for b in BOSSES["left"]][:k]
    else:
        bosses = main_ids + [b[0] for b in BOSSES["left"]] + [b[0] for b in BOSSES["right"]][:k]
    return ["I" + b[1:] for b in bosses]


def virtual_player(cfg, gear, exp_total):
    pl = S.Player(cfg, gear, manual=True)
    S.feed_exp(pl, exp_total)
    return pl


def stage_exp_coef(cfg, route_id, nf, boss_mult):
    gprobs = GROUP[route_id]
    gsize = sum(p * n for p, n in zip(gprobs, (1, 2, 3))) / 100
    kinds, weights = KIND[route_id], WEIGHTS[route_id]
    avg_m = sum(w * k["exp_m"] for w, k in zip(weights, kinds)) / sum(weights)
    zone_mult = 1 + cfg["combat"]["zone_p_manual"] * (cfg["formulas"]["exp_gain"]["zone_exp_mult"] - 1)
    return nf * gsize * avg_m * zone_mult + boss_mult, gsize * avg_m * zone_mult


def build_route(route_id, mons_spec, base_exp, cfg, anchors_out, exp_start):
    kinds, weights, gprobs = KIND[route_id], WEIGHTS[route_id], GROUP[route_id]
    nf = FIGHTS[route_id]
    boss_mult = BOSS_EXP_MULT["main" if route_id == "main" else "loop"]
    _, per_fight_coef = stage_exp_coef(cfg, route_id, nf, boss_mult)
    stages = []
    exp_total = exp_start
    z = -120
    for si, (spec, base) in enumerate(zip(mons_spec, base_exp)):
        owned = owned_for(route_id, si)
        gear = S.aggregate(cfg, S.auto_equip(cfg, owned))
        per_fight = per_fight_coef * base * gear["exp_mult"]
        intro = INTRO_MAIN if (route_id == "main" and si == 0) else 0
        p_1 = virtual_player(cfg, gear, exp_total)
        if intro:
            exp_after_intro = exp_total + intro * base * gear["exp_mult"]
            exp_f1 = exp_after_intro
            exp_boss = exp_after_intro + (nf - intro) * per_fight
        else:
            exp_f1 = exp_total + per_fight
            exp_boss = exp_total + nf * per_fight
        p_f1 = virtual_player(cfg, gear, exp_f1)
        p_b = virtual_player(cfg, gear, exp_boss)
        mon_ids = []
        for ki, ((mid, mname, model, height), kd) in enumerate(zip(spec, kinds)):
            if route_id == "main" and si == 0 and ki == 0:
                hp, atk = nice(3.0 * p_1.atk(), 2), nice(0.12 * p_1.maxhp(), 2)   # 레벨 1: 3타에 죽고 9타를 버틴다
            else:
                hp, atk = nice(kd["hp_k"] * p_f1.atk()), nice(kd["atk_k"] * p_f1.maxhp())
            cfg["monsters"][mid] = dict(id=mid, name_ko=mname, model=model, height=height, route=route_id, stage=si + 1,
                                        kind_ko=["약", "중", "정예"][ki], hp=hp, atk=atk, interval=kd["interval"], speed=kd["speed"],
                                        spawn=kd["spawn"], exp=nice(base * kd["exp_m"]))
            mon_ids.append(mid)
        (bid, bname, model, height, phases, trans, cap, dps_k, interval, T0, arch, gm, guide, cond, pierce_cap) = BOSSES[route_id][si]
        T_mult, atk_f = ARCH[arch]
        T = round(T0 * T_mult)
        c, cm = p_b.crit_p(), p_b.crit_mult()
        Cc = cfg["combat"]
        hits_per_s = p_b.aspd() / Cc["attack_interval"]
        fever_up = Cc["fever_dur_s"] / (Cc["fever_dur_s"] + Cc["fever_hits"] / Cc["manual_combo_p"] / hits_per_s)
        fever_f = 1 + (Cc["fever_aspd"] - 1) * fever_up
        dps = p_b.atk() * (1 + c * (cm - 1)) * hits_per_s * fever_f
        eff = 1.0 - (phases - 1) * trans / T
        gm = json.loads(json.dumps(gm))
        if "mirror" in gm:
            hp = 0
            atk = 0
        else:
            hp = nice(dps * T * eff)
            atk = nice(dps_k * DPS_K_SCALE * interval * p_b.maxhp() * atk_f)
        if "adds" in gm:
            uk = gm["adds"].pop("unit_k")
            gm["adds"]["unit"] = dict(id=bid + "_add", name_ko=bname + "의 수하", hp=nice(uk["hp_k"] * p_b.atk()),
                                      atk=nice(uk["atk_k"] * p_b.maxhp()), interval=uk["interval"], exp=nice(base * uk["exp_m"]))
        boss_exp = nice(base * boss_mult)
        cfg["bosses"][bid] = dict(
            id=bid, name_ko=bname, model=model, height=height, route=route_id, stage=si + 1, archetype_ko=arch,
            hp=hp, atk=atk, interval=interval, speed=9, spawn="rise", exp=boss_exp,
            phases=phases, transition_s=trans, hit_cap=cap, crit_pierce_cap=pierce_cap, min_hits=int(math.ceil(1 / cap)),
            gimmick=gm, spawn_condition=cond, guide_ko=guide, drop_item="I" + bid[1:], stone_tier=cfg["items"]["I" + bid[1:]]["tier"],
            essence_id="ess_" + bid, recommended_level=int(p_b.lvl), target_secs_natural=T, atk_factor=atk_f,
            energy_reward=cfg["run"]["energy_boss_main"] if route_id == "main" else cfg["run"]["energy_boss_loop"],
            anchor=dict(player_lvl=int(p_b.lvl), player_atk=int(p_b.atk()), player_hp=int(p_b.maxhp()), player_dps_natural=int(dps),
                        natural_items=S.auto_equip(cfg, owned), boss_hit_pct_of_player_hp=round(atk / p_b.maxhp() * 100, 1) if atk else None,
                        boss_dps_pct_of_player_hp=round(dps_k * DPS_K_SCALE * 100 * atk_f, 1), fever_uptime_assumed=round(fever_up, 2)),
        )
        anchors_out.append((route_id, si + 1, int(p_f1.lvl), int(p_b.lvl), int(p_f1.atk()), int(p_f1.maxhp()), hp, atk, int(dps)))
        length = STAGE_LEN[route_id][si]
        p_in = virtual_player(cfg, gear, exp_total)
        exp_after_boss = exp_boss + boss_exp * gear["exp_mult"] * gear["boss_exp_mult"]
        p_after = virtual_player(cfg, gear, exp_after_boss)
        stages.append(dict(stage=si + 1, name_ko=f"{si+1}구간", z_from=z, z_to=z - length, length=length, fights=nf,
                           monsters=mon_ids, monster_weights=([60, 35, 5] if (route_id == "main" and si == 0) else weights), boss=bid, base_exp=nice(base),
                           luck_zones=3 if si % 2 == 0 else 2, group_probs=([100, 0, 0] if (route_id == "main" and si == 0) else gprobs),
                           anchor_levels=dict(enter=int(p_in.lvl), after_first_fight=int(p_f1.lvl), at_boss=int(p_b.lvl), after_boss=int(p_after.lvl),
                                              natural_exp_mult=round(gear["exp_mult"], 2))))
        z -= length
        exp_total = exp_after_boss
    meta = ROUTE_META[route_id]
    out = dict(id=route_id, name_ko=meta["name_ko"], desc_ko=meta["desc_ko"], unlock_ko=meta["unlock_ko"], group_probs=gprobs,
               intro_fights=INTRO_MAIN if route_id == "main" else 0, enter_s=meta["enter_s"], stages=stages)
    if route_id != "main":
        out["entry_after_main_stage"] = ENTRY[route_id]
        out["loop_length_stud"] = sum(STAGE_LEN[route_id]) + 2 * 60
        out["sign_recommended_level_factor"] = SIGN_FACTOR
        out["sign_recommended_level"] = int(stages[0]["anchor_levels"]["enter"] * SIGN_FACTOR)
        out["sign_ko"] = f"입구 표지판: '권장 레벨 {int(stages[0]['anchor_levels']['enter'] * SIGN_FACTOR):,} 이상 · 아이템 {ENTRY[route_id]}개' (A 안의 권장 레벨 = 진입 기대 레벨 × {SIGN_FACTOR})"
    return out, exp_total


def generate():
    cfg = build_config()
    cfg["monsters"], cfg["bosses"], cfg["routes"] = {}, {}, {}
    anchors = []
    # 가운데 길
    cfg["routes"]["main"], exp_end_main = build_route("main", MAIN_MONS, MAIN_BASE, cfg, anchors, 0.0)
    main_stages = cfg["routes"]["main"]["stages"]
    curve = S.Curve(cfg["exp_curve"])
    # 질풍 루프: 5단계 보스 처치 뒤 경험치에서 시작. 총 경험치 = 가운데 6단계 총 경험치 × LEFT_SHARE
    gear_l0 = S.aggregate(cfg, S.auto_equip(cfg, owned_for("left", 0)))
    exp_after_b05 = curve.E(main_stages[4]["anchor_levels"]["after_boss"]) * gear_l0["exp_mult"] / main_stages[4]["anchor_levels"]["natural_exp_mult"]
    main6_total_coef, _ = stage_exp_coef(cfg, "main", FIGHTS["main"], BOSS_EXP_MULT["main"])
    main6_total = main6_total_coef * MAIN_BASE[5]
    loop_coef, _ = stage_exp_coef(cfg, "left", FIGHTS["left"], BOSS_EXP_MULT["loop"])
    geo = sum(LEFT_G ** k for k in range(1, 6))
    left_scale = LEFT_SHARE * main6_total / (loop_coef * geo)
    LEFT_BASE = [left_scale * LEFT_G ** k for k in range(1, 6)]
    cfg["routes"]["left"], _ = build_route("left", LEFT_MONS, LEFT_BASE, cfg, anchors, exp_after_b05)
    # 군단 루프: 10단계 뒤 경험치에서 시작, 구간당 ×4.6 (가운데 11~15단계에 해당). 2전투 구성이라 기본 경험치를 보정해 구간당 총 경험치 = 가운데 구간과 같게
    main_total_coef, _ = stage_exp_coef(cfg, "main", FIGHTS["main"], BOSS_EXP_MULT["main"])
    right_coef, _ = stage_exp_coef(cfg, "right", FIGHTS["right"], BOSS_EXP_MULT["loop"])
    right_scale = main_total_coef / right_coef
    RIGHT_BASE = [MAIN_BASE[9] * R_MAIN ** k * right_scale for k in range(1, 6)]
    gear_r0 = S.aggregate(cfg, S.auto_equip(cfg, owned_for("right", 0)))
    exp_after_b10 = curve.E(main_stages[9]["anchor_levels"]["after_boss"]) * gear_r0["exp_mult"] / main_stages[9]["anchor_levels"]["natural_exp_mult"]
    cfg["routes"]["right"], _ = build_route("right", RIGHT_MONS, RIGHT_BASE, cfg, anchors, exp_after_b10)
    cfg["design_anchors_note_ko"] = (
        "몬스터 체력 = hp_k × (구간 첫 전투 직후 기대 공격력), 공격력 = atk_k × (같은 시점 기대 최대 체력). "
        "보스 체력 = 자연 장비 기대 DPS(피버 가동률 포함) × 목표 초(성향 배율 적용) × (1 − 전환 초/목표 초), 공격력 = dps_k × 간격 × 도착 기대 체력 × 성향 공격 배율. "
        "기대값은 경험치 곡선 + 자연 장비(이전 보스 아이템 자동 장착) + 균형 분배로 계산. 질풍 루프는 가운데 5구간 뒤 경험치에서, 군단 루프는 10구간 뒤 경험치에서 이어진다. "
        "마지막으로 앵커 플레이어로 보스전을 40회 시뮬해 중간 전투 시간이 목표 초가 되도록 보스 체력(거울 기사는 T)을 보정했다(calibrated_secs_median).")
    cfg["gen_params"] = dict(R_MAIN=R_MAIN, MAIN_BASE0=300, BOSS_EXP_MULT=BOSS_EXP_MULT, LEFT_SHARE=LEFT_SHARE, LEFT_G=LEFT_G,
                             LEFT_BASE=[nice(x) for x in LEFT_BASE], RIGHT_BASE=[nice(x) for x in RIGHT_BASE], KIND=KIND, WEIGHTS=WEIGHTS, GROUP=GROUP,
                             ARCH={k: {"T_mult": v[0], "atk_factor": v[1]} for k, v in ARCH.items()}, DPS_K_SCALE=DPS_K_SCALE, STAGE_LEN=STAGE_LEN, FIGHTS=FIGHTS)
    refine_anchors(cfg)
    calibrate(cfg)
    return cfg, anchors


def refine_anchors(cfg, runs=60):
    """2차 앵커: 각 보스를 '처음 만나는 판'(자연 장비)을 60판 돌려 실제 도착 레벨 중간값을 재고, 그 레벨의 플레이어로 보스 공격력·수하·앵커를 다시 계산한다.
    (1차 앵커는 경험치 곡선 기대값이라 도박 구역·떼 크기·행운 당첨 분산을 못 본다.) 체력은 다음 단계 calibrate 가 맞춘다."""
    curve = S.Curve(cfg["exp_curve"])
    Cc = cfg["combat"]
    for bid, b in cfg["bosses"].items():
        plan, owned = S.natural_for(cfg, bid)
        res = [S.run(cfg, plan, owned, seed=4000 + i) for i in range(runs)]
        arr = [bl["arrive"] for r in res for bl in r["boss_log"] if bl["boss"] == bid]
        if len(arr) < 5:
            continue
        L = int(statistics.median(arr))
        gear = S.aggregate(cfg, S.auto_equip(cfg, owned))
        p_b = virtual_player(cfg, gear, curve.E(L))
        spec = [x for x in BOSSES[b["route"]] if x[0] == bid][0]
        (_, _, _, _, phases, trans, cap, dps_k, interval, T0, arch, gm0, _, _, _) = spec
        T_mult, atk_f = ARCH[arch]
        c, cm = p_b.crit_p(), p_b.crit_mult()
        hits_per_s = p_b.aspd() / Cc["attack_interval"]
        fever_up = Cc["fever_dur_s"] / (Cc["fever_dur_s"] + Cc["fever_hits"] / Cc["manual_combo_p"] / hits_per_s)
        dps = p_b.atk() * (1 + c * (cm - 1)) * hits_per_s * (1 + (Cc["fever_aspd"] - 1) * fever_up)
        T = b["target_secs_natural"]
        eff = 1.0 - (phases - 1) * trans / T
        if not b["gimmick"].get("mirror"):
            b["hp"] = nice(dps * T * eff)
            b["atk"] = nice(dps_k * DPS_K_SCALE * interval * p_b.maxhp() * atk_f)
        if "adds" in b["gimmick"]:
            uk = gm0["adds"]["unit_k"]
            u = b["gimmick"]["adds"]["unit"]
            u["hp"], u["atk"] = nice(uk["hp_k"] * p_b.atk()), nice(uk["atk_k"] * p_b.maxhp())
        b["recommended_level"] = L
        b["anchor"].update(player_lvl=L, player_atk=int(p_b.atk()), player_hp=int(p_b.maxhp()), player_dps_natural=int(dps),
                           boss_hit_pct_of_player_hp=round(b["atk"] / p_b.maxhp() * 100, 1) if b["atk"] else None,
                           arrival_level_measured_median=L, arrival_level_p10_p90=[int(sorted(arr)[len(arr) // 10]), int(sorted(arr)[len(arr) * 9 // 10])],
                           natural_reach_pass1=round(len(arr) / runs, 2))
        stage = [st_ for st_ in cfg["routes"][b["route"]]["stages"] if st_["boss"] == bid][0]
        stage["anchor_levels"]["at_boss"] = L
        boss_exp = b["exp"]
        p_after = virtual_player(cfg, gear, curve.E(L) + boss_exp * gear["exp_mult"] * gear["boss_exp_mult"])
        stage["anchor_levels"]["after_boss"] = int(p_after.lvl)


DEATH_TARGET = {"main": 0.6, "left": 0.5, "right": 0.5, "B01": 0.35, "B13": 0.3, "B19": 0.35}


def _measure(cfg, b, gear, exp_b, n=40):
    secs, deaths = [], []
    for i in range(n):
        rnd = random.Random(777 + i)
        rs = S.RunState(cfg, rnd, 999)
        pl = S.Player(cfg, gear, manual=True)
        S.feed_exp(pl, exp_b)
        pl.hp = pl.maxhp()
        res = S.combat(rs, pl, None, b, False, True)
        secs.append(res["secs"]); deaths.append(res["deaths"])
    return statistics.median(secs), sum(deaths) / len(deaths)


def calibrate(cfg):
    """앵커 레벨의 자연 장비 플레이어로 보스전 40회씩 → (1) 공격력 배율 m 을 격자(0.5~3.0)+이분 탐색해 평균 사망이 목표
    (가운데 0.6 / 루프 0.5 / 1보스 0.35 / B13·B19 0.3~0.35)에 가장 가깝게(동률이면 큰 배율), (2) 체력(거울은 T)을 2회 반복 보정해 중간 전투 시간 = 목표 초.
    사망은 '초당 회복 상한 vs 보스 DPS' 문턱 현상(지속 피해형 보스는 계단 함수)이라 곱셈 반복이 아니라 탐색이 필요하다."""
    GRID = [0.5, 0.65, 0.8, 1.0, 1.25, 1.6, 2.0, 2.5, 3.0]
    for rid, route in cfg["routes"].items():
        for si, stage in enumerate(route["stages"]):
            b = cfg["bosses"][stage["boss"]]
            owned = owned_for(rid, si)
            gear = S.aggregate(cfg, S.auto_equip(cfg, owned))
            curve = S.Curve(cfg["exp_curve"])
            exp_b = curve.E(b["anchor"]["player_lvl"])
            T = b["target_secs_natural"]
            tgt = DEATH_TARGET.get(b["id"], DEATH_TARGET[rid])
            mirror = b["gimmick"].get("mirror")
            atk0 = b["atk"] if not mirror else mirror["dps_k"]

            def set_atk(m):
                if mirror:
                    mirror["dps_k"] = round(atk0 * m, 4)
                else:
                    b["atk"] = nice(atk0 * m)

            def err(d):
                return abs(math.log((d + 0.15) / (tgt + 0.15)))
            # 체력 1차 보정(공격 1.0 기준)
            m0, d0 = _measure(cfg, b, gear, exp_b)
            if mirror:
                mirror["T"] = round(mirror["T"] * (T / m0) ** 0.8, 1)
            else:
                b["hp"] = nice(b["hp"] * (T / m0) ** 0.8)
            # 공격 격자 탐색
            best = None
            table = []
            for m in GRID:
                set_atk(m)
                _, d = _measure(cfg, b, gear, exp_b)
                table.append((m, d))
                # 같은 오차(예: 사망 0 이 여러 배율에서 이어지는 평탄 구간)면 더 큰 배율을 택한다 → 문턱 바로 아래의 '가장 위협적인' 공격력
                if best is None or err(d) < err(best[1]) or (abs(err(d) - err(best[1])) < 1e-9 and m > best[0]):
                    best = (m, d)
            # 이웃 사이 이분 2회
            lo = max([m for m, _ in table if m < best[0]], default=best[0])
            hi = min([m for m, _ in table if m > best[0]], default=best[0])
            for cand in (math.sqrt(lo * best[0]), math.sqrt(hi * best[0])):
                set_atk(cand)
                _, d = _measure(cfg, b, gear, exp_b)
                if err(d) < err(best[1]):
                    best = (cand, d)
            set_atk(best[0])
            # 체력 2차 보정
            for it in range(2):
                m_, d_ = _measure(cfg, b, gear, exp_b)
                if mirror:
                    mirror["T"] = round(mirror["T"] * (T / m_) ** 0.8, 1)
                else:
                    b["hp"] = nice(b["hp"] * (T / m_) ** 0.8)
            m_, d_ = _measure(cfg, b, gear, exp_b)
            b["anchor"]["calibrated_secs_median"] = round(m_, 1)
            b["anchor"]["calibrated_deaths_mean"] = round(d_, 2)
            b["anchor"]["death_target"] = tgt
            b["anchor"]["atk_calib_mult"] = round(best[0], 3)
            b["anchor"]["death_curve"] = [[m, round(d, 2)] for m, d in table]
            if not mirror:
                b["anchor"]["natural_hit_pct_of_boss_hp"] = round(b["anchor"]["player_atk"] * 1.3 / b["hp"] * 100, 2)
                b["anchor"]["boss_hit_pct_of_player_hp"] = round(b["atk"] / b["anchor"]["player_hp"] * 100, 1)
                b["anchor"]["boss_dps_pct_of_player_hp"] = round(b["atk"] / b["interval"] / b["anchor"]["player_hp"] * 100, 1)


def main():
    cfg, anchors = generate()
    if "--check" in sys.argv:
        with open(OUT, encoding="utf-8") as f:
            cur = json.load(f)
        same = json.dumps(cur, sort_keys=True, ensure_ascii=False) == json.dumps(cfg, sort_keys=True, ensure_ascii=False)
        print("check:", "OK — 재생성 결과 == boss20_config.json" if same else "DIFF — 파일이 생성기와 다르다")
        sys.exit(0 if same else 1)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=1)
    print("wrote", OUT)
    print("route stage  L_f1       L_boss     atk_f1     hp_f1      bossHP(보정후)  bossATK   T   secs  deaths  arch")
    for a in anchors:
        b = [bb for bb in cfg["bosses"].values() if bb["route"] == a[0] and bb["stage"] == a[1]][0]
        hp = b["hp"] if b["hp"] else ("mirror T=%s" % b["gimmick"]["mirror"]["T"])
        print("%-5s %2d  %10d %10d %10d %10d %13s %11d %4d %5.1f %5.2f  %s" % (a[:6] + (hp, b["atk"], b["target_secs_natural"], b["anchor"]["calibrated_secs_median"], b["anchor"]["calibrated_deaths_mean"], b["archetype_ko"])))


if __name__ == "__main__":
    main()
