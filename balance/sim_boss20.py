#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
레벨 폭발 모험단 — 20보스 최종 통합 설계 시뮬레이터 (표준 라이브러리만, boss20_config.json 만 읽음)

사용:
  python3 sim_boss20.py                                  # 전체 보고서 (설계서 §13 원문, 약 2~4분)
  python3 sim_boss20.py --report quick                   # 핵심 표만 (C·K-0·K·L 표는 판 수 절반)
  python3 sim_boss20.py --runs 300 --report all          # 최종 보고서(SIM_RESULT.txt)
  python3 sim_boss20.py --runs 300 --gear none           # 한 시나리오: 장비 0
  python3 sim_boss20.py --gear partial --build luck      # 가운데 길 10종 + 행운 빌드
  python3 sim_boss20.py --gear I01,I02,I03 --build hp --seed 7
  python3 sim_boss20.py --gear full --plus 10 --plan main
  python3 sim_boss20.py --gear partial --build hp --report quick   # 시나리오 + 핵심 표
옵션:
  --gear none|partial|full|<아이템 id 쉼표>   --build auto|str|luck|hp|ls
  --plus N (전 장비 강화)   --plan main|left|right|full (루프 포함 여부)   --auto (자동 모험 모드)
  --start village|plaza5|plaza10 (워프 제단)   --fever on|off   --seed S   --config 경로

