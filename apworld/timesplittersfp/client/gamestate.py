"""Reading and writing TimeSplitters: Future Perfect (GameCube) state -- no Archipelago dependency.

Split out so a dry run can watch a live game with nothing but Dolphin and this repo,
and so every address conversion lives in exactly one place.
"""
import os
import random
import sys
import tempfile
import typing

import dolphin_memory_engine as dme

from .. import data
from .. import memmap as mm

POLL_INTERVAL = 0.4

STORY_BASE = data.BASE_ID + 0x1400
TROPHY_BASE = data.BASE_ID + 0x1000
LOCATION_NAME = {loc_id: name for name, loc_id in data.location_name_to_id.items()}
DIFF_BIT = {"Easy": 1, "Normal": 2, "Hard": 4}
MISSION_OF_LEVEL = {level: index for index, level in enumerate(data.STORY_LEVEL_ID)}
OBJ_LOCATION = {}                       # (mission index, objective index) -> location id
for _name, (_idx, _prim, _sec, _mission) in data.OBJ_LOC_INFO.items():
    OBJ_LOCATION[(data.STORY.index(_mission), _idx)] = data.location_name_to_id[_name]


def u32(addr: int) -> int:
    return int.from_bytes(dme.read_bytes(addr, 4), "big")


def u16(addr: int) -> int:
    return int.from_bytes(dme.read_bytes(addr, 2), "big")


def u8(addr: int) -> int:
    return dme.read_bytes(addr, 1)[0]


def w32(addr: int, value: int) -> None:
    dme.write_bytes(addr, (value & 0xFFFFFFFF).to_bytes(4, "big"))


def in_ram(addr) -> bool:
    return 0x80000000 <= addr < 0x81800000


def hook() -> bool:
    """Attach to Dolphin and confirm the right game is running."""
    if not dme.is_hooked():
        dme.hook()
    if not dme.is_hooked():
        return False
    try:
        return dme.read_bytes(0x80000000, 6).decode("latin-1") == mm.GAME_ID
    except Exception:
        return False


# --- profile ---------------------------------------------------------------------
def profile_base(slot: int = 0) -> typing.Optional[int]:
    """Profile record address, or None while the slot is unused."""
    addr = mm.PROFILE_BASE + slot * mm.PROFILE_STRIDE
    try:
        info = u32(addr + mm.PROFILE_INFO_PTR_OFF)
    except Exception:
        return None
    return addr if in_ram(info) else None


def profile_name(slot: int = 0) -> str:
    addr = mm.PROFILE_BASE + slot * mm.PROFILE_STRIDE
    info = u32(addr + mm.PROFILE_INFO_PTR_OFF)
    if not in_ram(info):
        return ""
    return dme.read_bytes(info + mm.PROFILE_INFO_NAME_OFF, mm.PROFILE_NAME_LEN).split(b"\0", 1)[0].decode("latin-1")


def is_default_profile(name: str) -> bool:
    """The "Player 1".."Player 4" stand-ins the game holds until a card profile is loaded."""
    return name in ("Player 1", "Player 2", "Player 3", "Player 4")


def profile_tag(gamedata: int) -> int:
    return u32(gamedata + mm.PROFILE_TAG_G)


def set_profile_tag(gamedata: int, tag: int) -> None:
    w32(gamedata + mm.PROFILE_TAG_G, tag)


def profile_has_progress(gamedata: int) -> bool:
    """Anything a check could be read from: a story clear, a medal, or story locks a
    client has already written (an older randomizer profile)."""
    if any(story_words(gamedata)) or trophy_checks(gamedata):
        return True
    gate = u32(gamedata + mm.MEDAL_BITS_G + 1 * mm.MEDAL_TIER_STRIDE + ((mm.STORY_BIT_BASE >> 5) * 4))
    return bool(gate >> (mm.STORY_BIT_BASE & 31))


def gamedata_blocks(profile: int) -> typing.List[int]:
    """The game-data blocks the unlock code may read: the profile's own, plus the
    aggregate scratch when the game is pointing at that (co-op)."""
    blocks = [profile + mm.GAMEDATA_OFF]
    try:
        active = u32(mm.ACTIVE_GAMEDATA_PTR)
    except Exception:
        active = 0
    if in_ram(active) and active not in blocks:
        blocks.append(active)
    return blocks


# --- mode / level ----------------------------------------------------------------
def mode_byte() -> typing.Optional[int]:
    try:
        return u8(mm.MODE_BYTE_ADDR)
    except Exception:
        return None


