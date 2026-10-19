"""
Baseline simulator for 레벨 폭발 모험단 v8 (PDF numbers as-is).
Purpose: measure where the CURRENT design lands (level per stage, boss fight seconds,
death points) so the 20-boss redesign starts from facts, not guesses.
Model: discrete-time duel. Player auto-attacks every ATK_INT (1.1s v7). Monster attacks
every 1.3s (boss 1.7s), first attack 1.2s after spawn. Damage per PDF formulas.
"""
import random, math, statistics as st

random.seed(1)

# ---- v7/v8 player model ----
BASE = dict(hp=100, atk=10, luk=1, ls=0.0)
PER  = dict(hp=10,  atk=2,  luk=1, ls=0.001)   # per point ; ls = +0.001 (=0.1%?) PDF says +0.001%
AUTO = dict(hp=1, atk=2, luk=0.5, ls=0.5)      # auto distribute ratio (sum 4)
PTS_PER_LVL = 3
ATK_INT = 1.1   # v7: auto attack 1.1s
MON_INT = 1.3
BOSS_INT = 1.7
FIRST_HIT = 1.2

def crit_p(luk, lvl):
    return 0.08 + 0.22 * luk / (luk + 0.5*lvl + 20)

def luck_bonus_pts(luk, lvl):
    p = min(0.5, 0.5*luk/(luk + lvl*0.5 + 20))
    k = 1 + math.floor(math.log2(1 + luk/50))
    return p, k

class Player:
    def __init__(self, weapon=0, aspd=1.0, ls_gear=0.0, lvl_mult=1.0, rng_mult=1.0):
        self.lvl = 1; self.pts = {k:0.0 for k in BASE}
        self.weapon = weapon; self.aspd = aspd; self.ls_gear = ls_gear
        self.lvl_mult = lvl_mult
        self.hp = self.maxhp()
    def stat(self,k): return BASE[k] + PER[k]*self.pts[k]
    def maxhp(self): return self.stat('hp')
    def atk(self): return self.stat('atk') + self.weapon
    def luk(self): return self.stat('luk')
    def lifesteal(self): return self.stat('ls')/100.0 + self.ls_gear   # PDF: +0.001% per pt
    def gain_levels(self, n):
        n = int(n * self.lvl_mult)
        # luck bonus points (expected value if >60 levels)
        p,k = luck_bonus_pts(self.luk(), self.lvl)
        pts = n*PTS_PER_LVL + n*p*k
        self.lvl += n
        tot = sum(AUTO.values())
        for k_ in AUTO: self.pts[k_] += pts*AUTO[k_]/tot
        self.hp = min(self.maxhp(), self.hp + (self.maxhp()-self.hp)) # heal by growth (approx full)

def duel(p, mon, boss=False, mhp=None):
    """returns (won, seconds, hp_left_frac, mhp_left)"""
    mhp = mon['hp'] if mhp is None else mhp; t=0.0
    p_next = 0.0; m_next = FIRST_HIT
    interval = ATK_INT / p.aspd
    m_int = BOSS_INT if boss else MON_INT
    while t < 600:
        # player attack
        if p_next <= m_next:
            t = p_next
            crit = random.random() < crit_p(p.luk(), p.lvl)
            dmg = math.floor(p.atk()*random.uniform(0.9,1.1)*(2 if crit else 1))
            dmg = max(1,dmg)
            mhp -= dmg
            p.hp = min(p.maxhp(), p.hp + dmg*p.lifesteal())
            if mhp <= 0: return True, t, p.hp/p.maxhp(), 0
            p_next += interval
        else:
            t = m_next
            taken = max(1, math.floor(mon['atk']*random.uniform(0.9,1.1)))
            p.hp -= taken
            if p.hp <= 0: return False, t, 0.0, mhp
            m_next += m_int
    return False, t, p.hp/p.maxhp(), mhp

