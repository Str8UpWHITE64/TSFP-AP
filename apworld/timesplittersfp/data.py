"""TimeSplitters: Future Perfect content catalog + Archipelago id tables.

Every name here is the game's own string (front-end and story string tables of the
GameCube build), so it matches what the player sees. Names become AP item /
location names and are PERMANENT once seeds exist.

Check model (same shape as the TimeSplitters 2 world):
  * Story missions -> one location per DIFFICULTY (Easy / Normal / Hard), plus one
    location per visible objective.
  * Challenges + Arcade League matches (the 48 "trophy events") -> one location per
    TROPHY TIER (Bronze..Platinum).
  * Items: one unlock per unit (mission or event); unlocking a unit enables all of
    its tier/difficulty checks. Weapons are items too when Weapon Gating is on.
Options select which difficulties / tiers become checks; every possible id is
allocated here so ids stay stable regardless of options.
"""

BASE_ID = 0x54534650  # "TSFP"

# --- Challenges: 7 groups -> 3 each (21). Game event ids 0..20, in this order. ---
CHALLENGES = {
    "Behead The Undead":             ["Brain Drain", "Rare or Well Done?", "Boxing Clever"],
    "Cut-out Shoot-out":             ["Hart Attack", "Come Hell or High Water", "Balls of Steel"],
    "Cat Driving":                   ["The Cat's out of the bag!", "Lap it up", "The Cat's Pajamas"],
    "Super Smashing Great":          ["Avec Le Brique", "Absolutely Potty", "Don't Lose Your Bottle"],
    "TimeSplitters 'Story' Classic": ["Queen of Harts", "Sammy Hammy Namby Pamby", "Glimpse of Stocking"],
    "Monkeying Around":              ["Electro Chimp Discomatic", "Melon Heist", "Brass Monkeys"],
    "Miscellaneous Challenges":      ["Cortez Can't Jump!", "TSUG:TimeSplitters Underground", "Plainly Off His Rocker"],
}

# --- Arcade League: 3 leagues -> 3 groups -> 3 matches (27). Game event ids 21..47, in this order. ---
ARCADE = {
    "Amateur League": {
        "One Gun Fun":   ["Rockets 101", "Big game hunt", "Divine Immolation"],
        "Nightstick":    ["Commuting will kill you", "Toy Soldiers", "Dam cold out here!"],
        "On The Take":   ["Vamping in Venice", "Pirate Gold", "Virtual brutality"],
    },
    "Honorary League": {
        "Dead Weight":   ["A Pox of Mox", "Rumble in the jungle", "Freak Unique"],
        "Fever Pitch":   ["Outbreak Hotel", "Missile Bunker", "Bag Slag"],
        "Mode Madness":  ["I like dead people", "Zany Zeppelin", "Lip Up Fatty"],
    },
    "Elite League": {
        "Smash 'n Grab": ["Screw loose", "Oh Shoal-o-Mio", "Astro Jocks"],
        "Group Therapy": ["Zone Control", "Front Loaded", "Old Blaggers"],
        "Retro Chique":  ["The Dead, the bad and the silly", "Ninja Garden", "Sock it to Them"],
    },
}
LEAGUES = list(ARCADE)                                  # index = the game's league id 0/1/2

# --- Story missions, in the game's mission-table order ---
STORY = [
    "Time to Split", "Scotland the Brave", "The Russian Connection", "The Khallos Express",
    "Mansion of Madness", "What Lies Below", "Breaking and Entering", "You Genius, U-Genix",
    "Machine Wars", "Something to Crow About", "You Take the High Road", "The Hooded Man",
    "Future Perfect",
]
FINAL_STORY_MISSION = "Future Perfect"
# level id per mission (the number in pak/story/l_NN_st.pak; the mission table's +0x06)
STORY_LEVEL_ID = [2, 4, 18, 11, 1, 17, 6, 22, 5, 14, 9, 26, 81]

STORY_DIFFICULTIES = ["Easy", "Normal", "Hard"]
TROPHY_TIERS = ["Bronze", "Silver", "Gold", "Platinum"]     # game tier 1..4
FILLER_ITEM = "Banana"
TIME_CRYSTAL_ITEM = "Time Crystal"

_ALL = frozenset(("Easy", "Normal", "Hard")); _NONE = frozenset()