def in_story() -> bool:
    return mode_byte() == mm.MODE_STORY


def current_level() -> typing.Optional[int]:
    try:
        return u32(mm.CURRENT_LEVEL_ADDR)
    except Exception:
        return None


def current_mission() -> typing.Optional[int]:
    """Story mission index for the level now loaded, or None if it is not one.

    Story and Arcade share level ids, so the mode byte settles it."""
    mission = MISSION_OF_LEVEL.get(current_level())
    if mission is None or not in_story():
        return None
    return mission


def menu_selected_mission() -> typing.Optional[int]:
    """The mission the story menu has committed to, before any load starts."""
    try:
        if u32(mm.MENU_STATE_ADDR) != mm.MENU_STATE_STORY:
            return None
        m = u32(mm.SELECTED_MISSION_ADDR)
    except Exception:
        return None
    return m if 0 <= m < len(data.STORY) else None


# --- story clears ----------------------------------------------------------------
def story_words(gamedata: int) -> typing.List[int]:
    """Per-difficulty mission bitmasks, solo OR co-op. The client never writes these."""
    return [u32(gamedata + mm.STORY_SOLO_G + d * 4) | u32(gamedata + mm.STORY_COOP_G + d * 4)
            for d in range(3)]


def story_checks(gamedata: int) -> typing.Set[int]:
    found = set()
    words = story_words(gamedata)
    for di in range(3):
        for mi in range(len(data.STORY)):
            if words[di] >> mi & 1:
                found.add(STORY_BASE + mi * 3 + di)
    return found


def story_cleared_mask(gamedata: int, mission: int) -> int:
    words = story_words(gamedata)
    return sum(1 << di for di in range(3) if words[di] >> mission & 1)


# --- medals ----------------------------------------------------------------------
def trophy_checks(gamedata: int) -> typing.Set[int]:
    """Challenge and arcade checks from the medal records (event id == AP index)."""
    found = set()
    for ev in range(mm.TROPHY_COUNT):
        tier = u32(gamedata + mm.TROPHY_G + ev * mm.TROPHY_STRIDE + mm.TROPHY_TIER)
        for ti in range(min(tier, len(data.TROPHY_TIERS))):
            found.add(TROPHY_BASE + ev * 4 + ti)
    return found


# --- objectives ------------------------------------------------------------------
def build_objectives():
    """mission index -> [(location id, difficulty mask)] for objectives a clear implies."""
    by_mission: typing.Dict[int, list] = {}
    underivable = []
    for loc_name, (idx, prim, sec, mission) in data.OBJ_LOC_INFO.items():
        loc_id = data.location_name_to_id[loc_name]
        mi = data.STORY.index(mission)
        difficulties = prim | sec if (mission, idx) in data.MISSION_COMPLETE_OBJS else prim
        if not difficulties:
            underivable.append(loc_name)
            continue
        mask = 0
        for d in difficulties:
            mask |= DIFF_BIT[d]
        by_mission.setdefault(mi, []).append((loc_id, mask))
    return by_mission, underivable


OBJECTIVES_BY_MISSION, UNDERIVABLE_OBJECTIVES = build_objectives()


def objective_pool() -> typing.Optional[int]:
    try:
        pool = u32(mm.OBJ_POOL_PTR)
    except Exception:
        return None
    return pool if in_ram(pool) else None


class ObjectiveWatcher:
    """Fires an objective only when it is SEEN to become complete.

    The pool is reset when a level starts, but a baseline is still taken on every
    level change and nothing fires from it: a real completion is always a
    transition into status 5, and a stale value never transitions.
    """

    def __init__(self):
        self.key = None
        self.status = {}

    def poll(self):
        """(newly completed location ids, [(objective index, old, new)])."""
        mission = current_mission()
        pool = objective_pool()
        if mission is None or pool is None:
            self.key = None
            return set(), []
        key = (mission, pool)
        if key != self.key:
            self.key = key
            self.status = {}
        newly, transitions = set(), []
        for i in range(mm.OBJ_POOL_ENTRIES):
            entry = pool + i * mm.OBJ_STRIDE
            try:
                status = u8(entry + mm.OBJ_STATUS)
                idx = u16(entry + mm.OBJ_INDEX)
            except Exception:
                continue
            if status == 0:
                continue
            if idx != i:                        # the pool is indexed by objective index
                continue
            was = self.status.get(i)
            self.status[i] = status
            if was is None or status == was:
                continue
            transitions.append((i, was, status))
            if status == mm.OBJ_STATUS_COMPLETE:
                loc = OBJ_LOCATION.get((mission, i))
                if loc is not None:
                    newly.add(loc)
        return newly, transitions