# v8 monsters
MON = {
 1: [dict(id='penguin',lvl=30,hp=30,atk=15), dict(id='jelly',lvl=40,hp=45,atk=25), dict(id='firewolf',lvl=80,hp=90,atk=60)],
 2: [dict(id='deer',lvl=300,hp=2000,atk=20000), dict(id='unicorn',lvl=500,hp=3500,atk=30000), dict(id='icewolf',lvl=800,hp=6000,atk=45000)],
 3: [dict(id='golem',lvl=3000,hp=80000,atk=300000), dict(id='lavagolem',lvl=5000,hp=140000,atk=450000), dict(id='hellhound',lvl=8000,hp=200000,atk=650000)],
 4: [dict(id='hellboar',lvl=30000,hp=3e6,atk=1.5e6), dict(id='balrog',lvl=50000,hp=5e6,atk=2.2e6), dict(id='cerberus',lvl=80000,hp=8e6,atk=3.2e6)],
 5: [dict(id='giant',lvl=300000,hp=4e7,atk=1e7), dict(id='sage',lvl=500000,hp=7e7,atk=1.5e7), dict(id='gumiho',lvl=800000,hp=1e8,atk=2.2e7)],
}
BOSS = {
 1: dict(id='mammoth',lvl=2000,hp=20000,atk=6000),
 2: dict(id='leopard',lvl=20000,hp=300000,atk=90000),
 3: dict(id='dragon',lvl=200000,hp=5e6,atk=1e6),
 4: dict(id='griffon',lvl=2e6,hp=6e7,atk=6e6),
 5: dict(id='bluedragon',lvl=2e7,hp=1.5e9,atk=4e7),
}
BOSS_GEAR = {1:dict(weapon=10000), 2:dict(aspd=2.0), 3:dict(ls_gear=0.03), 4:dict(), 5:dict(lvl_mult=2.0)}

def run(gear_from_bosses=0, verbose=False):
    kw = {}
    for b in range(1, gear_from_bosses+1): kw.update(BOSS_GEAR[b])
    p = Player(**kw)
    energy = 12; stage=1; fights=0; deaths=0; log=[]
    intro = 3
    while energy>0 and stage<=5:
        # fights until boss: assume ~4 encounters per stage (walk length 265 stud / gauge)
        for f in range(4):
            if energy<=0: break
            if stage==1 and intro>0:
                mons=[MON[1][0]]; intro-=1
            else:
                n = random.choices([1,2,3],[35,45,20])[0]
                mons=[random.choice(MON[stage]) for _ in range(n)]
            p.hp = p.maxhp()
            won_all=True
            for m in mons:
                w,t,_,_=duel(p,m)
                if not w: won_all=False; break
                p.gain_levels(m['lvl'])
            if won_all: energy-=1; fights+=1
            else: energy-=3; deaths+=1; p.hp=p.maxhp()
        if energy<=0: break
        # boss
        b=BOSS[stage]; p.hp=p.maxhp(); mhp=None; lives=0; ttot=0.0; arrive=p.lvl
        while True:
            w,t,hpf,mhp=duel(p,b,boss=True,mhp=mhp)
            ttot+=t; 
            if w: break
            energy-=3; deaths+=1; lives+=1; p.hp=p.maxhp()
            # after revive: 2.5s invuln -> player gets ~2 free swings; approximate by extra damage
            if energy<=0: break
            free=int(2.5/(ATK_INT/p.aspd))
            mhp-=free*p.atk()
            if mhp<=0: w=True; break
        log.append((stage,arrive,int(p.atk()),int(p.maxhp()),w,round(ttot,1),lives))
        if w: energy+=4; p.gain_levels(b['lvl']); stage+=1
        else: break
    return dict(final_lvl=p.lvl, stage=stage-1, deaths=deaths, energy=energy, log=log)

for gear in range(0,6):
    res=[run(gear) for _ in range(200)]
    print(f"\n== gear from bosses 1..{gear} ==")
    print(" cleared stages dist:", {s: sum(1 for r in res if r['stage']==s) for s in range(0,6)})
    print(" median final lvl:", int(st.median(r['final_lvl'] for r in res)), " mean deaths:", round(st.mean(r['deaths'] for r in res),2))
    # boss fight seconds per stage (wins only)
    for s in range(1,6):
        ts=[e[5] for r in res for e in r['log'] if e[0]==s and e[4]]
        ls=[e[1] for r in res for e in r['log'] if e[0]==s]
        lv=[e[6] for r in res for e in r['log'] if e[0]==s and e[4]]
        if ls: print(f"  stage{s} boss: arrive lvl med {int(st.median(ls))}, win rate {len(ts)/len(ls):.2f}, win secs med {st.median(ts) if ts else '-'}, deaths-to-win med {st.median(lv) if lv else '-'}")