# --- Story objectives -> AP locations ---
# Keyed by (mission, objective INDEX): the game keeps each level's objectives in a
# fixed-index pool, so the index is the identity the client matches. Per objective:
#     (index, name, primary_difficulties, secondary_difficulties)
# Future Perfect's tiers are the same on every difficulty (checked against the level
# data): main objectives are primary everywhere, secondaries optional everywhere.
# loc id = BASE_ID + 0x1500 + missionIdx*64 + index.
OBJECTIVES = {
    "Time to Split": [
        (0, "Reach the rebel base", _ALL, _NONE),
        (1, "Use the gun emplacement to defend against the TimeSplitter attack", _ALL, _NONE),
        (2, "Help defend the rebel base", _ALL, _NONE),
    ],
    "Scotland the Brave": [
        (1, "Infiltrate the castle", _ALL, _NONE),
        (2, "Locate the time crystal mining site", _ALL, _NONE),
        (3, "Gain entry to the meeting hall", _ALL, _NONE),
        (4, "Access the underground areas of the island", _ALL, _NONE),
        (5, "Destroy the enemy tank", _ALL, _NONE),
        (6, "Protect Captain Ash", _ALL, _NONE),
        (7, "Help Captain Ash rescue his assistant", _NONE, _ALL),
        (10, "Escape the trap", _ALL, _NONE),
    ],
    "The Russian Connection": [
        (0, "Find Time Traveler", _ALL, _NONE),
        (1, "Deactivate Electricity", _ALL, _NONE),
        (2, "Protect Harry Tipper", _ALL, _NONE),
        (3, "Gain Access to Sector 3", _ALL, _NONE),
        (4, "Restore Main Power", _ALL, _NONE),
        (5, "Activate Starter-Motor", _ALL, _NONE),
        (6, "Restore Water Pressure", _ALL, _NONE),
        (7, "Locate Khallos's Train", _ALL, _NONE),
        (9, "Rendezvous at the Water Tower", _ALL, _NONE),
    ],
    "The Khallos Express": [
        (0, "Destroy the helicopter", _ALL, _NONE),
        (1, "Find Khallos", _ALL, _NONE),
        (2, "Deactivate the gas trap", _ALL, _NONE),
        (3, "Prevent the missile launch", _ALL, _NONE),
        (4, "Defeat Khallos", _ALL, _NONE),
        (5, "Stop the train", _ALL, _NONE),
    ],
    "Mansion of Madness": [
        (0, "Investigate the Mansion", _ALL, _NONE),
        (1, "Rescue the scientist", _ALL, _NONE),
        (2, "Locate Lab entrance", _ALL, _NONE),
        (3, "Defeat the creature", _ALL, _NONE),
        (4, "Investigate the attic", _ALL, _NONE),
    ],
    "What Lies Below": [
        (0, "Uncover the identity of the mystery time traveler", _ALL, _NONE),
        (1, "Protect Jo-Beth from the zombie horde", _ALL, _NONE),
        (2, "Eliminate 'Princess'", _ALL, _NONE),
        (3, "Escape from the catacombs", _ALL, _NONE),
    ],
    "Breaking and Entering": [
        (0, "Locate Crow's office", _ALL, _NONE),
        (1, "Penetrate rooftop security", _ALL, _NONE),
        (2, "Protect the intruder", _ALL, _NONE),
        (3, "Activate fire suppression system", _ALL, _NONE),
        (4, "Help Amy gain access to Crow's floor", _ALL, _NONE),
        (5, "Access Crow's Terminal", _ALL, _NONE),
        (6, "Return to the lift", _ALL, _NONE),
    ],
    "You Genius, U-Genix": [
        (0, "Find Jacob Crow", _ALL, _NONE),
        (1, "Obtain an employee's ID card", _ALL, _NONE),
        (2, "Advance past the security area with Amy", _ALL, _NONE),
        (3, "Pass through the sterilization sensors", _ALL, _NONE),
        (5, "Destroy Crows security droids", _ALL, _NONE),
        (6, "Clear the area of hostiles", _ALL, _NONE),
        (14, "Decode first security terminal", _NONE, _ALL),
        (15, "Decode phase two of first security terminal", _NONE, _ALL),
        (16, "Destroy the railbots", _NONE, _ALL),
        (17, "Destroy second wave of railbots", _NONE, _ALL),
        (18, "Decode second security terminal", _NONE, _ALL),
        (19, "Destroy the spiderbots", _NONE, _ALL),
    ],
    "Machine Wars": [
        (0, "Reach the battle tank", _ALL, _NONE),
        (1, "Gain access to the processing facility", _ALL, _NONE),
        (2, "Obtain a cybernetic security implant", _ALL, _NONE),
        (3, "Locate the UltraNet secret laboratory", _ALL, _NONE),
    ],
    "Something to Crow About": [
        (0, "Terminate Crow", _ALL, _NONE),
        (1, "Deactivate the central power core", _ALL, _NONE),
        (2, "Defeat the battle mech", _ALL, _NONE),
        (3, "Destroy the TimeSplitter life support system", _ALL, _NONE),
        (4, "Eliminate the creature", _ALL, _NONE),
    ],
    "You Take the High Road": [
        (0, "Activate the Drilling Machine", _ALL, _NONE),
        (1, "Destroy the Time Crystals", _ALL, _NONE),
    ],
    "The Hooded Man": [
        (0, "Protect your past self from the time assassins", _ALL, _NONE),
        (1, "Destroy the TimeSplitter mothership", _ALL, _NONE),
    ],
    "Future Perfect": [
        (0, "Destroy the Time Crystals", _ALL, _NONE),
    ],
}