# --- patched-image detection -----------------------------------------------------
def story_patch_present() -> bool:
    try:
        words = tuple(u32(mm.STORY_GATE_PATCH_ADDR + k * 4) for k in range(6))
    except Exception:
        return False
    return words == mm.STORY_GATE_APPLIED


def mount_patch_present() -> bool:
    try:
        return u32(mm.PAK_MOUNT_PATCH_ADDR) == mm.PAK_MOUNT_APPLIED
    except Exception:
        return False


def precache_patch_present() -> bool:
    try:
        return u32(mm.PRECACHE_HOOK_ADDR) == mm.PRECACHE_HOOK_APPLIED
    except Exception:
        return False


def skip_intro_patch_present() -> bool:
    try:
        return u32(mm.SKIP_INTRO_HOOK_ADDR) == mm.SKIP_INTRO_HOOK_APPLIED
    except Exception:
        return False


def set_skip_intro(on: bool) -> None:
    want = b"\x01" if on else b"\x00"
    if dme.read_bytes(mm.SKIP_INTRO_FLAG, 1) != want:
        dme.write_bytes(mm.SKIP_INTRO_FLAG, want)


def camera_patch_present() -> bool:
    try:
        return u32(mm.CAMERA_GUARD_HOOK_ADDR) == mm.CAMERA_GUARD_HOOK_APPLIED
    except Exception:
        return False


def level_items_base(level: int) -> int:
    """First .war item record of the level now loaded, or 0."""
    a = mm.LEVEL_TABLE
    for _ in range(256):
        if not u16(a + 4):
            return 0
        if u32(a + 8) == level:
            params = u32(a + 0x24)
            return u32(params + 0x14) if in_ram(params) else 0
        a += 0x80
    return 0


def taken_pickups() -> typing.List[typing.Tuple[typing.Optional[int], str, typing.Tuple[float, float, float]]]:
    """Health/armour items taken in the level now loaded: (.war index or None for a
    spawned drop, kind, spawn position)."""
    import struct
    level = current_level()
    base = level_items_base(level) if level is not None else 0
    pool, n = u32(mm.ITEM_POOL_PTR), u32(mm.ITEM_POOL_COUNT)
    if not in_ram(pool) or n > 0x78:
        return []
    blob = dme.read_bytes(pool, n * mm.ITEM_DATA_STRIDE)
    out = []
    for i in range(n):
        e = blob[i * mm.ITEM_DATA_STRIDE:(i + 1) * mm.ITEM_DATA_STRIDE]
        kind = mm.PICKUP_TYPES.get(struct.unpack(">I", e[mm.ITEM_TYPE:mm.ITEM_TYPE + 4])[0])
        if kind is None or not struct.unpack(">I", e[mm.ITEM_TAKEN_BY:mm.ITEM_TAKEN_BY + 4])[0]:
            continue
        rec = struct.unpack(">I", e[mm.ITEM_WAR_RECORD:mm.ITEM_WAR_RECORD + 4])[0] - mm.WAR_ITEM_PROPS
        idx = None
        if base and rec >= base:
            q, r = divmod(rec - base, mm.WAR_ITEM_STRIDE)
            if r == 0 and q < 0x200:
                idx = q
        pos = struct.unpack(">3f", e[mm.ITEM_SPAWN_POS:mm.ITEM_SPAWN_POS + 12])
        out.append((idx, kind, pos))
    return out


def sequencer_patch_present() -> bool:
    try:
        return (all(u32(a) == w for a, w in zip(mm.SEQUENCER_PATCH_ADDRS, mm.SEQUENCER_APPLIED))
                and u32(mm.SEQUENCER_MENU_STATE[0]) == mm.SEQUENCER_MENU_STATE[1])
    except Exception:
        return False


# --- gating writes ---------------------------------------------------------------
def event_record_addr(ev: int) -> int:
    base = mm.EVENT_PTRS_CHALLENGE if ev < 21 else mm.EVENT_PTRS_ARCADE
    return u32(base + ev * 4) + mm.EVENT_REQ_OFF


