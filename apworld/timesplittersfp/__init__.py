"""TimeSplitters: Future Perfect — Archipelago world (GameCube, played through Dolphin).

Locations = completing a mission on a difficulty, completing an objective, or earning a medal tier on a challenge or
Arcade League match; items = unlocking the mission/event (and the weapons, when Weapon Gating is on). The client
enforces locks by rewriting the game's own unlock requirement records in memory, and detects progress from the
profile's story bits and medal records and the live objective pool.
"""

import logging
import typing
from typing import ClassVar, Any, Dict, List, Tuple

from BaseClasses import Item, ItemClassification, Location, LocationProgressType, Region
from Options import OptionError
from settings import Bool, Group, UserFilePath
from worlds.AutoWorld import World, WebWorld
from worlds.LauncherComponents import Component, Type, components, launch

from . import data
from .options import TSFPOptions

GAME = "TimeSplitters Future Perfect"
MODE_NAMES = ("Story", "Arcade", "Challenge")
SCOPE_COMPLETELY_RANDOM, SCOPE_SAME_CLASS, SCOPE_WITHIN_LEVEL = 0, 1, 2
# slot_data schema version. Bump whenever the keys the client reads change.
SLOT_DATA_VERSION = 4
# Smallest Time Crystal gate the density clamp may leave behind (see create_items).
TC_REQUIRED_FLOOR = 7


class TSFPItem(Item):
    game = GAME


class TSFPLocation(Location):
    game = GAME


class TSFPSettings(Group):
    """Paths the client needs, remembered in host.yaml so they are asked for once."""

    class DolphinPath(UserFilePath):
        """Dolphin executable, used to launch the game."""
        is_exe = True
        description = "Dolphin Executable"

    class GamePath(UserFilePath):
        """Your TimeSplitters: Future Perfect (USA, G3FE69) disc image -- the original. The client
        writes a patched copy beside it, "<name> (AP)", and keeps that copy up to date."""
        description = "TimeSplitters: Future Perfect disc image"

    class MouseLook(Bool):
        """Mouse look: the client starts a mouse driver alongside the game (Windows). F8 turns
        capture on/off, F6/F7 lower/raise the sensitivity."""

    class MusicShuffle(str):
        """Music, applied each time the client launches the game:
        off             - the normal soundtrack
        game_music      - the level and menu music shuffled
        game_and_custom - your songs join the game's, and the level and menu music is picked from both
        custom_only     - as many of your songs as fit replace game tracks, shuffled in with the rest
        Cutscene music is never changed (it carries the dialogue). Your songs go in music_folder; put
        short stingers (mission complete, challenge won) in an "events" subfolder."""

    class MusicFolder(str):
        """Folder (or .zip) of your songs, in any common audio format. Needs ffmpeg installed (Windows:
        winget install Gyan.FFmpeg; macOS: brew install ffmpeg); each song is converted once and matched
        to the game's volume. Asked for the first time a custom mode needs it."""

    class MusicSeed(int):
        """0 shuffles the music anew every launch; any other number keeps the same shuffle."""

    class FfmpegPath(str):
        """ffmpeg executable for converting your songs. Leave empty to find it automatically."""

    class VoiceDisc(str):
        """Your own European disc image of the game (French, German, Italian or Spanish) to hear its
        voices in the randomizer: in-level dialogue and cutscenes. Any format Dolphin reads (RVZ uses the
        DolphinTool that comes with Dolphin). Empty for the English voices. Menus and subtitles stay in
        English."""

    dolphin_path: DolphinPath = DolphinPath(None)
    game_path: GamePath = GamePath(None)
    mouse_look: typing.Union[MouseLook, bool] = True
    music_shuffle: MusicShuffle = MusicShuffle("off")
    music_folder: MusicFolder = MusicFolder("")
    music_seed: MusicSeed = MusicSeed(0)
    ffmpeg_path: FfmpegPath = FfmpegPath("")
    voice_disc: VoiceDisc = VoiceDisc("")


def run_client(*args: str) -> None:
    from .client.tsfp_client import main
    launch(main, name="TimeSplittersFPClient", args=args)