# Objectives that can only be earned by finishing the mission (so a clear implies
# them even on difficulties where they are secondary). None known yet for FP.
MISSION_COMPLETE_OBJS = frozenset()

# --- Weapons as items --------------------------------------------------------
# The game's gun table has 71 rows; rows sharing a FAMILY (base gun + its alt-fire
# and dual-wield variants) are one weapon. The apworld's weapon SLOT is the family's
# base row, and WEAPON_ROWS lists every row the client must gate/swap together.
WEAPONS = {
    2: "Pistol 9mm", 5: "Kruger 9mm", 8: "LX-18", 11: "Revolver", 12: "Flare Gun",
    14: "Tactical 12-Gauge", 15: "Dispersion Gun", 16: "Minigun", 18: "Sniper Rifle",
    19: "Vintage Rifle", 20: "Flamethrower", 21: "Harpoon Gun", 22: "Soviet Rifle",
    23: "ElectroTool", 25: "Scifi Handgun", 29: "Heatseeker", 30: "Rocket Launcher",
    32: "Scifi Sniper", 34: "Ghost Gun", 35: "Plasma Autorifle", 36: "Mag-Charger",
    38: "Monkey Gun", 40: "Grenades", 41: "Time Disrupter Grenades", 42: "Plasma Grenades",
    43: "Proximity Mines", 44: "Remote Mines", 46: "Timed Mines", 47: "TNT", 48: "K-SMG",
    51: "Machine Gun", 53: "Shotgun", 54: "Baseball Bat", 55: "Brick", 56: "Temporal Uplink",
    58: "Injector", 59: "SBP500",
}
WEAPON_ROWS = {
    2: (2, 3, 4), 5: (5, 6, 7), 8: (8, 9, 10), 11: (11,), 12: (12, 13), 14: (14,), 15: (15,),
    16: (16, 17), 18: (18,), 19: (19,), 20: (20,), 21: (21,), 22: (22,), 23: (23, 24),
    25: (25, 26, 27, 28), 29: (29,), 30: (30, 31), 32: (32, 33), 34: (34,), 35: (35,),
    36: (36, 37), 38: (38, 39), 40: (40,), 41: (41,), 42: (42,), 43: (43,), 44: (44, 45),
    46: (46,), 47: (47,), 48: (48, 49, 50), 51: (51, 52), 53: (53,), 54: (54,), 55: (55,),
    56: (56, 57), 58: (58,), 59: (59,),
}
# Row role within a family, so a shuffle pairs like with like (base<->base, alt<->alt,
# dual<->dual, dual-alt<->dual-alt). Missing roles on the target side are skipped.
def weapon_row_roles(slot):
    rows = WEAPON_ROWS[slot]
    roles = {}
    for r in rows:
        alt = r in _ALT_ROWS
        dual = r in _DUAL_ROWS
        roles[(dual, alt)] = r
    return roles
_ALT_ROWS = frozenset({3, 6, 9, 17, 24, 26, 28, 31, 33, 37, 45, 49, 56})   # gun table +0x14 = 1
_DUAL_ROWS = frozenset({4, 7, 10, 13, 27, 28, 39, 50, 52})               # gun table +0x00 & 4

# BASELINE: always usable, never an item, never shuffled: the Temporal Uplink (the
# story tool in every level). Unarmed (rows 0/1) is implicitly baseline.
WEAPON_BASELINE = frozenset({56})
# NO-SHUFFLE: gated items that keep their identity through a shuffle: ElectroTool
# (a level tool), Baseball Bat and Brick (melee with their own assets), and the
# Flamethrower -- Mansion of Madness hands it out first and its ghosts only die to
# fire, so the handout itself has to stay a fire weapon (nothing else is one).
WEAPON_NOSHUFFLE = frozenset({20, 23, 54, 55})