def write_record(addr: int, first_word: int) -> bool:
    """Set a 5-dword requirement record to {first_word, 0, 0, 0, 0}; True if it changed."""
    want = first_word.to_bytes(4, "big") + bytes(16)
    if dme.read_bytes(addr, 20) == want:
        return False
    dme.write_bytes(addr, want)
    return True


def apply_event_gate(granted_events: typing.Set[int]) -> int:
    """{1} for granted events, {0} for the rest; leagues open with any granted match."""
    changed = 0
    for ev in range(mm.TROPHY_COUNT):
        addr = event_record_addr(ev)
        if not in_ram(addr):
            continue
        changed += write_record(addr, mm.REQ_ALWAYS if ev in granted_events else mm.REQ_NEVER)
    for league, addr in mm.LEAGUE_REQ.items():
        open_league = any(data.EVENT_LEAGUE[ev] == league for ev in granted_events)
        changed += write_record(addr, mm.REQ_ALWAYS if open_league else mm.REQ_NEVER)
    return changed


def apply_story_gate(gamedata: int, granted_missions: typing.Set[int]) -> bool:
    """Tier-1 spare medal bits 48+m for the granted missions (patched image). True if changed."""
    word_addr = gamedata + mm.MEDAL_BITS_G + 1 * mm.MEDAL_TIER_STRIDE + ((mm.STORY_BIT_BASE >> 5) * 4)
    keep_mask = (1 << (mm.STORY_BIT_BASE & 31)) - 1
    current = u32(word_addr)
    want = current & keep_mask
    for mi in granted_missions:
        want |= 1 << ((mm.STORY_BIT_BASE + mi) & 31)
    if want == current:
        return False
    w32(word_addr, want)
    return True


def clear_unlock_overrides():
    for k in range(1, 6):
        if dme.read_bytes(mm.UNLOCK_OVERRIDE_BYTES + k, 1) != b"\0":
            dme.write_bytes(mm.UNLOCK_OVERRIDE_BYTES + k, b"\0")
    if u32(mm.UNLOCK_ALL_GLOBAL):
        w32(mm.UNLOCK_ALL_GLOBAL, 0)


# --- the player pawn ---------------------------------------------------------------
class AmmoScaler:
    """Scale the player's gains of each borrowed ammo type (WeaponTables.ammo_scale):
    pickups and handouts give the replaced gun's amounts, and this turns them into the
    same share of the shuffled-in gun's maximum. Losses (firing, reloading) pass as they
    are. Fractions carry over, so ten pickups worth 0.4 each still come to four."""

    def __init__(self):
        self.pawn = None
        self.watched_load = False       # saw the level load, so a new pawn's ammo is all handouts
        self.last: typing.List[int] = []
        self.carry: typing.Dict[int, float] = {}

    def reset(self):
        """No pawn (a load): the next pawn is a fresh one."""
        self.pawn = None
        self.watched_load = True

    def poll(self, pawn: int, scale: typing.Dict[int, float]) -> int:
        raw = dme.read_bytes(pawn + mm.PAWN_AMMO, mm.AMMO_TYPE_COUNT * 2)
        now = [int.from_bytes(raw[i * 2:i * 2 + 2], "big", signed=True) for i in range(mm.AMMO_TYPE_COUNT)]
        if pawn != self.pawn:
            # a pawn seen from its load starts empty, so what it holds was handed out and is
            # scaled; one already there when the client started was scaled by an earlier client
            fresh = self.watched_load
            self.pawn, self.carry, self.watched_load = pawn, {}, False
            self.last = [0] * mm.AMMO_TYPE_COUNT if fresh else list(now)
        changed = 0
        for t, f in scale.items():
            gain = now[t] - self.last[t]
            if gain <= 0 or f == 1:
                continue
            want = gain * f + self.carry.get(t, 0.0)
            whole = int(want)
            self.carry[t] = want - whole
            most = u32(mm.AMMO_TYPES + t * mm.AMMO_TYPE_STRIDE + mm.AMMO_TYPE_MAX)
            value = max(0, min(self.last[t] + whole, most))
            if value != now[t]:
                dme.write_bytes(pawn + mm.PAWN_AMMO + t * 2, value.to_bytes(2, "big", signed=True))
                now[t] = value
                changed += 1
        self.last = now
        return changed



def player_position() -> typing.Optional[typing.Tuple[float, float, float]]:
    """The player's world position (feet), or None outside a level."""
    import struct
    try:
        game = u32(mm.GAME_PTR)
        if not in_ram(game):
            return None
        player = u32(game + mm.PLAYER_OFF)
        if not in_ram(player):
            return None
        return struct.unpack(">3f", dme.read_bytes(player + mm.PLAYER_POS_OFF, 12))
    except Exception:
        return None


