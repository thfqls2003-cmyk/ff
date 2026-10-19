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
        "id": "boss20_final", "title": "레벨 폭발 모험단 — 20보스 최종 통합 설계 (B_dopamine 뼈대 + A/C/D 이식, 비평 K1·K2·K3 반영)", "version": "1.2",
        "units": "체력/공격력/경험치 정수, 시간 초, 거리 stud",
        "skeleton": "B_dopamine (앵커 보정·체력바·타격 상한·피버·need(L)=10(1+L/1000)^0.3·3길)",
        "grafts": ["A: 흡혈 초당 상한 max(5%, 0.8×흡혈률), 험로 루프 에너지(2전투 −2 + 보스 +5), 숨은 보스 조건 4종, 치명 관통/장갑 보스, 도박 구역 1회 소진",
                   "C: PvE/PvP 상한표 + pvp_disabled, 누진 사망 비용 3·4·5·6, 보스 고유 정수(+5 이상), 3연속 실패 천장, 순간이동권·기록의 책·보스 러시",
                   "D: 보스 성향(목표 초 ×, 공격 ×), 행운 보너스 '포인트 2배 당첨 p≤0.5', 제단 입장 체력 가득, 하위 5→상위 1 교환, 워프 제단, --check 재생성 검증, 재처치 무사망 +1 강화석",
                   "v1.2 비평 반영(K1 초보·K2 익스플로잇·K3 솔로 개발): 보스전 도중 게임오버 통계, 마지막 도전 규칙, 문마다 사망 카운터 초기화, 에너지 상한 30, 마지막 보스 뒤 자동 결산, "
                   "장갑 제약(자연 평타 ≤ 0.75×장갑 & 풀 +10 ≥ 11초), 고정 트리거 조우, 구역 = 구간당 1곳, PvP 피해감소 상한 15%·강화 불가·상한 뒤 적용·45초 뒤 회복 0, "
                   "행운! 이항 근사, 경험치 저장·레벨 캐시, 워프 재처치 50%·일 2회, 부활 무적 중 보스 피해 ×0.25, 첫 보스 보상 2택1, MVP 1~5구간, 서버 판정, 패스 = 30일 개발자 상품"],
        "notes": [
            "자동 타격과 버튼 평타는 1.0초 쿨다운을 공유한다 (v7 1.1/0.6 → 변경: 탭 속도 우위 제거, PvP 예측 가능). 1차(피버 OFF)에서 버튼 = 그로기/전환 창 전용 강타(combat.button_stagger_strike).",
            "리듬 탭(쿨다운 뒤 0.5초 창) 성공 = 콤보 +1, 실패 = 유지, 1.5초 무입력 = 0. 10콤보 = 피버 5초(공속 ×1.5). 보정 기준 탭 성공률 0.6(보수적). 실효 공속 절대 상한 ×2.2(피버·선제 러시 포함).",
            "보스 타격당 피해 상한(hit_cap, 장갑)은 보스마다 자동 산출: 자연 장비 플레이어의 평타(평균) ≤ 0.75×장갑(레벨이 보스전에 반영되고 '한계!'는 풀장비·강화의 신호) 이면서 풀 +10 균형 플레이어 중간 보스전 ≥ 11초. 치명 관통 ×1.5(광전사 ×1.6, 상한 ×1.6), 일부 보스 ×1.2 제한, 그로기 ×1.5, 파멸의 대검 ×1.2(비율형).",
            "플레이어가 받는 한 타격 상한 = 최대 체력 75%. 어느 쪽도 한 방 즉사 없음.",
            "한 판 = 가운데 길 10단계 + (5단계 광장) 질풍 루프 5구간 + (10단계 광장) 군단 루프 5구간 = 보스 20. 루프는 선택. 마지막 열린 보스를 잡으면 자동 결산, 처치한 구간은 조우 없음, 루프 재입장 불가, 보스 제단은 판당 1회.",
            "시뮬에 거리 모델이 없는 이유 = 규칙: 보스전은 좁은 원형 제단(반지름 ≤ 보스 반지름 + 4)에서 치르고 플레이어는 보스 사거리 밖으로 나갈 수 없다(브레스만 바깥 고리로 회피). 일반 몬스터 rise 종 이속 22 ≥ 플레이어 20 이라 뒤로 걷기 카이팅 불가.",
        ],
    }
    cfg["stats"] = {
        "hp":  {"name_ko": "체력", "base": 100, "per_pt": 10, "auto_ratio": 1.0, "desc_ko": "최대 체력 = (100 + 10×체력pt) × 장비 체력 배율"},
        "atk": {"name_ko": "힘",   "base": 10,  "per_pt": 2,  "auto_ratio": 2.0, "desc_ko": "공격력 = (10 + 2×힘pt) × 장비 공격 배율. 피해 = 공격력 × U(0.9,1.1) × 치명 배율"},
        "luk": {"name_ko": "행운", "base": 1,   "per_pt": 1,  "auto_ratio": 0.5, "desc_ko": "치명타 확률, 레벨업 '행운! 2배 당첨' 확률, 정수 추가 드롭, (PvP) 회피"},
        "ls":  {"name_ko": "흡혈", "base": 0,   "per_pt": 1,  "auto_ratio": 0.5, "desc_ko": "포인트 P → 흡혈% = 30%×P/(P + 1.0×레벨 + 50) (장비와 합산; 레벨 ≫ 50 수렴값: 균형 분배 ≈8.2%, 흡혈 균형(0.75) ≈10.8%, 몰빵(3) ≈20.8%). 초당 회복 상한(0.8×흡혈률)을 함께 올린다"},
        "pts_per_level": 3,
    }
    cfg["formulas"] = {
        "crit": {"base": 0.05, "span": 0.60, "lvl_coef": 0.5, "c": 40, "mult_base": 2.0,
                 "text_ko": "치명타 확률 = min(상한, 5% + 60%×행운/(행운 + 0.5×레벨 + 40) + 장비). 치명타 피해 = min(상한, ×2.0 + 장비). 보스 상한 관통 ×1.5(기본)."},
        "luck_bonus": {"p_coef": 0.5, "lvl_coef": 0.5, "c": 50, "p_cap": 0.5, "double_mult": 2.0, "binomial_direct_below_n": 50,
                       "text_ko": "레벨이 n 오를 때 당첨 수 ~ Binomial(n, p), p = min(50%, 0.5×행운/(행운 + 0.5×레벨 + 50)); 당첨된 레벨의 포인트 3 → 6 ('행운!' 팝). 서버는 레벨마다 주사위를 굴리지 않는다: n < 50 이면 직접 n회, 그 이상은 정규 근사 n·p + √(n·p·(1−p))·Z (Box–Muller) 1회 계산 (B20 처치 한 번 = 레벨 +112억 → 112억 회 루프 불가). 기대 포인트 = 3×(1+p) ≤ 4.5 (상한 ×1.5). 자동 모험·예측 수정구도 같은 함수(시드 고정). 고레벨은 '행운 ×n' 묶음 표시."},
        "lifesteal": {"max_from_pts": 0.30, "lvl_coef": 1.0, "c": 50, "heal_per_s_cap_base": 0.05, "heal_per_s_ls_coef": 0.8,
                      "text_ko": "흡혈% = min(상한, 30%×P/(P + 1.0×레벨 + 50) + 장비). 초당 회복 상한 = max(5% + 성배, 0.8×흡혈률) × 최대 체력 (스윙당 상한 = 그 값 × 공격 간격) → 공속을 올려도 회복은 늘지 않고, 흡혈에 투자하면 상한이 오른다. 보스 기믹으로 흡혈 ×0.5. 거울 기사(B15) 전투에서는 결투장 초당 회복 상한(caps.pvp.heal_per_s_max 6%)을 쓴다."},
        "aspd": {"half": 1.5, "fever_abs_cap": 2.2,
                 "text_ko": "공속 배율 = 1 + S/(1 + S/1.5), S = 장비 공속 보너스 합. S 0.6→1.43, 0.9→1.56, 1.2→1.67, ∞→2.5(상한). 음수는 1+S. 피버 ×1.5·선제 러시(첫 3타 ÷2)를 전부 적용한 뒤 실효 공속을 절대 상한 ×2.2(간격 0.45초)로 자른다 — 풀 +10 보스전 11초 하한과 탭 매크로 상한."},
        "range": {"base": 9, "cap": 18, "per_target": 3,
                  "text_ko": "공격 범위 R = min(18, 9 + 장비). 동시 타격 수 = min(살아있는 적, 상한, 1 + floor((R−9)/3)). 13.5 → 2마리, 15+ → 3마리."},
        "damage_taken": {"player_hit_cap": 0.75, "zone_dmg_mult": 1.5, "zone_dmg_mult_by_stage": {"main": {"1": 1.0, "2": 1.2}}, "var_lo": 0.9, "var_hi": 1.1,
                         "text_ko": "받는 피해 = 몬스터 공격력 × U(0.9,1.1) × (1−피해감소) × (도박 구역 1.5; 가운데 1구간 1.0, 2구간 1.2 — 초보 보호). 한 타격 상한 = 최대 체력 75%. 사망 시 그 자리 부활·체력 가득·무적 2.5초(+수호 부적 2초, 강화 불가), 적 체력 유지. 부활 무적 중 보스에게 주는 피해 ×0.25."},
        "exp_gain": {"zone_exp_mult": 2.0,
                     "text_ko": "획득 경험치 = 몬스터 경험치 × 장비 경험치 배율 × (도박 구역 ×2, 행운의 왕관 +0.5) × (보스: 영혼 왕관 ×2)."},
    }
    cfg["caps"] = {
        "text_ko": "장비·강화·스탯을 아무리 쌓아도 못 넘는 선. PvE 열은 판에서, PvP 열은 마을 결투장에서. 같은 코드가 열만 바꿔 읽는다. PvP 피해감소 15% 는 한 타 상한(10%) '뒤'에 적용되고, 피해감소 효과는 어느 아이템도 강화되지 않는다(K2: 용암 망토 +10 하나로 상성표가 뒤집혔다).",
        "pve": {"aspd_mult": 2.5, "lifesteal": 0.30, "heal_per_s_max": 0.20, "crit_p": 0.60, "crit_mult": 4.0, "crit_pierce": 1.6,
                "dmg_reduce": 0.40, "reflect": 0.30, "splash": 0.50, "range_targets": 3, "exp_mult": 3.5, "boss_exp_mult": 2.0,
                "atk_mult": 3.5, "hp_mult": 2.0, "hit_taken_cap": 0.75, "dmg_mult": 1.0},
        "pvp": {"aspd_mult": 2.2, "lifesteal": 0.30, "heal_per_s_max": 0.06, "crit_p": 0.50, "crit_mult": 3.0, "crit_pierce": 1.0,
                "dmg_reduce": 0.15, "reflect": 0.10, "splash": 0.15, "range_targets": 2, "exp_mult": 1.0, "boss_exp_mult": 1.0,
                "atk_mult": 2.5, "hp_mult": 2.0, "hit_taken_cap": 0.10, "dmg_mult": 0.08},
        "names_ko": {"aspd_mult": "공속 배율", "lifesteal": "흡혈률", "heal_per_s_max": "초당 회복 상한 최대", "crit_p": "치명 확률", "crit_mult": "치명 피해",
                     "crit_pierce": "상한 관통", "dmg_reduce": "피해감소", "reflect": "반격", "splash": "스플래시", "range_targets": "동시 타격 수",
                     "exp_mult": "경험치 배율", "boss_exp_mult": "보스 경험치 배율", "atk_mult": "공격 배율", "hp_mult": "체력 배율",
                     "hit_taken_cap": "받는 한 타 상한(최대 체력 비율)", "dmg_mult": "피해 보정"},
    }
    cfg["exp_curve"] = {"n0": 10, "K": 1000, "a": 0.30,
                        "text_ko": "need(L) = 10×(1+L/1000)^0.3. 누적 E(L) = 7692.3×((1+L/1000)^1.3 − 1.0013). 역함수 L(E) = 1000×((E/7692.3 + 1.0013)^(1/1.3) − 1). need(1)=10, need(1만)=20.5, need(100만)=79, need(1억)=316."}
    cfg["combat"] = {
        "attack_interval": 1.0, "button_shares_cooldown": True, "button_range": 11, "auto_range": 9,
        "button_stagger_strike": {"enabled_phase": 1, "text_ko": "1차(피버 OFF)의 버튼 역할: 그로기/전환 창 안에서 누르면 그 1타에 그로기 배율(피해 ×1.5·상한 ×1.5)이 '손으로' 터진다. 시뮬의 그로기 수치와 같아 재보정 불필요. 피버 도입 뒤에는 리듬 탭 버튼으로 전환."},
        "first_hit": 1.2, "approach_s": 0.5, "crit_cap_mult": 1.5,
        "zone_use_p_manual": 0.9, "zone_use_p_auto": 0.6, "zone_once_per_zone": True, "intro_no_zone": True, "zones_per_stage": 1,
        "max_fight_s": 240, "revive_invuln": 2.5, "revive_invuln_boss_dmg_mult": 0.25, "death_anim_s": 1.5, "spawn_s": 2.0, "loot_s": 0.8,
        "boss_intro_s": 3.0, "door_s": 4.0, "after_fight_heal": 0.5, "regen_per_s": 0.06,
        "fever_hits": 10, "fever_dur_s": 5.0, "fever_aspd": 1.5, "manual_combo_p": 0.6, "tap_window_s": 0.5, "combo_idle_reset_s": 1.5,
        "monster_attack_reach": "3.2 + 반지름", "monster_windup_s": 0.45,
        "boss_arena": {"radius_add": 4, "text_ko": "보스전은 좁은 원형 제단: 반지름 ≤ 보스 반지름 + 4 stud, 플레이어는 보스 사거리(3.2+반지름) 밖으로 나갈 수 없다(보이지 않는 벽). 브레스는 바닥 부채꼴을 제단 바깥 고리로 걸어 나가 피한다. → 시뮬 '보스 항상 사거리 안' 가정이 규칙이 된다. 보스 이속 9 는 연출값."},
        "timing": {"add_spawn_stagger_s": 0.3, "boss_attack_after_transition_s": 0.8, "boss_attack_delay_after_transition_hit_s": 0.6, "boss_attack_delay_after_stagger_s": 0.4,
                   "near_miss_hp_frac": 0.15, "no_boss_door_s_mult": 0.5, "max_adds_alive": 3,
                   "text_ko": "소환수는 0.3초 간격으로 순차 등장, 동시 수하 상한 3(초과분은 소환되지 않음 — 모바일 성능). 체력바 전환이 끝난 뒤 보스 첫 공격 0.8초. 전환/그로기 중 공격 차례가 돌아온 보스는 각각 0.6/0.4초 뒤에 공격. 니어미스 = 체력 15% 이하로 떨어졌다가 무사망 승리. 조건부 보스가 안 나온 구간의 문 열림 연출 = 4초×0.5. 피해 숫자는 대상별 0.25초 합산 1개."},
        "text_ko": "도박 구역: 반지름 10, 구간마다 정확히 1곳 — 조우 트리거 지점 위에 놓인다(인트로 3전투 제외). 그 안에서 시작한 전투는 경험치 ×2·받는 피해 ×1.5(1구간 1.0, 2구간 1.2), 전투 1회 뒤 소진. 바닥 붉은 테두리 + '위험' 아이콘. 수동 플레이어는 90%, 자동 모험은 60% 가 구역을 쓴다고 가정(앵커도 같은 값). 전투 종료 시 최대 체력 50% 즉시 회복 + 비전투 초당 6%. 보스 제단 입장 시 체력 가득.",
    }
    cfg["run"] = {
        "energy_start": 16, "energy_max": 30, "energy_fight": 1, "energy_death_base": 3, "energy_death_step": 1, "energy_death_max": 6,
        "energy_boss_main": 4, "energy_boss_loop": 5, "boss_altar_full_heal": True,
        "death_counter_reset": "door", "last_stand": True, "end_after_last_boss": True, "cleared_stage_no_encounter": True, "loop_reentry": False, "altar_once_per_run": True,
        "leftover_energy_reward": "none",
        "move_speed": 20, "village_to_gate_s": 14, "result_s": 5,
        "encounter": {"mode": "fixed_trigger", "jitter_stud": 10, "fights_main": 4, "fights_loop": 2,
                      "legacy_gauge_ko": "v8 의 확률 게이지(1칸 30 stud, 3칸부터 매초 칸×15%)와 설계 v1.1 의 1칸 25 stud 는 폐기 — 265 stud 에서 기대 전투 2.6회라 '구간당 4전투' 앵커와 어긋났다(K3-1).",
                      "text_ko": "조우 = 고정 트리거: 구간 길이 ÷ fights 간격의 Z 지점(±10 stud 지터)마다 전투 1회 강제. routes.*.stages[].fights 가 트리거 수(가운데 4, 루프 2). 이속·스피드핵이 전투 수를 바꾸지 못하고 config·시뮬·게임이 1:1. 처치한 구간의 트리거는 꺼진다(안전지대). 에너지 0 이면 남은 트리거도 꺼진다(마지막 도전)."},
        "warp": {"unlock_kills": 3, "start_energy": 12, "level_factor": 0.9, "warp_s": 5, "repeat_stone_mult": 0.5, "daily_limit": 2,
                 "text_ko": "워프 제단: 광장 문 보스(청색의 드래곤/황제 드래곤)를 3회 처치하면 그 광장에서 판 시작 가능(레벨 = 그 광장 기준 진입 레벨 ×0.9, 에너지 12). 워프 판은 기록판에 '워프' 표식, 20보스 기록 제외, 재처치 강화석은 자동 모험과 같은 50%(무사망·25% 보너스 없음), 하루 2회 — 3.7분 워프 판이 마을 20보스 판을 사장시키지 않게(K2-4)."},
        "text_ko": "시작 에너지 16, 보유 상한 30, 전투 승리 −1, 사망 n번째(한 구간 안) = min(6, 3+(n−1)) → 3,4,5,6,6…, 가운데 보스 +4, 루프 보스 +5(그 전투는 −1 없음). 루프 구간 = 2전투 −2 + 보스 +5 = 순이익 +3 → '장비 갖춘 뒤 들어가는 에너지 광산'. 사망 누진 카운터는 문(보스 처치)마다, 그리고 루프 입장 1회 0 으로 초기화 — 광장 왕복·루프 퇴장으로는 초기화되지 않는다. 수호 부적의 '첫 사망 −1' 은 판당 1회. 에너지 0 = 남은 조우 없이 그 구간 제단까지 가서 보스전을 치를 수 있다('마지막 도전', 사망하면 종료, 승리하면 +4 로 계속). 판 종료 = 보스전 사망으로 에너지 0 / 마지막 열린 보스 처치(자동 결산) / 복귀. 종료 시 레벨 1·포인트 0, 장비·강화·강화석·정수·기록 유지, 잔여 에너지는 어떤 보상으로도 바뀌지 않는다. 보스 제단은 판당 1회(한 판에 한 번만 활성, 재도전 불가), 처치한 구간은 조우 없음(안전지대), 루프는 광장 복귀 뒤 재진입 불가. 문은 이번 판에 그 보스를 잡아야 열림. 조건부 보스가 등장하지 않은 구간은 문이 바로 열린다(보상 없음). HUD: 에너지 옆에 '남은 목숨 ♥'(지금 에너지로 감당 가능한 사망 수) 병기, 튜토리얼 문구 '이 구간에서 세 번 죽으면 판이 끝나요'.",
    }
    cfg["slots"] = {"무기": 1, "정령": 1, "반지": 2, "망토": 1, "왕관": 1, "부적": 1}

    def E(k, v, up=True, **kw):
        d = {"k": k, "v": v, "up": up}
        d.update(kw)
        return d

    cfg["items"] = {
        "I01": dict(name_ko="엄니검", boss="B01", slot="무기", tier=1, rank=1, effects=[E("atk_mult_bonus", 0.35)], pvp_disabled=[],
                    desc_ko="공격력 ×1.35 (힘 기반 배율 — 레벨과 함께 자란다). +10강 ×1.76. B01 첫 처치 보상 2택1(엄니검 / 수정 갑주)의 기본 선택.", pvp_ko="허용"),
        "I00": dict(name_ko="수정 갑주", boss="B01", slot="망토", tier=1, rank=0, effects=[E("dmg_reduce", 0.10, up=False), E("range_add", 3.0, up=False)], pvp_disabled=[], alt_of="I01",
                    desc_ko="B01 첫 처치 보상 2택1 의 다른 쪽(엄니검 ×1.35 대신): 받는 피해 −10%, 범위 +3(2마리). 강화 불가. 미선택 쪽은 B01 재처치 때 100% 드롭 — 첫 10분 안의 첫 '선택'(K1). 20종 드롭 + 선택 보상 1종.", pvp_ko="허용"),
        "I02": dict(name_ko="바람 정령", boss="B02", slot="정령", tier=1, rank=1, effects=[E("S", 0.60)], pvp_disabled=[],
                    desc_ko="공속 보너스 S +0.6 → 배율 1.43(단독). +10강 S 1.30 → 1.70.", pvp_ko="허용(공속 상한 2.2)"),
        "I03": dict(name_ko="흡혈 송곳니", boss="B03", slot="반지", tier=1, rank=2, effects=[E("ls", 0.05)], pvp_disabled=[],
                    desc_ko="흡혈 +5%p (총 30% 상한, 초당 회복 상한도 0.8×흡혈률로 오름). +10강 +10.8%p.", pvp_ko="허용(흡혈 상한 30%·초당 회복 6%)"),
        "I04": dict(name_ko="거인 망토", boss="B04", slot="망토", tier=1, rank=1, effects=[E("range_add", 4.5), E("move_bonus", 0.10, up=False)], pvp_disabled=[],
                    desc_ko="공격 범위 9→13.5 stud = 동시에 2마리. 이동속도 +10%. +10강 범위 +9.7 → 3마리.", pvp_ko="3v3 에서만 의미(2마리 상한)"),
        "I05": dict(name_ko="에테르 왕관", boss="B05", slot="왕관", tier=1, rank=1, effects=[E("exp_mult_bonus", 0.50)], pvp_disabled=["exp_mult_bonus"],
                    desc_ko="얻는 경험치 ×1.5 (레벨 ×1.37). +10강 ×2.08 (총 ×3.5 상한).", pvp_ko="무효(결투는 레벨 고정)"),
        "I06": dict(name_ko="광전사 반지", boss="B06", slot="반지", tier=2, rank=3, effects=[E("crit_dmg", 0.50), E("ls_crit_mult", 2.0, up=False), E("crit_pierce_add", 0.1, up=False)], pvp_disabled=["crit_pierce_add"],
                    desc_ko="치명타 피해 ×2 → ×2.5, 치명타 시 흡혈 2배, 보스 장갑 관통 ×1.5 → ×1.6(상한, 행운에 '장갑 뚫기' 역할). +10강 ×3.08.", pvp_ko="허용(치명 ×3 상한, 관통 무효)"),
        "I07": dict(name_ko="용암 망토", boss="B07", slot="망토", tier=2, rank=3, effects=[E("dmg_reduce", 0.15, up=False), E("range_add", 3.0, up=False), E("reflect", 0.10)], pvp_disabled=[],
                    desc_ko="받는 피해 −15%(PvE 총 40%·PvP 15% 상한, 강화 불가), 받은 피해의 10% 반격, 범위 +3(2마리). +10강 반격 22%.", pvp_ko="허용(피해감소 15%·반격 10% 상한)"),
        "I08": dict(name_ko="번개 정령", boss="B08", slot="정령", tier=2, rank=2, effects=[E("S", 0.70), E("nth_crit", 5, up=False)], pvp_disabled=[],
                    desc_ko="공속 S +0.7, 매 5번째 타격은 치명타 확정(번개) — 저주 보스의 답. +10강 S 1.51.", pvp_ko="허용"),
        "I09": dict(name_ko="수호 부적", boss="B09", slot="부적", tier=2, rank=1, effects=[E("revive_invuln_add", 2.0, up=False), E("first_death_cost", 1, up=False), E("dmg_reduce", 0.05, up=False)], pvp_disabled=["revive_invuln_add", "first_death_cost"],
                    desc_ko="부활 무적 2.5→4.5초(강화 불가; 무적 중 보스 피해 ×0.25), 판당 1회 첫 사망의 에너지 −3 → −1, 받는 피해 −5%. 강화 대상 없음.", pvp_ko="피해감소 5%만 허용"),
        "I10": dict(name_ko="파멸의 대검", boss="B10", slot="무기", tier=2, rank=3, effects=[E("atk_mult_bonus", 0.60), E("S", -0.15, up=False), E("cap_rel_add", 0.2, up=False)], pvp_disabled=["cap_rel_add"],
                    desc_ko="공격력 ×1.6, 공속 −15%, 보스 타격 상한 ×1.2(비율형 — 장갑 3% 보스도 5% 보스도 같은 +20%). +10강 ×2.30.", pvp_ko="허용(상한 보너스 무효)"),
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
                    desc_ko="범위 9→15(3마리), 적이 2마리 이상이면 공격력 +25%, 받는 피해 −15%(군단 갑주, 강화 안 됨 — 1:1 보스에서 용암 망토 대신 껴도 손해가 아니게; 용암 망토는 반격 강화로 1:1 전용). +10강 범위 +13(상한 18), +54%.", pvp_ko="3v3 에서만 의미(피해감소 15% 는 허용)"),
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
        "text_ko": "강화 +p 는 up:true 효과값에 1.08^p (+5 ×1.47, +10 ×2.16). 피해감소·부활 무적·에너지·관통 효과는 강화 대상이 아니고(up:false), 나머지는 합산 상한(caps)에 걸린다 → 강화가 PvP 상성(L-1·L-4 비대칭 격자 20~80%)을 망가뜨리지 않는다. 강화석·정수 판매 없음.",
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
        "newbie_bonus_days": 7,
        "first_release_products": ["teleport"],
        "auto_adventure": {"free_per_day": 3, "pass_per_day": 6, "stone_rate": 0.5, "manual_runs_per_day_assumed": 5, "first_kill": False, "records": False, "speed_free": 2, "speed_pass": 8,
                           "text_ko": "자동 모험: 피버 없음·구역 사용 60%·브레스 회피 35%·조건 보스는 운에 맡김 → 항상 수동보다 손해. 이미 잡은 보스까지만, 강화석·정수 50%, 첫 처치·기록 없음. 무료 3회/일, 패스 6회/일. 서버는 순수 전투 모듈(플레이어 상태·적 목록·시드 → 이벤트 로그)을 돌리고 화면은 그 로그를 ×2/×8 로 재생한다."},
        "rules_ko": "꾸미기·치장 상품 없음. 확률형 유료 뽑기 없음. 강화석·정수·에너지·강화 보호권·레벨 직접 판매 없음(B의 강화 보호 두루마리 삭제). 결과(레벨·클리어·PvP 전력)를 크게 바꾸지 않는 시간·정보·사회·도전권 상품만. 계정 성장 속도 영향 ≤ ×1.3(시뮬 O표). 상품 유형은 Roblox 가 실제로 제공하는 것만(구독은 현지 통화 가격 단계·연령/플랫폼 제한·무료 체험 없음 → 패스는 30일 개발자 상품). 1차 출시 과금은 순간이동권 1종.",
        "products": [
            {"id": "pass", "name_ko": "모험 패스 (30일)", "price_robux": 399, "product_type_ko": "개발자 상품(소모) — 구매 시 서버가 만료 시각(+30일) 저장, 구독 아님",
             "trial_ko": "신규 계정 7일 혜택: 가입 뒤 7일 동안 패스 기능이 켜져 있고 8일째 알림 없이 조용히 무료 구성으로 돌아간다(축소 연출·상실감 트리거 없음 — 저연령 다크패턴 회피)",
             "effects_ko": ["자동 모험 3→6회/일, 빨리감기 ×8(무료 ×2)", "장비 프리셋 3개(무료 1개) — 제단 앞 교체가 한 번에", "자동 모험 판 리플레이 30개·공유 카드", "상세 통계(DPS·상한 타격 비율·피버·행운! 횟수)", "에너지 보너스 없음 — B 안의 '시작 에너지 +1' 은 시뮬 H표에서 결과를 바꾸는 수치로 측정되어 삭제"],
             "why_no_result_ko": "판의 전투·보상 규칙은 무료와 동일. 자동 모험은 첫 처치 없음·50% → 계정 성장 ≤×1.3(O표). H표가 '+1 에너지를 팔면 어떻게 되는가'를 기록."},
            {"id": "teleport", "name_ko": "순간이동권 (영구)", "price_robux": 149, "product_type_ko": "게임 패스(영구) — 1차 출시 유일 상품",
             "effects_ko": ["마을 ↔ 갈림길 광장 ↔ 루프 입구 순간이동(루프 입출 6초×4 + 마을 문 14초 = 판당 약 40초 절약)", "판 종료 결산 즉시 스킵"],
             "why_no_result_ko": "전투·조우·보상 동일. 20보스 판 18분 중 이동 약 2.2분의 일부만 줄인다."},
            {"id": "record_book", "name_ko": "기록의 책", "price_robux": 99, "product_type_ko": "게임 패스(영구)",
             "effects_ko": ["보스별 최단 처치 기록·빌드 저장", "자동 모험 판 리플레이 공유 코드(시드 + 빌드 → 같은 결과; 수동 판은 이동·탭·구역 입력이 변수라 재현 불가 → 보스전 이벤트 로그 요약만 저장)", "서버 리더보드 등록(최종 레벨만, 누적형 통계 없음)"],
             "why_no_result_ko": "기록·공유만."},
            {"id": "festival", "name_ko": "축제 깃발 (서버 전체)", "price_robux": 99, "product_type_ko": "개발자 상품(소모, 서버 전체 효과)",
             "effects_ko": ["구매자 이름 서버 공지 + 10분간 서버 모두의 도박 구역 ×2 → ×2.5(구역 수는 구간당 1곳 그대로)", "결산·공유 카드·기록판에 '깃발 판' 표식 강제(기록 오염 방지)"],
             "why_no_result_ko": "서버 전원 대칭. 구역 전투가 전투의 22%(1/4 × 90%) 이므로 레벨 기록 +약 6% — 표식으로 분리."},
            {"id": "lens", "name_ko": "관찰 렌즈 (영구)", "price_robux": 149, "product_type_ko": "게임 패스(영구)",
             "effects_ko": ["보스 체력바에 페이즈 경계·그로기/브레스/폭주 타이머 표시, 숫자에 '한계!'·'장갑!' 표기", "제단 앞 조건부 보스 조건 표시"],
             "why_no_result_ko": "정보 상품. 보스는 결정적이라 숙련자는 외운다."},
            {"id": "crystal", "name_ko": "예측 수정구", "price_robux": 49, "bundle_ko": "10개", "product_type_ko": "개발자 상품(소모, 10개 묶음)",
             "effects_ko": ["제단 앞 예측 카드: 현재 빌드로 이 보스 '예상 32초·사망 1.1 → 거북 반지면 25초·0.6' (서버가 같은 규칙으로 40회 시뮬)", "결투장 입장 시 저장 분배가 프리셋 밖이면 같은 로직으로 '결투 승률 예측' 카드(무료)", "자동 모험(시뮬) 추가 실행권. 하루 무료 3회"],
             "why_no_result_ko": "정보만. 실제 판은 조우가 랜덤이라 공략 계획 도구."},
            {"id": "rush_tickets", "name_ko": "보스 러시 도전권 3장", "price_robux": 49, "product_type_ko": "개발자 상품(소모, 3장)",
             "effects_ko": ["20보스 연속 타임어택(결투 레벨 100,000 고정·장비·강화만, 에너지 없음). 보상 기록 + 4급 강화석(일 상한 30). 무료 1장/일"],
             "why_no_result_ko": "PvP 와 같은 축(장비·강화만)에서 경쟁을 미리 학습. 강화석 일 상한은 E-2 실측 수입 대비 비율을 §10 에 병기."},
        ],
        "free_paths_ko": ["워프 제단: 광장 문 보스 3회 처치로 무료 해금(유료 즉시 해금 없음)", "자동 모험 3회/일", "예측 수정구 3회/일", "결투 승률 예측 카드 무료", "보스 러시 1장/일", "리플레이 5개"],
    }
    cfg["pvp"] = {
        "duel_level": 100000, "time_limit_s": 60, "heal_off_after_s": 45, "dmg_mult": 0.08, "dodge_from_crit": 0.35, "dodge_cap": 0.25, "dodge_floor": 0.10, "fever": False, "first_swing_delay_s": [0.3, 0.7],
        "points_fixed": True, "heal_per_hit_hp_frac": 0.12, "heal_basis": "geomean",
        "caps_ref": "caps.pvp",
        "gear_sets_for_test": {"공격셋": ["I10", "I20", "I06", "I17", "I16", "I14", "I18"], "방어셋": ["I10", "I12", "I17", "I06", "I07", "I14", "I09"],
                               "흡혈셋": ["I10", "I12", "I17", "I03", "I07", "I14", "I09"], "속공셋": ["I15", "I20", "I11", "I06", "I16", "I14", "I18"],
                               "PvE 자동 장착(참고)": None},
        "gear_sets_note_ko": "L-4 기준 상대 = 균형 + 공격셋(전부 +10). 결투용 4셋은 모두 대검/질풍검 + 행운의 왕관(치명→회피) 기준. 'PvE 자동 장착'(영혼 왕관·경험치 효과는 결투 무효)은 참고 열. 폭풍 정령(치명 −10%p)·질풍검 분산 0.7~1.5(한 타 상한 10% 에 잘림)·엄니검(+10 ×1.76 vs 대검 ×2.30) 조합은 결투 열세 → 예측 카드가 경고.",
        "trap_builds_for_test": {"체력 몰빵": {"hp": 3.0, "atk": 1.0, "luk": 0.0, "ls": 0.0}, "흡혈 몰빵": {"hp": 1.0, "atk": 1.0, "luk": 0.0, "ls": 2.0},
                                 "체력 흡혈": {"hp": 2.0, "atk": 0.5, "luk": 0.5, "ls": 1.0}, "공격 몰빵": {"hp": 0.5, "atk": 3.0, "luk": 0.5, "ls": 0.0}},
        "text_ko": "마을 결투장: 두 플레이어 모두 결투 레벨 100,000 으로 정규화(각자 저장된 분배 비율대로 포인트), 장착 장비·강화만 그대로. 주는 피해 ×0.08, 한 타 ≤ 상대 최대 체력 10%(최소 10타) — 피해감소(≤15%, 강화 불가)는 그 상한 '뒤'에 적용, 공속 ≤2.2, 흡혈 ≤30%(PvE 와 같음 — 20% 로 자르면 흡혈 빌드의 유일한 결투 장점이 사라져 전패했다), 초당 회복 ≤6%, 치명 ≤50%·×3, 반격 ≤10%, 관통 없음, 피버 없음. 회피 = max(10%, 치명 확률 ×0.35) ≤25% (행운 = 결투 방어 스탯, 행운 0 도 하한 10%). 결투 포인트는 레벨 100,000 분량(300,000)으로 고정(행운 당첨 없음 — 당첨은 PvE 전용). 결투 흡혈: 타격당 회복 = 흡혈률 × √(내 최대 체력 × 상대 최대 체력) × 12%, 초당 ≤6%. 45초부터 양측 회복 0(버티기 메타 방지), 60초 후 체력% 높은 쪽 승. pvp_disabled 효과(경험치·에너지·상한 돌파·부활·보스 경험치) 무효. 3v3 에서 범위 2마리·스플래시 15%. 합격 조건: 프리셋 미러(L-1)와 '프리셋 5 × 장비셋 4 vs 균형 기본 장비'(L-4, 전부 +10) 승률 20~80%. 입장 시 저장 분배가 프리셋 밖이면 '결투 승률 예측' 카드(체력 몰빵 등 L-5 함정 경고).",
    }
    cfg["boss_rush"] = {"level": 100000, "death_penalty_s": 10, "daily_stone_cap": 30, "daily_stone_tier": 4, "free_tickets_per_day": 1,
                        "text_ko": "보스 러시: 결투 레벨 100,000 고정·장비·강화만, 20보스 연속(조건 무시), 사망 = +10초 페널티·체력 가득 부활, 합계 초 기록. 보상 강화석은 4급, 일 상한 30. 결투장 공간·UI 재사용."}
    cfg["server_authority"] = {
        "text_ko": "Roblox 는 캐릭터 이동이 클라이언트 권위이므로 전투 상태(체력·쿨다운·콤보·피버·구역 플래그·사망 카운터·에너지)는 전부 서버에 둔다. "
                   "회피 판정은 서버가 보는 위치 + 속도 검증(틱당 이동 > 이속×1.3 이면 되돌림, 제단 안 가두기). 탭은 클라이언트 타임스탬프를 받되 서버가 '쿨다운당 콤보 +1 최대'로 레이트 리밋하고 창 판정은 서버 기준 ±RTT/2 보정. "
                   "실효 공속 절대 상한 ×2.2 가 매크로 상한. 조건부 보스(25초 컷·무사망·구역 전투)·재처치 무사망 +1 강화석·에너지·강화 시도 전부 서버 판정. 1차 작업 2~3일.",
        "speed_check_mult": 1.3, "combo_rate_limit": "쿨다운당 +1", "rtt_compensation": "±RTT/2",
    }
    cfg["save_schema"] = {
        "version": 2, "datastore": "LvBoom_v2",
        "fields_ko": ["exp_total(double, 저장 원본) + level(캐시 = floor(L(E)+1e-9), 단조 보호)", "items 보유 21(I00~I20) + plus 0~10", "stones 4급 + essence 20종", "pity 카운터", "builds 저장 분배 비율", "records(보스별 최단 초·최고 레벨 — 누적형 통계 없음)", "daily 카운터(자동 모험·수정구·러시·워프)", "pass_expires_at", "b10/b05 처치 횟수(워프 해금)"],
        "migration_ko": "LvBoom_v1(아이템 5 + plus 1.3^plus) → v2: 아이템 5 → I01~I05 매핑, 기존 plus 는 0 으로 리셋(배율 체계 상이)하고 보상으로 1급 강화석 2×plus 지급, 로드 시 1회 변환 뒤 v:2 기록. 전부 채운 계정 블롭 약 6.5 KB(한도 4 MB). 작업 1일.",
        "precision_ko": "한 판 안의 모든 수(E ≈ 4.3e13)는 2^53 안. 평생 누적 경험치·총 피해량 같은 누적형 통계는 저장하지 않는다(212판에 2^53 초과). 리더보드는 레벨만. E 가 1e15 를 넘으면 경고 로그.",
    }
    cfg["ui_ko"] = {
        "hud": "에너지 숫자 옆 '남은 목숨 ♥♥♥'(지금 에너지로 감당 가능한 사망 수, 누진 3·4·5·6 반영). 튜토리얼 문구 '이 구간에서 세 번 죽으면 판이 끝나요'.",
        "first_run_result": "첫 판 결산 카드에 '다음 판 분배 프리셋 5종' 선택(기본 균형, 치명·흡혈 % 비교 표시) — 첫 10분 안의 두 번째 선택.",
        "b01_reward_choice": "B01 첫 처치: 엄니검(공격 ×1.35) / 수정 갑주(받는 피해 −10%·범위 +3) 2택1 카드. 미선택은 B01 재처치 때 드롭.",
        "zone": "도박 구역 바닥 붉은 테두리 + '위험·경험치 ×2' 아이콘. 1구간은 피해 배율 1.0 이라 안전하게 배운다.",
        "last_stand": "에너지 0 이 되면 화면 상단 '마지막 도전 — 제단까지 조우 없음, 보스전에서 죽으면 끝'.",
        "duel_predict": "결투장 입장 시 저장 분배가 프리셋 밖이면 '결투 승률 예측' 카드(40회 시뮬).",
    }
    cfg["hidden_conditions"] = {
        "prev_boss_secs_max": "직전 보스를 N초 안에 처치 (피버·그로기·공속의 보상)",
        "zone_fight_this_stage": "이 구간의 도박 구역에서 전투 1회 승리 (선택이 곧 조건)",
        "no_death_prev_boss": "직전 보스전 무사망 (숙련)",
        "all_prev_loop_bosses": "이 루프의 앞 보스 전부 이번 판 처치 (험로 전부)",
        "text_ko": "조건 미충족 시 제단에 흔적(발자국·시계 소리·거울 파편)만 남고 문이 바로 열린다. 조건은 전부 JSON(bosses[].spawn_condition), 코드에는 판정 함수 1개.",
    }
    cfg["release_plan_ko"] = [
        "1차 MVP(약 18 작업일, 솔로): 가운데 1~5구간·보스 5(v8 모델 5 재사용, 신규 모델 0)·아이템 5(+수정 갑주)·기믹 7키(그로기·브레스·분노·보호막·소환·광란·전환 그로기)·경험치 곡선·에너지 16/상한 30·누진 사망(문마다 초기화)·마지막 도전·장갑/체력바·고정 트리거 조우·구역 1곳·제단 가두기·1급 강화석 적립(+5 까지 100% 구간만)·피버 OFF(버튼 = 그로기 강타)·서버 전투 상태·순수 전투 모듈·저장 v2 마이그레이션·과금 순간이동권 1종·연출 3종(레벨 티커·체력바 깨짐·문) — 시뮬 R표 성립",
        "2차: 가운데 6~10구간·보스 5(신규 대형 모델 3)·아이템 5·2급 강화석·정수·천장·5:1 교환·반지 2칸·부적·피버 ON(탭 창 0.5초 실측 뒤 manual_combo_p 재설정·gen 재보정)·패스(30일 개발자 상품)·자동 모험·예측 수정구·기록의 책·렌즈 — 시뮬 I표 성립",
        "3차: 질풍 루프 5보스(Z 리스킨, 신규 Mount23~26) + 조건부 보스 B13·B14 + 3급 강화석 + 표지판 + 루프 에너지",
        "4차: 군단 루프 5보스(Mount27) + B18·B19 + 4급 강화석 + 결투장(거울 기사 코드 재사용, L-4 격자 재검) + 보스 러시 + 워프 제단(일 2회) + 축제 깃발 + 리더보드",
    ]
    cfg["schedule_estimate_ko"] = {
        "mvp_days": {"경험치·포인트·행운! 이항 근사": 2, "전투 코어(쿨다운 공유·치명·흡혈 상한·공속·범위·한 타 75%·회복)": 3, "보스 프레임(체력바·전환·장갑·관통) + 기믹 7키": 4,
                     "보스 5 배치·제단 가두기·문·고정 트리거·구역": 2, "아이템 6(12키)·자동 장착": 1.5, "저장 v2·마이그레이션": 1, "서버 판정·속도 검증": 1.5, "연출 3종": 1.5, "밸런스 QA·모바일 실기": 1.5},
        "mvp_total_days": 18, "full_total_days": "60~75 작업일(12~15주)", "full_note_ko": "v1.1 의 '1차 2~3주' 는 전체 범위 기준으로 4~6배 과소(K3-2)",
        "asset_count": "모델 참조 81(몬스터 60 + 보스 20 + 선택 보상 0) 중 재질 변경 51(몬스터 35 + 보스 16), '크게/최대' 스케일 8, 신규 Mount23~30 8종. MVP 는 신규 0.",
    }
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
# 이속: rise 종 22(플레이어 20 보다 빠름 → 뒤로 걷기 카이팅 불가, K3-3), rush 종 23~25 (3초간 ×1.5 돌진은 기존 규칙)
KIND = {
    "main":  [dict(hp_k=0.85, atk_k=0.07, interval=1.3, speed=22, spawn="rise", exp_m=1.0),
              dict(hp_k=1.80, atk_k=0.10, interval=1.3, speed=22, spawn="rise", exp_m=1.5),
              dict(hp_k=3.20, atk_k=0.15, interval=1.1, speed=24, spawn="rush", exp_m=2.5)],
    "left":  [dict(hp_k=0.70, atk_k=0.09, interval=1.0, speed=23, spawn="rush", exp_m=1.0),
              dict(hp_k=1.50, atk_k=0.13, interval=1.0, speed=24, spawn="rush", exp_m=1.5),
              dict(hp_k=2.60, atk_k=0.18, interval=0.9, speed=25, spawn="rush", exp_m=2.5)],
    "right": [dict(hp_k=1.00, atk_k=0.06, interval=1.3, speed=22, spawn="rise", exp_m=1.0),
              dict(hp_k=2.00, atk_k=0.085, interval=1.3, speed=22, spawn="rise", exp_m=1.5),
              dict(hp_k=3.50, atk_k=0.12, interval=1.2, speed=24, spawn="rush", exp_m=2.5)],
}
WEIGHTS = {"main": [45, 35, 20], "left": [40, 35, 25], "right": [35, 35, 30]}
GROUP = {"main": [35, 45, 20], "left": [25, 45, 30], "right": [0, 30, 70]}
# 보스 성향(D): 목표 초 배율, 공격 배율. 유리대포 ×0.7→×0.85 (K1-F3: 18초 보스는 자연 평타가 장갑을 4배 넘어 '타수 카운터'가 됐다)
ARCH = {"균형": (1.0, 1.0), "탱커": (1.3, 0.75), "유리대포": (0.85, 1.25), "균형(최종)": (1.0, 1.0)}
DPS_K_SCALE = 0.75  # 전 보스 공통 치명도 배율 (누진 사망 비용·초당 회복 상한 도입 보정)
BR = {"every_s": 9, "atk_mult": 2.2, "dodge_p_manual": 0.70, "dodge_p_auto": 0.35}
INTRO_SEQ = ["penguin", "penguin", "jelly"]   # 인트로 3전투: 2·3번째가 0.5초 원킬이던 것을 젤리말(2~3타, 피격 1~2회)로 (K1-F9)
NAT_CAP_RATIO = 0.75   # 자연 장비 플레이어 평타(평균) ≤ 장갑 × 0.75 → 레벨이 보스전에 반영, '한계!' 는 풀장비·강화의 신호 (K1-F3)
FLOOR_SECS = 11.0      # 풀 +10 균형 플레이어 보스전 중간값 하한 (BRIEF 10초 + 여유 1초) (K2-6)
CAP_STEP = 0.001