components.append(Component("TimeSplitters FP Client", func=run_client, component_type=Type.CLIENT,
                            description="Connects to Archipelago and launches TimeSplitters: Future Perfect "
                                        "in Dolphin"))


class TSFPWeb(WebWorld):
    theme = "dirt"
    game_info_languages = ["en"]


class TSFPWorld(World):
    """TimeSplitters: Future Perfect (GameCube release, played through Dolphin)."""
    game = GAME
    settings: ClassVar[TSFPSettings]
    options_dataclass = TSFPOptions
    options: TSFPOptions
    web = TSFPWeb()

    item_name_to_id = data.item_name_to_id
    location_name_to_id = data.location_name_to_id
    item_name_groups = data.item_name_groups

    # ---- Universal Tracker support: regenerate from the seed's slot_data, never from default options ----
    ut_can_gen_without_yaml = True

    def _ut_passthrough(self) -> dict:
        return getattr(self.multiworld, "re_gen_passthrough", {}).get(self.game, {})

    def interpret_slot_data(self, slot_data: dict) -> dict:
        return slot_data

    def _set_modes(self, keep) -> None:
        keep = set(keep or MODE_NAMES)
        self.modes = tuple(m for m in MODE_NAMES if m in keep)
        self.story = "Story" in keep
        self.arcade = "Arcade" in keep
        self.challenge = "Challenge" in keep

    def generate_early(self) -> None:
        pt = self._ut_passthrough()
        if pt:
            self._ut = True
            self.diffs = frozenset(pt["story_difficulty_checks"])
            self.tiers = frozenset(pt["trophy_tier_checks"])
            self.goal_difficulty = pt["goal_difficulty"]
            self.gating = bool(pt["weapon_gating"])
            self.shuffle = bool(pt["weapon_shuffle"])
            self.weapon_remap = {int(k): v for k, v in pt.get("weapon_remap", {}).items()}
            self.scope = pt.get("weapon_shuffle_scope", SCOPE_COMPLETELY_RANDOM)
            self.weapon_remap_by_level = {data.STORY[int(mi)]: {int(k): v for k, v in mp.items()}
                                          for mi, mp in pt.get("weapon_remap_by_level", {}).items()
                                          if int(mi) < len(data.STORY)}
            self.tc_required = pt["time_crystals_required"]
            self.tc_total = pt["time_crystals_total"]
            self._set_modes(pt.get("game_modes"))
            self.trophy_goal_pct = pt.get("trophy_goal_percentage", 90)
            self.pickups = bool(pt.get("pickup_checks", False))
            self.tts_pickups = bool(pt.get("time_to_split_pickups", False))
            return
        self._ut = False
        keep = set(self.options.game_modes.value)
        if not keep:
            raise OptionError(f"{GAME} (player {self.player}): Game Modes is empty. Keep at least one of "
                              f"{', '.join(MODE_NAMES)}.")
        self._set_modes(keep)
        self.trophy_goal_pct = self.options.trophy_goal_percentage.value
        self.pickups = bool(self.options.pickup_checks.value)
        self.tts_pickups = self.pickups and bool(self.options.time_to_split_pickups.value)
        self.gating = bool(self.options.weapon_gating.value)
        self.shuffle = bool(self.options.weapon_shuffle.value)
        if not self.story:
            if self.gating or self.shuffle:
                logging.info("%s (player %d): Story not in Game Modes -- Weapon Gating/Shuffle forced off.",
                             GAME, self.player)
            self.gating = False
            self.shuffle = False
            self.options.weapon_gating.value = 0
            self.options.weapon_shuffle.value = 0
            self.options.trap_count.value = 0       # traps only go off in story missions
        di = self.options.story_difficulty.value
        self.diffs = frozenset(data.STORY_DIFFICULTIES[:di + 1])
        self.goal_difficulty = data.STORY_DIFFICULTIES[di]
        ti = self.options.trophy_tier.value
        self.tiers = frozenset(data.TROPHY_TIERS[:ti + 1])
        self.weapon_remap = {}
        self.weapon_remap_by_level = {}
        self.scope = self.options.weapon_shuffle_scope.value
        if self.shuffle:
            if self.scope == SCOPE_WITHIN_LEVEL:
                # levels are independent here, so each is rerolled on its own -- rerolling
                # all thirteen together until every one passed gave up on ~0.2% of seeds
                byl = {}
                for m in data.STORY:
                    for _ in range(200):
                        cand = data.weapon_remap_for_level(self.random, m)
                        if all(data.mission_coverable(m, cand, d) for d in self.diffs):
                            byl[m] = cand
                            break
                    else:
                        byl = None
                        break
                if byl is not None:
                    self.weapon_remap_by_level = byl
                else:
                    logging.warning("%s (player %d): no completable within-level weapon shuffle found -- "
                                    "using identity.", GAME, self.player)
            else:
                gen = data.weapon_remap_same_class if self.scope == SCOPE_SAME_CLASS else data.weapon_global_remap
                for _ in range(200):
                    remap = gen(self.random)
                    if all(data.mission_coverable(m, data.pin_remap(m, remap), d)
                           for m in data.STORY for d in self.diffs):
                        self.weapon_remap = remap
                        break
                else:
                    logging.warning("%s (player %d): no completable weapon shuffle found -- using identity.",
                                    GAME, self.player)

    def _remap_for(self, mission: str) -> dict:
        if self.weapon_remap_by_level:
            return self.weapon_remap_by_level.get(mission, {})
        return data.pin_remap(mission, self.weapon_remap)

    # ---- active set derived from options: list of (location_name, unit_name) ----
    def _active_locations(self) -> List[Tuple[str, str]]:
        out: List[Tuple[str, str]] = []
        for kind, _, name in data.TROPHY_EVENTS:
            if not self._kind_kept(kind):
                continue
            for t in data.TROPHY_TIERS:
                if t in self.tiers:
                    out.append((f"{data.DISPLAY_OF[name]} ({t})", data.ITEM_OF[name]))
        if self.story:
            for m in data.STORY:
                for d in data.STORY_DIFFICULTIES:
                    if d in self.diffs:
                        out.append((f"{data.DISPLAY_OF[m]} ({d})", data.ITEM_OF[m]))
            for m in data.STORY:
                for idx, name, prim, sec in data.OBJECTIVES.get(m, []):
                    if (prim | sec) & self.diffs:
                        out.append((data.objective_location_name(m, name), data.ITEM_OF[m]))
            if self.pickups:
                for ln, (m, spot) in data.PICKUP_LOC_INFO.items():
                    if m == "Time to Split" and not self.tts_pickups:
                        continue
                    if set(spot[3]) & self.diffs:
                        out.append((ln, data.ITEM_OF[m]))
        return out

    def _kind_kept(self, kind: str) -> bool:
        return self.arcade if kind == "arcade" else self.challenge

    def _trophy_event_items(self) -> List[str]:
        seen, out = set(), []
        for kind, _, name in data.TROPHY_EVENTS:
            if not self._kind_kept(kind):
                continue
            it = data.ITEM_OF[name]
            if it not in seen:
                seen.add(it)
                out.append(it)
        return out

    def _goal_trophy_eis(self) -> List[int]:
        return [i for i, (kind, _, _) in enumerate(data.TROPHY_EVENTS) if self._kind_kept(kind)]

    def _excluded(self, loc_name: str, unit: str) -> bool:
        if unit == data.FINAL_STORY_ITEM or loc_name in data.PICKUP_UNVERIFIED:
            return True
        info = data.OBJ_LOC_INFO.get(loc_name)
        if info is not None:
            return not (info[1] & self.diffs)
        return False

    def _active_units(self, active_locs) -> List[str]:
        seen, ordered = set(), []
        for unit in data.ITEM_NAMES:
            if any(u == unit for _, u in active_locs) and unit not in seen:
                seen.add(unit)
                ordered.append(unit)
        return ordered

    # ---- items ----
    tc_total = 0
    tc_required = 0
    _ut = False

    def create_item(self, name: str) -> TSFPItem:
        if name == data.FILLER_ITEM:
            classification = ItemClassification.filler
        elif name in data.TRAP_CHEATS:
            classification = ItemClassification.trap
        elif name in data.WEAPON_ITEM_NAMES:
            classification = (ItemClassification.progression if self.gating else ItemClassification.useful)
        else:
            classification = ItemClassification.progression
        return TSFPItem(name, classification, self.item_name_to_id[name], self.player)

    def get_filler_item_name(self) -> str:
        return data.FILLER_ITEM

    def create_items(self) -> None:
        active_locs = self._active_locations()
        units = self._active_units(active_locs)

        pt = self._ut_passthrough()
        if pt.get("starting_units") is not None:
            starters = [u for u in pt["starting_units"] if u in units]
        else:
            n = self.options.starting_unlocks_per_category.value
            story_units = [u for u in units if u in set(data.STORY_ITEMS) and u != data.FINAL_STORY_ITEM]
            arcade_units = [u for u in units if u in data.item_name_groups["Arcade"]]
            chal_units = [u for u in units if u in data.item_name_groups["Challenge"]]
            starters = (self.random.sample(story_units, min(n, len(story_units)))
                        + self.random.sample(arcade_units, min(n, len(arcade_units)))
                        + self.random.sample(chal_units, min(n, len(chal_units))))
        self.starters = list(starters)
        for name in starters:
            self.multiworld.push_precollected(self.create_item(name))

        pool = [self.create_item(u) for u in units if u not in starters]

        weapon_items: List[TSFPItem] = []
        self.starter_weapons: List[str] = []
        if self.gating:
            if pt.get("starting_weapons") is not None:
                starter_weapons = {w for w in pt["starting_weapons"] if w in data.WEAPON_ITEM_OF.values()}
            else:
                mission_of_item = {data.ITEM_OF[m]: m for m in data.STORY}
                starter_weapons = set()
                for st in starters:
                    m = mission_of_item.get(st)
                    if m is not None and m in data.LEVEL_PRIMARY_SLOT:
                        ps = data.LEVEL_PRIMARY_SLOT[m]
                        starter_weapons.add(data.WEAPON_ITEM_OF[self._remap_for(m).get(ps, ps)])
                if not starter_weapons:
                    starter_weapons.add(data.WEAPON_ITEM_OF[2])
            self.starter_weapons = sorted(starter_weapons)
            for it in starter_weapons:
                self.multiworld.push_precollected(self.create_item(it))
            weapon_items = [self.create_item(data.WEAPON_ITEM_OF[s]) for s in data.weapon_gated_slots()
                            if data.WEAPON_ITEM_OF[s] not in starter_weapons]
        pool += weapon_items

        if not self.story:
            if not self._ut:
                self.tc_total = 0
                self.tc_required = 0
        elif not self._ut:
            excluded = sum(1 for ln, u in active_locs if self._excluded(ln, u))
            slack = max(0, len(active_locs) - excluded - len(units) - len(weapon_items))
            cap = slack * 4 // 5
            want_required = self.options.time_crystals_required.value
            want_total = want_required + self.options.time_crystals_extra.value
            floor = min(want_required, TC_REQUIRED_FLOOR)
            self.tc_total = min(max(min(want_total, cap), floor), slack)
            self.tc_required = min(want_required, self.tc_total)
            if self.tc_total < want_total or self.tc_required < want_required:
                logging.warning("%s (player %d): Time Crystals reduced to %d placed / %d required (wanted "
                                "%d/%d) -- low check density.", GAME, self.player, self.tc_total,
                                self.tc_required, want_total, want_required)
        pool += [self.create_item(data.TIME_CRYSTAL_ITEM) for _ in range(self.tc_total)]

        # Traps take the place of filler, drawn at random from the set; trimmed if there is not room.
        traps = self.random.choices(data.TRAP_ITEMS, k=self.options.trap_count.value)
        room = len(active_locs) - len(pool)
        if len(traps) > room:
            logging.warning("%s (player %d): %d traps requested but only %d filler slots -- trimming to fit.",
                            GAME, self.player, len(traps), room)
            traps = traps[:max(0, room)]
        pool += [self.create_item(t) for t in traps]

        while len(pool) < len(active_locs):
            pool.append(self.create_item(data.FILLER_ITEM))
        self.multiworld.itempool += pool

    # ---- regions / locations ----
    def create_regions(self) -> None:
        menu = Region("Menu", self.player, self.multiworld)
        self.multiworld.regions.append(menu)
        self._unit_of = {}
        for loc_name, unit in self._active_locations():
            loc = TSFPLocation(self.player, loc_name, self.location_name_to_id[loc_name], menu)
            if self._excluded(loc_name, unit):
                loc.progress_type = LocationProgressType.EXCLUDED
            menu.locations.append(loc)
            self._unit_of[loc_name] = unit
        victory = TSFPLocation(self.player, "Victory", None, menu)
        victory.place_locked_item(TSFPItem("Victory", ItemClassification.progression, None, self.player))
        menu.locations.append(victory)

    # ---- rules ----
    def set_rules(self) -> None:
        p = self.player
        get = self.multiworld.get_location
        final = data.FINAL_STORY_ITEM
        tc = data.TIME_CRYSTAL_ITEM
        req = self.tc_required
        gating = self.gating
        sel_diffs = set(self.diffs)

        if not self.story:
            event_items = self._trophy_event_items()
            need_events = max(1, -(-len(event_items) * self.trophy_goal_pct // 100))
            self.trophy_goal_events = need_events

            def goal_rule(state) -> bool:
                return sum(1 for it in event_items if state.has(it, p)) >= need_events
        else:
            self.trophy_goal_events = 0

            def goal_rule(state) -> bool:
                return state.has(final, p) and state.has(tc, p, req)

        DORDER = ["Easy", "Normal", "Hard"]

        def make_h(mission, difficulty, state):
            def h(tok):
                if tok in data.WEAPON_GROUPS:
                    items = data.level_category_items(mission, tok, self._remap_for(mission), difficulty)
                    return bool(items) and state.has_any(items, p)
                return state.has(data.WEAPON_ITEM_OF[data.WEAPON_TOOL_SLOT[tok]], p)
            h.difficulty = difficulty
            return h

        def armed(mission, difficulty, state):
            items = data.level_early_combat_items(mission, self._remap_for(mission), difficulty)
            return bool(items) and state.has_any(items, p)

        def complete_ok(mission, difficulty, diffs, state):
            if not armed(mission, difficulty, state):
                return False
            if difficulty == "Hard":
                sec = data.LEVEL_HARD_SECONDARY.get(mission)
                if sec is not None:
                    item = data.WEAPON_ITEM_OF.get(self._remap_for(mission).get(sec, sec))
                    if item is not None and not state.has(item, p):
                        return False
            h = make_h(mission, difficulty, state)
            for idx, _name, prim, _sec in data.OBJECTIVES.get(mission, []):
                if (prim & diffs) and not data.objective_rule(mission, idx)(h):
                    return False
            return True

        misscomp = {f"{data.DISPLAY_OF[m]} ({d})": (m, d) for m in data.STORY for d in data.STORY_DIFFICULTIES}
        easiest = next((d for d in DORDER if d in sel_diffs), "Easy")

        def easiest_for(prim, sec):
            appears = (prim | sec) & sel_diffs
            return next((d for d in DORDER if d in appears), easiest)

        for loc_name, unit in self._unit_of.items():
            gate = goal_rule if unit == final else None
            info = data.OBJ_LOC_INFO.get(loc_name)
            mc = misscomp.get(loc_name)
            pk = data.PICKUP_LOC_INFO.get(loc_name)
            if gating and pk is not None:
                mission, spot = pk
                d = easiest_for(frozenset(spot[3]), frozenset())
                needs = [data.objective_rule(mission, i) for i in spot[5]]
                extra = spot[6]
                rule = (lambda state, m=mission, d=d, needs=needs, extra=extra, u=unit:
                        state.has(u, p) and armed(m, d, state)
                        and all(r(make_h(m, d, state)) for r in needs)
                        and all(make_h(m, d, state)(t) for t in extra))
            elif gating and info is not None:
                idx, prim, sec, mission = info
                d = easiest_for(prim, sec)
                if (mission, idx) in data.MISSION_COMPLETE_OBJS:
                    rule = (lambda state, m=mission, d=d, u=unit:
                            state.has(u, p) and complete_ok(m, d, frozenset({d}), state))
                else:
                    r = data.objective_rule(mission, idx)
                    rule = (lambda state, m=mission, d=d, r=r, u=unit:
                            state.has(u, p) and armed(m, d, state) and r(make_h(m, d, state)))
            elif gating and mc is not None:
                m, d = mc
                rule = (lambda state, m=m, d=d, u=unit:
                        state.has(u, p) and complete_ok(m, d, frozenset({d}), state))
            else:
                rule = (lambda state, u=unit: state.has(u, p))
            get(loc_name, p).access_rule = rule if gate is None else (
                lambda state, rule=rule, gate=gate: gate(state) and rule(state))

        if self.story and gating:
            gd = self.goal_difficulty

            def victory_rule(state) -> bool:
                return goal_rule(state) and complete_ok(data.FINAL_STORY_MISSION, gd, frozenset({gd}), state)
        else:
            victory_rule = goal_rule
        get("Victory", p).access_rule = victory_rule
        self.multiworld.completion_condition[p] = lambda state: state.has("Victory", p)

    # ---- client handshake ----
    def fill_slot_data(self) -> Dict[str, Any]:
        goal_eis = self._goal_trophy_eis()
        trophy_goal_checks = 0
        if not self.story:
            total = len(goal_eis) * len(self.tiers)
            trophy_goal_checks = max(1, -(-total * self.trophy_goal_pct // 100))
        return {
            "game_modes": list(self.modes),
            "trophy_goal_percentage": self.trophy_goal_pct,
            "trophy_goal_checks": trophy_goal_checks,
            "goal_trophy_events": goal_eis,
            "story_content": self.story,
            "time_crystals_required": self.tc_required,
            "time_crystals_total": self.tc_total,
            "story_difficulty_checks": sorted(self.diffs),
            "pickup_checks": bool(self.pickups),
            "time_to_split_pickups": bool(self.tts_pickups),
            "skip_intro_cutscenes": bool(self.options.skip_intro_cutscenes.value),
            "trophy_tier_checks": sorted(self.tiers),
            "goal_difficulty": self.goal_difficulty,
            "objective_primary": data.objective_primary_mask(),
            "weapon_gating": bool(self.gating),
            "weapon_shuffle": bool(self.shuffle),
            "weapon_item_slots": data.weapon_gated_slots(),
            "weapon_item_base": data.WEAPON_ITEM_ID_BASE,
            "weapon_shuffle_scope": self.scope,
            # slots that keep their identity in one mission (the client applies these, so
            # a newer client never changes an older seed's shuffle)
            "weapon_pins": {str(data.STORY.index(m)): sorted(s) for m, s in data.LEVEL_PINNED_SLOTS.items()}
                           if self.shuffle else {},
            "weapon_remap": {str(s): v for s, v in self.weapon_remap.items()},
            "weapon_remap_by_level": {str(data.STORY.index(m)): {str(s): v for s, v in mp.items() if v != s}
                                      for m, mp in self.weapon_remap_by_level.items()},
            "weapon_remap_readable": [f"{data.WEAPONS.get(s, s)} -> {data.WEAPONS.get(v, v)}"
                                      for s, v in sorted(self.weapon_remap.items()) if v != s],
            "weapon_remap_by_level_readable": {
                m: [f"{data.WEAPONS.get(s, s)} -> {data.WEAPONS.get(v, v)}" for s, v in sorted(mp.items()) if v != s]
                for m, mp in self.weapon_remap_by_level.items()},
            "starting_units": sorted(getattr(self, "starters", [])),
            "starting_weapons": sorted(getattr(self, "starter_weapons", [])),
            # profile preferences, written once per profile by the client; 0 = unchanged for the extras
            "preferences": {"inverse_look": int(self.options.inverse_look.value),
                            "auto_lookahead": int(self.options.auto_lookahead.value),
                            "weapon_change": int(self.options.weapon_change.value),
                            "crosshair": int(self.options.crosshair.value),
                            "auto_aim": int(self.options.auto_aim.value),
                            "aim_mode": int(self.options.aim_mode.value),
                            "crouch_mode": int(self.options.crouch_mode.value),
                            "rumble": int(self.options.rumble.value)},
            "version": SLOT_DATA_VERSION,
        }