# PINNED per level: slots that keep their identity in ONE mission while still shuffling
# everywhere else. A level loads the data for its own weapons only; a scripted event that
# handles a gun as a physical object needs that gun's own data.
#   The Khallos Express
#     29 Heatseeker -- the level's only explosive, needed to bring down the helicopter.
#   (A freeze at Khallos's wall-gun set piece with the shuffle on was first taken for
#   the guards' gun toss, and pins were tried; none helped. The script spawns the
#   Pistol's drop model by object type, which the level never loaded once the Pistol
#   was shuffled away. Fixed for every level by the patched precache and the client's
#   list of native drop models -- see memmap PRECACHE_BLOCK_ADDR -- not by pins.)
#   What Lies Below
#     34 Ghost Gun -- needed to complete the level (maintainer, 2026-09-30).
LEVEL_PINNED_SLOTS = {
    "The Khallos Express": frozenset({29}),
    "What Lies Below": frozenset({34}),
}


def pin_remap(mission, remap, pins=None):
    """`remap` with the mission's pinned slots mapped to themselves.

    `pins` overrides LEVEL_PINNED_SLOTS (the client passes the seed's own list)."""
    pinned = (pins if pins is not None else LEVEL_PINNED_SLOTS).get(mission, ())
    if not pinned:
        return remap
    out = dict(remap)
    for s in pinned:
        out[s] = s
    return out

# Functional groups for the objective access logic ("any <group> weapon").
WEAPON_REG = frozenset({2, 5, 8, 11, 12, 14, 15, 16, 18, 19, 21, 22, 25, 32, 34, 35, 36, 38, 48, 51, 53, 58, 59})
WEAPON_EXP = frozenset({29, 30, 40, 41, 42})
WEAPON_MINE = frozenset({43, 44, 46, 47})
WEAPON_FIRE = frozenset({20})
# Logic only (the shuffle classes stay as above): anything that can fire an explosive --
# the explosive weapons plus the K-SMG, whose alt-fire is a grenade launcher (the alt row
# travels with the family through a shuffle).
WEAPON_EXPLOSIVE_ALT = frozenset({48})
WEAPON_BLAST = WEAPON_EXP | WEAPON_EXPLOSIVE_ALT
# What Lies Below's Princess: shot in the mouth with the Harpoon Gun -- a rocket did the
# same job in a live test (2026-09-30), so any explosive-capable weapon counts too.
WEAPON_HARPOON_OR_BLAST = WEAPON_BLAST | frozenset({21})
WEAPON_GROUPS = {"REG": WEAPON_REG, "EXP": WEAPON_EXP, "MINE": WEAPON_MINE, "FIRE": WEAPON_FIRE,
                 "BLAST": WEAPON_BLAST, "HARPOON_OR_BLAST": WEAPON_HARPOON_OR_BLAST}
WEAPON_TOOL_SLOT = {"ELECTRO": 23, "GHOST": 34}
WEAPON_COMBAT = WEAPON_REG | WEAPON_EXP | WEAPON_MINE | WEAPON_FIRE

WEAPON_ITEM_ID_BASE = 0xA00   # weapon item id = BASE_ID + 0xA00 + slot


def weapon_gated_slots():
    return [s for s in sorted(WEAPONS) if s not in WEAPON_BASELINE]


WEAPON_ITEM_OF = {s: f"{WEAPONS[s]} (Weapon)" for s in weapon_gated_slots()}
WEAPON_ITEM_NAMES = frozenset(WEAPON_ITEM_OF.values())

# Per-objective weapon requirements. MAPPING PASS PENDING: every objective currently
# takes the default (any regular or explosive weapon). Fill in as the missions are
# mapped, the way the TimeSplitters 2 world's OBJ_RULES were.
def only_on(diffs, rule):
    return lambda h, _d=diffs, _r=rule: (getattr(h, "difficulty", "Hard") not in _d) or _r(h)