# (id, 이름, 모델, 키, 페이즈, 전환초, 상한, dps_k, 간격, 기준 목표 초, 성향, 기믹, 공략, 등장 조건, 관통 제한)
BOSSES = {
 "main": [
  ("B01", "수정 매머드", "Mount10 구슬 코뿔소(수정 재질)", 8, 3, 1.5, 0.035, 0.095, 2.1, 26, "균형",
   {"stagger": {"every_s": 10, "dur_s": 3, "dmg_mult": 1.5, "cap_mult": 1.5}},
   "10초마다 돌진 뒤 엄니가 땅에 박혀 3초 그로기(피해 ×1.5, 상한 ×1.5). 장비 없이도 그로기 3번이면 체력바 1개가 통째로 날아간다. 첫 보스 = 튜토리얼: 체력바·그로기·상한을 몸으로 배운다. 첫 처치 보상은 엄니검/수정 갑주 2택1.", None, None),
  ("B02", "화염 와이번", "Mount07", 9, 3, 1.2, 0.035, 0.070, 1.9, 26, "유리대포",
   {"breath": dict(BR), "enrage": {"from_phase": 2, "atk_mult": 1.3, "int_mult": 0.9}},
   "유리대포: 짧지만 아프다. 9초마다 1.5초 예고 후 화염 브레스(일반 타의 2.2배) — 예고 중 뒤로 걸으면 피함(수동 70%). 2페이즈 분노(공격 ×1.3, 간격 ×0.9). 브레스 직후 다시 붙기, 흡혈·체력 분배가 안정.", None, None),
  ("B03", "에테르 드래곤", "Mount28(v8 키 14 → 12)", 12, 3, 1.0, 0.05, 0.120, 1.9, 26, "균형",
   {"shield_hits": 3},
   "페이즈마다 에테르 보호막 3타 무효(피해량 무관) → 공속이 정답, 바람 정령이 보호막 벗기는 시간을 3초→2.1초로. 큰 한 방 빌드는 손해. (v1.1 탱커·보호막 5타는 엄니검만 든 2판째 플레이어에게 45초 벽이었다 — K1-F6)", None, None),
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
   {"regen_per_s": 0.005, "timer": {"at_s": 56, "atk_mult": 2.5}},
   "매초 최대 체력 0.5% 재생 + 56초(목표 초의 2배) 뒤 폭주(공격 ×2.5). 순수 DPS 체크. 자연 장비(6종) DPS 의 약 1/7 을 재생이 먹는다 (v1.1 0.8% 는 자연 처치 69%·게임오버 29% 의 첫 벽 — K1-F8).", None, None),
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
   {"stagger": {"every_s": 12, "dur_s": 3, "dmg_mult": 1.5, "cap_mult": 1.5}, "thorns_frac": 0.02},
   "조건부(군단 루프 앞 3보스 이번 판 전부 처치). 12초마다 3초 그로기(상한 ×1.5) + 가시 2%. 그로기 창에 한 방을 몰아넣는 리듬 보스. 영혼 왕관의 관문.",
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
                 desc_ko="10구간 10보스. 구간당 4전투 고정 트리거(1구간은 인트로 펭귄·펭귄·젤리말 3 + 1, 인트로는 구역 없음). 한 판 풀클리어가 '숙련 목표'(8~10분)."),
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


