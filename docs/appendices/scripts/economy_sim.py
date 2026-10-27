#!/usr/bin/env python3
"""
Deepforge economy simulator: design-time pacing and fairness model.

Companion to docs/04-economy-and-progression.md and docs/appendices/D-economy-simulation.md.
Pure Python 3.10+ standard library; no third-party packages.

    python3 docs/appendices/scripts/economy_sim.py            # summary report
    python3 docs/appendices/scripts/economy_sim.py --tables   # generated content tables (Markdown)
    python3 docs/appendices/scripts/economy_sim.py --check    # exit 1 if any pacing/fairness target fails
    python3 docs/appendices/scripts/economy_sim.py --seeds 20 # average over more seeds

The model is deliberately coarse. It steps per session, uses expected values for
mining, and seeded random rolls for assay grades and geodes. It answers questions such as
"when does an engaged player craft the Bronze Pick?" or "does a top spender outpace a
free player by more than the fairness cap?". It does not predict exact numbers.

Every constant below mirrors a table in docs/04 or docs/appendices/B. Change both together;
the content compiler (docs/15) will eventually generate these from the same source files.
"""
from __future__ import annotations

import argparse
import math
import random
import statistics
import sys
from dataclasses import dataclass, field

# --------------------------------------------------------------------------------------
# Calendar
# --------------------------------------------------------------------------------------
ERA2_OPEN_DAY = 15          # realm-wide Era II unlock (earliest); realm age in days, 1-indexed
ERA3_TARGET_DAY = 91        # first post-launch Era (content runway target)
WAKING_HOURS = 15.0         # sessions are spread over 08:00-23:00 local time
RICHNESS_DROP = 0.10        # per delve on the same site
RICHNESS_FLOOR = 0.25
RICHNESS_REGEN_PER_H = 0.05

# --------------------------------------------------------------------------------------
# Sites (docs/appendices/B §B.3)
# --------------------------------------------------------------------------------------
SITES = {
    "copperhollow": dict(era=1, min_level=1, min_hh=1, stone_hp=20, stone_tiles=10, move=16,
                         combat_base=10, power_req=10, ore_tiles=6,
                         mix={"cu": 0.80, "coal": 0.15, "quartz": 0.05},
                         coins_floor=12, xp_floor=25, geode_rate=0.0025, star_per_floor=0.0),
    "emberseam":    dict(era=1, min_level=8, min_hh=4, stone_hp=25, stone_tiles=10, move=16,
                         combat_base=10, power_req=16, ore_tiles=6,
                         mix={"coal": 0.55, "quartz": 0.30, "cu": 0.15},
                         coins_floor=15, xp_floor=32, geode_rate=0.0030, star_per_floor=0.0),
    "tinreach":     dict(era=2, min_level=20, min_hh=8, stone_hp=30, stone_tiles=11, move=16,
                         combat_base=12, power_req=30, ore_tiles=7,
                         mix={"sn": 0.75, "cu": 0.15, "quartz": 0.10},
                         coins_floor=30, xp_floor=45, geode_rate=0.0040, star_per_floor=0.08),
}
ORE_HP = {"cu": 30, "coal": 25, "quartz": 50, "sn": 40}
STARSTONE_HP = 120

# --------------------------------------------------------------------------------------
# Gear (docs/appendices/B §B.5)
# --------------------------------------------------------------------------------------
PICKS = [  # name, mining power (MPW), tier value for Power Score
    ("Rusty Pick", 8, 0), ("Copper Pick", 12, 30), ("Bronze Pick", 18, 70), ("Starstone Pick", 22, 110)]
LAMPS = [("Rusty Lamp", 180, 0), ("Copper Lamp", 220, 30), ("Bronze Lamp", 260, 70)]
KITS = [("No Kit", 0, 0), ("Copper Kit", 1, 30), ("Bronze Kit", 2, 70), ("Starstone Kit", 3, 110)]

# Material cost keys: cu_comp/cu_asm/br_comp/br_asm are merge products (9/27 ingots each).
RECIPES = {
    ("pick", 1): dict(cost={"cu_comp": 2, "stone": 20, "coins": 300}, hh=2, era=1),
    ("lamp", 1): dict(cost={"cu_comp": 1, "quartz": 3, "coins": 200}, hh=3, era=1),
    ("kit", 1):  dict(cost={"cu_comp": 3, "coins": 400}, hh=3, era=1),
    ("pick", 2): dict(cost={"br_asm": 3, "cu_asm": 2, "quartz": 12, "coins": 3000}, hh=8, era=2),
    ("lamp", 2): dict(cost={"br_asm": 2, "quartz": 20, "coins": 2500}, hh=9, era=2),
    ("kit", 2):  dict(cost={"br_asm": 4, "coins": 4000}, hh=9, era=2),
    ("pick", 3): dict(cost={"star": 12, "br_asm": 3, "coins": 8000}, hh=12, era=2),
    ("kit", 3):  dict(cost={"star": 16, "br_asm": 4, "coins": 10000}, hh=13, era=2),
}
MERGE_FEE = {"fitting": 5, "comp": 15, "asm": 60}           # coins per merge operation
COMP_COINS = 3 * MERGE_FEE["fitting"] + MERGE_FEE["comp"]   # 30 coins per component
ASM_COINS = 3 * COMP_COINS + MERGE_FEE["asm"]               # 150 coins per assembly