OBJ_RULE_DEFAULT = lambda h: h("REG") or h("EXP")
OBJ_RULES = {
    # The ghosts at the start of the mansion only die to fire; nothing else opens the way
    # (the Flamethrower is no-shuffle for exactly this reason).
    ("Mansion of Madness", 0): lambda h: h("FIRE"),                              # Investigate the Mansion
    # The helicopter only comes down to an explosive (the Heatseeker is pinned for it).
    ("The Khallos Express", 0): lambda h: h("EXP"),                              # Destroy the helicopter
    # The tank has to be stalled with an explosive (hand grenades or the K-SMG's grenade
    # launcher; the Flare Gun does nothing) and then finished with TNT or another mine.
    ("Scotland the Brave", 5): lambda h: h("MINE") and h("BLAST"),               # Destroy the enemy tank
    # Everything after "Protect Jo-Beth" needs the Ghost Gun (pinned in this level).
    ("What Lies Below", 0): lambda h: h("GHOST") and OBJ_RULE_DEFAULT(h),      # Uncover the identity...
    ("What Lies Below", 2): lambda h: h("GHOST") and h("HARPOON_OR_BLAST"),    # Eliminate 'Princess'
    ("What Lies Below", 3): lambda h: h("GHOST") and OBJ_RULE_DEFAULT(h),      # Escape from the catacombs
    # Everything past the first two pickups needs the ElectroTool (no-shuffle, always itself).
    ("Something to Crow About", 0): lambda h: h("ELECTRO") and OBJ_RULE_DEFAULT(h),   # Terminate Crow
    ("Something to Crow About", 1): lambda h: h("ELECTRO") and OBJ_RULE_DEFAULT(h),   # Deactivate the central power core
    ("Something to Crow About", 2): lambda h: h("ELECTRO") and OBJ_RULE_DEFAULT(h),   # Defeat the battle mech
    ("Something to Crow About", 3): lambda h: h("ELECTRO") and OBJ_RULE_DEFAULT(h),   # Destroy the TimeSplitter life support system
    ("Something to Crow About", 4): lambda h: h("ELECTRO") and OBJ_RULE_DEFAULT(h),   # Eliminate the creature
}
# Inter-objective dependencies: a dependent objective's rule ANDs in each required one's.
OBJ_REQUIRES = {
    ("Mansion of Madness", 1): [0],
    ("Mansion of Madness", 2): [0],
    ("Mansion of Madness", 3): [0],
    ("Mansion of Madness", 4): [0],
    # after the tank (live order, 2026-09-24): underground, then the mining site
    ("Scotland the Brave", 4): [5],
    ("Scotland the Brave", 2): [5],
    # after Princess (live order): Uncover the identity, then Escape
    ("What Lies Below", 0): [2],
    ("What Lies Below", 3): [2],
}


def objective_rule(mission, index, _seen=None):
    base = OBJ_RULES.get((mission, index), OBJ_RULE_DEFAULT)
    reqs = OBJ_REQUIRES.get((mission, index))
    if not reqs:
        return base
    seen = (_seen or frozenset()) | {index}
    rules = (base, *(objective_rule(mission, r, seen) for r in reqs if r not in seen))
    return lambda h, _rules=rules: all(r(h) for r in _rules)

# --- per-level weapons ----------------------------------------------------------
# The weapon FAMILIES each mission provides: its weapon set (bots, placed pickups and
# the assets the level loads all follow it) plus the guns its script hands out.
# Turret/vehicle pseudo-guns and the baseline Uplink are left out.
LEVEL_WEAPON_SLOTS = {
    "Time to Split":           frozenset({25, 35, 32, 42}),
    "Scotland the Brave":      frozenset({5, 19, 48, 12, 47, 40}),
    "The Russian Connection":  frozenset({2, 18, 51, 22, 40}),
    "The Khallos Express":     frozenset({2, 29, 51, 22, 14}),
    "Mansion of Madness":      frozenset({53, 11, 20, 54}),
    "What Lies Below":         frozenset({53, 11, 21, 34}),
    "Breaking and Entering":   frozenset({36, 59, 41, 15, 8}),
    "You Genius, U-Genix":     frozenset({58, 59, 15, 20, 41, 8}),
    "Machine Wars":            frozenset({25, 35, 16, 32, 42}),
    "Something to Crow About": frozenset({25, 35, 16, 23, 30, 42}),
    "You Take the High Road":  frozenset({5, 19, 48, 21, 40}),
    "The Hooded Man":          frozenset({25, 35, 32, 42}),
    "Future Perfect":          frozenset({5, 19, 48, 21}),
}
# EARLY slots: obtainable at or near the start (the weapon the level hands you or
# places first). MAPPING PASS PENDING beyond the first gun.
LEVEL_EARLY_SLOTS = {
    "Time to Split": frozenset({25}), "Scotland the Brave": frozenset({5}),
    "The Russian Connection": frozenset({2}), "The Khallos Express": frozenset({2}),
    "Mansion of Madness": frozenset({20}), "What Lies Below": frozenset({11}),   # Revolver, then Shotgun
    "Breaking and Entering": frozenset({36}), "You Genius, U-Genix": frozenset({8}),   # LX-18 (live)
    "Machine Wars": frozenset({25}), "Something to Crow About": frozenset({25}),
    "You Take the High Road": frozenset({5}), "The Hooded Man": frozenset({32}),
    "Future Perfect": frozenset({5}),
}
LEVEL_NH_ONLY_SLOTS = {}
# The weapon each mission hands you first (precollected when the mission is a starting unlock).
# Every entry recorded live (2026-10-08, pickup_run.py weapon log).
LEVEL_PRIMARY_SLOT = {
    "Time to Split": 25, "Scotland the Brave": 5, "The Russian Connection": 2, "The Khallos Express": 2,
    "Mansion of Madness": 20, "What Lies Below": 11, "Breaking and Entering": 36, "You Genius, U-Genix": 8,
    "Machine Wars": 25, "Something to Crow About": 25, "You Take the High Road": 5, "The Hooded Man": 32,
    "Future Perfect": 5,
}
# A guaranteed second weapon for Hard. MAPPING PASS PENDING: none required yet.
LEVEL_HARD_SECONDARY = {}