def zone_frac(cfg, nf, intro=0):
    """구간당 구역 전투 비율 = (구역 수 / 비인트로 전투 수) × 수동 사용 확률."""
    k = min(cfg["combat"]["zones_per_stage"], max(1, nf - intro))
    return k / max(1, nf - intro) * cfg["combat"]["zone_use_p_manual"]


def stage_exp_coef(cfg, route_id, nf, boss_mult):
    gprobs = GROUP[route_id]
    gsize = sum(p * n for p, n in zip(gprobs, (1, 2, 3))) / 100
    kinds, weights = KIND[route_id], WEIGHTS[route_id]
    avg_m = sum(w * k["exp_m"] for w, k in zip(weights, kinds)) / sum(weights)
    zone_mult = 1 + zone_frac(cfg, nf) * (cfg["formulas"]["exp_gain"]["zone_exp_mult"] - 1)
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
            intro_exp_m = sum(kinds[[s_[0] for s_ in spec].index(mid)]["exp_m"] for mid in INTRO_SEQ)   # 펭귄 1 + 펭귄 1 + 젤리말 1.5 (구역 없음)
            exp_after_intro = exp_total + intro_exp_m * base * gear["exp_mult"]
            exp_f1 = exp_after_intro
            # 1구간 비인트로 전투(1회)의 구역 비율 = 1/1 × 0.9
            pf_intro = per_fight_coef / (1 + zone_frac(cfg, nf) * (cfg["formulas"]["exp_gain"]["zone_exp_mult"] - 1)) * (1 + zone_frac(cfg, nf, intro) * (cfg["formulas"]["exp_gain"]["zone_exp_mult"] - 1)) * base * gear["exp_mult"]
            exp_boss = exp_after_intro + (nf - intro) * pf_intro
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
            phases=phases, transition_s=trans, hit_cap=cap, hit_cap_design_min=cap, crit_pierce_cap=pierce_cap, min_hits=int(math.ceil(1 / cap)), min_hits_floor=None,
            gimmick=gm, spawn_condition=cond, guide_ko=guide, drop_item="I" + bid[1:], stone_tier=cfg["items"]["I" + bid[1:]]["tier"],
            essence_id="ess_" + bid, recommended_level=int(p_b.lvl), target_secs_natural=T, target_secs_design=T, atk_factor=atk_f,
            energy_reward=cfg["run"]["energy_boss_main"] if route_id == "main" else cfg["run"]["energy_boss_loop"],
            anchor=dict(player_lvl=int(p_b.lvl), player_atk=int(p_b.atk()), player_hp=int(p_b.maxhp()), player_dps_natural=int(dps),
                        natural_items=S.auto_equip(cfg, owned), boss_hit_pct_of_player_hp=round(atk / p_b.maxhp() * 100, 1) if atk else None,
                        boss_dps_pct_of_player_hp=round(dps_k * DPS_K_SCALE * 100 * atk_f, 1), fever_uptime_assumed=round(fever_up, 2)),
        )
        if bid == "B01":
            cfg["bosses"][bid]["alt_drop_item"] = "I00"
            cfg["bosses"][bid]["reward_choice_ko"] = "첫 처치 보상 2택1: 엄니검(I01) / 수정 갑주(I00). 미선택은 재처치 때 100% 드롭."
        anchors_out.append((route_id, si + 1, int(p_f1.lvl), int(p_b.lvl), int(p_f1.atk()), int(p_f1.maxhp()), hp, atk, int(dps)))
        length = STAGE_LEN[route_id][si]
        p_in = virtual_player(cfg, gear, exp_total)
        exp_after_boss = exp_boss + boss_exp * gear["exp_mult"] * gear["boss_exp_mult"]
        p_after = virtual_player(cfg, gear, exp_after_boss)
        stages.append(dict(stage=si + 1, name_ko=f"{si+1}구간", z_from=z, z_to=z - length, length=length, fights=nf, trigger_spacing_stud=round(length / nf, 1),
                           monsters=mon_ids, monster_weights=([60, 35, 5] if (route_id == "main" and si == 0) else weights), boss=bid, base_exp=nice(base),
                           luck_zones=cfg["combat"]["zones_per_stage"], group_probs=([100, 0, 0] if (route_id == "main" and si == 0) else gprobs),
                           anchor_levels=dict(enter=int(p_in.lvl), after_first_fight=int(p_f1.lvl), at_boss=int(p_b.lvl), after_boss=int(p_after.lvl),
                                              natural_exp_mult=round(gear["exp_mult"], 2))))
        z -= length
        exp_total = exp_after_boss
    meta = ROUTE_META[route_id]
    out = dict(id=route_id, name_ko=meta["name_ko"], desc_ko=meta["desc_ko"], unlock_ko=meta["unlock_ko"], group_probs=gprobs,
               intro_fights=INTRO_MAIN if route_id == "main" else 0, intro_sequence=(list(INTRO_SEQ) if route_id == "main" else []), enter_s=meta["enter_s"], stages=stages)
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
                             ARCH={k: {"T_mult": v[0], "atk_factor": v[1]} for k, v in ARCH.items()}, DPS_K_SCALE=DPS_K_SCALE, STAGE_LEN=STAGE_LEN, FIGHTS=FIGHTS,
                             INTRO_SEQ=INTRO_SEQ, NAT_CAP_RATIO=NAT_CAP_RATIO, FLOOR_SECS=FLOOR_SECS, DEATH_TARGET=DEATH_TARGET)
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
        rs = S.RunState(cfg, rnd, 999, unlimited=True)   # 보정용 결투는 에너지 무제한
        pl = S.Player(cfg, gear, manual=True)
        S.feed_exp(pl, exp_b)
        pl.hp = pl.maxhp()
        res = S.combat(rs, pl, None, b, False, True)
        secs.append(res["secs"]); deaths.append(res["deaths"])
    return statistics.median(secs), sum(deaths) / len(deaths)