class MapAreas:
    """Which tracker map tab the player is on: tracker_areas.json, written by the
    tracker build, maps each mission's floor cells to the floors over them
    ([y_lo, y_hi, area]); the floor just under the player wins."""

    def __init__(self):
        # read through the package loader: inside an .apworld this file is in a zip
        try:
            import json
            import pkgutil
            self.data = json.loads(pkgutil.get_data(__name__, "tracker_areas.json").decode("utf-8"))
        except (OSError, ValueError, AttributeError, TypeError):
            self.data = {}

    def area(self, mission: int, pos) -> typing.Optional[int]:
        import math
        m = self.data.get(str(mission))
        if not m or pos is None:
            return None
        x, y, z = pos
        cell = m["cell"]
        best = None
        for dx in (0, -1, 1):
            for dz in (0, -1, 1):
                key = "%d,%d" % (math.floor(x / cell) + dx, math.floor(z / cell) + dz)
                for lo, hi, a in m["grid"].get(key, ()):
                    if lo <= y <= hi:
                        score = abs(y - (lo + 2.3)) + (0 if dx == dz == 0 else 1.5)
                        if best is None or score < best[0]:
                            best = (score, a)
            if best is not None and dx == 0:
                break
        return best[1] if best else None


def player_pawn() -> typing.Optional[int]:
    try:
        game = u32(mm.GAME_PTR)
        if not in_ram(game):
            return None
        player = u32(game + mm.PLAYER_OFF)
        if not in_ram(player):
            return None
        pawn = u32(player + mm.PAWN_OFF)
    except Exception:
        return None
    if not in_ram(pawn):
        return None
    try:
        # every live player pawn owns the unarmed row
        if u8(pawn + mm.PAWN_OWNED + mm.UNARMED_SLOT) != 1:
            return None
    except Exception:
        return None
    return pawn


ROW_FAMILY = {row: slot for slot, rows in data.WEAPON_ROWS.items() for row in rows}


_stats_ammo_cache: typing.Dict[int, typing.Tuple[int, int]] = {}
_stats_ammo_table = None


def _row_ammo_types(gun: bytes, row: int) -> typing.Set[int]:
    """The ammo types (primary, alt) a live gun-table row fires."""
    global _stats_ammo_table
    if gun != _stats_ammo_table:            # the shuffle rewrote the tables (and the stats' ammo)
        _stats_ammo_cache.clear()
        _stats_ammo_table = gun
    out = set()
    for off in (mm.GUN_LEFT_STATS, mm.GUN_RIGHT_STATS):
        i = int.from_bytes(gun[row * mm.GUN_STRIDE + off:row * mm.GUN_STRIDE + off + 4], "big")
        if i >= mm.GUN_STATS_COUNT:
            continue
        if i not in _stats_ammo_cache:
            base = mm.GUN_STATS + i * mm.GUN_STATS_STRIDE
            _stats_ammo_cache[i] = (u32(base + mm.GUN_STATS_AMMO), u32(base + mm.GUN_STATS_AMMO2))
        out.update(t for t in _stats_ammo_cache[i] if 0 < t < 0x40)
    return out