# Thrown and placed weapons only ever trade places among themselves, in every scope:
# a grenade standing in for a gun (or a gun for a mine) changes how a level plays,
# not just what it looks like.
WEAPON_GRENADE = frozenset({40, 41, 42})
WEAPON_SHUFFLE_GROUPS = (WEAPON_MINE, WEAPON_GRENADE)

WEAPON_SHUFFLE_CLASSES = {
    "MINE": WEAPON_MINE,
    "GRENADE": WEAPON_GRENADE,
    "EXP":  WEAPON_EXP - WEAPON_GRENADE,      # the launchers
    "FIRE": WEAPON_FIRE,
    "REG":  WEAPON_REG,
}


def _derange_grouped(rng, slots):
    """A derangement of `slots` that keeps each WEAPON_SHUFFLE_GROUPS group to itself."""
    slots = sorted(slots)
    out = {}
    rest = [s for s in slots if not any(s in g for g in WEAPON_SHUFFLE_GROUPS)]
    for group in (*(sorted(g & set(slots)) for g in WEAPON_SHUFFLE_GROUPS), rest):
        out.update(_derange(rng, group))
    return out


def _weapon_shuffle_pool():
    return [s for s in weapon_gated_slots() if s not in WEAPON_NOSHUFFLE]


def _derange(rng, group):
    group = list(group)
    if len(group) < 2:
        return {s: s for s in group}
    shuffled = list(group)
    for _ in range(1000):
        rng.shuffle(shuffled)
        if all(o != n for o, n in zip(group, shuffled)):
            break
    return dict(zip(group, shuffled))


def weapon_remap_same_class(rng):
    remap = {s: s for s in WEAPONS}
    pool = set(_weapon_shuffle_pool())
    for cls in ("MINE", "GRENADE", "EXP", "FIRE", "REG"):
        remap.update(_derange(rng, sorted(pool & set(WEAPON_SHUFFLE_CLASSES[cls]))))
    return remap


def weapon_remap_for_level(rng, mission):
    """One mission's within_level shuffle: a derangement of its own unpinned weapons."""
    pool = set(_weapon_shuffle_pool())
    return _derange_grouped(rng, [s for s in LEVEL_WEAPON_SLOTS.get(mission, ())
                                  if s in pool and s not in LEVEL_PINNED_SLOTS.get(mission, ())])


def weapon_remap_within_level(rng):
    return {m: weapon_remap_for_level(rng, m) for m in STORY}


def weapon_global_remap(rng):
    """Mines shuffle among mines, grenades among grenades, everything else among
    itself, each a derangement."""
    remap = {s: s for s in WEAPONS}
    remap.update(_derange_grouped(rng, _weapon_shuffle_pool()))
    return remap


def level_category_items(mission, group, remap=None, difficulty="Hard"):
    remap = remap or {}
    gset = WEAPON_GROUPS[group]
    nh_only = LEVEL_NH_ONLY_SLOTS.get(mission, frozenset())
    items = set()
    for s in LEVEL_WEAPON_SLOTS.get(mission, ()):
        if difficulty == "Easy" and s in nh_only:
            continue
        w = remap.get(s, s)
        if w in WEAPON_ITEM_OF and w in gset:
            items.add(WEAPON_ITEM_OF[w])
    return frozenset(items)