def floor_cap(cfg, b, L):
    """풀 +10 균형 플레이어(자동 장착 7칸 전부 +10)가 레벨 L 에서 이 보스를 FLOOR_SECS 안에 못 잡게 하는 최대 장갑(평균 관통·피버 가동률·전환·보호막 반영)."""
    Cc, F = cfg["combat"], cfg["formulas"]
    eq = S.auto_equip(cfg, list(cfg["items"].keys()))
    g = S.aggregate(cfg, eq, {i: 10 for i in eq})
    p = virtual_player(cfg, g, S.Curve(cfg["exp_curve"]).E(L))
    c = p.crit_p()
    pierce = min(Cc["crit_cap_mult"] + g["crit_pierce_add"], cfg["caps"]["pve"]["crit_pierce"])
    if b.get("crit_pierce_cap"):
        pierce = min(pierce, b["crit_pierce_cap"])
    pierce_eff = 1 + c * (pierce - 1)
    gm = b["gimmick"]
    stag_avg = 1.0
    if "stagger" in gm:
        s_ = gm["stagger"]
        stag_avg = 1 + s_["dur_s"] / (s_["every_s"] + s_["dur_s"]) * (s_["cap_mult"] - 1)
    iv10 = p.interval()
    iv_fev = max(Cc["attack_interval"] / F["aspd"]["fever_abs_cap"], iv10 / Cc["fever_aspd"])
    up = Cc["fever_dur_s"] / (Cc["fever_dur_s"] + Cc["fever_hits"] / Cc["manual_combo_p"] * iv10)
    iv_eff = up * iv_fev + (1 - up) * iv10
    trans = (b["phases"] - 1) * b["transition_s"]
    shield_t = gm.get("shield_hits", 0) * b["phases"] * iv_eff
    avail = FLOOR_SECS - trans - shield_t - Cc["approach_s"]
    if avail <= 1.0:
        return 0.03
    hits = avail / iv_eff
    return 1.0 / (hits * (1 + g["cap_rel_add"]) * pierce_eff * stag_avg)