def clear_ungranted_weapons(pawn: int, allowed_slots: typing.Set[int]):
    """Take away every weapon family the player has not been granted.

    Re-applied continuously: the game hands weapons out on pickup and by script.
    Rows outside data.WEAPON_ROWS (unarmed, turrets) are never touched. Thrown and
    placed weapons are used straight from their ammo, so theirs is emptied too (unless
    a granted weapon fires the same ammo).
    """
    cleared = []
    owned = dme.read_bytes(pawn + mm.PAWN_OWNED, mm.GUN_COUNT)
    gun = dme.read_bytes(mm.GUN_TABLE, mm.GUN_COUNT * mm.GUN_STRIDE)
    keep = set()
    spent = {}                                  # ammo type -> a row of an ungranted family
    for row, slot in ROW_FAMILY.items():
        types = _row_ammo_types(gun, row)
        if slot in allowed_slots or slot in data.WEAPON_BASELINE:
            keep |= types
        elif int.from_bytes(gun[row * mm.GUN_STRIDE:row * mm.GUN_STRIDE + 4], "big") & mm.GUN_FLAGS_SPENT_FROM_AMMO:
            for t in types:
                spent.setdefault(t, row)
    for t, row in spent.items():
        if t not in keep and u16(pawn + mm.PAWN_AMMO + t * 2):
            dme.write_bytes(pawn + mm.PAWN_AMMO + t * 2, bytes(2))
            cleared.append(row)
    for row, slot in ROW_FAMILY.items():
        if slot in allowed_slots or slot in data.WEAPON_BASELINE:
            continue
        if owned[row]:
            dme.write_bytes(pawn + mm.PAWN_OWNED + row, b"\0")
            cleared.append(row)
    switched = None
    try:
        held = u32(pawn + mm.PAWN_HELD)
    except Exception:
        held = 0
    held_slot = ROW_FAMILY.get(held)
    if held_slot is not None and held_slot not in allowed_slots and held_slot not in data.WEAPON_BASELINE:
        fallback = mm.UNARMED_SLOT
        for slot in sorted(allowed_slots, reverse=True):
            row = data.WEAPON_ROWS.get(slot, (None,))[0]
            if row is not None and owned[row] and slot in data.WEAPON_COMBAT:
                fallback = row
                break
        w32(pawn + mm.PAWN_HELD, fallback)
        switched = (held, fallback)
    return cleared, switched