def enhance_cost(slot_tier: int, n: int) -> dict:
    """Cost to go from +n to +n+1. Fittings of the slot's metal; never fails."""
    metal = "cu_fit" if slot_tier <= 1 else "br_fit"
    return {metal: math.ceil(2 * 1.35 ** n), "coins": round(40 * (1 + slot_tier) * 1.4 ** n / 10) * 10}

# --------------------------------------------------------------------------------------
# Buildings (docs/appendices/B §B.6)
# --------------------------------------------------------------------------------------
HH_MINUTES = {2: 5, 3: 15, 4: 30, 5: 60, 6: 120, 7: 180, 8: 300, 9: 480, 10: 720,
              11: 960, 12: 1200, 13: 1440, 14: 1680, 15: 1920}
HH_MAX = 15

def hh_cost(level: int) -> dict:
    """Homestead Hall upgrade cost to reach `level` (2..15)."""
    c = {"coins": round(250 * 1.42 ** (level - 2) / 10) * 10,
         "stone": round(30 * (level - 1) ** 1.5)}
    if level <= 8:
        c["cu_comp"] = max(1, level - 2)
    else:
        c["cu_comp"] = 4
        c["br_comp"] = 3 * (level - 8)
    return c

def smelter_cost(level: int) -> dict:
    c = {"coins": round(150 * 1.5 ** (level - 2) / 10) * 10}
    if level <= 7:
        c["cu_comp"] = math.ceil(level / 2)
    else:
        c["br_comp"] = 2 * (level - 6)
    return c