def enforce_cap_constraint(cfg, b, gear, exp_b):
    """장갑 제약 (K1-F3·K2-6): 자연 평타(평균) / 보스 체력 ≤ NAT_CAP_RATIO × hit_cap 이면서 hit_cap ≤ floor_cap(풀 +10 하한).
    둘이 충돌하면 목표 초 T 를 늘려(체력 ↑ → 평타 비율 ↓) 둘 다 만족시킨다. 반환 (바뀐 T 여부)."""
    if b["gimmick"].get("mirror"):
        return False
    p_nat = virtual_player(cfg, gear, exp_b)
    h = p_nat.atk() / b["hp"]
    need = h / NAT_CAP_RATIO
    cmax = floor_cap(cfg, b, b["anchor"]["player_lvl"])
    changed_T = False
    if need > cmax + 1e-9:
        T_old = b["target_secs_natural"]
        b["target_secs_natural"] = int(math.ceil(T_old * need / cmax))
        b["hp"] = nice(b["hp"] * b["target_secs_natural"] / T_old)
        need = need * T_old / b["target_secs_natural"]
        changed_T = True
    cap = max(b["hit_cap_design_min"], need)
    cap = min(cap, cmax)
    b["hit_cap"] = round(math.ceil(cap / CAP_STEP) * CAP_STEP, 3) if cap > b["hit_cap_design_min"] else b["hit_cap_design_min"]
    b["hit_cap"] = min(b["hit_cap"], round(math.floor(cmax / CAP_STEP) * CAP_STEP, 3)) if b["hit_cap"] > b["hit_cap_design_min"] else b["hit_cap"]
    b["anchor"]["floor_cap_plus10"] = round(cmax, 4)
    return changed_T