모델: 이벤트 구동 1:N 전투(한 전투 1~3마리, 보스는 소환수 포함). 플레이어 자동 타격 1.0초 ÷ 공속(버튼은 쿨다운 공유,
리듬 탭 성공률 manual_combo_p 로 콤보 → 피버). 흡혈은 '초당 회복 상한 × 공격 간격'으로 스윙당 묶어 초당 회복 vs 초당 피격 모델.
보스: 체력바(페이즈)·전환 무적·타격 상한(장갑)·치명 관통·그로기/보호막/소환/분노/브레스/가시/재생/타이머/광란/보스 흡혈/저주/거울.
사망: 그 자리 부활·체력 가득·무적, 적 체력 유지(v6), 에너지 누진(3,4,5,6). 레벨업 시 최대 체력 증가분 회복(현행 규칙).
"""
import json, math, random, statistics as st, sys, os, argparse, time

HERE = os.path.dirname(os.path.abspath(__file__))
CFG_PATH = os.path.join(HERE, "boss20_config.json")
INF = float("inf")


def load_config(path=CFG_PATH):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ----------------------------------------------------------------------------
# 경험치 곡선 (닫힌 형식)
# ----------------------------------------------------------------------------
class Curve:
    """need(L) = n0 (1+L/K)^a ; E(L) = n0 K/(1+a) ((1+L/K)^(1+a) − (1+1/K)^(1+a)) ; L(E) = K((E/A + c1)^(1/(1+a)) − 1)"""

    def __init__(self, c):
        self.n0, self.K, self.a = c["n0"], c["K"], c["a"]
        self.A = self.n0 * self.K / (1 + self.a)
        self.c1 = (1 + 1 / self.K) ** (1 + self.a)

    def need(self, L):
        return self.n0 * (1 + L / self.K) ** self.a

    def E(self, L):
        return self.A * ((1 + L / self.K) ** (1 + self.a) - self.c1)

    def L(self, E):
        return self.K * ((E / self.A + self.c1) ** (1 / (1 + self.a)) - 1)


# ----------------------------------------------------------------------------
# 장비 합산
# ----------------------------------------------------------------------------
DEFAULT_GEAR = dict(
    atk_mult=1.0, S=0.0, ls=0.0, range_add=0.0, exp_mult=1.0, boss_exp_mult=1.0,
    crit_dmg=0.0, crit_p_add=0.0, dmg_reduce=0.0, hp_mult=1.0, energy_start=0,
    energy_boss=0, cap_add=0.0, nth_crit=0, first_hits_fast=0, first_hits_mult=1.0,
    multi_atk_bonus=0.0, revive_invuln_add=0.0, first_death_cost=None, luk_mult=1.0,
    zone_exp_bonus=0.0, var_lo=0.9, var_hi=1.1, move_bonus=0.0, ls_crit_mult=1.0,
    reflect=0.0, splash=0.0, heal_cap_s_add=0.0, crit_pierce_add=0.0, cap_rel_add=0.0, items=[],
)
MULT_KEYS = {"atk_mult_bonus": "atk_mult", "exp_mult_bonus": "exp_mult",
             "boss_exp_mult_bonus": "boss_exp_mult", "hp_mult_bonus": "hp_mult",
             "luk_mult_bonus": "luk_mult"}
ADD_KEYS = {"S", "ls", "range_add", "crit_dmg", "crit_p_add", "energy_start", "energy_boss",
            "cap_add", "cap_rel_add", "multi_atk_bonus", "revive_invuln_add", "zone_exp_bonus", "move_bonus",
            "reflect", "splash", "heal_cap_s_add", "crit_pierce_add"}


def jackpot_draw(n, p, rnd):
    """'행운!' 당첨 수 ~ Binomial(n, p). 서버 구현과 동일: n<50 은 직접 주사위, 그 이상은 정규 근사 n·p + √(n·p·(1−p))·Z 1회
    (K3: 레벨마다 주사위는 B20 한 번에 112억 회라 불가). rnd 가 None 이면 기대값(보정·PvP 용 결정론)."""
    if n <= 0 or p <= 0:
        return 0.0
    if rnd is None:
        return n * p
    if n < 50:
        return float(sum(1 for _ in range(n) if rnd.random() < p))
    mu = n * p
    sd = math.sqrt(n * p * (1 - p))
    return float(min(n, max(0, round(mu + sd * rnd.gauss(0.0, 1.0)))))


def caps_of(cfg, pvp=False):
    return cfg["caps"]["pvp" if pvp else "pve"]


def aggregate(cfg, item_ids, plus=None, pvp=False):
    """장착 아이템(+강화) → 합산 장비 효과. 강화는 up:true 값에 upgrade_mult^plus. PvP 는 pvp_disabled 키 무시 + caps.pvp."""
    g = dict(DEFAULT_GEAR)
    g["items"] = list(item_ids)
    up = cfg["stones"]["upgrade_mult_per_plus"]
    caps = caps_of(cfg, pvp)
    for iid in item_ids:
        it = cfg["items"][iid]
        p = (plus or {}).get(iid, 0)
        disabled = set(it.get("pvp_disabled", [])) if pvp else set()
        for e in it["effects"]:
            k = e["k"]
            if k in disabled:
                continue
            v = e["v"] * (up ** p if e.get("up") else 1.0)
            if k in MULT_KEYS:
                g[MULT_KEYS[k]] *= (1 + v)
            elif k == "dmg_reduce":
                g["dmg_reduce"] = 1 - (1 - g["dmg_reduce"]) * (1 - v)
            elif k in ADD_KEYS:
                g[k] += v
            elif k == "nth_crit":
                g["nth_crit"] = int(v)
            elif k == "first_hits_fast":
                g["first_hits_fast"] = int(v)
            elif k == "first_hits_mult":
                g["first_hits_mult"] = v
            elif k == "first_death_cost":
                g["first_death_cost"] = int(v)
            elif k == "var":
                g["var_lo"], g["var_hi"] = e["lo"], e["hi"]
            elif k == "ls_crit_mult":
                g["ls_crit_mult"] = v
            else:
                raise ValueError("unknown effect " + k)
    # 합산 상한 (caps.pve / caps.pvp)
    g["atk_mult"] = min(g["atk_mult"], caps["atk_mult"])
    g["hp_mult"] = min(g["hp_mult"], caps["hp_mult"])
    g["exp_mult"] = min(g["exp_mult"], caps["exp_mult"])
    g["boss_exp_mult"] = min(g["boss_exp_mult"], caps["boss_exp_mult"])
    g["dmg_reduce"] = min(g["dmg_reduce"], caps["dmg_reduce"])
    g["reflect"] = min(g["reflect"], caps["reflect"])
    g["splash"] = min(g["splash"], caps["splash"])
    rc = cfg["formulas"]["range"]
    g["range_add"] = min(g["range_add"], (caps["range_targets"] - 1) * rc["per_target"])
    return g


def auto_equip(cfg, owned):
    """보유 아이템 중 칸별로 rank 가 높은 것을 자동 장착 (반지 2칸)."""
    by_slot = {}
    for iid in owned:
        it = cfg["items"][iid]
        by_slot.setdefault(it["slot"], []).append(iid)
    out = []
    for slot, n in cfg["slots"].items():
        c = sorted(by_slot.get(slot, []), key=lambda i: -cfg["items"][i]["rank"])
        out += c[:n]
    return out


# ----------------------------------------------------------------------------
# 플레이어
# ----------------------------------------------------------------------------
class Player:
    def __init__(self, cfg, gear, ratio=None, manual=True, pvp=False, no_jackpot=False, rng=None):
        self.cfg = cfg
        self.g = gear
        self.pvp = pvp
        self.no_jackpot = no_jackpot
        self.rng = rng   # 행운! 당첨 주사위(이항 근사). None = 기대값
        self.caps = caps_of(cfg, pvp)
        self.curve = Curve(cfg["exp_curve"])
        self.st = cfg["stats"]
        self.F = cfg["formulas"]
        self.ratio = ratio or {k: self.st[k]["auto_ratio"] for k in ("hp", "atk", "luk", "ls")}
        self.lvl = 1
        self.exp = 0.0
        self.pts = {"hp": 0.0, "atk": 0.0, "luk": 0.0, "ls": 0.0}
        self.manual = manual
        self.jackpots = 0.0
        self.hp = self.maxhp()

    # --- 기본 능력치 (장비 없는 값: 거울 기사·PvP 설명용) ---
    def maxhp_base(self):
        return self.st["hp"]["base"] + self.st["hp"]["per_pt"] * self.pts["hp"]

    def atk_base(self):
        return self.st["atk"]["base"] + self.st["atk"]["per_pt"] * self.pts["atk"]

    def luk_base(self):
        return self.st["luk"]["base"] + self.st["luk"]["per_pt"] * self.pts["luk"]

    def maxhp(self):
        return self.maxhp_base() * self.g["hp_mult"]

    def atk(self):
        return self.atk_base() * self.g["atk_mult"]

    def luk(self):
        return self.luk_base() * self.g["luk_mult"]

    def crit_p_of(self, L):
        f = self.F["crit"]
        return min(self.caps["crit_p"], f["base"] + f["span"] * L / (L + f["lvl_coef"] * self.lvl + f["c"]) + self.g["crit_p_add"])

    def crit_p(self):
        return self.crit_p_of(self.luk())

    def crit_mult(self):
        f = self.F["crit"]
        return min(self.caps["crit_mult"], f["mult_base"] + self.g["crit_dmg"])

    def ls(self):
        f = self.F["lifesteal"]
        P = self.pts["ls"] * self.st["ls"]["per_pt"]
        raw = f["max_from_pts"] * P / (P + f["lvl_coef"] * self.lvl + f["c"]) + self.g["ls"]
        return min(self.caps["lifesteal"], raw)

    def heal_cap_per_s(self, ls_eff):
        """초당 회복 상한(최대 체력 비율) = min(상한, max(기본 + 장비, 계수 × 흡혈률)). 흡혈에 투자하면 상한도 오른다."""
        f = self.F["lifesteal"]
        return min(self.caps["heal_per_s_max"], max(f["heal_per_s_cap_base"] + self.g["heal_cap_s_add"], f["heal_per_s_ls_coef"] * ls_eff))

    def aspd(self):
        f = self.F["aspd"]
        S = self.g["S"]
        m = 1 + S / (1 + S / f["half"]) if S >= 0 else 1 + S
        return min(self.caps["aspd_mult"], max(0.5, m))

    def interval(self):
        return self.cfg["combat"]["attack_interval"] / self.aspd()

    def targets(self, alive):
        rc = self.F["range"]
        R = min(rc["cap"], rc["base"] + self.g["range_add"])
        return max(1, min(alive, self.caps["range_targets"], 1 + int((R - rc["base"]) // rc["per_target"])))

    def luck_jackpot_p(self):
        f = self.F["luck_bonus"]
        L = self.luk()
        return min(f["p_cap"], f["p_coef"] * L / (L + f["lvl_coef"] * self.lvl + f["c"]))

    def gain_exp(self, e):
        """경험치 → 레벨(닫힌 식, floor(L(E)+1e-9) — 부동소수 왕복 −1 방지, 단조 보호) → 포인트(레벨당 3, 당첨 수 ~ Binomial(n,p) 1회 추첨으로
        그 레벨들의 포인트 2배) → 자동 분배 → 최대체력 증가분 회복. 저장 원본은 누적 경험치 E(double), 레벨은 캐시."""
        self.exp += e
        newL = max(self.lvl, int(math.floor(self.curve.L(self.exp) + 1e-9)))
        n = newL - self.lvl
        if n <= 0:
            return 0
        f = self.F["luck_bonus"]
        p = 0.0 if self.no_jackpot else self.luck_jackpot_p()
        ppl = self.st["pts_per_level"]
        hits = jackpot_draw(n, p, self.rng)
        pts = n * ppl + hits * ppl * (f["double_mult"] - 1)
        self.jackpots += hits
        old = self.maxhp()
        tot = sum(self.ratio.values())
        for key in self.pts:
            self.pts[key] += pts * self.ratio[key] / tot
        self.lvl = newL
        self.hp = min(self.maxhp(), self.hp + (self.maxhp() - old))
        return n


def feed_exp(pl, exp_total, steps=80):
    """경험치를 기하급수 조각으로 나눠 넣어 행운 당첨 포인트가 실제 판처럼 누적되게 한다 (gen·PvP·러시 공용)."""
    if exp_total <= 0:
        return
    got = 0.0
    for i in range(1, steps + 1):
        target = exp_total * (1.12 ** i - 1) / (1.12 ** steps - 1)
        pl.gain_exp(target - got)
        got = target


# ----------------------------------------------------------------------------
# 전투 단위
# ----------------------------------------------------------------------------
class Unit:
    __slots__ = ("id", "name", "hp", "maxhp", "atk", "interval", "next", "alive", "exp", "is_boss")

    def __init__(self, m, first_hit, is_boss=False):
        self.id, self.name = m["id"], m.get("name_ko", m.get("name", m["id"]))
        self.hp = self.maxhp = float(m["hp"])
        self.atk = float(m["atk"])
        self.interval = float(m["interval"])
        self.next = first_hit
        self.alive = True
        self.exp = float(m["exp"])
        self.is_boss = is_boss


class BossState:
    def __init__(self, b, unit, player, C):
        self.unit = unit
        gm = b.get("gimmick", {})
        self.phases = b.get("phases", 1)
        self.transition = b.get("transition_s", 1.0)
        self.cap = b.get("hit_cap", 1.0)
        self.pierce_cap = b.get("crit_pierce_cap", None)
        self.phase = 1
        self.in_trans = False
        self.trans_until = -1.0
        s = gm.get("stagger")
        self.stagger_every = s["every_s"] if s else None
        self.stagger_dur = s["dur_s"] if s else 0
        self.stagger_dmg = s["dmg_mult"] if s else 1
        self.stagger_cap = s["cap_mult"] if s else 1
        self.next_stagger = s["every_s"] if s else None
        self.stagger_until = -1.0
        self.stagger_on_phase = gm.get("stagger_on_phase_s", 0.0)
        self.shield_hits = gm.get("shield_hits", 0)
        self.shield = self.shield_hits
        self.adds = gm.get("adds")
        self.enrage = gm.get("enrage")
        self.enraged = False
        self.regen = gm.get("regen_per_s", 0.0)
        self.thorns = gm.get("thorns_frac", 0.0)
        tm = gm.get("timer")
        self.timer_at = tm["at_s"] if tm else None
        self.timer_mult = tm["atk_mult"] if tm else 1
        self.timer_on = False
        self.frenzy = gm.get("frenzy")
        self.base_interval = unit.interval
        self.boss_ls = gm.get("boss_lifesteal", 0.0)
        self.curse_noncrit = gm.get("curse_noncrit_mult", None)
        self.breath = gm.get("breath")
        self.next_breath = self.breath["every_s"] if self.breath else None
        self.crit_immune = gm.get("crit_immune", False)
        self.ls_mult = gm.get("player_ls_mult", 1.0)
        self.dodge_p = 0.0
        mi = gm.get("mirror")
        self.mirror = mi
        if mi:
            # 거울 기사: 플레이어의 '장비 없는' 능력치를 복사. 장비·강화만이 차이 = PvP 예습.
            c = player.crit_p_of(player.luk_base())
            cm = player.F["crit"]["mult_base"]
            base_dps = player.atk_base() * (1 + c * (cm - 1)) / C["attack_interval"]
            unit.hp = unit.maxhp = base_dps * mi["T"]
            unit.atk = mi["dps_k"] * unit.interval * player.maxhp_base()
            self.dodge_p = min(mi["dodge_cap"], c * mi["dodge_from_crit"])

    def interval_at(self, t):
        iv = self.unit.interval
        if self.frenzy:
            f = self.frenzy
            frac = min(1.0, t / f["over_s"])
            iv = (self.base_interval + (f["int_min"] - self.base_interval) * frac)
            if self.enraged:
                iv *= self.enrage.get("int_mult", 1.0)
        return iv


class RunOver(Exception):
    pass


class RunState:
    def __init__(self, cfg, rnd, energy, unlimited=False):
        self.cfg = cfg
        self.rnd = rnd
        self.energy_max = 10 ** 9 if unlimited else cfg["run"].get("energy_max", 10 ** 9)   # 보유 상한 (K2: 잔여 에너지 농사·죽음 러시 봉인); unlimited = 보정·러시용 결투
        self.energy = min(energy, self.energy_max)
        self.time = 0.0
        self.deaths = 0
        self.chapter_deaths = 0   # 문(보스 처치)·루프 입장에서 0 으로 초기화되는 누진 사망 카운터 (K1·K2: 광장 왕복으로는 초기화 안 됨)
        self.first_death_used = False   # 수호 부적 '판마다 첫 사망' 판당 1회 플래그 (K2-7)
        self.fever_count = 0
        self.near_miss = 0
        self.capped_hits = 0
        self.boss_hits = 0
        self.max_hit_taken = 0.0     # 최대 체력 대비 한 타 최대
        self.heal_total = 0.0
        self.dmg_taken_total = 0.0
        self.boss_secs_total = 0.0
        self.cur_boss_unit = None    # 진행 중인 보스전의 보스 유닛 (게임오버 순간 잔여 체력 기록용, K1-F1)
        self.last_stand = False      # 에너지 0 '마지막 도전' 중 (K1-F5)
        self.end_where = None        # 판이 끝난 지점: complete / boss_gameover:Bxx / fight_death / no_boss_energy0

    def add_energy(self, v):
        self.energy = min(self.energy_max, self.energy + v)

    def death_cost(self, g):
        R = self.cfg["run"]
        mode = R.get("death_counter_reset", "door")
        n = self.chapter_deaths if mode in ("door", "plaza") else self.deaths  # 이번이 n+1 번째 사망
        cost = min(R["energy_death_max"], R["energy_death_base"] + n * R["energy_death_step"])
        if g["first_death_cost"] is not None and not self.first_death_used:
            cost = g["first_death_cost"]
        return cost


# ----------------------------------------------------------------------------
# 전투
# ----------------------------------------------------------------------------
def combat(rs, p, mons, boss_def=None, zone=False, fever_on=True, pvp_like=False, zone_dmg=None):
    """mons: 몬스터 dict 리스트(보스전이면 None + boss_def). zone_dmg: 구간별 도박 구역 피해 배율(None 이면 기본값).
    반환 dict(won, secs, deaths, lv_gain, hits, heal_ps, dmg_ps).
    거리 모델 없음 = 규칙: 보스전은 좁은 원형 제단(반지름 ≤ 보스 반지름 + combat.boss_arena_radius_add) 안에서 치르고 플레이어는 보스 사거리 밖으로
    나갈 수 없다(브레스만 바깥 고리로 회피). 일반 몬스터 rise 종 이속 22 ≥ 플레이어 20 이라 뒤로 걷기 카이팅 불가 (K3-3)."""
    cfg = rs.cfg
    C = cfg["combat"]
    F = cfg["formulas"]
    g = p.g
    rnd = rs.rnd
    t = 0.0
    TM = C["timing"]
    DV = (F["damage_taken"]["var_lo"], F["damage_taken"]["var_hi"])
    dmg_in = (zone_dmg if zone_dmg is not None else F["damage_taken"]["zone_dmg_mult"]) if zone else 1.0
    exp_m = (F["exp_gain"]["zone_exp_mult"] + g["zone_exp_bonus"]) if zone else 1.0
    enemies = []
    B = None
    if boss_def is not None:
        bu = Unit(boss_def, C["first_hit"], is_boss=True)
        enemies.append(bu)
        B = BossState(boss_def, bu, p, C)
        rs.cur_boss_unit = bu
    else:
        for i, m in enumerate(mons):
            enemies.append(Unit(m, C["first_hit"] + TM["add_spawn_stagger_s"] * i))

    state = dict(deaths=0, invuln=-1.0, fever=-1.0, combo=0, hits=0, lvl0=p.lvl, lowest=1.0,
                 heal=0.0, taken=0.0, idle_since=0.0)
    p_next = C["approach_s"]

    def spawn_adds(when):
        a = B.adds
        alive_adds = sum(1 for e in enemies if e.alive and not e.is_boss)
        room = max(0, TM.get("max_adds_alive", 3) - alive_adds)   # 동시 수하 상한 (K3-12: 모바일 성능), 초과분은 소환되지 않음
        for i in range(min(a["count"], room)):
            enemies.append(Unit(a["unit"], when + C["first_hit"] + TM["add_spawn_stagger_s"] * i))

    def die():
        state["deaths"] += 1
        cost = rs.death_cost(g)
        rs.deaths += 1
        rs.chapter_deaths += 1
        rs.first_death_used = True
        rs.energy -= cost
        rs.time += C["death_anim_s"]
        if rs.energy <= 0:
            raise RunOver()
        p.hp = p.maxhp()
        state["invuln"] = t + C["revive_invuln"] + g["revive_invuln_add"]

    def take(dmg, e=None):
        """플레이어 피격 (상한·반격·사망 처리)."""
        dmg = min(dmg, p.maxhp() * F["damage_taken"]["player_hit_cap"])
        p.hp -= dmg
        state["taken"] += dmg
        rs.dmg_taken_total += dmg
        rs.max_hit_taken = max(rs.max_hit_taken, dmg / p.maxhp())
        if e is not None and g["reflect"] > 0 and e.alive:
            r = dmg * g["reflect"]
            if B is not None and e is B.unit:
                if not B.in_trans:
                    r = min(r, B.cap * e.maxhp)
                    e.hp -= r
                    check_phase(e)
            else:
                e.hp -= r
                if e.hp <= 0:
                    kill(e)
        if p.hp <= 0:
            die()
        else:
            state["lowest"] = min(state["lowest"], p.hp / p.maxhp())

    def kill(e):
        e.alive = False
        mult = g["exp_mult"] * (g["boss_exp_mult"] if e.is_boss else exp_m)
        p.gain_exp(e.exp * mult)

    def check_phase(e):
        thr = e.maxhp * (1 - B.phase / B.phases)
        if B.phase < B.phases and e.hp <= thr + 1e-9:
            e.hp = thr
            B.in_trans = True
            B.trans_until = t + B.transition
        elif e.hp <= 0:
            kill(e)

    def deal(e, dmg, crit):
        """피해 적용. 반환 실제 피해(흡혈 계산용)."""
        if B is not None and e is B.unit:
            if B.in_trans:
                return 0.0
            if B.dodge_p > 0 and rnd.random() < B.dodge_p:
                return 0.0
            if B.shield > 0:
                B.shield -= 1
                return 0.0
            if B.curse_noncrit is not None and not crit:
                dmg *= B.curse_noncrit
            stag = t < B.stagger_until
            if stag:
                dmg *= B.stagger_dmg
            pierce = 1.0
            if crit:
                pierce = min(C["crit_cap_mult"] + g["crit_pierce_add"], p.caps["crit_pierce"])
                if B.pierce_cap is not None:
                    pierce = min(pierce, B.pierce_cap)
            if t < state["invuln"]:
                dmg *= C.get("revive_invuln_boss_dmg_mult", 1.0)   # 부활 무적 중 보스에게 주는 피해 감쇠 (K2-5: 죽음 러시 봉인, 일반 몬스터는 그대로)
            cap = (B.cap * (1 + g["cap_rel_add"]) + g["cap_add"]) * e.maxhp * pierce * (B.stagger_cap if stag else 1.0)
            rs.boss_hits += 1
            if dmg > cap:
                dmg = cap
                rs.capped_hits += 1
            if B.thorns > 0 and t >= state["invuln"]:
                take(B.thorns * p.maxhp() * (1 - g["dmg_reduce"]))
            e.hp -= dmg
            if B.boss_ls > 0:
                e.hp = min(e.maxhp, e.hp + dmg * B.boss_ls)
            check_phase(e)
            return dmg
        e.hp -= dmg
        if e.hp <= 0:
            kill(e)
        return dmg

    def end_transition():
        B.in_trans = False
        B.phase += 1
        if B.enrage and B.phase >= B.enrage["from_phase"] and not B.enraged:
            B.unit.atk *= B.enrage.get("atk_mult", 1.0)
            B.unit.interval *= B.enrage.get("int_mult", 1.0)
            B.enraged = True
        B.shield = B.shield_hits
        if B.adds and B.phase in B.adds["phases"]:
            spawn_adds(t)
        if B.stagger_on_phase > 0:
            B.stagger_until = t + B.stagger_on_phase
        B.unit.next = t + TM["boss_attack_after_transition_s"]

    if B is not None and B.adds and 1 in B.adds["phases"]:
        spawn_adds(0.0)

    while t < C["max_fight_s"]:
        al = [e for e in enemies if e.alive]
        if not al:
            break
        cand = [p_next] + [e.next for e in al]
        if B is not None and B.unit.alive:
            if B.in_trans:
                cand.append(B.trans_until)
            if B.stagger_until > t:
                cand.append(B.stagger_until)
            if B.next_stagger is not None:
                cand.append(B.next_stagger)
            if B.next_breath is not None:
                cand.append(B.next_breath)
            if B.timer_at is not None and not B.timer_on:
                cand.append(B.timer_at)
        tn = min(cand)
        dt = tn - t
        if B is not None and B.regen > 0 and B.unit.alive and dt > 0 and not B.in_trans:
            B.unit.hp = min(B.unit.maxhp, B.unit.hp + B.unit.maxhp * B.regen * dt)
        t = tn
        if state["fever"] > 0 and t > state["fever"]:
            state["fever"] = -1.0

        # ---- 보스 타이머류 ----
        if B is not None and B.unit.alive:
            if B.in_trans and t >= B.trans_until:
                end_transition()
            if B.timer_at is not None and not B.timer_on and t >= B.timer_at:
                B.unit.atk *= B.timer_mult
                B.timer_on = True
            if B.next_stagger is not None and t >= B.next_stagger:
                if not B.in_trans:
                    B.stagger_until = t + B.stagger_dur
                B.next_stagger = t + B.stagger_dur + B.stagger_every
            if B.next_breath is not None and t >= B.next_breath:
                B.next_breath += B.breath["every_s"]
                if not B.in_trans and t >= B.stagger_until:
                    dodge = B.breath["dodge_p_manual"] if p.manual else B.breath["dodge_p_auto"]
                    if rnd.random() >= dodge and t >= state["invuln"]:
                        take(B.unit.atk * B.breath["atk_mult"] * rnd.uniform(*DV) * dmg_in * (1 - g["dmg_reduce"]), B.unit)

        # ---- 플레이어 공격 ----
        if t >= p_next - 1e-9:
            al = [e for e in enemies if e.alive]
            if al:
                # 이번 스윙의 간격 (피버·선제 러시 반영) → 흡혈 상한도 이 간격에 비례
                iv = p.interval()
                if state["hits"] < g["first_hits_fast"]:
                    iv /= g["first_hits_mult"]
                if state["fever"] > t:
                    iv /= C["fever_aspd"]
                iv = max(C["attack_interval"] / F["aspd"]["fever_abs_cap"], iv)   # 실효 공속 절대 상한 — 피버·선제 러시를 전부 적용한 뒤 자른다 (K2-8)
                k = p.targets(len(al))
                state["hits"] += 1
                forced = g["nth_crit"] > 0 and state["hits"] % g["nth_crit"] == 0
                cp, cm = p.crit_p(), p.crit_mult()
                base_atk = p.atk()
                if g["multi_atk_bonus"] > 0 and len(al) >= 2:
                    base_atk *= (1 + g["multi_atk_bonus"])
                ls_eff = p.ls() * (B.ls_mult if B is not None else 1.0)
                hc_s = p.heal_cap_per_s(ls_eff)
                if B is not None and B.mirror:
                    hc_s = min(hc_s, caps_of(cfg, True)["heal_per_s_max"])   # 거울 기사 = PvP 예습: 결투장 초당 회복 상한 적용 (K2-9)
                heal_cap = hc_s * p.maxhp() * iv
                swing_heal = 0.0
                for e in al[:k]:
                    if not e.alive:
                        continue
                    crit = forced or rnd.random() < cp
                    if B is not None and e is B.unit and B.crit_immune:
                        crit = False
                    dmg = base_atk * rnd.uniform(g["var_lo"], g["var_hi"])
                    if crit:
                        dmg *= cm
                    done = deal(e, dmg, crit)
                    if done > 0:
                        swing_heal += done * ls_eff * (g["ls_crit_mult"] if crit else 1.0)
                if g["splash"] > 0:
                    for e in al[k:]:
                        if e.alive:
                            done = deal(e, base_atk * g["splash"], False)
                            swing_heal += done * ls_eff
                heal = min(swing_heal, heal_cap)
                heal = min(heal, p.maxhp() - p.hp)
                p.hp += heal
                state["heal"] += heal
                rs.heal_total += heal
                # 콤보/피버 (수동 조작 + 피버 ON)
                if p.manual and fever_on and state["fever"] <= t:
                    if rnd.random() < C["manual_combo_p"]:
                        state["combo"] += 1
                    # 실패 = 콤보 유지(진행 없음). 1.5초 이상 탭이 없으면 0 (자동 모험은 탭 없음 → 피버 없음)
                    if state["combo"] >= C["fever_hits"]:
                        state["fever"] = t + C["fever_dur_s"]
                        state["combo"] = 0
                        rs.fever_count += 1
                p_next = t + iv

        # ---- 적 공격 ----
        for e in enemies:
            if not e.alive or t < e.next - 1e-9:
                continue
            if B is not None and e is B.unit:
                if B.in_trans:
                    e.next = B.trans_until + TM["boss_attack_delay_after_transition_hit_s"]
                    continue
                if t < B.stagger_until:
                    e.next = B.stagger_until + TM["boss_attack_delay_after_stagger_s"]
                    continue
            if t >= state["invuln"]:
                take(e.atk * rnd.uniform(*DV) * dmg_in * (1 - g["dmg_reduce"]), e)
            iv_e = B.interval_at(t) if (B is not None and e is B.unit) else e.interval
            e.next = t + iv_e

    won = all(not e.alive for e in enemies)
    if won and state["lowest"] <= TM["near_miss_hp_frac"] and state["deaths"] == 0:
        rs.near_miss += 1
    secs = max(t, 1e-6)
    return dict(won=won, secs=t, deaths=state["deaths"], lv_gain=p.lvl - state["lvl0"], hits=state["hits"],
                heal_ps=state["heal"] / secs, dmg_ps=state["taken"] / secs)


# ----------------------------------------------------------------------------
# 한 판 (가운데 길 10단계 + 광장에서 들어가는 질풍/군단 루프)
# ----------------------------------------------------------------------------
BUILD_ALIAS = {"auto": "균형(기본)", "str": "속공(위험)", "luck": "행운 도박", "hp": "탱커", "ls": "흡혈 균형"}


def plan_of(name):
    return {"main": dict(left=False, right=False), "left": dict(left=True, right=False),
            "right": dict(left=False, right=True), "full": dict(left=True, right=True)}[name]


def boss_order(cfg, plan, start="village"):
    """plan 에 따른 보스 등장 순서(id 리스트). start=plazaN 이면 N단계 뒤부터."""
    R = cfg["routes"]
    out = []
    start_stage = 1 if start == "village" else int(start.replace("plaza", "")) + 1
    for st_ in R["main"]["stages"]:
        if st_["stage"] < start_stage:
            if st_["stage"] == start_stage - 1:
                for rid in ("left", "right"):
                    if plan.get(rid) and R[rid]["entry_after_main_stage"] == st_["stage"]:
                        out += [s["boss"] for s in R[rid]["stages"]]
            continue
        out.append(st_["boss"])
        for rid in ("left", "right"):
            if plan.get(rid) and R[rid]["entry_after_main_stage"] == st_["stage"]:
                out += [s["boss"] for s in R[rid]["stages"]]
    return out


def condition_met(cond, ctx):
    """숨은 보스 등장 조건 (전부 JSON). ctx: 이 루프의 진행 기록."""
    if not cond:
        return True
    typ = cond["type"]
    if typ == "prev_boss_secs_max":
        pb = ctx["prev_boss"]
        return bool(pb and pb["spawned"] and pb["won"] and pb["secs"] <= cond["value"])
    if typ == "zone_fight_this_stage":
        return ctx["zone_win_this_stage"]
    if typ == "no_death_prev_boss":
        pb = ctx["prev_boss"]
        return bool(pb and pb["spawned"] and pb["won"] and pb["deaths"] == 0)
    if typ == "all_prev_loop_bosses":
        return all(b["spawned"] and b["won"] for b in ctx["loop_bosses"])
    if typ == "no_death_since_loop_entry":
        return ctx["loop_deaths"] == 0
    raise ValueError("unknown condition " + typ)


def run(cfg, plan="main", owned=(), plus=None, manual=True, ratio=None, vip=False, seed=None, equip=None,
        start="village", fever=True, killed_before=None):
    """한 판. plan: 'main'|'left'|'right'|'full' 또는 dict. 반환: 판 결과 dict."""
    if isinstance(plan, str):
        plan = plan_of(plan)
    rnd = random.Random(seed)
    R, C, F = cfg["run"], cfg["combat"], cfg["formulas"]
    routes = cfg["routes"]
    eq = equip if equip is not None else auto_equip(cfg, owned)
    gear = aggregate(cfg, eq, plus)
    p = Player(cfg, gear, ratio, manual, rng=rnd)
    rs = RunState(cfg, rnd, R["energy_start"] + gear["energy_start"] + (cfg["monetization"]["pass_energy_bonus"] if vip else 0))
    rs.time = R["village_to_gate_s"]
    killed_before = set(killed_before) if killed_before is not None else {cfg["items"][i]["boss"] for i in owned}
    curve = p.curve
    boss_log, stage_log = [], []
    stones = {str(k): 0 for k in cfg["stones"]["tiers"]}
    essence = {}
    conds = {}
    start_stage = 1
    if start != "village":
        W = R["warp"]
        plaza = int(start.replace("plaza", ""))
        start_stage = plaza + 1
        lvl = routes["main"]["stages"][plaza]["anchor_levels"]["enter"] * W["level_factor"] if plaza < len(routes["main"]["stages"]) \
            else routes["right"]["stages"][0]["anchor_levels"]["enter"] * W["level_factor"]
        feed_exp(p, curve.E(lvl))
        rs.energy = W["start_energy"] + gear["energy_start"]
        rs.time = W["warp_s"]

    def do_stage(rid, stage, loop_ctx):
        """일반 전투(고정 트리거 fights 회) + 보스. 반환 boss 로그 항목.
        규칙(run.text_ko 와 1:1): ① 조우는 구간 길이/fights 지점마다 1회 강제(확률 게이지 아님, K3-1) ② 도박 구역은 트리거 지점 위 luck_zones 곳(인트로 제외)
        ③ 에너지 0 이면 남은 조우는 생기지 않고 제단 보스전만 치른다('마지막 도전', K1-F5) ④ 보스 제단은 판당 1회, 처치한 구간은 조우 없음, 루프 재입장 불가
        ⑤ 마지막 열린 보스를 잡으면 자동 결산(end_after_last_boss) — 잔여 에너지 농사 없음 (K2-1·K3-5)."""
        route = routes[rid]
        mons = [cfg["monsters"][m] for m in stage["monsters"]]
        weights = stage["monster_weights"]
        gprobs = stage.get("group_probs", route["group_probs"])
        nf = stage["fights"]
        seg = stage["length"] / nf
        fight_deaths, fight_secs, lvl_in = 0, 0.0, p.lvl
        b = cfg["bosses"][stage["boss"]]
        cond = b.get("spawn_condition")
        zone_win = False
        intro = route.get("intro_fights", 0) if (rid == "main" and stage["stage"] == 1) else 0
        intro_seq = route.get("intro_sequence") or [stage["monsters"][0]] * intro
        cand_idx = list(range(intro, nf))
        zone_idx = set(rnd.sample(cand_idx, min(stage.get("luck_zones", 1), len(cand_idx)))) if cand_idx else set()
        use_p = C["zone_use_p_manual"] if manual else C["zone_use_p_auto"]
        if cond and cond["type"] == "zone_fight_this_stage" and manual:
            use_p = 1.0   # 조건을 아는 수동 플레이어는 일부러 구역에서 싸운다
        zdm = F["damage_taken"].get("zone_dmg_mult_by_stage", {}).get(rid, {}).get(str(stage["stage"]), F["damage_taken"]["zone_dmg_mult"])
        speed = R["move_speed"] * (1 + gear["move_bonus"])
        for fi in range(nf):
            if rs.energy <= 0:
                # 마지막 도전: 에너지 0 → 남은 트리거는 비활성(안전 통로), 제단으로 직행
                rs.last_stand = True
                rs.time += (nf - fi) * seg / speed
                break
            walk = seg / speed
            rs.time += walk
            p.hp = min(p.maxhp(), p.hp + p.maxhp() * (C["after_fight_heal"] + C["regen_per_s"] * walk))
            if fi < intro:
                group = [cfg["monsters"][intro_seq[fi]]]
            else:
                n = rnd.choices([1, 2, 3], gprobs)[0]
                group = [rnd.choices(mons, weights)[0] for _ in range(n)]
            zone = (fi in zone_idx) and rnd.random() < use_p
            rs.time += C["spawn_s"]
            try:
                res = combat(rs, p, group, None, zone, fever, zone_dmg=zdm)
            except RunOver:
                rs.end_where = "fight_death"   # 일반 전투 사망으로 에너지 0
                raise
            rs.time += res["secs"]
            fight_deaths += res["deaths"]
            fight_secs += res["secs"]
            if not res["won"]:
                rs.end_where = "fight_death"
                raise RunOver()
            if zone:
                zone_win = True
            rs.energy -= R["energy_fight"]
            rs.time += C["loot_s"]
            if rs.energy <= 0 and not R.get("last_stand", True):
                rs.end_where = "after_fight_win"
                raise RunOver()
        # 보스 (조건부 등장)
        ctx = dict(prev_boss=(loop_ctx["bosses"][-1] if loop_ctx and loop_ctx["bosses"] else None),
                   zone_win_this_stage=zone_win, loop_bosses=(loop_ctx["bosses"] if loop_ctx else []),
                   loop_deaths=(rs.deaths - loop_ctx["deaths_at_entry"]) if loop_ctx else rs.deaths)
        spawned = condition_met(cond, ctx)
        if cond:
            conds[b["id"]] = spawned
        entry = dict(boss=b["id"], route=rid, stage=stage["stage"], arrive=p.lvl, spawned=spawned, won=False,
                     secs=0.0, deaths=0, hits=0, gameover=False, boss_hp_left=None, last_stand=rs.last_stand)
        stage_log.append(dict(route=rid, stage=stage["stage"], lvl_in=lvl_in, lvl_out=p.lvl, fight_deaths=fight_deaths, fight_secs=fight_secs))
        if spawned:
            rs.time += C["boss_intro_s"]
            if R.get("boss_altar_full_heal", True):
                p.hp = p.maxhp()
            d0, t0 = rs.deaths, rs.time
            try:
                res = combat(rs, p, None, b, False, fever)
            except RunOver:
                # 보스전 도중 에너지 0 = 게임오버. 통계에서 빠뜨리지 않는다 (K1-F1): 진입·사망·그 순간 보스 잔여 체력 기록
                bu = rs.cur_boss_unit
                entry.update(gameover=True, deaths=rs.deaths - d0, boss_hp_left=(max(0.0, bu.hp / bu.maxhp) if bu else None))
                boss_log.append(entry)
                if loop_ctx is not None:
                    loop_ctx["bosses"].append(entry)
                rs.end_where = "boss_gameover:" + b["id"]
                raise
            rs.time += res["secs"]
            rs.boss_secs_total += res["secs"]
            entry.update(won=res["won"], secs=res["secs"], deaths=res["deaths"], hits=res["hits"])
            boss_log.append(entry)
            if loop_ctx is not None:
                loop_ctx["bosses"].append(entry)
            if not res["won"]:
                rs.end_where = "boss_timeout:" + b["id"]
                raise RunOver()
            # 보상
            rs.add_energy((R["energy_boss_main"] if rid == "main" else R["energy_boss_loop"]) + gear["energy_boss"])
            rs.last_stand = False
            if R.get("death_counter_reset", "door") == "door":
                rs.chapter_deaths = 0   # 문을 열면 누진 사망 카운터 0 (K1-F2: 한 구간 안에서만 3→4→5→6)
            D = cfg["stones"]["drop"]
            W = R["warp"]
            first = b["id"] not in killed_before
            if first:
                n_st = D["first_kill"] + (D["no_death_bonus"] if res["deaths"] == 0 else 0)
            elif start != "village":
                n_st = D["repeat_kill"] * W.get("repeat_stone_mult", 1.0)   # 워프 판 재처치 = 자동 모험과 같은 50%, 보너스 없음 (K2-4)
            else:
                n_st = D["repeat_kill"]
                if rnd.random() < D["repeat_bonus_p"]:
                    n_st += D["repeat_bonus_n"]
                if res["deaths"] == 0:
                    n_st += D["no_death_bonus"]
            stones[str(b["stone_tier"])] += n_st
            Ed = cfg["stones"]["essence_drop"]
            lk = p.luk()
            r = lk / (lk + F["crit"]["lvl_coef"] * p.lvl + F["luck_bonus"]["c"])
            n_es = Ed["first_kill"] if first else Ed["repeat_kill"]
            if rnd.random() < Ed["extra_base"] + Ed["extra_luck_coef"] * r:
                n_es += 1
            essence[b["id"]] = essence.get(b["id"], 0) + n_es
            rs.time += C["door_s"]
        else:
            boss_log.append(entry)
            if loop_ctx is not None:
                loop_ctx["bosses"].append(entry)
            rs.time += C["door_s"] * C["timing"]["no_boss_door_s_mult"]
            if rs.energy <= 0:
                rs.end_where = "no_boss_energy0"
                raise RunOver()
        return entry

    def do_loop(rid):
        route = routes[rid]
        rs.time += route["enter_s"]
        rs.chapter_deaths = 0   # 루프 '입장' 1회만 초기화 — 퇴장·광장 왕복으로는 초기화되지 않는다 (K2-7)
        ctx = dict(bosses=[], deaths_at_entry=rs.deaths)
        for stage in route["stages"]:
            do_stage(rid, stage, ctx)
        rs.time += route["enter_s"]

    try:
        if start != "village":
            for rid in ("left", "right"):
                if plan.get(rid) and routes[rid]["entry_after_main_stage"] == start_stage - 1:
                    do_loop(rid)
        for stage in routes["main"]["stages"]:
            if stage["stage"] < start_stage:
                continue
            do_stage("main", stage, None)
            for rid in ("left", "right"):
                if plan.get(rid) and routes[rid]["entry_after_main_stage"] == stage["stage"]:
                    do_loop(rid)
        rs.end_where = "complete"   # 마지막 열린 보스 처치 → 자동 결산 (run.end_after_last_boss)
    except RunOver:
        pass
    rs.time += R["result_s"]
    killed = [e["boss"] for e in boss_log if e["won"]]
    return dict(final_lvl=p.lvl, bosses=len(killed), bosses_main=sum(1 for e in boss_log if e["won"] and e["route"] == "main"),
                killed=killed, deaths=rs.deaths, energy=rs.energy, time=rs.time, boss_log=boss_log, stage_log=stage_log,
                fever=rs.fever_count, near_miss=rs.near_miss, jackpots=p.jackpots, equip=eq, stones=stones, essence=essence,
                conds=conds, atk=p.atk(), hp=p.maxhp(), crit=p.crit_p(), ls=p.ls(), aspd=p.aspd(),
                max_hit_taken=rs.max_hit_taken, capped_ratio=(rs.capped_hits / rs.boss_hits if rs.boss_hits else 0.0),
                boss_secs_total=rs.boss_secs_total, end_where=rs.end_where or "unknown")


# ----------------------------------------------------------------------------
# 집계 / 출력
# ----------------------------------------------------------------------------
def fmt_big(x):
    x = float(x)
    if x >= 1e12:
        return f"{x/1e12:.2f}조"
    if x >= 1e8:
        return f"{x/1e8:.2f}억"
    if x >= 1e4:
        return f"{x/1e4:.1f}만"
    return f"{int(x):,}"


def med(xs, d="-"):
    xs = list(xs)
    return st.median(xs) if xs else d


def summarize(cfg, plan, results, start="village"):
    if isinstance(plan, str):
        plan = plan_of(plan)
    order = boss_order(cfg, plan, start)
    nb = len(order)
    rows = []
    N = len(results)
    for bid in order:
        logs = [bl for r in results for bl in r["boss_log"] if bl["boss"] == bid]
        reach = len(logs) / N
        sp = [l for l in logs if l["spawned"]]          # 보스전 '진입' (게임오버 포함, K1-F1)
        wins = [l for l in sp if l["won"]]
        go = [l for l in sp if l.get("gameover")]
        go_hp = [l["boss_hp_left"] for l in go if l.get("boss_hp_left") is not None]
        rows.append(dict(
            boss=bid, name=cfg["bosses"][bid]["name_ko"], reach=reach, spawn=(len(sp) / len(logs)) if logs else 0.0,
            arrive=med([l["arrive"] for l in logs], 0), win=(len(wins) / len(sp)) if sp else 0.0,
            enter=len(sp) / N, kill=len(wins) / N, gameover=len(go) / N, go_hp=(st.median(go_hp) if go_hp else None),
            secs=med([l["secs"] for l in wins], 0), secs_min=min([l["secs"] for l in wins], default=0),
            secs_max=max([l["secs"] for l in wins], default=0),
            deaths=st.mean([l["deaths"] for l in sp]) if sp else 0.0,   # 진입자 전체(게임오버 판 포함) 기준
            hits=med([l["hits"] for l in wins], 0),
        ))
    clears = [r for r in results if r["bosses"] == nb]
    main_n = len([b for b in order if cfg["bosses"][b]["route"] == "main"]) or len(cfg["routes"]["main"]["stages"])
    ends = {}
    for r in results:
        k = r.get("end_where", "unknown")
        k = "boss_gameover" if k.startswith("boss_gameover") else k
        ends[k] = ends.get(k, 0) + 1
    return dict(
        rows=rows, nb=nb, clear=len(clears) / N,
        clear_main=sum(1 for r in results if r["bosses_main"] == main_n) / N,
        final=med([r["final_lvl"] for r in results], 0),
        time=med([r["time"] for r in results], 0), time_clear=med([r["time"] for r in clears], 0),
        deaths=st.mean([r["deaths"] for r in results]), bosses=st.mean([r["bosses"] for r in results]),
        fever=st.mean([r["fever"] for r in results]), near=st.mean([r["near_miss"] for r in results]),
        jackpots=st.mean([r["jackpots"] for r in results]), equip=results[0]["equip"],
        max_hit=max(r["max_hit_taken"] for r in results), capped=st.mean([r["capped_ratio"] for r in results]),
        stones=st.mean([sum(r["stones"].values()) for r in results]),
        essence=st.mean([sum(r["essence"].values()) for r in results]),
        fight_deaths=st.mean([sum(sl["fight_deaths"] for sl in r["stage_log"]) for r in results]),
        energy_left=med([r["energy"] for r in results], 0), energy_min=min(r["energy"] for r in results),
        ends={k: v / N for k, v in ends.items()},
        boss_gameover=sum(1 for r in results if r.get("end_where", "").startswith("boss_gameover")) / N,
    )


END_KO = {"complete": "완주(자동 결산)", "boss_gameover": "보스전 도중 게임오버", "fight_death": "일반 전투 사망", "after_fight_win": "전투 승리 직후 에너지 0",
          "no_boss_energy0": "에너지 0·조건부 보스 미등장", "unknown": "기타"}


def ends_text(S):
    return ", ".join(f"{END_KO.get(k.split(':')[0], k)} {v*100:.0f}%" for k, v in sorted(S["ends"].items(), key=lambda x: -x[1]))


def print_summary(cfg, title, S, show_rows=True):
    print(f"\n### {title}")
    print(f"장착: {', '.join(cfg['items'][i]['name_ko'] for i in S['equip']) or '(없음)'}")
    print(f"클리어율(전 보스 {S['nb']}) {S['clear']*100:.0f}% | 가운데 10보스 클리어 {S['clear_main']*100:.0f}% | 평균 처치 보스 {S['bosses']:.2f} | "
          f"중간 최종 레벨 {fmt_big(S['final'])} | 중간 판 시간 {S['time']/60:.1f}분 (클리어판 {S['time_clear']/60 if S['time_clear'] else 0:.1f}분) | "
          f"평균 사망 {S['deaths']:.2f} (일반 전투 {S['fight_deaths']:.2f}) | 피버 {S['fever']:.1f}회 | 니어미스 {S['near']:.2f}회 | "
          f"행운! {S['jackpots']:.0f}회 | 한 타 최대 피격 {S['max_hit']*100:.0f}% | 상한 타격 {S['capped']*100:.0f}% | 강화석 {S['stones']:.1f} 정수 {S['essence']:.1f} | "
          f"에너지 잔여(중간/최소) {S['energy_left']:.0f}/{S['energy_min']:.0f}")
    print(f"판 종료 지점: {ends_text(S)}")
    if show_rows:
        print("| # | 보스 | 도달율 | 등장(조건) | 도착 레벨(중간) | 진입→처치 | 처치율 | 게임오버율 | 게임오버 잔여 체력 | 보스전 초(중간) | 최소~최대 | 타수 | 사망(진입자) |")
        print("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
        for i, r in enumerate(S["rows"]):
            if r["reach"] == 0:
                print(f"| {i+1} | {r['name']} | 0% | - | - | - | - | - | - | - | - | - | - |")
                continue
            cond = cfg["bosses"][r["boss"]].get("spawn_condition")
            sp = f"{r['spawn']*100:.0f}%" if cond else "항상"
            if r["spawn"] == 0:
                print(f"| {i+1} | {r['name']} | {r['reach']*100:.0f}% | {sp} | {fmt_big(r['arrive'])} | - | - | - | - | - | - | - | - |")
                continue
            gh = f"{r['go_hp']*100:.0f}%" if r["go_hp"] is not None else "-"
            print(f"| {i+1} | {r['name']} | {r['reach']*100:.0f}% | {sp} | {fmt_big(r['arrive'])} | {r['win']*100:.0f}% | {r['kill']*100:.0f}% | "
                  f"{r['gameover']*100:.0f}% | {gh} | {r['secs']:.1f} | {r['secs_min']:.1f}~{r['secs_max']:.1f} | {r['hits']:.0f} | {r['deaths']:.2f} |")


def scenario(cfg, plan, owned, runs, plus=None, manual=True, ratio=None, vip=False, equip=None, seed0=1000,
             start="village", fever=True, killed_before=None):
    res = [run(cfg, plan, owned, plus, manual, ratio, vip, seed=seed0 + i, equip=equip, start=start, fever=fever,
               killed_before=killed_before) for i in range(runs)]
    return summarize(cfg, plan, res, start), res


def route_items(cfg, rid):
    return [cfg["bosses"][s["boss"]]["drop_item"] for s in cfg["routes"][rid]["stages"]]


def natural_for(cfg, bid):
    """보스 bid 를 '처음 만나는 판'의 (plan, owned). 가운데: 이전 가운데 보스 아이템. 질풍: 가운데 1~5 + 이전 질풍. 군단: 가운데 10 + 질풍 5 + 이전 군단."""
    b = cfg["bosses"][bid]
    main_items = route_items(cfg, "main")
    if b["route"] == "main":
        return "main", main_items[:b["stage"] - 1]
    if b["route"] == "left":
        ent = cfg["routes"]["left"]["entry_after_main_stage"]
        return "left", main_items[:ent] + route_items(cfg, "left")[:b["stage"] - 1]
    # 군단 루프의 자연 플레이어는 질풍 루프도 돈다(에너지 광산) → plan full
    return "full", main_items + route_items(cfg, "left") + route_items(cfg, "right")[:b["stage"] - 1]


# ----------------------------------------------------------------------------
# PvP 결투 (마을 결투장)
# ----------------------------------------------------------------------------
def make_duelist(cfg, ratio, owned, plus=None, use_caps=True, equip=None):
    P = cfg["pvp"]
    g = aggregate(cfg, equip if equip is not None else auto_equip(cfg, owned), plus, pvp=use_caps)
    pl = Player(cfg, g, ratio, manual=False, pvp=use_caps, no_jackpot=(use_caps and P.get("points_fixed", False)))
    feed_exp(pl, pl.curve.E(P["duel_level"]))
    pl.hp = pl.maxhp()
    return pl


def pvp_duel(cfg, ratio1, ratio2, owned, n, plus=None, use_caps=True, seed0=50000, equip1=None, equip2=None, plus2=None):
    """둘 다 결투 레벨로 정규화, 각자 분배 비율 + 장비(+강화; equip1/equip2 로 비대칭 장비, plus2 로 상대 강화). caps.pvp 적용(use_caps).
    피해감소는 한 타 상한 '뒤'에 적용(K2-2), heal_off_after_s 뒤에는 양측 회복 0(K2-13). 반환 (승률, 평균 초)."""
    P = cfg["pvp"]
    caps = caps_of(cfg, True) if use_caps else caps_of(cfg, False)
    wins = 0
    secs = []
    heal_off = P.get("heal_off_after_s", 10 ** 9)
    for i in range(n):
        rnd = random.Random(seed0 + i)
        ps = [make_duelist(cfg, ratio1, owned, plus, use_caps, equip1),
              make_duelist(cfg, ratio2, owned, (plus2 if plus2 is not None else plus), use_caps, equip2)]
        d0, d1 = P["first_swing_delay_s"]
        nxt = [rnd.uniform(d0, d1), rnd.uniform(d0, d1)]
        t = 0.0
        while t < P["time_limit_s"]:
            i_ = 0 if nxt[0] <= nxt[1] else 1
            t = nxt[i_]
            a, d = ps[i_], ps[1 - i_]
            iv = cfg["combat"]["attack_interval"] / a.aspd()
            dodge = min(P["dodge_cap"], max(P["dodge_floor"], d.crit_p() * P["dodge_from_crit"])) if use_caps else 0.0
            if rnd.random() < dodge:
                nxt[i_] = t + iv
                continue
            crit = rnd.random() < a.crit_p()
            dmg = a.atk() * (P["dmg_mult"] if use_caps else 1.0) * rnd.uniform(a.g["var_lo"], a.g["var_hi"]) * (a.crit_mult() if crit else 1)
            dmg = min(dmg, d.maxhp() * caps["hit_taken_cap"]) * (1 - d.g["dmg_reduce"])
            d.hp -= dmg
            if d.g["reflect"] > 0:
                a.hp -= min(dmg * d.g["reflect"], a.maxhp() * caps["hit_taken_cap"])
            if use_caps:
                # 결투장 흡혈: 타격당 회복 = 흡혈률 × (상대 최대 체력) × k — 피해량처럼 상대 체력에 비례(체력형이 회복까지 독식하지 않게)
                hb = P.get("heal_basis", "geomean")
                basis = d.maxhp() if hb == "opponent_maxhp" else (a.maxhp() if hb == "own_maxhp" else math.sqrt(a.maxhp() * d.maxhp()))
                heal = a.ls() * basis * P["heal_per_hit_hp_frac"] * (a.g["ls_crit_mult"] if crit else 1.0)
            else:
                heal = dmg * a.ls() * (a.g["ls_crit_mult"] if crit else 1.0)
            heal = min(heal, a.maxhp() * a.heal_cap_per_s(a.ls()) * iv)
            if use_caps and t >= heal_off:
                heal = 0.0   # 버티기 메타 방지: 45초부터 회복 없음
            a.hp = min(a.maxhp(), a.hp + heal)
            if d.hp <= 0 or a.hp <= 0:
                break
            nxt[i_] = t + iv
        f1, f2 = ps[0].hp / ps[0].maxhp(), ps[1].hp / ps[1].maxhp()
        if f1 > f2:
            wins += 1
        elif f1 == f2:
            wins += 0.5
        secs.append(t)
    return wins / n, st.mean(secs)


# ----------------------------------------------------------------------------
# 보스 러시 타임어택 (결투 레벨 고정, 장비만, 에너지 없음)
# ----------------------------------------------------------------------------
def rush_scaled_boss(cfg, bid, pl):
    """보스 러시용: 보스를 결투 레벨 플레이어의 '장비 없는' 능력치에 맞춰 재조정 (앵커 대비 비율 유지 → 장비·강화만이 차이)."""
    b = json.loads(json.dumps(cfg["bosses"][bid]))
    if b["gimmick"].get("mirror"):
        return b
    a = b["anchor"]
    g_nat = aggregate(cfg, a["natural_items"])
    k_hp = pl.atk_base() / (a["player_atk"] / g_nat["atk_mult"])
    k_atk = pl.maxhp_base() / (a["player_hp"] / g_nat["hp_mult"])
    b["hp"] = b["hp"] * k_hp
    b["atk"] = b["atk"] * k_atk
    if "adds" in b["gimmick"]:
        u = b["gimmick"]["adds"]["unit"]
        u["hp"] *= k_hp
        u["atk"] *= k_atk
    return b


def boss_rush(cfg, owned, plus=None, n=30, ratio=None, seed0=70000):
    BR = cfg["boss_rush"]
    totals, per_boss = [], {}
    order = boss_order(cfg, plan_of("full"))
    for i in range(n):
        rnd = random.Random(seed0 + i)
        g = aggregate(cfg, auto_equip(cfg, owned), plus)
        pl = Player(cfg, g, ratio, manual=True)
        feed_exp(pl, pl.curve.E(BR["level"]))
        rs = RunState(cfg, rnd, 10 ** 9, unlimited=True)   # 러시는 에너지 없음
        tot = 0.0
        for bid in order:
            b = rush_scaled_boss(cfg, bid, pl)
            pl.hp = pl.maxhp()
            res = combat(rs, pl, None, b, False, True)
            tt = res["secs"] + res["deaths"] * BR["death_penalty_s"]
            per_boss.setdefault(bid, []).append(tt)
            tot += tt
            # 러시는 레벨 고정: 경험치로 오른 레벨을 되돌린다
            pl2 = Player(cfg, g, ratio, manual=True)
            feed_exp(pl2, pl2.curve.E(BR["level"]))
            pl.pts, pl.lvl, pl.exp = pl2.pts, pl2.lvl, pl2.exp
        totals.append(tot)
    return st.median(totals), {b: st.median(v) for b, v in per_boss.items()}


# ----------------------------------------------------------------------------
# 계정 성장 (판 반복): 첫 계정 → 매 판 드롭·강화석·정수 → 탐욕 강화
# ----------------------------------------------------------------------------
def enhance_greedy(cfg, plus, stones, essence, equipped):
    """장착 중 가장 낮은 +부터, 그 급 강화석·그 보스 정수가 충분하면 강화 시도(천장 포함). 반환 시도 수."""
    S = cfg["stones"]
    rnd = random.Random(len(stones) * 7919 + sum(stones.values()))
    tries = 0
    pity = {}
    progressed = True
    while progressed:
        progressed = False
        for iid in sorted(equipped, key=lambda i: plus.get(i, 0)):
            pl = plus.get(iid, 0)
            if pl >= S["max_plus"]:
                continue
            it = cfg["items"][iid]
            tier = str(it["tier"])
            cost, es = S["cost"][pl], S["essence_cost"][pl]
            # 하위 강화석 5 → 상위 1 교환 (부족할 때만, 아래 급부터 차례로 올림)
            ex = S["exchange"]["lower_to_upper"]
            moved = True
            while stones[tier] < cost and moved:
                moved = False
                for lower in range(1, int(tier)):
                    lt, ut = str(lower), str(lower + 1)
                    if stones[lt] >= ex:
                        stones[lt] -= ex
                        stones[ut] += 1
                        moved = True
            if stones[tier] < cost or essence.get(it["boss"], 0) < es:
                continue
            stones[tier] -= cost
            tries += 1
            ok = rnd.random() < S["success"][pl] or pity.get((iid, pl), 0) >= S["pity_fails"] - 1
            if ok:
                essence[it["boss"]] = essence.get(it["boss"], 0) - es
                plus[iid] = pl + 1
                pity[(iid, pl)] = 0
            else:
                pity[(iid, pl)] = pity.get((iid, pl), 0) + 1
            progressed = True
    return tries


def account_growth(cfg, seed, max_runs=120, pass_auto=False, use_warp=True):
    """첫 계정에서 시작. 정책: 아이템 5개 미만이면 가운데만, 질풍 입구 보스(B05) 기록이 있으면 질풍 포함, B10 기록이 있으면 군단 포함.
    워프(K2-4 반영): B10 을 unlock_kills 회 잡은 뒤에는 하루 5판 중 warp.daily_limit(2)판을 10단계 광장 워프 판(군단 루프만)으로 쓴다 — 재처치 강화석 50%·보너스 없음.
    강화: 판 끝마다 탐욕. 자동 모험: 하루(=판 5회)마다 free/pass 횟수 × 50% 강화석(첫 처치 없음). 반환 이정표."""
    owned, killed_ever, plus = [], set(), {}
    stones = {str(k): 0 for k in cfg["stones"]["tiers"]}
    essence = {}
    kills = {}
    tmin = 0.0
    out = dict(first10=None, first20=None, all_plus5=None, all_plus10=None, t10=None, t20=None, t5=None, tp10=None, runs=0, warp_runs=0)
    A = cfg["monetization"]["auto_adventure"]
    W = cfg["run"]["warp"]
    for rn in range(1, max_runs + 1):
        plan = dict(left="B05" in killed_ever, right="B10" in killed_ever)
        warp_ok = use_warp and plan["right"] and kills.get("B10", 0) >= W["unlock_kills"]
        day_slot = rn % A["manual_runs_per_day_assumed"]
        if warp_ok and day_slot in tuple(range(1, W.get("daily_limit", 2) + 1)):
            r = run(cfg, dict(left=False, right=True), owned, plus, seed=seed * 100000 + rn, killed_before=killed_ever, start="plaza10")
            out["warp_runs"] += 1
        else:
            r = run(cfg, plan, owned, plus, seed=seed * 100000 + rn, killed_before=killed_ever)
        for k in r["killed"]:
            kills[k] = kills.get(k, 0) + 1
        tmin += r["time"] / 60
        for k, v in r["stones"].items():
            stones[k] += v
        for k, v in r["essence"].items():
            essence[k] = essence.get(k, 0) + v
        killed_ever |= set(r["killed"])
        owned = [cfg["bosses"][b]["drop_item"] for b in sorted(killed_ever)]
        # 자동 모험(하루 = 판 5회): 이미 잡은 보스까지 재처치 강화석 50%
        if rn % A["manual_runs_per_day_assumed"] == 0:
            n_auto = A["pass_per_day"] if pass_auto else A["free_per_day"]
            for _ in range(n_auto):
                ra = run(cfg, plan, owned, plus, manual=False, seed=seed * 100000 + rn * 31 + _, killed_before=killed_ever)
                for k, v in ra["stones"].items():
                    stones[k] += int(v * A["stone_rate"])
                for k, v in ra["essence"].items():
                    essence[k] = essence.get(k, 0) + int(v * A["stone_rate"])
        eq = auto_equip(cfg, owned)
        enhance_greedy(cfg, plus, stones, essence, eq)
        if out["first10"] is None and r["bosses_main"] == 10:
            out["first10"], out["t10"] = rn, round(tmin)
        if out["first20"] is None and r["bosses"] == 20:
            out["first20"], out["t20"] = rn, round(tmin)
        if out["all_plus5"] is None and len(eq) == 7 and all(plus.get(i, 0) >= 5 for i in eq):
            out["all_plus5"], out["t5"] = rn, round(tmin)
        if out["all_plus10"] is None and len(eq) == 7 and all(plus.get(i, 0) >= 10 for i in eq):
            out["all_plus10"], out["tp10"] = rn, round(tmin)
            break
    out["runs"] = rn
    out["plus"] = {i: plus.get(i, 0) for i in auto_equip(cfg, owned)}
    return out


# ----------------------------------------------------------------------------
# 보고서
# ----------------------------------------------------------------------------
def full_report(cfg, N, quick=False):
    t0 = time.time()
    all_items = list(cfg["items"].keys())
    main_items = route_items(cfg, "main")
    curve = Curve(cfg["exp_curve"])
    H = N // 2
    print("# 20보스 최종 통합 설계 시뮬레이션 결과 (판 수 = %d, 수동 조작 모델, 탭 성공률 %.2f)" % (N, cfg["combat"]["manual_combo_p"]))
    print("경험치 곡선 확인: need(1)=%.1f need(1000)=%.1f need(1e6)=%.1f need(1e8)=%.1f ; E(30)=%.0f E(1e6)=%s"
          % (curve.need(1), curve.need(1000), curve.need(1e6), curve.need(1e8), curve.E(30), fmt_big(curve.E(1e6))))

    # A. 장비 0
    S0, _ = scenario(cfg, "main", [], N)
    print_summary(cfg, "A. 가운데 길 — 장비 0 (첫 판 / 부트스트랩 검증)", S0)
    _b2, _b3 = S0["rows"][1], S0["rows"][2]
    print(f"첫 판 결산: 판 사망 {S0['deaths']:.2f} | B02 진입 {_b2['enter']*100:.0f}%·처치 {_b2['kill']*100:.0f}%·게임오버 {_b2['gameover']*100:.0f}% | "
          f"B03 진입 {_b3['enter']*100:.0f}%·처치 {_b3['kill']*100:.0f}%·게임오버 {_b3['gameover']*100:.0f}% | "
          f"보스전 도중 게임오버로 끝난 판 {S0['boss_gameover']*100:.0f}% | 전투 승리 직후 에너지 0 종료 {S0['ends'].get('after_fight_win', 0)*100:.0f}%")
    S0f, _ = scenario(cfg, "main", [], N, fever=False)
    print_summary(cfg, "A-2. 가운데 길 — 장비 0, 피버 OFF (1차 출시 구성의 첫 판)", S0f, show_rows=False)
    _f2, _f3 = S0f["rows"][1], S0f["rows"][2]
    print(f"피버 OFF 첫 판 결산: 1보스 {S0f['rows'][0]['secs']:.1f}초 사망 {S0f['rows'][0]['deaths']:.2f} | B02 진입 {_f2['enter']*100:.0f}%·처치 {_f2['kill']*100:.0f}%·게임오버 {_f2['gameover']*100:.0f}% | B03 진입 {_f3['enter']*100:.0f}%·처치 {_f3['kill']*100:.0f}%")
    alt = cfg["bosses"]["B01"].get("alt_drop_item")
    if alt:
        print(f"\n### A-3. 첫 보스 보상 2택1 — 2판째(그 아이템 하나만 보유): 엄니검 vs {cfg['items'][alt]['name_ko']} (첫 10분 안의 첫 '선택')")
        print("| 선택 | B02 진입 | B02 처치 | B02 보스전 초 | B02 사망 | B03 진입 | B03 처치 | 평균 처치 보스 | 판 시간(분) | 판 사망 |")
        print("|---|---|---|---|---|---|---|---|---|---|")
        for iid in ("I01", alt):
            Sx, _ = scenario(cfg, "main", [iid], H)
            x2, x3 = Sx["rows"][1], Sx["rows"][2]
            print(f"| {cfg['items'][iid]['name_ko']} | {x2['enter']*100:.0f}% | {x2['kill']*100:.0f}% | {x2['secs']:.1f} | {x2['deaths']:.2f} | {x3['enter']*100:.0f}% | {x3['kill']*100:.0f}% | {Sx['bosses']:.2f} | {Sx['time']/60:.1f} | {Sx['deaths']:.2f} |")
    # B. 장비 1개
    S1, _ = scenario(cfg, "main", main_items[:1], N)
    print_summary(cfg, "B. 가운데 길 — 장비 1개(엄니검)", S1)
    # C. 자연 진행 20보스
    print("\n### C. 자연 진행 — 보스 k 를 처음 만나는 판(이전 보스 아이템만 보유, 가운데 1~5 → 질풍 루프 / 가운데 10 + 질풍 5 → 군단 루프)")
    print("| 보스 | 보유 아이템 수 | 도달율 | 등장(조건) | 도착 레벨 | 진입→처치 | 처치율 | 게임오버율 | 게임오버 잔여 체력 | 보스전 초 | 타수 | 사망(진입자) | 판 시간(분) |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    nat_rows = {}
    for bid in cfg["bosses"]:
        plan, owned = natural_for(cfg, bid)
        Sk, _ = scenario(cfg, plan, owned, H if quick else N)
        r = [x for x in Sk["rows"] if x["boss"] == bid][0]
        nat_rows[bid] = r
        cond = cfg["bosses"][bid].get("spawn_condition")
        sp = f"{r['spawn']*100:.0f}%" if cond else "항상"
        gh = f"{r['go_hp']*100:.0f}%" if r["go_hp"] is not None else "-"
        print(f"| {bid} {r['name']} | {len(owned)} | {r['reach']*100:.0f}% | {sp} | {fmt_big(r['arrive'])} | {r['win']*100:.0f}% | {r['kill']*100:.0f}% | {r['gameover']*100:.0f}% | {gh} | {r['secs']:.1f} | {r['hits']:.0f} | {r['deaths']:.2f} | {Sk['time']/60:.1f} |")
    # D. 가운데 10종
    S10, _ = scenario(cfg, "main", main_items, N)
    print_summary(cfg, "D. 가운데 길만 — 가운데 길 아이템 10종 보유(자동 장착)", S10)
    # E. 풀장비 20종: 가운데만 / 20보스 루프 전부
    S20m, _ = scenario(cfg, "main", all_items, N)
    print_summary(cfg, "E-1. 가운데 길만 — 아이템 20종 전부(자동 장착 7칸) = 풀장비, 숙련 풀클리어", S20m)
    S20, _ = scenario(cfg, "full", all_items, N)
    print_summary(cfg, "E-2. 20보스 완전 클리어 판 — 풀장비, 가운데 1~5 → 질풍 루프 → 가운데 6~10 → 군단 루프", S20)
    # F. 강화
    SP = {}
    for pl in (5, 10):
        Sp, _ = scenario(cfg, "full", all_items, H, plus={i: pl for i in all_items})
        print_summary(cfg, f"F{pl}. 20보스 완전 클리어 판 — 풀장비 전부 +{pl} 강화", Sp)
        SP[pl] = Sp
    # G. 자동 모험
    Sa, _ = scenario(cfg, "full", all_items, H, manual=False)
    print_summary(cfg, "G. 20보스 판 — 풀장비, 자동 모험(시뮬) 모드 (피버 없음·구역 22%·회피 35%·조건 보스 거의 못 봄)", Sa, show_rows=False)
    Sa0, _ = scenario(cfg, "main", [], H, manual=False)
    print_summary(cfg, "G0. 가운데 길 — 장비 0, 자동 모험 모드", Sa0, show_rows=False)
    # H. 패스
    cfg_v = json.loads(json.dumps(cfg)); cfg_v["monetization"]["pass_energy_bonus"] = 1
    Sv, _ = scenario(cfg_v, "main", [], N, vip=True)
    print_summary(cfg, "H. 가운데 길 — 장비 0 + '시작 에너지 +1' 을 팔았다면: 과금 영향 측정 (현재 패스에는 에너지 보너스 없음)", Sv, show_rows=False)
    Sv2, _ = scenario(cfg_v, "main", main_items[:4], H, vip=True)
    Sn2, _ = scenario(cfg, "main", main_items[:4], H, vip=False)
    print(f"  아이템 4개 보유 판: 패스 없음 평균 보스 {Sn2['bosses']:.2f} / 패스 {Sv2['bosses']:.2f}, 최종 레벨 {fmt_big(Sn2['final'])} / {fmt_big(Sv2['final'])}, 사망 {Sn2['deaths']:.2f} / {Sv2['deaths']:.2f}")
    # I. 피버 OFF (1차 출시: 쿨다운 공유만)
    Sf, _ = scenario(cfg, "main", main_items, H, fever=False)
    print_summary(cfg, "I. 가운데 길 — 가운데 10종, 피버 OFF (1차 출시 구성: 리듬 탭 없음)", Sf)
    print(f"  장비 0 + 피버 OFF(A-2): 1보스 승률 {S0f['rows'][0]['win']*100:.0f}% 사망 {S0f['rows'][0]['deaths']:.2f} 초 {S0f['rows'][0]['secs']:.1f}, 2보스 도달 {S0f['rows'][1]['reach']*100:.0f}% 처치 {S0f['rows'][1]['kill']*100:.0f}%")
    # J. 빌드 비교
    print("\n### J. 빌드(자동 분배 비율) 비교 — 풀장비 +0, 가운데 길 10보스 / 20보스 판")
    print("| 빌드 | 체:공:행:흡 | 가운데 10 클리어 | 20보스 클리어 | 중간 최종 레벨(20보스 판) | 판 시간(분) | 평균 사망 | 보스전 초 합(중간) | 치명 | 흡혈 |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    build_rows = {}
    for name, ratio in cfg["builds"].items():
        Sb, Rb = scenario(cfg, "main", all_items, H, ratio=ratio)
        Sb2, Rb2 = scenario(cfg, "full", all_items, H, ratio=ratio)
        tot = med([r["boss_secs_total"] for r in Rb2 if r["bosses"] == 20], 0)
        build_rows[name] = (Sb, Sb2)
        print(f"| {name} | {ratio['hp']}:{ratio['atk']}:{ratio['luk']}:{ratio['ls']} | {Sb['clear_main']*100:.0f}% | {Sb2['clear']*100:.0f}% | {fmt_big(Sb2['final'])} | {Sb2['time']/60:.1f} | {Sb2['deaths']:.2f} | {tot:.0f} | {Rb2[0]['crit']*100:.0f}% | {Rb2[0]['ls']*100:.1f}% |")
    # K-0. 획득 직후 기여도
    print("\n### K-0. 아이템 '획득 직후' 기여도 — 그 보스를 처음 잡은 다음 판(자연 장비+이 아이템) vs 같은 판에 이 아이템만 없을 때 (다음 보스 도달×등장×승리)")
    print("| 아이템 | 보스 | 다음 보스 | 없음→있음 승리 | 평균 처치 보스(없음→있음) | 평균 사망 | 중간 최종 레벨 | 판 시간(분) |")
    print("|---|---|---|---|---|---|---|---|")
    k0 = {}
    for rid in ("main", "left", "right"):
        bosses = [s["boss"] for s in cfg["routes"][rid]["stages"]]
        for k, bid in enumerate(bosses):
            nxt = bosses[k + 1] if k + 1 < len(bosses) else bid
            plan, owned = natural_for(cfg, nxt)
            if k + 1 >= len(bosses):
                plan, owned = natural_for(cfg, bid)
                owned = owned + [cfg["bosses"][bid]["drop_item"]]
            iid = cfg["bosses"][bid]["drop_item"]
            without = [i for i in owned if i != iid]
            Sw, _ = scenario(cfg, plan, without, H)
            Si, _ = scenario(cfg, plan, owned, H)
            rw = [x for x in Sw["rows"] if x["boss"] == nxt][0]
            ri = [x for x in Si["rows"] if x["boss"] == nxt][0]
            ww, wi = rw["win"] * rw["reach"] * rw["spawn"], ri["win"] * ri["reach"] * ri["spawn"]
            k0[iid] = dict(d_win=wi - ww, d_boss=Si["bosses"] - Sw["bosses"], d_death=Si["deaths"] - Sw["deaths"], ratio=Si["final"] / Sw["final"] if Sw["final"] else 1)
            print(f"| {cfg['items'][iid]['name_ko']} | {bid} | {nxt} | {ww*100:.0f}%→{wi*100:.0f}% | {Sw['bosses']:.2f}→{Si['bosses']:.2f} | {Sw['deaths']:.2f}→{Si['deaths']:.2f} | {fmt_big(Sw['final'])}→{fmt_big(Si['final'])} | {Sw['time']/60:.1f}→{Si['time']/60:.1f} |")
    # K. 풀장비 기여도 (20보스 판)
    print("\n### K. 아이템 기여도 — 풀장비 20보스 판 기준. 장착 아이템은 '없다면(차순위 자동 장착)', 미장착은 '같은 칸 최하위와 교체하면'")
    base_eq = auto_equip(cfg, all_items)
    base_S, _ = scenario(cfg, "full", all_items, N, equip=base_eq)
    print(f"기준: 20보스 클리어 {base_S['clear']*100:.0f}% | 시간 {base_S['time_clear']/60:.2f}분 | 최종 {fmt_big(base_S['final'])} | 사망 {base_S['deaths']:.2f} | 보스전 초 합 {sum(r['secs'] for r in base_S['rows']):.0f}")
    print("| 아이템 | 칸 | 상태 | 비교 방식 | 클리어율 변화 | 클리어 시간 변화(분) | 최종 레벨 비 | 사망 변화 | 보스전 초 합 변화 | 획득 직후 Δ승리 |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    base_bsum = sum(r["secs"] for r in base_S["rows"])
    contrib = {}
    for iid, it in cfg["items"].items():
        if iid in base_eq:
            eq = auto_equip(cfg, [i for i in all_items if i != iid])
            how = "없다면(차순위 자동 장착)"
        else:
            same = [i for i in base_eq if cfg["items"][i]["slot"] == it["slot"]]
            worst = min(same, key=lambda i: cfg["items"][i]["rank"])
            eq = [i for i in base_eq if i != worst] + [iid]
            how = f"{cfg['items'][worst]['name_ko']}와 교체"
        Sx, _ = scenario(cfg, "full", all_items, H, equip=eq)
        d_clear = base_S["clear"] - Sx["clear"]
        d_time = ((Sx["time_clear"] or Sx["time"]) - base_S["time_clear"]) / 60
        ratio = Sx["final"] / base_S["final"] if base_S["final"] else 0
        d_death = Sx["deaths"] - base_S["deaths"]
        d_b = sum(r["secs"] for r in Sx["rows"]) - base_bsum
        contrib[iid] = dict(how=how, d_clear=d_clear, d_time=d_time, ratio=ratio, d_death=d_death, d_boss=d_b, k0=k0.get(iid, {}).get("d_win", 0))
        state = "장착" if iid in base_eq else "미장착"
        print(f"| {it['name_ko']} | {it['slot']} | {state} | {how} | {d_clear*100:+.0f}%p | {d_time:+.2f} | ×{ratio:.2f} | {d_death:+.2f} | {d_b:+.1f}s | {k0.get(iid, {}).get('d_win', 0)*100:+.0f}%p |")
    zero = [cfg["items"][i]["name_ko"] for i, c in contrib.items()
            if abs(c["d_clear"]) < 0.005 and abs(c["d_time"]) < 0.05 and abs(c["ratio"] - 1) < 0.01 and abs(c["d_death"]) < 0.05 and abs(c["d_boss"]) < 1.0 and abs(c["k0"]) < 0.02]
    print(f"기여도 0 아이템(모든 지표 변화 없음): {zero if zero else '없음'}")
    # L. PvP
    builds = list(cfg["builds"].items())
    pvp_range = (0.0, 1.0)
    for use_caps, title in ((True, "L-1. PvP 결투장 미러 매치 (결투 레벨 %s, 풀장비 +0, 60초, caps.pvp 적용) — 행 빌드가 열 빌드를 이길 확률" % fmt_big(cfg["pvp"]["duel_level"])),
                            (False, "L-2. 같은 결투, 상한 없음(caps.pve·피해 ×1·회피 없음) — 비교용")):
        print("\n### " + title)
        print("| 빌드 \\ 상대 | " + " | ".join(b for b, _ in builds) + " | 평균 결투 초 |")
        print("|---|" + "---|" * (len(builds) + 1))
        worst = (1.0, 0.0)
        for n1, r1 in builds:
            cells, secs_all = [], []
            for n2, r2 in builds:
                w, s = pvp_duel(cfg, r1, r2, all_items, H, use_caps=use_caps)
                cells.append(f"{w*100:.0f}%")
                secs_all.append(s)
                if n1 != n2:
                    worst = (min(worst[0], w), max(worst[1], w))
            print(f"| {n1} | " + " | ".join(cells) + f" | {st.mean(secs_all):.1f} |")
        print(f"비대칭 쌍 승률 범위: {worst[0]*100:.0f}%~{worst[1]*100:.0f}% (목표 20~80%)" if use_caps else "")
        if use_caps:
            pvp_range = worst
    # L-3 +10 PvP
    w10, s10 = pvp_duel(cfg, cfg["builds"]["균형(기본)"], cfg["builds"]["균형(기본)"], all_items, H, plus={i: 10 for i in all_items})
    w10b, s10b = pvp_duel(cfg, cfg["builds"]["탱커"], cfg["builds"]["균형(기본)"], all_items, H, plus={i: 10 for i in all_items})
    print(f"L-3. 전부 +10 결투: 균형 vs 균형 {w10*100:.0f}% ({s10:.1f}초), 탱커 vs 균형 {w10b*100:.0f}% ({s10b:.1f}초)")
    # L-4 비대칭 장비 격자 (K2-2): 프리셋 5 × 장비셋 4, 상대 = 균형·기본(자동 장착) 장비, 양쪽 전부 +10
    GEAR_SETS = {k: (v if v is not None else auto_equip(cfg, all_items)) for k, v in cfg["pvp"]["gear_sets_for_test"].items()}
    base_eq_pvp = GEAR_SETS["공격셋"]
    print("\n### L-4. PvP 장비 비대칭 격자 — 행(빌드 + 장비셋, 전부 +10) 이 '균형 + 공격셋(+10)' 을 이길 확률 (합격: 결투용 4셋 전부 20~80%; 'PvE 자동 장착' 열은 참고)")
    print("| 빌드 \\ 장비셋 | " + " | ".join(GEAR_SETS.keys()) + " |")
    print("|---|" + "---|" * len(GEAR_SETS))
    asym = (1.0, 0.0)
    for n1, r1 in builds:
        cells = []
        for gname, geq in GEAR_SETS.items():
            w, s_ = pvp_duel(cfg, r1, cfg["builds"]["균형(기본)"], all_items, H, plus={i: 10 for i in all_items}, equip1=geq, equip2=base_eq_pvp)
            cells.append(f"{w*100:.0f}%({s_:.0f}s)")
            if "참고" not in gname:
                asym = (min(asym[0], w), max(asym[1], w))
        print(f"| {n1} | " + " | ".join(cells) + " |")
    g_def = aggregate(cfg, GEAR_SETS["방어셋"], {i: 10 for i in GEAR_SETS["방어셋"]}, pvp=True)
    print(f"비대칭 격자 승률 범위: {asym[0]*100:.0f}%~{asym[1]*100:.0f}% (목표 20~80%) — 방어셋 +10 PvP 피해감소 {g_def['dmg_reduce']*100:.1f}%(상한 {cfg['caps']['pvp']['dmg_reduce']*100:.0f}%, 용암 망토 강화 불가, 한 타 상한 {cfg['caps']['pvp']['hit_taken_cap']*100:.0f}% 뒤 적용). {cfg['pvp']['gear_sets_note_ko']}")
    # L-5 함정 분배 (K2-15)
    print("\n### L-5. 결투 함정 분배 — 임의 분배 vs 균형(기본 장비, +0 / +10) 승률")
    print("| 분배 | +0 | +10 | 판정 |")
    print("|---|---|---|---|")
    trap_rows = {}
    for name, rt in cfg["pvp"]["trap_builds_for_test"].items():
        w0, _ = pvp_duel(cfg, rt, cfg["builds"]["균형(기본)"], all_items, H)
        w1, _ = pvp_duel(cfg, rt, cfg["builds"]["균형(기본)"], all_items, H, plus={i: 10 for i in all_items})
        trap_rows[name] = (w0, w1)
        print(f"| {name} {rt['hp']}:{rt['atk']}:{rt['luk']}:{rt['ls']} | {w0*100:.0f}% | {w1*100:.0f}% | {'함정(결투장 입장 시 예측 카드 경고)' if max(w0, w1) < 0.2 else '허용'} |")
    # M. 익스플로잇
    print("\n### M. 익스플로잇 체크")
    f = cfg["formulas"]["luck_bonus"]
    print("M-1 행운 보너스(2배 당첨) 레벨당 실효 포인트 배율 — 상한 ×%.1f" % (1 + f["p_cap"] * (f["double_mult"] - 1)))
    print("| 레벨 | 균형 | 행운 도박 | 행운 몰빵(0.5:0.5:3:0) | 행운 도박+행운의 왕관 |")
    print("|---|---|---|---|---|")
    for L in (1e3, 1e4, 1e6, 1e8, 1e10):
        cells = []
        for ratio, items in ((cfg["builds"]["균형(기본)"], []), (cfg["builds"]["행운 도박"], []), ({"hp": 0.5, "atk": 0.5, "luk": 3.0, "ls": 0.0}, []), (cfg["builds"]["행운 도박"], ["I14"])):
            pl = Player(cfg, aggregate(cfg, items), ratio)
            feed_exp(pl, curve.E(L))
            cells.append(f"×{1 + pl.luck_jackpot_p() * (f['double_mult'] - 1):.2f} (치명 {pl.crit_p()*100:.0f}%)")
        print(f"| {fmt_big(L)} | " + " | ".join(cells) + " |")
    Sl, _ = scenario(cfg, "main", all_items, H, ratio={"hp": 0.5, "atk": 0.5, "luk": 3.0, "ls": 0.0})
    print(f"행운 몰빵(0.5:0.5:3:0) 풀장비 가운데 길: 클리어 {Sl['clear_main']*100:.0f}% 사망 {Sl['deaths']:.2f} 최종 {fmt_big(Sl['final'])} (균형 {S20m['clear_main']*100:.0f}% / {S20m['deaths']:.2f} / {fmt_big(S20m['final'])})")
    glass = {"hp": 0.5, "atk": 3.0, "luk": 0.5, "ls": 0.0}
    for pl_ in (0, 5, 10):
        pp = {i: pl_ for i in all_items} if pl_ else None
        Sg, _ = scenario(cfg, "full", all_items, H, ratio=glass, plus=pp)
        Sbal = S20 if pl_ == 0 else SP[pl_]
        if Sg["clear"] < Sbal["clear"] - 0.05:
            verdict = "함정(클리어 ↓): 누진 사망 비용·에너지 상한·부활 무적 중 보스 피해 ×%.2f 이 '죽으며 깎기'를 벌한다" % cfg["combat"]["revive_invuln_boss_dmg_mult"]
        elif Sg["final"] <= Sbal["final"] * 1.01:
            verdict = "클리어는 되지만 기록 이득 없음(최종 레벨 ≤ 균형) — 함정 라벨은 +5 까지, +10 은 '손해 없는 취향'"
        else:
            verdict = "주의: 이 강화 단계에서는 균형보다 기록이 높다"
        print(f"공격 몰빵(0.5:3:0.5:0, 유리대포 함정) 풀장비 +{pl_} 20보스 판: 클리어 {Sg['clear']*100:.0f}% 사망 {Sg['deaths']:.2f} 판 {Sg['time']/60:.1f}분 최종 {fmt_big(Sg['final'])} 에너지 잔여 {Sg['energy_left']:.0f} | "
              f"균형 +{pl_}: 클리어 {Sbal['clear']*100:.0f}% 사망 {Sbal['deaths']:.2f} 최종 {fmt_big(Sbal['final'])} — {verdict}")
    St, _ = scenario(cfg, "main", all_items, H, ratio={"hp": 1.5, "atk": 1.5, "luk": 0.0, "ls": 1.0})
    print(f"행운 0 탱커(1.5:1.5:0:1, 함정) 풀장비 가운데 길: 클리어 {St['clear_main']*100:.0f}% 사망 {St['deaths']:.2f} 판 {St['time']/60:.1f}분 — 치명 5%·당첨 0·(PvP)회피 하한만 → 행운 10~17% 가 최적(한계 효용)")
    print("\nM-2 흡혈 무한 생존 시도: 흡혈 극대(0.5:1:0:2.5 + 송곳니·성배 +10) vs 균형, 권장 레벨에서 보스 단독 100회 — 초당 회복(최대체력 %) vs 초당 피격")
    print("| 보스 | 빌드 | 흡혈률 | 초당 회복 상한 | 실측 회복/초 | 실측 피격/초 | 승률 | 사망 | 초 |")
    print("|---|---|---|---|---|---|---|---|---|")
    ls_ratio = {"hp": 0.5, "atk": 1.0, "luk": 0.0, "ls": 2.5}
    for bid in ("B09", "B15", "B17", "B20"):
        b = cfg["bosses"][bid]
        for name, ratio, plus in (("흡혈 극대", ls_ratio, {"I03": 10, "I17": 10}), ("균형", cfg["builds"]["균형(기본)"], None)):
            eq = auto_equip(cfg, all_items)
            if name == "흡혈 극대":
                eq = [i for i in eq if cfg["items"][i]["slot"] != "반지"] + ["I03", "I17"]
            g = aggregate(cfg, eq, plus)
            heals, dmgs, wins, deaths, secs = [], [], 0, 0, []
            for i in range(100):
                rnd = random.Random(900 + i)
                pl = Player(cfg, g, ratio)
                feed_exp(pl, curve.E(b["recommended_level"]))
                pl.hp = pl.maxhp()
                rs = RunState(cfg, rnd, 999, unlimited=True)
                res = combat(rs, pl, None, b, False, True)
                heals.append(res["heal_ps"] / pl.maxhp()); dmgs.append(res["dmg_ps"] / pl.maxhp()); wins += res["won"]; deaths += res["deaths"]; secs.append(res["secs"])
            ls_eff = pl.ls() * b["gimmick"].get("player_ls_mult", 1.0)
            print(f"| {bid} {b['name_ko']} | {name} | {pl.ls()*100:.1f}% | {pl.heal_cap_per_s(ls_eff)*100:.1f}%/s | {st.mean(heals)*100:.1f}%/s | {st.mean(dmgs)*100:.1f}%/s | {wins}% | {deaths/100:.2f} | {st.median(secs):.1f} |")
    print("\nM-3 공속 중첩: 정령 1칸 + 질풍의 반지 + 질풍검/파멸의 대검 — S 합과 배율(상한 PvE %.1f / PvP %.1f, 피버 ×%.1f 절대 상한 %.1f)" % (cfg["caps"]["pve"]["aspd_mult"], cfg["caps"]["pvp"]["aspd_mult"], cfg["combat"]["fever_aspd"], cfg["formulas"]["aspd"]["fever_abs_cap"]))
    for combo in (["I02"], ["I12"], ["I12", "I11"], ["I12", "I11", "I15"], ["I20", "I11", "I15"], ["I10", "I12", "I11"]):
        for pl in (0, 10):
            g = aggregate(cfg, combo, {i: pl for i in combo})
            p_ = Player(cfg, g)
            print(f"  {'+'.join(cfg['items'][i]['name_ko'] for i in combo)} +{pl}: S={g['S']:.2f} → 공속 ×{p_.aspd():.2f} (간격 {p_.interval():.2f}초, 피버 중 {max(cfg['combat']['attack_interval']/cfg['formulas']['aspd']['fever_abs_cap'], p_.interval()/cfg['combat']['fever_aspd']):.2f}초)")
    up = cfg["stones"]["upgrade_mult_per_plus"]
    print(f"\nM-4 강화 복리: up 값 ×{up}^p → +5 ×{up**5:.2f}, +10 ×{up**10:.2f} (선형 아님, 그러나 합산 상한에 걸림). 풀 +10 20보스 판 최단 보스전 {min(r['secs_min'] for r in SP[10]['rows'] if r['reach']>0):.1f}초(목표 ≥10), 중간값 최단 {min(r['secs'] for r in SP[10]['rows'] if r['reach']>0):.1f}초")
    g0, g10 = aggregate(cfg, base_eq), aggregate(cfg, base_eq, {i: 10 for i in base_eq})
    print(f"  풀장비 합산: 공격 배율 {g0['atk_mult']:.2f}→{g10['atk_mult']:.2f} (상한 {cfg['caps']['pve']['atk_mult']}), 공속 S {g0['S']:.2f}→{g10['S']:.2f}, 흡혈 +{g0['ls']*100:.1f}→{g10['ls']*100:.1f}%p (상한 {cfg['caps']['pve']['lifesteal']*100:.0f}%), 경험치 ×{g0['exp_mult']:.2f}→{g10['exp_mult']:.2f} (상한 {cfg['caps']['pve']['exp_mult']}), 보스 경험치 ×{g0['boss_exp_mult']:.2f} (상한 {cfg['caps']['pve']['boss_exp_mult']}), 피해감소 {g0['dmg_reduce']*100:.0f}→{g10['dmg_reduce']*100:.0f}%")
    # N. 숨은 보스 조건 달성률
    print("\n### N. 조건부 보스 등장률 (수동) — 자연 장비 / 풀장비 +0 / 풀장비 +5 / 자동 모험(풀장비)")
    print("| 보스 | 조건 | 자연 | 풀 +0 | 풀 +5 | 자동 모험 |")
    print("|---|---|---|---|---|---|")
    for bid, b in cfg["bosses"].items():
        c = b.get("spawn_condition")
        if not c:
            continue
        cells = [f"{nat_rows[bid]['spawn']*100:.0f}%"]
        for S_ in (S20, SP[5], Sa):
            r = [x for x in S_["rows"] if x["boss"] == bid][0]
            cells.append(f"{r['spawn']*100:.0f}%" if r["reach"] > 0 else "-")
        print(f"| {bid} {b['name_ko']} | {c['text_ko']} | " + " | ".join(cells) + " |")
    # O. 계정 성장
    print("\n### O. 계정 성장 시뮬 (첫 계정 → 매 판 드롭·강화석·정수 → 탐욕 강화, 하루 = 판 5회 + 자동 모험 무료 3회) — 3시드")
    print("| 시드 | 자동 모험 | 처음 10보스 (판/분) | 처음 20보스 (판/분) | 장착 7종 전부 +5 (판/분) | 전부 +10 (판/분) | 끝 +단계 |")
    print("|---|---|---|---|---|---|---|")
    acc = {}
    for pass_auto in (False, True):
        for seed in (1, 2, 3):
            o = account_growth(cfg, seed, max_runs=60 if quick else 120, pass_auto=pass_auto)
            acc.setdefault(pass_auto, []).append(o)
            fm = lambda a, b: f"{a}/{b}" if a else "-"
            print(f"| {seed} | {'패스 6회' if pass_auto else '무료 3회'} | {fm(o['first10'], o['t10'])} | {fm(o['first20'], o['t20'])} | {fm(o['all_plus5'], o['t5'])} | {fm(o['all_plus10'], o['tp10'])} | {','.join(str(v) for v in o['plus'].values())} |")
    def medk(lst, k):
        v = [o[k] for o in lst if o[k]]
        return st.median(v) if v else None
    a0, a1 = acc[False], acc[True]
    print(f"중간값: 무료 — 10보스 {medk(a0,'first10')}판/{medk(a0,'t10')}분, 20보스 {medk(a0,'first20')}판/{medk(a0,'t20')}분, 전부 +5 {medk(a0,'all_plus5')}판, 전부 +10 {medk(a0,'all_plus10')}판/{medk(a0,'tp10')}분 ; "
          f"패스 — 20보스 {medk(a1,'first20')}판, 전부 +5 {medk(a1,'all_plus5')}판, 전부 +10 {medk(a1,'all_plus10')}판/{medk(a1,'tp10')}분")
    # P. 보스 러시
    print("\n### P. 보스 러시 타임어택 (결투 레벨 %s 고정, 장비만, 사망 +%d초) — 20보스 합계 중간값" % (fmt_big(cfg["boss_rush"]["level"]), cfg["boss_rush"]["death_penalty_s"]))
    for pl in (0, 5, 10):
        tot, per = boss_rush(cfg, all_items, {i: pl for i in all_items}, n=20)
        print(f"  풀장비 +{pl}: 합계 {tot:.0f}초 ({tot/60:.1f}분), 보스별 {' '.join(f'{v:.0f}' for v in per.values())}")
    # Q. 워프 판
    Sw10, Rw10 = scenario(cfg, "right", all_items, H, start="plaza10")
    print_summary(cfg, "Q. 워프 제단 판 — 10단계 광장에서 시작(군단 루프만), 풀장비 (해금: 황제 드래곤 3회 처치; 기록판 '워프 판' 표식; 재처치 강화석 ×%.1f·보너스 없음·일 %d회)" % (cfg["run"]["warp"]["repeat_stone_mult"], cfg["run"]["warp"]["daily_limit"]), Sw10)
    # Q-2 워프 농사 효율 (K2-4): 분당 4급 강화석·정수, 마을 20보스 판과 비교
    print("\n### Q-2. 강화석 농사 효율 — 마을 20보스 판 vs 워프 판(10단계 광장 → 군단 5보스), 풀장비 +0 / +10, 분당 4급 강화석·정수")
    print("| 판 | 강화 | 판 시간(분) | 4급 강화석/판 | 4급/분 | 정수/판 | 정수/분 |")
    print("|---|---|---|---|---|---|---|")
    warp_eff = {}
    for label, plan_, start_ in (("마을 20보스(E-2)", "full", "village"), ("워프 plaza10 → 군단 5보스(Q)", "right", "plaza10")):
        for pl_ in (0, 10):
            pp = {i: pl_ for i in all_items} if pl_ else None
            Sx, Rx = scenario(cfg, plan_, all_items, H, plus=pp, start=start_)
            t4 = st.mean(r["stones"]["4"] for r in Rx)
            es = st.mean(sum(r["essence"].values()) for r in Rx)
            tm = Sx["time"] / 60
            warp_eff[(label, pl_)] = t4 / tm
            print(f"| {label} | +{pl_} | {tm:.1f} | {t4:.1f} | {t4/tm:.2f} | {es:.1f} | {es/tm:.2f} |")
    print(f"워프 판 분당 4급 강화석 / 마을 판 = ×{warp_eff[('워프 plaza10 → 군단 5보스(Q)', 10)]/warp_eff[('마을 20보스(E-2)', 10)]:.2f} (+10 기준, 목표 ≤1.3 — 여기에 일 {cfg['run']['warp']['daily_limit']}회 제한)")
    # R. MVP (K3-2): 가운데 1~5구간만 (기존 v8 자산 5보스)
    cfg_m = json.loads(json.dumps(cfg))
    cfg_m["routes"]["main"]["stages"] = cfg_m["routes"]["main"]["stages"][:5]
    five = [cfg_m["bosses"][s["boss"]]["drop_item"] for s in cfg_m["routes"]["main"]["stages"]]
    print("\n### R. MVP 검증 — 가운데 1~5구간만(보스 5·아이템 5·기믹 7키, 신규 모델 0), 피버 OFF")
    print("| 보유 아이템 | 5보스 클리어 | 평균 처치 | 판 시간(분) | 사망 | 중간 최종 레벨 | B02 처치 | B03 처치 | 에너지 잔여(중간) |")
    print("|---|---|---|---|---|---|---|---|---|")
    mvp_rows = {}
    for k in (0, 1, 2, 3, 5):
        Sm, _ = scenario(cfg_m, "main", five[:k], H, fever=False)
        mvp_rows[k] = Sm
        print(f"| {k}개 | {Sm['clear']*100:.0f}% | {Sm['bosses']:.2f} | {Sm['time']/60:.1f} | {Sm['deaths']:.2f} | {fmt_big(Sm['final'])} | {Sm['rows'][1]['kill']*100:.0f}% | {Sm['rows'][2]['kill']*100:.0f}% | {Sm['energy_left']:.0f} |")
    # 핵심 요약
    print("\n### 핵심 수치 요약")
    first = S0["rows"][0]
    nat_secs = [r["secs"] for r in nat_rows.values() if r["reach"] > 0 and r["spawn"] > 0]
    nat_deaths = [r["deaths"] for r in nat_rows.values() if r["reach"] > 0 and r["spawn"] > 0]
    f10 = [r["secs"] for r in SP[10]["rows"] if r["reach"] > 0 and r["spawn"] > 0]
    nat_kill = [r["kill"] for r in nat_rows.values() if r["reach"] > 0 and r["spawn"] > 0]
    nat_go = [r["gameover"] for r in nat_rows.values() if r["reach"] > 0 and r["spawn"] > 0]
    print(f"first_run_minutes={S0['time']/60:.2f} first_boss_win_no_gear={first['win']:.3f} first_boss_deaths={first['deaths']:.2f} first_boss_secs={first['secs']:.1f} "
          f"second_boss_reach={S0['rows'][1]['reach']:.2f} second_boss_kill={S0['rows'][1]['kill']:.2f} third_boss_enter={S0['rows'][2]['enter']:.2f} third_boss_kill={S0['rows'][2]['kill']:.2f} "
          f"first_run_deaths={S0['deaths']:.2f} first_run_boss_gameover={S0['boss_gameover']:.2f} first_run_after_fight_win_end={S0['ends'].get('after_fight_win', 0):.2f} "
          f"first_run_capped={S0['capped']:.2f} fever_off_second_boss_kill={S0f['rows'][1]['kill']:.2f} "
          f"full_clear_main_minutes={S20m['time_clear']/60:.2f} full_clear_20_minutes={S20['time_clear']/60:.2f} "
          f"clear20_full_gear={S20['clear']:.2f} final_level_full20={int(S20['final'])} energy_left_full20={S20['energy_left']:.0f} natural_secs={min(nat_secs):.1f}~{max(nat_secs):.1f} "
          f"natural_deaths={min(nat_deaths):.2f}~{max(nat_deaths):.2f} natural_kill={min(nat_kill):.2f}~{max(nat_kill):.2f} natural_gameover_max={max(nat_go):.2f} "
          f"plus10_min_secs={min(f10):.1f} fever_per_run={S20m['fever']:.1f} "
          f"plus10_abs_min_secs={min(r['secs_min'] for r in SP[10]['rows'] if r['reach'] > 0 and r['spawn'] > 0):.1f} "
          f"tank_clear_main={build_rows['탱커'][0]['clear_main']:.2f} tank_clear_20={build_rows['탱커'][1]['clear']:.2f} "
          f"ls_deaths_main={build_rows['흡혈 균형'][0]['deaths']:.2f} bal_deaths_main={build_rows['균형(기본)'][0]['deaths']:.2f} "
          f"ls_deaths_20={build_rows['흡혈 균형'][1]['deaths']:.2f} bal_deaths_20={build_rows['균형(기본)'][1]['deaths']:.2f} "
          f"pvp_pair_range={pvp_range[0]*100:.0f}~{pvp_range[1]*100:.0f}% pvp_asym_range={asym[0]*100:.0f}~{asym[1]*100:.0f}% max_hit_taken={max(S0['max_hit'], S20['max_hit'])*100:.0f}% "
          f"glass10_clear={Sg['clear']:.2f} glass10_final_ratio={Sg['final']/SP[10]['final']:.2f} warp_stone_ratio={warp_eff[('워프 plaza10 → 군단 5보스(Q)', 10)]/warp_eff[('마을 20보스(E-2)', 10)]:.2f} "
          f"mvp5_clear_5items={mvp_rows[5]['clear']:.2f} mvp5_minutes_0items={mvp_rows[0]['time']/60:.2f}")
    print(f"(소요 {time.time()-t0:.0f}초)")


def quick_scenario(cfg, args):
    all_items = list(cfg["items"].keys())
    if args.gear in (None, "full"):
        owned = all_items
    elif args.gear == "none":
        owned = []
    elif args.gear == "partial":
        owned = route_items(cfg, "main")
    else:
        owned = [x.strip() for x in args.gear.split(",") if x.strip()]
    ratio = cfg["builds"][BUILD_ALIAS[args.build]] if args.build else None
    plus = {i: args.plus for i in all_items} if args.plus else None
    S, R = scenario(cfg, args.plan, owned, args.runs, plus=plus, manual=not args.auto, ratio=ratio, seed0=args.seed,
                    start=args.start, fever=(args.fever != "off"))
    title = f"시나리오: gear={args.gear or 'full'} build={args.build or 'auto'} plus={args.plus} plan={args.plan} start={args.start} fever={args.fever} auto={args.auto} runs={args.runs} seed={args.seed}"
    print_summary(cfg, title, S)
    r0 = R[0]
    print(f"판 끝 능력치(1번 판): 레벨 {fmt_big(r0['final_lvl'])} 공격 {fmt_big(r0['atk'])} 체력 {fmt_big(r0['hp'])} 치명 {r0['crit']*100:.0f}% 흡혈 {r0['ls']*100:.1f}% 공속 ×{r0['aspd']:.2f}")
    print("단계별 중간 레벨(진입→퇴장): " + " / ".join(f"{sl['route'][0]}{sl['stage']}:{fmt_big(sl['lvl_in'])}→{fmt_big(sl['lvl_out'])}" for sl in R[0]["stage_log"]))
    print("판 소요 초(중간) %.0f, 에너지 잔여(중간/최소) %s/%s, 보스전 도중 게임오버 %.0f%%" % (S["time"], S["energy_left"], S["energy_min"], S["boss_gameover"] * 100))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=200)
    ap.add_argument("--report", default=None, choices=["all", "quick", "none"], help="all=전체 보고서, quick=핵심 표만(C·K·L 표 판 수 절반), none=시나리오만. 생략하면 --gear/--build 등 시나리오 옵션이 있을 때 none, 없을 때 all")
    ap.add_argument("--quick", action="store_true", help="--report quick 과 같음")
    ap.add_argument("--config", default=CFG_PATH)
    ap.add_argument("--gear", default=None)
    ap.add_argument("--build", default=None, choices=list(BUILD_ALIAS.keys()))
    ap.add_argument("--plus", type=int, default=0)
    ap.add_argument("--plan", default="full", choices=["main", "left", "right", "full"])
    ap.add_argument("--auto", action="store_true")
    ap.add_argument("--start", default="village", choices=["village", "plaza5", "plaza10"])
    ap.add_argument("--fever", default="on", choices=["on", "off"])
    ap.add_argument("--seed", type=int, default=1000)
    ap.add_argument("--pvp", action="store_true", help="PvP 미러 매치 표만")
    args = ap.parse_args()
    cfg = load_config(args.config)
    if args.pvp:
        builds = list(cfg["builds"].items())
        print("| 빌드 \\ 상대 | " + " | ".join(b for b, _ in builds) + " |")
        for n1, r1 in builds:
            cells = []
            for n2, r2 in builds:
                w, s_ = pvp_duel(cfg, r1, r2, list(cfg["items"].keys()), args.runs)
                cells.append(f"{w*100:.0f}%({s_:.0f}s)")
            print(f"| {n1} | " + " | ".join(cells) + " |")
        return
    scenario_flags = args.gear is not None or args.build is not None or args.plus or args.auto or args.start != "village" or args.fever == "off"
    report = args.report or ("none" if scenario_flags else "all")
    if args.quick and report == "all":
        report = "quick"
    if scenario_flags:
        quick_scenario(cfg, args)
    if report != "none":
        full_report(cfg, args.runs, report == "quick")


if __name__ == "__main__":
    main()