def smelter_minutes(level: int) -> int:
    return max(5, HH_MINUTES[level] // 2)

def smelter_slots(level: int) -> int:
    return 1 + (level >= 4) + (level >= 8)

def smelter_batch(level: int) -> int:
    return 20 + 10 * (level - 1)

def smelt_minutes(level: int, alloy: bool) -> float:
    return (6.0 if alloy else 3.0) * 0.94 ** (level - 1)

CREW_SLOTS_BY_HH = [(13, 8), (11, 7), (9, 6), (7, 5), (5, 4), (3, 3), (1, 2)]
def crew_slots(hh: int) -> int:
    return next(s for lvl, s in CREW_SLOTS_BY_HH if hh >= lvl)

def crew_hire_cost(k: int) -> int:
    """Coins to hire the k-th crew member (k >= 3; the first two come with the tutorial)."""
    return round(200 * 1.6 ** (k - 3) / 10) * 10

COPPER_RESERVE = 60        # player habit modelled: keep copper ingots for Hall costs
BRONZE_STOCK_TARGET = 600
CREW_RATE_PER_H = 1.0      # ore units per crew-hour (surface ore: grade C, no assay)
CREW_COAL_PER_H = 0.6
OFFLINE_CAP_H = 12.0

# --------------------------------------------------------------------------------------
# Character progression
# --------------------------------------------------------------------------------------
LEVEL_CAP = {1: 20, 2: 40}

def xp_to_next(level: int) -> int:
    return round(17 * level ** 1.7 / 5) * 5

def mining_level(chunks_mined: int) -> int:
    return min(50, int(math.sqrt(chunks_mined / 10)))

GRADES = [("C", 0.60, 1), ("B", 0.30, 1), ("A", 0.09, 2), ("S", 0.01, 3)]  # name, p, ore units
ASSAY_FEE = 1              # coins per chunk
GEODE_PITY = 250           # guaranteed geode after this many chunks without one
GEODE_TABLE = [("gem", 0.70), ("relic", 0.25), ("star", 0.05)]

# --------------------------------------------------------------------------------------
# Monetization (docs/07): Aurum is premium currency; nothing below is randomized.
# --------------------------------------------------------------------------------------
HASTEN_AURUM_PER_MIN = 1
HASTEN_DAILY_CAP_MIN = 480
SEASON_DAYS = 42
PASS_FREE = dict(coins=5000, comps=4)
PASS_PREMIUM = dict(coins=6000, comps=8, aurum=600)
CRATE = dict(comps=2, coins=500)       # "Supply Crate", fixed contents, max 2 per week
MEMBERSHIP_AURUM_PER_DAY = 30


@dataclass
class Archetype:
    name: str
    delves: int
    sessions: int
    obj_coins: int
    obj_xp: int
    membership: bool = False
    premium_pass: bool = False
    crates_per_week: int = 0
    aurum_per_week: int = 0          # extra Aurum purchased weekly
    unlimited_aurum: bool = False    # whale: always buys enough to hit the Hasten cap


ARCHETYPES = [
    Archetype("casual", delves=4, sessions=3, obj_coins=300, obj_xp=300),
    Archetype("engaged", delves=10, sessions=5, obj_coins=600, obj_xp=500),
    Archetype("hardcore", delves=20, sessions=8, obj_coins=600, obj_xp=500),
    Archetype("spender", delves=10, sessions=5, obj_coins=600, obj_xp=500, membership=True,
              premium_pass=True, crates_per_week=2, aurum_per_week=650),
    Archetype("whale", delves=20, sessions=8, obj_coins=600, obj_xp=500, membership=True,
              premium_pass=True, crates_per_week=2, unlimited_aurum=True),
]


@dataclass
class Player:
    arch: Archetype
    rng: random.Random
    day: int = 1
    level: int = 1
    xp: int = 0
    hh: int = 1
    smelter: int = 1
    pick: int = 0
    lamp: int = 0
    kit: int = 0
    enh: dict = field(default_factory=lambda: {"pick": 0, "lamp": 0, "kit": 0})
    crew: int = 2
    chunks_mined: int = 0
    since_geode: int = 0
    builder: tuple | None = None           # (target, level, minutes_left)
    smelt_queue: list = field(default_factory=list)   # [kind, qty] kinds: cu, sn, br
    richness: dict = field(default_factory=lambda: {s: 1.0 for s in SITES})
    inv: dict = field(default_factory=lambda: dict(
        coins=700, stone=60, coal=20, quartz=0, star=0, ore_cu=0, ore_sn=0,
        cu=27, sn=0, br=0, aurum=0, gems=0, relics=0))
    hasten_used_today: int = 0
    # telemetry
    milestones: dict = field(default_factory=dict)
    coin_src: float = 0.0
    coin_sink: float = 0.0
    coin_src_window: float = 0.0
    coin_sink_window: float = 0.0
    geodes: int = 0
    chunks_assayed: float = 0.0
    ps_by_day: dict = field(default_factory=dict)

    # ---------------------------------------------------------------- helpers
    @property
    def era(self) -> int:
        return 2 if self.day >= ERA2_OPEN_DAY else 1

    def mark(self, key: str):
        self.milestones.setdefault(key, self.day)

    def earn_coins(self, n: float):
        self.inv["coins"] += n
        self.coin_src += n
        if 8 <= self.day <= 60:
            self.coin_src_window += n

    def spend_coins(self, n: float):
        self.inv["coins"] -= n
        self.coin_sink += n
        if 8 <= self.day <= 60:
            self.coin_sink_window += n

    def player_power(self) -> int:
        return 6 + self.level + 6 * KITS[self.kit][1] + self.enh["kit"]

    def mpw(self) -> int:
        return PICKS[self.pick][1] + self.enh["pick"]

    def oil(self) -> int:
        return LAMPS[self.lamp][1] + 4 * self.enh["lamp"]

    def power_score(self) -> int:
        gear = (PICKS[self.pick][2] + LAMPS[self.lamp][2] + KITS[self.kit][2]
                + 4 * sum(self.enh.values()))
        return gear + 10 * self.hh + 5 * self.smelter + 3 * self.crew + self.level

    def site_unlocked(self, s: str) -> bool:
        d = SITES[s]
        return self.era >= d["era"] and self.level >= d["min_level"] and self.hh >= d["min_hh"]

    # ---------------------------------------------------------------- costs
    def ingot_need(self, cost: dict) -> dict:
        """Translate a cost dict into raw ingot and coin requirements."""
        need = {"cu": 0, "br": 0, "coins": cost.get("coins", 0)}
        for key, qty in cost.items():
            if key == "cu_fit":
                need["cu"] += 3 * qty; need["coins"] += MERGE_FEE["fitting"] * qty
            elif key == "br_fit":
                need["br"] += 3 * qty; need["coins"] += MERGE_FEE["fitting"] * qty
            elif key == "cu_comp":
                need["cu"] += 9 * qty; need["coins"] += COMP_COINS * qty
            elif key == "br_comp":
                need["br"] += 9 * qty; need["coins"] += COMP_COINS * qty
            elif key == "cu_asm":
                need["cu"] += 27 * qty; need["coins"] += ASM_COINS * qty
            elif key == "br_asm":
                need["br"] += 27 * qty; need["coins"] += ASM_COINS * qty
        for key in ("stone", "quartz", "star"):
            if key in cost:
                need[key] = cost[key]
        return need

    def can_afford(self, cost: dict, reserve: dict | None = None) -> bool:
        need = self.ingot_need(cost)
        res = self.ingot_need(reserve) if reserve else {}
        return all(self.inv[k] >= v + res.get(k, 0) for k, v in need.items())

    def pay(self, cost: dict):
        need = self.ingot_need(cost)
        for k, v in need.items():
            if k == "coins":
                self.spend_coins(v)
            else:
                self.inv[k] -= v

    # ---------------------------------------------------------------- time passes
    def advance(self, hours: float):
        minutes = hours * 60
        # builder
        if self.builder:
            target, lvl, left = self.builder
            left -= minutes
            if left <= 0:
                self.complete_build(target, lvl)
            else:
                self.builder = (target, lvl, left)
        # smelter: slots work in parallel through the queue
        budget = smelter_slots(self.smelter) * minutes
        for item in self.smelt_queue:
            kind, qty = item
            per = smelt_minutes(self.smelter, kind == "br")
            n = min(qty, int(budget // per))
            self.inv[kind] += n
            item[1] -= n
            budget -= n * per
        self.smelt_queue = [i for i in self.smelt_queue if i[1] > 0]
        # richness regeneration
        for s in self.richness:
            self.richness[s] = min(1.0, self.richness[s] + RICHNESS_REGEN_PER_H * hours)
        # crew shifts
        cap = OFFLINE_CAP_H + (4 if self.arch.membership else 0)
        crew_h = self.crew * min(hours, cap)
        if self.era >= 2 and self.site_unlocked("tinreach"):
            self.inv["ore_cu"] += crew_h * CREW_RATE_PER_H * 0.5
            self.inv["ore_sn"] += crew_h * CREW_RATE_PER_H * 0.5
        else:
            self.inv["ore_cu"] += crew_h * CREW_RATE_PER_H
        self.inv["coal"] += crew_h * CREW_COAL_PER_H

    def complete_build(self, target: str, lvl: int):
        if target == "hh":
            self.hh = lvl
            self.mark(f"HH{lvl}")
        else:
            self.smelter = lvl
        self.builder = None

    # ---------------------------------------------------------------- delve
    def choose_site(self) -> str:
        weights = {"copperhollow": 1.0, "emberseam": 0.5, "tinreach": 1.8}
        if self.inv["quartz"] < 25:
            weights["emberseam"] += 0.7
        coal_need = 60 if self.era >= 2 else 25
        if self.inv["coal"] < coal_need:
            weights["emberseam"] += 0.9
        options = [s for s in SITES if self.site_unlocked(s)]
        return max(options, key=lambda s: weights[s] * self.richness[s])

    def delve(self):
        s = self.choose_site()
        d = SITES[s]
        mpw = self.mpw()
        factor = min(2.0, max(0.6, d["power_req"] / self.player_power()))
        ore_taps = sum(p * math.ceil(ORE_HP[o] / mpw) for o, p in d["mix"].items())
        tpf = (d["move"] + d["stone_tiles"] * math.ceil(d["stone_hp"] / mpw)
               + d["ore_tiles"] * ore_taps + round(d["combat_base"] * factor))
        if d["star_per_floor"]:
            tpf += d["star_per_floor"] * math.ceil(STARSTONE_HP / mpw)
        floors = self.oil() / tpf
        r = self.richness[s]
        bonus = 1 + mining_level(self.chunks_mined) / 100
        chunks = floors * d["ore_tiles"] * r * bonus
        self.chunks_mined += int(chunks)
        assayed = {o: chunks * p for o, p in d["mix"].items()}
        self.assay(assayed, d["geode_rate"])
        self.inv["stone"] += floors * d["stone_tiles"] * r
        self.inv["star"] += floors * d["star_per_floor"] * r
        self.earn_coins(floors * d["coins_floor"] * r)
        self.gain_xp(int(floors * d["xp_floor"]))
        self.richness[s] = max(RICHNESS_FLOOR, r - RICHNESS_DROP)

    def assay(self, chunks: dict, geode_rate: float):
        total = sum(chunks.values())
        self.chunks_assayed += total
        self.spend_coins(total * ASSAY_FEE)
        for ore, qty in chunks.items():
            if ore in ("coal", "quartz"):
                self.inv[ore] += qty          # not graded
                continue
            units = 0.0
            whole = int(qty)
            for _ in range(whole):
                roll = self.rng.random()
                acc = 0.0
                for _name, p, u in GRADES:
                    acc += p
                    if roll < acc:
                        units += u
                        break
            units += (qty - whole) * 1.11      # expected value for the fractional chunk
            self.inv["ore_" + ore] += units
        # geodes, with pity
        for _ in range(int(total)):
            self.since_geode += 1
            if self.rng.random() < geode_rate or self.since_geode >= GEODE_PITY:
                self.since_geode = 0
                self.geodes += 1
                roll, acc = self.rng.random(), 0.0
                for kind, p in GEODE_TABLE:
                    acc += p
                    if roll < acc:
                        if kind == "gem":
                            self.inv["gems"] += 1
                        elif kind == "relic":
                            self.inv["relics"] += 1
                        else:
                            self.inv["star"] += 1
                        break

    def gain_xp(self, n: int):
        cap = LEVEL_CAP[self.era]
        self.xp += n
        while self.level < cap and self.xp >= xp_to_next(self.level):
            self.xp -= xp_to_next(self.level)
            self.level += 1
            self.mark(f"Lv{self.level}")
        if self.level >= cap:
            self.xp = min(self.xp, xp_to_next(self.level))   # overflow is banked, not lost, in-game

    # ---------------------------------------------------------------- smelter
    def queue_smelter(self):
        cap = smelter_slots(self.smelter) * smelter_batch(self.smelter)
        queued = sum(q for _, q in self.smelt_queue)
        room = cap - queued
        if room <= 0:
            return
        # alloy first when Bronze is needed and inputs exist
        if self.era >= 2 and self.inv["br"] < BRONZE_STOCK_TARGET:
            spare_cu = max(0, self.inv["cu"] - COPPER_RESERVE)
            n = int(min(room // 2, spare_cu, self.inv["sn"], self.inv["coal"] * 2))
            if n > 0:
                self.inv["cu"] -= n; self.inv["sn"] -= n; self.inv["coal"] -= n / 2
                self.smelt_queue.append(["br", n]); room -= n
        for kind in ("cu", "sn"):
            n = int(min(room, self.inv["ore_" + kind]))
            if n > 0:
                self.inv["ore_" + kind] -= n
                self.smelt_queue.append([kind, n]); room -= n

    # ---------------------------------------------------------------- spending
    def next_builder_target(self):
        if self.hh < HH_MAX and (self.smelter >= self.hh - 2 or self.smelter >= 12):
            return "hh", self.hh + 1, hh_cost(self.hh + 1)
        if self.smelter < min(self.hh, 12):
            return "smelter", self.smelter + 1, smelter_cost(self.smelter + 1)
        return None

    def try_spend(self):
        progressed = True
        while progressed:
            progressed = False
            # 1. a pick upgrade beats everything (it multiplies all mining)
            r = RECIPES.get(("pick", self.pick + 1))
            if r and self.hh >= r["hh"] and self.era >= r["era"] and self.can_afford(r["cost"]):
                self.pay(r["cost"])
                self.pick += 1
                self.enh["pick"] = max(0, self.enh["pick"] - 3)
                self.gain_xp(100)
                self.mark(f"pick{self.pick}")
                progressed = True
            # 2. builder
            if self.builder is None:
                t = self.next_builder_target()
                if t and self.can_afford(t[2]):
                    target, lvl, cost = t
                    self.pay(cost)
                    minutes = HH_MINUTES[lvl] if target == "hh" else smelter_minutes(lvl)
                    self.builder = (target, lvl, minutes)
                    progressed = True
            # 3. other gear
            for slot in ("kit", "lamp"):
                cur = getattr(self, slot)
                r = RECIPES.get((slot, cur + 1))
                if r and self.hh >= r["hh"] and self.era >= r["era"] and self.can_afford(r["cost"]):
                    self.pay(r["cost"])
                    setattr(self, slot, cur + 1)
                    self.enh[slot] = max(0, self.enh[slot] - 3)   # carry over a partial enhancement
                    self.gain_xp(100)
                    self.mark(f"{slot}{cur + 1}")
                    progressed = True
            # 4. crew
            if self.crew < crew_slots(self.hh):
                c = crew_hire_cost(self.crew + 1)
                if self.inv["coins"] >= c:
                    self.spend_coins(c)
                    self.crew += 1
                    progressed = True
            # 5. enhancement with surplus only (keep the next builder cost in reserve)
            t = self.next_builder_target()
            reserve = t[2] if t else None
            slot = min(self.enh, key=lambda k: self.enh[k])
            tier = getattr(self, slot)
            if self.enh[slot] < min(10, self.hh) and tier > 0:
                cost = enhance_cost(tier, self.enh[slot])
                if self.can_afford(cost, reserve):
                    self.pay(cost)
                    self.enh[slot] += 1
                    progressed = True
            if all(v >= 10 for v in self.enh.values()) and self.pick == 3 and self.kit == 3 and self.lamp == 2:
                self.mark("era2_gear_maxed")

    def hasten(self):
        if self.builder is None:
            return
        target, lvl, left = self.builder
        allowance = HASTEN_DAILY_CAP_MIN - self.hasten_used_today
        if self.arch.unlimited_aurum:
            self.inv["aurum"] = max(self.inv["aurum"], allowance * HASTEN_AURUM_PER_MIN)
        use = int(min(left, allowance, self.inv["aurum"] // HASTEN_AURUM_PER_MIN))
        if use <= 0:
            return
        self.inv["aurum"] -= use * HASTEN_AURUM_PER_MIN
        self.hasten_used_today += use
        left -= use
        if left <= 0:
            self.complete_build(target, lvl)
        else:
            self.builder = (target, lvl, left)

    # ---------------------------------------------------------------- day loop
    def play_day(self):
        a = self.arch
        n = a.sessions
        day_gap = WAKING_HOURS / (n - 1) if n > 1 else WAKING_HOURS
        per_session = [a.delves // n + (1 if i < a.delves % n else 0) for i in range(n)]
        self.hasten_used_today = 0
        # daily grants (morning)
        if a.membership:
            self.inv["aurum"] += MEMBERSHIP_AURUM_PER_DAY
        self.inv["aurum"] += a.aurum_per_week / 7
        metal = "br" if self.era >= 2 else "cu"
        pass_comps = PASS_FREE["comps"] + (PASS_PREMIUM["comps"] if a.premium_pass else 0)
        pass_coins = PASS_FREE["coins"] + (PASS_PREMIUM["coins"] if a.premium_pass else 0)
        self.earn_coins(pass_coins / SEASON_DAYS)
        self.inv[metal] += 9 * pass_comps / SEASON_DAYS
        if a.premium_pass:
            self.inv["aurum"] += PASS_PREMIUM["aurum"] / SEASON_DAYS
        if a.crates_per_week and self.day % 7 == 1:
            self.inv[metal] += 9 * CRATE["comps"] * a.crates_per_week
            self.earn_coins(CRATE["coins"] * a.crates_per_week)
        for i in range(n):
            self.advance(9.0 if i == 0 else day_gap)
            self.hasten()
            for _ in range(per_session[i]):
                self.delve()
            self.queue_smelter()
            self.try_spend()
            self.hasten()
        # daily objectives (completed by the last session)
        self.earn_coins(a.obj_coins)
        self.gain_xp(a.obj_xp)
        # surplus stone is sold at the Trading Post (1 coin each), keeping enough for the
        # next Hall upgrade; the sell screen shows this "reserved for upgrades" amount (docs/04 §4.9)
        t = self.next_builder_target()
        keep = max(600, (t[2].get("stone", 0) + 200) if t else 600)
        if self.inv["stone"] > keep:
            surplus = self.inv["stone"] - keep
            self.inv["stone"] = keep
            self.earn_coins(surplus)
        self.ps_by_day[self.day] = self.power_score()
        self.day += 1


def simulate(arch: Archetype, days: int, seed: int) -> Player:
    p = Player(arch=arch, rng=random.Random(seed))
    for _ in range(days):
        p.play_day()
    return p


# --------------------------------------------------------------------------------------
# Targets (docs/04 §4.12). Each: (archetype, metric, lo, hi). None = unbounded.
# --------------------------------------------------------------------------------------
TARGETS = [
    ("casual",   "pick1",  None, 2),
    ("casual",   "Lv20",   None, 35),
    ("casual",   "pick2",  None, 42),
    ("engaged",  "pick1",  None, 1),
    ("engaged",  "HH5",    None, 4),
    ("engaged",  "Lv20",   12, 18),
    ("engaged",  "pick2",  15, 21),
    ("engaged",  "HH15",   55, 90),
    ("hardcore", "HH15",   45, None),
    ("hardcore", "era2_gear_maxed", 40, None),
]
FAIRNESS = [  # (numerator, denominator, day, max_ratio)
    ("spender", "engaged", 30, 1.30),
    ("spender", "engaged", 60, 1.30),
    ("whale", "hardcore", 30, 1.30),
    ("whale", "hardcore", 60, 1.30),
]
INFO_RATIOS = [("hardcore", "engaged", 30), ("whale", "engaged", 30)]


def run_all(days: int, seeds: int):
    results = {}
    for a in ARCHETYPES:
        runs = [simulate(a, days, seed=1000 + s) for s in range(seeds)]
        results[a.name] = runs
    return results


def median_milestone(runs, key):
    vals = [r.milestones.get(key) for r in runs]
    if any(v is None for v in vals):
        return None
    return statistics.median(vals)


def median_ps(runs, day):
    return statistics.median(r.ps_by_day[day] for r in runs)


def report(results, days: int) -> list[str]:
    failures = []
    keys = ["pick1", "kit1", "lamp1", "HH5", "HH8", "Lv20", "pick2", "kit2", "lamp2",
            "HH10", "pick3", "kit3", "HH15", "Lv40", "era2_gear_maxed"]
    print(f"Deepforge economy simulation: {days} days, {len(next(iter(results.values())))} seeds per archetype")
    print(f"Era II opens on day {ERA2_OPEN_DAY}; post-launch Era III target is day {ERA3_TARGET_DAY}\n")
    print("Median day each milestone is reached ('-' = not reached):\n")
    header = "| Milestone | " + " | ".join(results) + " |"
    print(header)
    print("|" + "---|" * (len(results) + 1))
    for k in keys:
        row = [k]
        for name, runs in results.items():
            m = median_milestone(runs, k)
            row.append("-" if m is None else f"{m:g}")
        print("| " + " | ".join(row) + " |")

    print("\nMedian Power Score (PS):\n")
    print("| Day | " + " | ".join(results) + " |")
    print("|" + "---|" * (len(results) + 1))
    for d in (1, 3, 7, 14, 21, 30, 45, 60, 90):
        if d <= days:
            print(f"| {d} | " + " | ".join(f"{median_ps(r, d):g}" for r in results.values()) + " |")

    print("\nCoins (days 8-60): sources / sinks / ratio, and geodes per day:\n")
    print("| Archetype | Sources | Sinks | Ratio | Chunks assayed/day | Geodes/day | Coins on hand at end |")
    print("|---|---|---|---|---|---|---|")
    for name, runs in results.items():
        src = statistics.median(r.coin_src_window for r in runs)
        snk = statistics.median(r.coin_sink_window for r in runs)
        geo = statistics.median(r.geodes / days for r in runs)
        end = statistics.median(r.inv["coins"] for r in runs)
        cpd = statistics.median(r.chunks_assayed / days for r in runs)
        print(f"| {name} | {src:,.0f} | {snk:,.0f} | {src / snk:.2f} | {cpd:,.0f} | {geo:.2f} | {end:,.0f} |")

    print("\nPacing targets:\n")
    for arch, key, lo, hi in TARGETS:
        m = median_milestone(results[arch], key)
        ok = m is not None and (lo is None or m >= lo) and (hi is None or m <= hi)
        rng = f"[{lo if lo is not None else '-'}, {hi if hi is not None else '-'}]"
        print(f"  {'PASS' if ok else 'FAIL'}  {arch:9s} {key:16s} day {m if m is not None else 'never'} target {rng}")
        if not ok:
            failures.append(f"{arch}.{key}")

    print("\nFairness caps (Power Score ratio):\n")
    for num, den, day, cap in FAIRNESS:
        ratio = median_ps(results[num], day) / median_ps(results[den], day)
        ok = ratio <= cap
        print(f"  {'PASS' if ok else 'FAIL'}  {num}/{den} day {day}: {ratio:.2f} (cap {cap:.2f})")
        if not ok:
            failures.append(f"{num}/{den}@{day}")
    for num, den, day in INFO_RATIOS:
        ratio = median_ps(results[num], day) / median_ps(results[den], day)
        print(f"  info  {num}/{den} day {day}: {ratio:.2f} (playtime differs; not a cap)")
    print("\nCoin economy (days 8-60 source/sink ratio, target 0.85-1.25):\n")
    for name in ("engaged", "hardcore", "spender"):
        runs = results[name]
        ratio = statistics.median(r.coin_src_window / r.coin_sink_window for r in runs)
        ok = 0.85 <= ratio <= 1.25
        print(f"  {'PASS' if ok else 'FAIL'}  {name:9s} {ratio:.2f}")
        if not ok:
            failures.append(f"{name}.coin_ratio")
    return failures


def print_tables():
    print("### XP to next level\n")
    print("| Level | XP to next | Cumulative |")
    print("|---|---|---|")
    cum = 0
    for lvl in range(1, 40):
        cum += xp_to_next(lvl)
        print(f"| {lvl} | {xp_to_next(lvl):,} | {cum:,} |")
    print("\n### Homestead Hall upgrades\n")
    print("| To level | Coins | Stone | Copper Components | Bronze Components | Build time | Crew slots |")
    print("|---|---|---|---|---|---|---|")
    for lvl in range(2, HH_MAX + 1):
        c = hh_cost(lvl)
        m = HH_MINUTES[lvl]
        t = f"{m} min" if m < 60 else f"{m / 60:g} h"
        print(f"| {lvl} | {c['coins']:,} | {c['stone']:,} | {c.get('cu_comp', 0)} | {c.get('br_comp', 0)} | {t} | {crew_slots(lvl)} |")
    print("\n### Smelter upgrades\n")
    print("| To level | Coins | Copper Components | Bronze Components | Build time | Slots | Batch cap/slot | Cu/Sn min per ingot | Bronze min per ingot |")
    print("|---|---|---|---|---|---|---|---|---|")
    for lvl in range(2, 13):
        c = smelter_cost(lvl)
        m = smelter_minutes(lvl)
        t = f"{m} min" if m < 60 else f"{m / 60:g} h"
        print(f"| {lvl} | {c['coins']:,} | {c.get('cu_comp', 0)} | {c.get('br_comp', 0)} | {t} | {smelter_slots(lvl)} | "
              f"{smelter_batch(lvl)} | {smelt_minutes(lvl, False):.2f} | {smelt_minutes(lvl, True):.2f} |")
    print("\n### Enhancement (+n to +n+1); never fails, never destroys\n")
    print("| From | Copper-tier fittings | Copper-tier coins | Bronze-tier fittings | Bronze-tier coins | Starstone-tier fittings (bronze) | Starstone-tier coins |")
    print("|---|---|---|---|---|---|---|")
    for n in range(10):
        c1, c2, c3 = enhance_cost(1, n), enhance_cost(2, n), enhance_cost(3, n)
        print(f"| +{n} | {c1['cu_fit']} | {c1['coins']:,} | {c2['br_fit']} | {c2['coins']:,} | {c3['br_fit']} | {c3['coins']:,} |")
    print("\n### Crew hire cost\n")
    print("| Crew # | Coins |")
    print("|---|---|")
    for k in range(3, 9):
        print(f"| {k} | {crew_hire_cost(k):,} |")


# --------------------------------------------------------------------------------------
# Collection completion (docs/02 §2.9): 18 relics, duplicates -> 25 dust, 100 dust = 1 chosen relic
# --------------------------------------------------------------------------------------
RELIC_CATALOG = 18
DUST_PER_DUPLICATE = 25
DUST_PER_TARGETED = 100


def relics_to_complete(rng: random.Random, use_dust: bool) -> int:
    owned, dust, drawn = set(), 0, 0
    while len(owned) < RELIC_CATALOG:
        drawn += 1
        r = rng.randrange(RELIC_CATALOG)
        if r in owned:
            dust += DUST_PER_DUPLICATE
        else:
            owned.add(r)
        while use_dust and dust >= DUST_PER_TARGETED and len(owned) < RELIC_CATALOG:
            dust -= DUST_PER_TARGETED
            owned.add(next(i for i in range(RELIC_CATALOG) if i not in owned))
    return drawn


def collection_report(results, trials: int = 4000):
    rng = random.Random(7)
    luck = statistics.mean(relics_to_complete(rng, False) for _ in range(trials))
    dust = statistics.mean(relics_to_complete(rng, True) for _ in range(trials))
    print(f"\nCollection completion ({RELIC_CATALOG} relics; relic share of geodes {GEODE_TABLE[1][1]:.0%}):\n")
    print(f"Relics needed on average: pure luck {luck:.1f}, with dust exchange {dust:.1f}\n")
    print("| Archetype | Relics/day | Days (pure luck) | Days (dust exchange) |")
    print("|---|---|---|---|")
    for name, runs in results.items():
        rpd = statistics.median(r.geodes for r in runs) / len(runs[0].ps_by_day) * GEODE_TABLE[1][1]
        print(f"| {name} | {rpd:.2f} | {luck / rpd:.0f} | {dust / rpd:.0f} |")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--days", type=int, default=90)
    ap.add_argument("--seeds", type=int, default=7)
    ap.add_argument("--tables", action="store_true", help="print generated content tables and exit")
    ap.add_argument("--check", action="store_true", help="exit 1 if any target fails")
    args = ap.parse_args()
    if args.tables:
        print_tables()
        return 0
    results = run_all(args.days, args.seeds)
    failures = report(results, args.days)
    collection_report(results)
    if failures:
        print(f"\n{len(failures)} target(s) failed: {', '.join(failures)}")
    else:
        print("\nAll targets pass.")
    return 1 if (args.check and failures) else 0


if __name__ == "__main__":
    sys.exit(main())