def calibrate(cfg):
    """앵커 레벨의 자연 장비 플레이어로 보스전 40회씩 → (0) 장갑 제약(자연 평타 ≤ 0.75×장갑, 풀 +10 ≥ 11초; 충돌 시 T 연장) (1) 공격력 배율 m 을 격자(0.5~3.0)+이분 탐색해 평균 사망이 목표
    (가운데 0.6 / 루프 0.5 / 1보스 0.35 / B13·B19 0.3~0.35)에 가장 가깝게(동률이면 큰 배율), (2) 체력(거울은 T)을 2회 반복 보정해 중간 전투 시간 = 목표 초, (3) 장갑 제약 재확인.
    사망은 '초당 회복 상한 vs 보스 DPS' 문턱 현상(지속 피해형 보스는 계단 함수)이라 곱셈 반복이 아니라 탐색이 필요하다."""
    GRID = [0.5, 0.65, 0.8, 1.0, 1.25, 1.6, 2.0, 2.5, 3.0]
    for rid, route in cfg["routes"].items():
        for si, stage in enumerate(route["stages"]):
            b = cfg["bosses"][stage["boss"]]
            owned = owned_for(rid, si)
            gear = S.aggregate(cfg, S.auto_equip(cfg, owned))
            curve = S.Curve(cfg["exp_curve"])
            exp_b = curve.E(b["anchor"]["player_lvl"])
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
            # 체력 1차 보정(공격 1.0 기준) + 장갑 제약
            T = b["target_secs_natural"]
            m0, d0 = _measure(cfg, b, gear, exp_b)
            if mirror:
                mirror["T"] = round(mirror["T"] * (T / m0) ** 0.8, 1)
            else:
                b["hp"] = nice(b["hp"] * (T / m0) ** 0.8)
                for _ in range(3):
                    if not enforce_cap_constraint(cfg, b, gear, exp_b):
                        break
                    T = b["target_secs_natural"]
                    m0, d0 = _measure(cfg, b, gear, exp_b)
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
            # 체력 2차 보정 (+ 장갑 제약 재확인)
            for it in range(2):
                m_, d_ = _measure(cfg, b, gear, exp_b)
                if mirror:
                    mirror["T"] = round(mirror["T"] * (T / m_) ** 0.8, 1)
                else:
                    b["hp"] = nice(b["hp"] * (T / m_) ** 0.8)
            if not mirror:
                if enforce_cap_constraint(cfg, b, gear, exp_b):
                    T = b["target_secs_natural"]
                    for it in range(2):
                        m_, d_ = _measure(cfg, b, gear, exp_b)
                        b["hp"] = nice(b["hp"] * (T / m_) ** 0.8)
            m_, d_ = _measure(cfg, b, gear, exp_b)
            b["anchor"]["calibrated_secs_median"] = round(m_, 1)
            b["anchor"]["calibrated_deaths_mean"] = round(d_, 2)
            b["anchor"]["death_target"] = tgt
            b["anchor"]["atk_calib_mult"] = round(best[0], 3)
            b["anchor"]["death_curve"] = [[m, round(d, 2)] for m, d in table]
            # 최소 타수: min_hits = 비치명 평타 기준 ceil(1/장갑), min_hits_floor = 치명 100%·관통 상한·대검 ×1.2·그로기 상한까지 전부 가정한 이론 하한 (K2-6)
            pierce_max = min(cfg["caps"]["pve"]["crit_pierce"], b["crit_pierce_cap"] or 9)
            stag_cap = b["gimmick"].get("stagger", {}).get("cap_mult", 1.0)
            cap_rel = 1 + max([e["v"] for it_ in cfg["items"].values() for e in it_["effects"] if e["k"] == "cap_rel_add"] + [0])
            b["min_hits"] = int(math.ceil(1 / b["hit_cap"]))
            b["min_hits_floor"] = int(math.ceil(1 / (b["hit_cap"] * pierce_max * cap_rel * stag_cap)))
            if not mirror:
                p_nat = virtual_player(cfg, gear, exp_b)
                b["anchor"]["natural_hit_pct_of_boss_hp"] = round(p_nat.atk() / b["hp"] * 100, 2)
                b["anchor"]["natural_crit_hit_pct_of_boss_hp"] = round(p_nat.atk() * p_nat.crit_mult() / b["hp"] * 100, 2)
                b["anchor"]["natural_hit_over_cap"] = round(p_nat.atk() / b["hp"] / b["hit_cap"], 2)
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