def level_early_combat_items(mission, remap=None, difficulty="Hard"):
    remap = remap or {}
    nh_only = LEVEL_NH_ONLY_SLOTS.get(mission, frozenset())
    items = set()
    for s in LEVEL_EARLY_SLOTS.get(mission, ()):
        if difficulty == "Easy" and s in nh_only:
            continue
        w = remap.get(s, s)
        if w in WEAPON_ITEM_OF and w in WEAPON_COMBAT:
            items.add(WEAPON_ITEM_OF[w])
    return frozenset(items)


# WHAT A SLOT MAY TURN INTO. The shuffle is otherwise free (completely_random is full
# chaos on purpose); these rules stop the results that make a level unplayable rather
# than merely strange. The pins above cover a slot's own identity; these cover what it
# may BECOME.
#  - A level's starting weapon may only become a regular gun. Starting The Khallos
#    Express with only a Heatseeker in hand (scarce ammo, splash damage) was unplayable.
PRIMARY_MUST_BECOME = WEAPON_REG


def mission_coverable(mission, remap, difficulty):
    primary = LEVEL_PRIMARY_SLOT.get(mission)
    if primary is not None and primary not in WEAPON_NOSHUFFLE             and remap.get(primary, primary) not in PRIMARY_MUST_BECOME:
        return False
    if not level_early_combat_items(mission, remap, difficulty):
        return False

    def h(tok):
        if tok in WEAPON_GROUPS:
            return bool(level_category_items(mission, tok, remap, difficulty))
        return True
    h.difficulty = difficulty
    for idx, _name, prim, sec in OBJECTIVES.get(mission, []):
        if difficulty in (prim | sec) and not objective_rule(mission, idx)(h):
            return False
    return True


# --- trophy events, in the game's own event-id order (challenges 0..20, arcade 21..47) ---
def trophy_events():
    out = []
    for cat, chs in CHALLENGES.items():
        for c in chs:
            out.append(("challenge", cat, c))
    for league, groups in ARCADE.items():
        for gname, matches in groups.items():
            for m in matches:
                out.append(("arcade", f"{league} / {gname}", m))
    return out


TROPHY_EVENTS = trophy_events()                 # 48; index == game event id
TROPHY_EVENT_NAMES = [e[2] for e in TROPHY_EVENTS]
EVENT_LEAGUE = [LEAGUES.index(g.split(" / ")[0]) if k == "arcade" else -1 for (k, g, _) in TROPHY_EVENTS]
UNIT_NAMES = TROPHY_EVENT_NAMES + list(STORY)  # 61 in-game names; the client keys on these
assert len(TROPHY_EVENTS) == 48
assert len(UNIT_NAMES) == len(set(UNIT_NAMES)), "duplicate unit name"


def _display_base(kind, group, ingame):
    if kind == "arcade":
        league, series = group.split(" / ")
        return f"{league} - {series} - {ingame}"
    if kind == "challenge":
        return f"Challenge - {group} - {ingame}"
    return ingame


DISPLAY_OF = {n: _display_base(k, g, n) for (k, g, n) in TROPHY_EVENTS}
DISPLAY_OF.update({m: _display_base("story", "", m) for m in STORY})
ITEM_OF = {n: f"{DISPLAY_OF[n]} Unlocked" for n in UNIT_NAMES}
ITEM_NAMES = [ITEM_OF[n] for n in UNIT_NAMES]
STORY_ITEMS = [ITEM_OF[m] for m in STORY]
FINAL_STORY_ITEM = ITEM_OF[FINAL_STORY_MISSION]

# ---- item ids ----
item_name_to_id = {ITEM_OF[n]: BASE_ID + i for i, n in enumerate(UNIT_NAMES)}
item_name_to_id[TIME_CRYSTAL_ITEM] = BASE_ID + 0x900
item_name_to_id[FILLER_ITEM] = BASE_ID + 0x901
for _ws in weapon_gated_slots():
    item_name_to_id[WEAPON_ITEM_OF[_ws]] = BASE_ID + WEAPON_ITEM_ID_BASE + _ws
assert len(set(item_name_to_id.values())) == len(item_name_to_id), "duplicate item id"