# --- the weapon shuffle: identity swaps on the gun tables ---------------------------
class WeaponTables:
    """Make gun X *be* gun Y by copying Y's rows over X's in the three per-gun tables.

    The pristine copy is taken from the running game once the tables look booted
    (family ids are filled at boot; the disc holds zeros), never from the disc.
    apply() writes the requested state only when it differs from the last one
    written, and restore() puts the pristine tables back.

    Restart-safe: the first snapshot of a game boot is saved to a file and tagged in
    low RAM (memmap SESSION_TAG_ADDR). A client started later in the same boot finds
    the tag and loads the saved copy instead of trusting the live tables, which an
    earlier client may have left shuffled. If the tag is there but the file is not,
    the originals cannot be known: `unrecoverable` is set and nothing is snapshotted,
    so the shuffle stays off until the game is restarted.
    """

    CACHE_DIR = os.path.join(tempfile.gettempdir(), "tsfp_ap")

    def __init__(self):
        self.pristine = None
        self.applied = None
        self.recovered = False                  # loaded from this boot's saved copy
        self.unrecoverable = False
        self.precached: typing.List[int] = []   # object types in the precache list
        self.ammo_scale: typing.Dict[int, float] = {}   # borrowed ammo type -> gain factor

    def _cache_file(self, tag: int) -> str:
        return os.path.join(self.CACHE_DIR, "weapon_tables_%08x.bin" % tag)

    def _sizes(self):
        return (mm.GUN_COUNT * mm.GUN_STRIDE, mm.GUN_COUNT * mm.GUN_UI_STRIDE, mm.GUN_COUNT * mm.GUN_ICON_STRIDE,
                mm.GUN_STATS_COUNT * 8, mm.AMMO_TYPE_COUNT * 4)

    def _session_tag(self) -> typing.Optional[int]:
        raw = dme.read_bytes(mm.SESSION_TAG_ADDR, 8)
        if raw[:4] != mm.SESSION_TAG_MAGIC:
            return None
        return int.from_bytes(raw[4:], "big")

    def _load_saved(self, tag: int) -> bool:
        try:
            with open(self._cache_file(tag), "rb") as f:
                blob = f.read()
        except OSError:
            return False
        sizes = self._sizes()
        if len(blob) != sum(sizes):
            return False
        parts, at = [], 0
        for n in sizes:
            parts.append(blob[at:at + n])
            at += n
        self.pristine = tuple(parts)
        return True

    def _save(self, tag: int) -> bool:
        try:
            os.makedirs(self.CACHE_DIR, exist_ok=True)
            with open(self._cache_file(tag), "wb") as f:
                f.write(b"".join(self.pristine))
            return True
        except OSError:
            return False

    def _read_all(self):
        ammo = b"".join(dme.read_bytes(mm.GUN_STATS + i * mm.GUN_STATS_STRIDE + mm.GUN_STATS_AMMO, 4)
                        + dme.read_bytes(mm.GUN_STATS + i * mm.GUN_STATS_STRIDE + mm.GUN_STATS_AMMO2, 4)
                        for i in range(mm.GUN_STATS_COUNT))
        return (dme.read_bytes(mm.GUN_TABLE, mm.GUN_COUNT * mm.GUN_STRIDE),
                dme.read_bytes(mm.GUN_UI_TABLE, mm.GUN_COUNT * mm.GUN_UI_STRIDE),
                dme.read_bytes(mm.GUN_ICON_TABLE, mm.GUN_COUNT * mm.GUN_ICON_STRIDE), ammo,
                b"".join(dme.read_bytes(mm.AMMO_TYPES + t * mm.AMMO_TYPE_STRIDE + mm.AMMO_TYPE_MAX, 4)
                         for t in range(mm.AMMO_TYPE_COUNT)))

    def snapshot(self) -> bool:
        if self.pristine is not None:
            return True
        if self.unrecoverable:
            return False
        try:
            tag = self._session_tag()
        except Exception:
            return False
        if tag is not None:
            # an earlier client in this boot took the snapshot: the live tables may be
            # shuffled, so only its saved copy can be trusted
            if self._load_saved(tag):
                self.recovered = True
                return True
            self.unrecoverable = True
            return False
        try:
            tables = self._read_all()
        except Exception:
            return False
        gun = tables[0]
        fam = int.from_bytes(gun[2 * mm.GUN_STRIDE + mm.GUN_FAMILY:2 * mm.GUN_STRIDE + mm.GUN_FAMILY + 4], "big")
        if fam != 2:                            # pistol's family id: filled at boot
            return False
        self.pristine = tables
        tag = random.randrange(1, 1 << 32)
        if self._save(tag):
            # the tag goes into RAM only once the file is safely written
            dme.write_bytes(mm.SESSION_TAG_ADDR, mm.SESSION_TAG_MAGIC + tag.to_bytes(4, "big"))
        return True

    def _swapped(self, remap: dict):
        gun, ui, icon, ammo, maxes = (bytearray(b) for b in self.pristine)
        pg, pu, pi = self.pristine[:3]
        for x, y in remap.items():
            if x == y or x not in data.WEAPON_ROWS or y not in data.WEAPON_ROWS:
                continue
            rx, ry = data.weapon_row_roles(x), data.weapon_row_roles(y)
            for role, row_x in rx.items():
                row_y = ry.get(role, ry.get((False, False)))
                gx, gy = row_x * mm.GUN_STRIDE, row_y * mm.GUN_STRIDE
                entry = (pg[gy:gy + mm.GUN_REQ_OFF] + pg[gx + mm.GUN_REQ_OFF:gx + mm.GUN_REQ_END]
                         + pg[gy + mm.GUN_REQ_END:gy + mm.GUN_FAMILY] + pg[gx + mm.GUN_FAMILY:gx + mm.GUN_STRIDE])
                gun[gx:gx + mm.GUN_STRIDE] = entry
                ux, uy = row_x * mm.GUN_UI_STRIDE, row_y * mm.GUN_UI_STRIDE
                ui[ux:ux + mm.GUN_UI_STRIDE] = (pu[uy:uy + mm.GUN_UI_CALLBACK]
                                               + pu[ux + mm.GUN_UI_CALLBACK:ux + mm.GUN_UI_STRIDE])
                ix, iy = row_x * mm.GUN_ICON_STRIDE, row_y * mm.GUN_ICON_STRIDE
                icon[ix:ix + mm.GUN_ICON_STRIDE] = pi[iy:iy + mm.GUN_ICON_STRIDE]
        scale = self._borrow_ammo(gun, ammo, maxes, remap)
        return (bytes(gun), bytes(ui), bytes(icon), bytes(ammo), bytes(maxes)), scale

    def _borrow_ammo(self, gun: bytearray, ammo: bytearray, maxes: bytearray, remap: dict) -> typing.Dict[int, float]:
        """Give the stats each shuffled slot borrows that slot's native ammo types (memmap
        GUN_STATS), unless a second weapon fires from the same stats (a level pin), and give
        each borrowed type the shuffled-in gun's maximum (memmap AMMO_TYPES). Returns
        {ammo type: factor} for scaling the player's gains of that type."""
        pg, pa, pm = self.pristine[0], self.pristine[3], self.pristine[4]
        scale: typing.Dict[int, float] = {}

        def most(table, t):
            return int.from_bytes(table[t * 4:t * 4 + 4], "big") if 0 < t < mm.AMMO_TYPE_COUNT else 0

        def borrow(t_native: bytes, t_gun: bytes):
            tn, tg = int.from_bytes(t_native, "big"), int.from_bytes(t_gun, "big")
            if tn in scale or tn == tg or not most(pm, tn) or not most(pm, tg):
                return
            maxes[tn * 4:tn * 4 + 4] = pm[tg * 4:tg * 4 + 4]
            scale[tn] = most(pm, tg) / most(pm, tn)

        def field(table, row, off):
            v = int.from_bytes(table[row * mm.GUN_STRIDE + off:row * mm.GUN_STRIDE + off + 4], "big")
            return v if v < mm.GUN_STATS_COUNT else None

        users: typing.Dict[int, typing.Set[int]] = {}
        for row in range(mm.GUN_COUNT):
            for off in (mm.GUN_LEFT_STATS, mm.GUN_RIGHT_STATS):
                i = field(gun, row, off)
                if i is not None:
                    users.setdefault(i, set()).add(ROW_FAMILY.get(row, -1 - row))
        for x, y in remap.items():
            if x == y or x not in data.WEAPON_ROWS or y not in data.WEAPON_ROWS:
                continue
            for row in data.WEAPON_ROWS[x]:
                native = field(pg, row, mm.GUN_RIGHT_STATS)
                if native is None:
                    continue
                own, own2 = pa[native * 8:native * 8 + 4], pa[native * 8 + 4:native * 8 + 8]
                for off in (mm.GUN_LEFT_STATS, mm.GUN_RIGHT_STATS):
                    i = field(gun, row, off)
                    if i is None or i == native or len(users.get(i, ())) != 1:
                        continue
                    borrow(own, pa[i * 8:i * 8 + 4])
                    ammo[i * 8:i * 8 + 4] = own
                    if own2 != bytes(4):
                        borrow(own2, pa[i * 8 + 4:i * 8 + 8])
                        ammo[i * 8 + 4:i * 8 + 8] = own2
        return scale

    def native_drop_models(self, ui: bytes, level_slots) -> typing.List[int]:
        """Object types the level would lose to the shuffle: the native drop model of
        each row of its own guns that no row of its guns carries any more (see memmap
        PRECACHE_BLOCK_ADDR -- level scripts spawn some of these by type)."""
        pu = self.pristine[1]

        def drop(table, row):
            off = row * mm.GUN_UI_STRIDE + mm.GUN_UI_DROP_MODEL
            return int.from_bytes(table[off:off + 4], "big")

        rows = [r for slot in sorted(level_slots) for r in data.WEAPON_ROWS.get(slot, ())]
        loaded = {drop(ui, r) for r in rows}
        out = []
        for r in rows:
            native = drop(pu, r)
            if native not in (0, 0xFFFFFFFF) and native not in loaded and native not in out:
                out.append(native)
        return out[:mm.PRECACHE_MAX_TYPES]

    def apply(self, remap: dict, key, level_slots=()) -> bool:
        """Write the tables for `remap` (identity when empty), plus the precache list of
        the level's native drop models. `key` names the state so repeated polls do not
        rewrite it. True when something was written."""
        if self.pristine is None or self.applied == key:
            return False
        (gun, ui, icon, ammo, maxes), scale = self._swapped(remap) if remap else (self.pristine, {})
        types = self.native_drop_models(ui, level_slots) if remap else []
        # the list goes in first: the level's precache must never see the swapped
        # tables without it
        dme.write_bytes(mm.PRECACHE_BLOCK_ADDR,
                        mm.PRECACHE_MAGIC + len(types).to_bytes(4, "big")
                        + b"".join(t.to_bytes(4, "big") for t in types) if types else bytes(8))
        dme.write_bytes(mm.GUN_TABLE, gun)
        dme.write_bytes(mm.GUN_UI_TABLE, ui)
        dme.write_bytes(mm.GUN_ICON_TABLE, icon)
        for i in range(mm.GUN_STATS_COUNT):
            base = mm.GUN_STATS + i * mm.GUN_STATS_STRIDE
            dme.write_bytes(base + mm.GUN_STATS_AMMO, ammo[i * 8:i * 8 + 4])
            dme.write_bytes(base + mm.GUN_STATS_AMMO2, ammo[i * 8 + 4:i * 8 + 8])
        for t in range(mm.AMMO_TYPE_COUNT):
            dme.write_bytes(mm.AMMO_TYPES + t * mm.AMMO_TYPE_STRIDE + mm.AMMO_TYPE_MAX, maxes[t * 4:t * 4 + 4])
        self.applied = key
        self.ammo_scale = scale
        self.precached = types
        return True

    def restore(self) -> bool:
        return self.apply({}, "pristine")