# ---- location ids ----
#   trophy events:  BASE + 0x1000 + eventIdx*4 + tierIdx      48*4 = 192
#   story:          BASE + 0x1400 + missionIdx*3 + diffIdx    13*3 = 39
#   objectives:     BASE + 0x1500 + missionIdx*64 + index      68
location_name_to_id = {}
for ei, (_, _, name) in enumerate(TROPHY_EVENTS):
    for ti, tier in enumerate(TROPHY_TIERS):
        location_name_to_id[f"{DISPLAY_OF[name]} ({tier})"] = BASE_ID + 0x1000 + ei * 4 + ti
for mi, m in enumerate(STORY):
    for di, d in enumerate(STORY_DIFFICULTIES):
        location_name_to_id[f"{DISPLAY_OF[m]} ({d})"] = BASE_ID + 0x1400 + mi * 3 + di


def objective_location_name(mission, objname):
    return f"{DISPLAY_OF[mission]} - {objname}"


OBJ_LOC_INFO = {}   # AP location name -> (index, primary_difficulties, secondary_difficulties, mission)
for _m, _objs in OBJECTIVES.items():
    _mi = STORY.index(_m)
    for _idx, _oname, _prim, _sec in _objs:
        _ln = objective_location_name(_m, _oname)
        location_name_to_id[_ln] = BASE_ID + 0x1500 + _mi * 64 + _idx
        OBJ_LOC_INFO[_ln] = (_idx, _prim, _sec, _m)

_n_obj = sum(len(o) for o in OBJECTIVES.values())
assert _n_obj == 68

# ---- health / armour pickups (optional; normal checks once a mapping run has taken them) ----
#   pickups:        BASE + 0x1A00 + missionIdx*0x40 + n           (listed spots)
#                   BASE + 0x1A00 + missionIdx*0x40 + 0x20 + n    (container drops)
# One location per spot: an Easy record and its Normal/Hard twin share a placement node.
try:
    from .pickups import PICKUPS, UNVERIFIED
except ImportError:                             # the client imports data.py directly
    from pickups import PICKUPS, UNVERIFIED

PICKUP_LOC_INFO = {}   # AP location name -> (mission, spot) with spot as in pickups.py
PICKUP_UNVERIFIED = set()   # names of spots no mapping run has taken: excluded (filler only)
for _mi, _m in enumerate(STORY):
    _count = {}
    for _spot in PICKUPS.get(_m, []):
        _n, _kind, _war, _diffs, _pos, _needs, _extra, _cont = _spot
        assert _n < 0x20
        _count[(_kind, _cont)] = _count.get((_kind, _cont), 0) + 1
        _ln = f"{DISPLAY_OF[_m]} - {'Container ' if _cont else ''}{_kind} {_count[(_kind, _cont)]}"
        location_name_to_id[_ln] = BASE_ID + 0x1A00 + _mi * 0x40 + (0x20 if _cont else 0) + _n
        PICKUP_LOC_INFO[_ln] = (_m, _spot)
        if (_m, _n, _cont) in UNVERIFIED:
            PICKUP_UNVERIFIED.add(_ln)

assert len(location_name_to_id) == (48 * len(TROPHY_TIERS) + len(STORY) * len(STORY_DIFFICULTIES) + _n_obj
                                    + len(PICKUP_LOC_INFO))
assert len(set(location_name_to_id.values())) == len(location_name_to_id), "duplicate location id"


def trophy_locations(name):
    return [f"{DISPLAY_OF[name]} ({t})" for t in TROPHY_TIERS]


def story_locations(mission):
    return [f"{DISPLAY_OF[mission]} ({d})" for d in STORY_DIFFICULTIES]


def objective_locations(mission):
    return [objective_location_name(mission, o[1]) for o in OBJECTIVES.get(mission, [])]


def objective_primary_mask():
    """{ str(missionIdx*64 + index): primary-difficulty bitmask } (Easy=1 Normal=2 Hard=4)."""
    bit = {"Easy": 1, "Normal": 2, "Hard": 4}
    out = {}
    for m, objs in OBJECTIVES.items():
        mi = STORY.index(m)
        for idx, _name, prim, _sec in objs:
            mask = 0
            for d in prim:
                mask |= bit[d]
            out[str(mi * 64 + idx)] = mask
    return out


item_name_groups = {
    "Arcade":    {ITEM_OF[e[2]] for e in TROPHY_EVENTS if e[0] == "arcade"},
    "Challenge": {ITEM_OF[e[2]] for e in TROPHY_EVENTS if e[0] == "challenge"},
    "Story":     {ITEM_OF[m] for m in STORY},
    "Weapons":   set(WEAPON_ITEM_OF.values()),
}
