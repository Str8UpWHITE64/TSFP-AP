"""Archipelago client for TimeSplitters: Future Perfect (GameCube, G3FE69) running under Dolphin.

A plain Python client that reads and writes emulator memory, in the established
Archipelago GameCube style. Locks are memory writes to state the game already
consults:

* Challenges and Arcade League matches are gated by the game's own unlock
  requirement records, which it builds in RAM at boot. The client rewrites them
  ({0} locked, {1} unlocked) every poll; the menus read them when a screen is built.
* Story missions are gated by spare bits in the profile's medal bitfield, which
  the patched disc's story gate reads. The story completion bits stay the game's
  own, so progress is read straight from them.
* Weapons are families of gun-table rows. Gating clears the owned bytes of every
  family the seed has not granted; the shuffle copies one family's table rows over
  another's, so a gun *is* another gun everywhere the game looks.
"""

import asyncio
import os
import zlib
import subprocess
import sys
import time
import typing

import dolphin_memory_engine as dme

import Utils
from CommonClient import (
    ClientCommandProcessor, CommonContext, get_base_parser, gui_enabled, logger, server_loop,
)
from NetUtils import ClientStatus

from .. import data
from .. import memmap as mm
from .. import music
from .. import patcher as patch_iso
from .. import voice as voice_pack
from . import gamestate

GAME = "TimeSplitters Future Perfect"
SLOT_DATA_VERSION = 4
POLL_INTERVAL = 0.4
TRAP_IDS = [data.item_name_to_id[name] for name in data.TRAP_ITEMS]
TRAP_SECONDS = 30

# Routine detail (objectives, pickups, gating, the shuffle) goes to the log file only: the
# window shows the checks sent, the server's messages, and anything the player must act on.
FILE_ONLY = {"skip_gui": True, "NoStream": True}


def note(msg, *args):
    logger.info(msg, *args, extra=FILE_ONLY)


STORY_BASE = data.BASE_ID + 0x1400
TROPHY_BASE = data.BASE_ID + 0x1000


class TSFPCommandProcessor(ClientCommandProcessor):
    def _cmd_dolphin(self):
        """Report the emulator connection and which profile is being tracked."""
        if self.ctx.hooked:
            logger.info("Hooked to Dolphin, profile slot %s (%r)", self.ctx.profile_slot, self.ctx.profile_name)
        else:
            logger.info("Not hooked. Start Dolphin and boot TimeSplitters: Future Perfect.")

    def _cmd_use_profile(self):
        """Play this seed on the profile loaded now, even though it already has progress
        (which is then sent as checks)."""
        if not self.ctx.hooked or not self.ctx.profile_name:
            logger.info("Load the profile in the game first.")
            return
        self.ctx.force_profile = self.ctx.profile_name
        logger.info("Registering profile %r on the next poll.", self.ctx.profile_name)

    def _cmd_gate(self):
        """Show what the client currently has unlocked in game."""
        self.ctx.log_gate()

    def _cmd_launch(self):
        """Start Dolphin on the patched image (the client does this at startup too)."""
        asyncio.create_task(launch(self.ctx), name="Launch")

    def _cmd_weapons(self):
        """Show which weapons are granted and what each shuffled weapon behaves as."""
        granted = sorted(self.ctx.granted_weapons)
        logger.info("Weapons granted: %s", ", ".join(data.WEAPONS[s] for s in granted if s in data.WEAPONS) or "none")
        remap = self.ctx.weapon_remap
        if not remap and not self.ctx.weapon_remap_by_level:
            logger.info("This seed does not shuffle weapons.")
            return
        for slot, target in sorted(remap.items()):
            if slot != target and slot in data.WEAPONS and target in data.WEAPONS:
                logger.info("  %-24s is a  %s", data.WEAPONS[slot], data.WEAPONS[target])
        for mi, mp in sorted(self.ctx.weapon_remap_by_level.items()):
            for slot, target in sorted(mp.items()):
                if slot != target and slot in data.WEAPONS and target in data.WEAPONS:
                    logger.info("  %s: %-24s is a  %s", data.STORY[mi], data.WEAPONS[slot], data.WEAPONS[target])

    def _cmd_readonly(self):
        """Toggle whether the client is allowed to write to the game."""
        self.ctx.read_only = not self.ctx.read_only
        logger.info("Read-only is now %s.", "ON -- no writes" if self.ctx.read_only else "OFF -- writing")


class TSFPContext(CommonContext):
    game = GAME
    command_processor = TSFPCommandProcessor
    items_handling = 0b111

    def __init__(self, server_address, password):
        super().__init__(server_address, password)
        self.hooked = False
        self.profile_slot = 0
        self.profile_name = ""
        self.slot_data: dict = {}
        self.granted_units: typing.Set[str] = set()
        self.granted_weapons: typing.Set[int] = set()
        self.time_crystals = 0
        self.sent_locations: typing.Set[int] = set()
        self.read_only = False
        self.dolphin_process = None
        self.mouse_process = None
        self.patched = None
        self.warned_about_writing = False
        self.objectives = gamestate.ObjectiveWatcher()
        self.objective_hits: typing.Set[int] = set()
        self.pickup_hits: typing.Set[int] = set()
        self.map_areas = gamestate.MapAreas()
        self.map_area_sent = None               # (mission, area) last published for the tracker
        self.map_area_seen = None
        self.map_area_hold = 0
        # mission index -> ({.war index: location id}, [(position, kind, location id)])
        self.pickup_table = {}
        for loc_name, (m, spot) in data.PICKUP_LOC_INFO.items():
            by_war, containers = self.pickup_table.setdefault(data.STORY.index(m), ({}, []))
            loc = data.location_name_to_id[loc_name]
            if spot[7]:
                containers.append((spot[4], spot[1], loc))
            for w in spot[2]:
                by_war[w] = loc
        self.weapons = gamestate.WeaponTables()
        self.ammo_scaler = gamestate.AmmoScaler()
        self.weapon_remap: typing.Dict[int, int] = {}
        self.weapon_remap_by_level: typing.Dict[int, typing.Dict[int, int]] = {}
        self.weapon_pins: typing.Dict[int, typing.FrozenSet[int]] = {}
        self.warned_no_pawn = False
        self.no_pawn_polls = 0
        self.reported_mode = None
        self.reported_snapshot = False
        self.ever_hooked = False
        self.lost_reported = False
        self.dolphin_exit_reported = False
        self.goal_reached = False
        self.primed = False
        self.room_seed_name = None
        self.pending_profile = None     # tagged on the last poll, confirmed on this one
        self.force_profile = None       # /use_profile
        self.profile_said = None
        self.traps_received = [0] * len(TRAP_IDS)
        self.trap = None                # (index, bit, ends at, cheat state before)

    def run_gui(self):
        import logging
        import threading
        # kvui first: it sets kivy up before kivy loads (DPI awareness off; kivy's own makes the window
        # re-lay itself out endlessly), and that can only happen before the first kivy import
        from kvui import GameManager, LogtoUI
        from kivy.clock import Clock
        from kivy.metrics import dp
        from kivymd.uix.boxlayout import MDBoxLayout
        from kivymd.uix.label import MDLabel
        from kivymd.uix.progressindicator import MDLinearProgressIndicator

        def on_main_thread(fn):
            """The window's log is not thread-safe; lines from the disc preparation thread are
            handed to the main thread."""
            def call(*args):
                if threading.current_thread() is threading.main_thread():
                    fn(*args)
                else:
                    Clock.schedule_once(lambda _dt: fn(*args))
            return call

        class TSFPManager(GameManager):
            logging_pairs = [("Client", "Archipelago")]
            base_title = "Archipelago TimeSplitters: Future Perfect Client"

            def build(self):
                layout = super().build()
                # a status line and bar under the server bar while a launch prepares the disc
                self.prep_box = MDBoxLayout(orientation="vertical", size_hint_y=None, height=0, opacity=0,
                                            padding=(dp(8), 0))
                self.prep_label = MDLabel(text="", size_hint_y=None, height=dp(24))
                self.prep_bar = MDLinearProgressIndicator(size_hint_y=None, height=dp(4), max=1, value=0)
                self.prep_box.add_widget(self.prep_label)
                self.prep_box.add_widget(self.prep_bar)
                # kivy lists children last-first: this index puts it just below Archipelago's own bar
                self.grid.add_widget(self.prep_box, index=self.grid.children.index(self.progressbar))
                for name in [None] + list(logging.Logger.manager.loggerDict):
                    for handler in logging.getLogger(name).handlers:
                        if isinstance(handler, LogtoUI):
                            handler.on_log = on_main_thread(handler.on_log)
                return layout

            def show_prep(self, text, done, total):
                self.prep_box.height, self.prep_box.opacity = dp(32), 1
                self.prep_label.text = text
                self.prep_bar.max = max(1, total or 0)
                self.prep_bar.value = done or 0

            def hide_prep(self):
                self.prep_box.height, self.prep_box.opacity = 0, 0

        self.ui = TSFPManager(self)
        self.ui_task = asyncio.create_task(self.ui.async_run(), name="UI")

    def show_prep(self, text, done=None, total=None):
        """Launch progress in the window (any thread), and in the log."""
        note(text)
        if self.ui is not None and hasattr(self.ui, "prep_box"):
            from kivy.clock import Clock
            Clock.schedule_once(lambda _dt: self.ui.show_prep(text, done, total))

    def hide_prep(self):
        if self.ui is not None and hasattr(self.ui, "prep_box"):
            from kivy.clock import Clock
            Clock.schedule_once(lambda _dt: self.ui.hide_prep())

    async def server_auth(self, password_requested: bool = False):
        if password_requested and not self.password:
            await super().server_auth(password_requested)
        if not self.auth:
            await self.get_username()
        await self.send_connect()

    def on_package(self, cmd: str, args: dict):
        if cmd == "RoomInfo":
            self.room_seed_name = args.get("seed_name")     # older CommonClients keep it nowhere
        elif cmd == "Connected":
            self.slot_data = args.get("slot_data", {}) or {}
            version = self.slot_data.get("version")
            if version != SLOT_DATA_VERSION:
                logger.warning("slot_data version %s, client expects %s -- continuing.", version, SLOT_DATA_VERSION)
            for name in self.slot_data.get("starting_units", []) or []:
                self.granted_units.add(name)
            # which profiles have had the yaml preferences written, so it happens once
            self.set_notify(self.prefs_key())
            self.set_notify(self.profile_key())
            self.set_notify(self.traps_key())
            self.profile_said = None
            slot_of_item = {name: slot for slot, name in data.WEAPON_ITEM_OF.items()}
            for name in self.slot_data.get("starting_weapons") or []:
                if name in slot_of_item:
                    self.granted_weapons.add(slot_of_item[name])
            self.weapon_remap = {int(k): int(v) for k, v in (self.slot_data.get("weapon_remap") or {}).items()}
            self.weapon_remap_by_level = {
                int(mi): {int(k): int(v) for k, v in mapping.items()}
                for mi, mapping in (self.slot_data.get("weapon_remap_by_level") or {}).items()}
            self.weapon_pins = {int(mi): frozenset(int(s) for s in slots)
                                for mi, slots in (self.slot_data.get("weapon_pins") or {}).items()}
            if gamestate.UNDERIVABLE_OBJECTIVES:
                note("%d optional objective(s) are only detected live, while the client watches: %s",
                            len(gamestate.UNDERIVABLE_OBJECTIVES), ", ".join(sorted(gamestate.UNDERIVABLE_OBJECTIVES)))
            self.primed = False
        elif cmd == "ReceivedItems":
            before = (len(self.granted_units), len(self.granted_weapons), self.time_crystals)
            for item in args["items"]:
                self.handle_item(item.item)
            ids = [item.item for item in self.items_received]
            self.traps_received = [ids.count(i) for i in TRAP_IDS]
            after = (len(self.granted_units), len(self.granted_weapons), self.time_crystals)
            if after != before:
                note("Received %d item(s): %d unlock(s), %d weapon(s), %d Time Crystal(s) held.",
                            len(args["items"]), *after)
                self.log_gate(note)

    # ---- items -----------------------------------------------------------
    def handle_item(self, item_id: int):
        if item_id == data.item_name_to_id.get(data.TIME_CRYSTAL_ITEM):
            self.time_crystals += 1
            return
        index = item_id - data.BASE_ID
        weapon_slot = index - data.WEAPON_ITEM_ID_BASE
        if weapon_slot in data.WEAPONS:
            self.granted_weapons.add(weapon_slot)
            return
        if 0 <= index < len(data.UNIT_NAMES):
            self.granted_units.add(data.UNIT_NAMES[index])

    def granted_events(self) -> typing.Set[int]:
        return {i for i, name in enumerate(data.TROPHY_EVENT_NAMES) if name in self.granted_units}

    def granted_missions(self) -> typing.Set[int]:
        """Missions to open. The final one also waits for the Time Crystals: clearing it early would not
        count for the goal, and the player would only have to play it again."""
        need = self.slot_data.get("time_crystals_required", 0)
        return {mi for mi, m in enumerate(data.STORY) if m in self.granted_units
                and (m != data.FINAL_STORY_MISSION or self.time_crystals >= need)}

    # ---- emulator --------------------------------------------------------
    def ensure_hooked(self) -> bool:
        was = self.hooked
        self.hooked = gamestate.hook()
        if self.hooked and not was:
            note("Hooked to Dolphin running %s.", mm.GAME_ID)
            self.ever_hooked = True
            self.lost_reported = False
        if (self.dolphin_process is not None and self.dolphin_process.poll() is not None
                and not self.dolphin_exit_reported):
            self.dolphin_exit_reported = True
            logger.warning("Dolphin has closed. Restart this client to play again -- it launches the game fresh.")
        elif not self.hooked and self.ever_hooked and not self.lost_reported:
            self.lost_reported = True
            logger.warning("Lost the game. If it crashed or was stopped, close Dolphin and restart this client: "
                           "it launches the game fresh. Restart both together whenever either one crashes.")
        return self.hooked

    def profile_base(self) -> typing.Optional[int]:
        addr = gamestate.profile_base(self.profile_slot)
        if addr is not None:
            try:
                self.profile_name = gamestate.profile_name(self.profile_slot)
            except Exception:
                return None
        return addr

    # ---- which profile is this seed's ----------------------------------------
    # A seed is played on one profile, claimed by a tag in its save data. Only a profile
    # with no progress is claimed on its own, so a profile played outside this seed never
    # has its clears and medals sent as this seed's checks.
    def profile_key(self):
        return "tsfp_profile_%s_%s" % (self.team, self.slot)

    def seed_tag(self) -> typing.Optional[int]:
        seed = self.room_seed_name or getattr(self, "server_seed_name", None) or self.seed_name
        if not seed or self.slot is None:
            return None
        return zlib.crc32(("%s|%s|%s" % (seed, self.team, self.slot)).encode()) or 1

    def say_profile(self, key, msg, *args, warn=False):
        if key != self.profile_said:
            self.profile_said = key
            (logger.warning if warn else logger.info)(msg, *args)

    def seed_profile_hint(self) -> str:
        name = self.stored_data.get(self.profile_key())
        return " This seed's profile is %r." % name if name else ""

    async def registered(self, name: str):
        await self.send_msgs([{"cmd": "Set", "key": self.profile_key(), "default": "", "want_reply": False,
                               "operations": [{"operation": "replace", "value": name}]}])

    async def check_profile(self, profile: int) -> bool:
        """True when the profile loaded is this seed's (claiming a fresh one)."""
        tag = self.seed_tag()
        if tag is None:
            self.say_profile(("no seed",), "Waiting for the server's seed name before checking the profile.")
            return False
        gamedata = profile + mm.GAMEDATA_OFF
        name = self.profile_name
        have = gamestate.profile_tag(gamedata)
        if self.force_profile is not None:
            forced, self.force_profile = self.force_profile, None
            if forced != name or gamestate.is_default_profile(name):
                logger.info("Not registered: load your own profile and try /use_profile again.")
                return False
            if not self.read_only:
                gamestate.set_profile_tag(gamedata, tag)
            self.pending_profile = None
            self.say_profile(("ours", name), "Profile %r registered to this seed; its existing progress is sent "
                             "as checks.", name)
            await self.registered(name)
            return True
        used = gamestate.profile_has_progress(gamedata)
        if have == tag:
            if self.pending_profile == name:
                self.pending_profile = None
                if used:
                    # a card profile loaded over the one just claimed: let it go
                    if not self.read_only:
                        gamestate.set_profile_tag(gamedata, 0)
                    return False
                self.say_profile(("ours", name), "Profile %r registered to this seed. Play this seed on it; "
                                 "other profiles are ignored.", name)
                await self.registered(name)
            self.say_profile(("ours", name), "Playing on profile %r (this seed's).", name)
            return True
        was_pending, self.pending_profile = self.pending_profile == name, None
        if gamestate.is_default_profile(name):
            self.say_profile(("default",), "Waiting for a profile. In the game, create a NEW profile for this seed "
                             "(or load the one you made for it) -- the client registers it by itself.%s",
                             self.seed_profile_hint())
        elif have == 0 and not used:
            if was_pending:
                self.say_profile(("lost", name), "Could not register profile %r: the game did not keep the "
                                 "client's mark. Please report this.", name, warn=True)
            if self.read_only:
                self.say_profile(("ours", name), "Playing on profile %r (read-only: not registered).", name)
                return True
            gamestate.set_profile_tag(gamedata, tag)
            self.pending_profile = name
        elif have:
            self.say_profile(("other", name), "Profile %r belongs to a different seed, so it is ignored. Create a "
                             "new profile for this seed.%s", name, self.seed_profile_hint(), warn=True)
        else:
            self.say_profile(("used", name), "Profile %r already has progress, so it is ignored: nothing is sent "
                             "or unlocked on it. Create a new profile for this seed.%s To play this seed on %r "
                             "anyway and send its progress as checks, type /use_profile.",
                             name, self.seed_profile_hint(), name, warn=True)
        return False

    # ---- reading progress -> checks --------------------------------------
    def seed_from_server(self):
        self.sent_locations |= set(self.checked_locations)
        self.primed = True
        note("Restored progress from the server: %d checks already recorded.", len(self.checked_locations))

    async def publish_map_area(self):
        """Tell a map tracker which mission and map area the player is in (data storage
        key tsfp_map_<team>_<slot>), once it has held for two polls."""
        mission = gamestate.current_mission()
        if mission is None or self.slot is None:
            return
        area = self.map_areas.area(mission, gamestate.player_position())
        if area is None:
            return
        cur = (mission, area)
        if cur != self.map_area_seen:
            self.map_area_seen, self.map_area_hold = cur, 0
            return
        self.map_area_hold += 1
        if self.map_area_hold < 1 or cur == self.map_area_sent:
            return
        self.map_area_sent = cur
        await self.send_msgs([{"cmd": "Set", "key": "tsfp_map_%d_%d" % (self.team or 0, self.slot),
                               "default": {}, "want_reply": False,
                               "operations": [{"operation": "replace",
                                               "value": {"mission": mission, "area": area}}]}])

    def collect_pickup_checks(self) -> typing.Set[int]:
        """Health/armour pickups taken in the story mission now loaded (when the seed has
        them): placed ones by their .war index, container drops by where they appeared."""
        if not self.slot_data.get("pickup_checks"):
            return set()
        mission = gamestate.current_mission()
        if mission is None:
            return set()
        name = data.STORY[mission]
        if name == "Time to Split" and not self.slot_data.get("time_to_split_pickups"):
            return set()
        by_war, containers = self.pickup_table.get(mission, ({}, []))
        found = set()
        for idx, kind, pos in gamestate.taken_pickups():
            if idx is not None:
                loc = by_war.get(idx)
            else:
                near = [(sum((a - b) ** 2 for a, b in zip(pos, cpos)), loc) for cpos, ckind, loc in containers
                        if ckind == kind]
                near.sort()
                loc = near[0][1] if near and near[0][0] <= 2.5 ** 2 else None
            if loc is not None:
                if loc not in self.sent_locations and loc not in self.pickup_hits:
                    note("Pickup taken: %s", gamestate.LOCATION_NAME.get(loc, loc))
                self.pickup_hits.add(loc)
                found.add(loc)
        return found

    def collect_objective_checks(self, gamedata: int) -> typing.Set[int]:
        newly, _ = self.objectives.poll()
        for loc in sorted(newly - self.objective_hits):
            note("Objective completed: %s", gamestate.LOCATION_NAME.get(loc, loc))
        self.objective_hits |= newly
        found = set(self.objective_hits)
        for mission_index, entries in gamestate.OBJECTIVES_BY_MISSION.items():
            cleared = gamestate.story_cleared_mask(gamedata, mission_index)
            if cleared:
                for loc_id, mask in entries:
                    if mask & cleared and loc_id not in found:
                        if loc_id not in self.sent_locations:
                            note("Objective implied by the mission clear (never seen live): %s",
                                        gamestate.LOCATION_NAME.get(loc_id, loc_id))
                        found.add(loc_id)
        return found

    # ---- writing the gate ------------------------------------------------
    def apply_gate(self, profile: int):
        if self.read_only:
            return
        if not self.warned_about_writing:
            self.warned_about_writing = True
            note("Applying Archipelago lock state to profile %r.", self.profile_name)
        gamestate.clear_unlock_overrides(keep_extras=self.trap is not None)
        gamestate.apply_event_gate(self.granted_events())
        if self.patched and self.patched[0]:
            for g in gamestate.gamedata_blocks(profile):
                gamestate.apply_story_gate(g, self.granted_missions())
        self.apply_weapons()
        self.apply_weapon_gating()
        self.scale_ammo()
        gamestate.set_skip_intro(bool(self.slot_data.get("skip_intro_cutscenes")))

    def prefs_key(self):
        return "tsfp_prefs_%s_%s" % (self.team, self.slot)

    def apply_preferences(self, profile: int):
        """Write the yaml's profile preferences, once per profile.

        Only once the player is actually in a level: at boot the game fills slot 0 with a
        default "Player 1" profile until the card profile loads, and a write to that
        placeholder would be wiped by the load -- and then never retried, since the name
        would already be recorded as done. Gameplay reads the profile directly, so a
        write here takes effect at once.

        Inverse Look, Auto Lookahead and Weapon Change are always written, as on TS2. The
        other preferences are written only when the yaml asks for something other than
        "unchanged" (0), so a profile the player has already set up keeps its own choices.
        """
        prefs = self.slot_data.get("preferences")
        if not prefs or self.read_only:
            return
        if self.prefs_key() not in self.stored_data:
            return                              # not heard back from the server yet
        done = self.stored_data[self.prefs_key()] or {}   # an unset key comes back as None
        if not self.profile_name or self.profile_name in done:
            return
        if gamestate.player_pawn() is None:
            return                              # not in a level yet: maybe still the boot placeholder
        flags = gamestate.u32(profile + mm.PROFILE_PREF_FLAGS_OFF)

        def put(bit, on):
            return (flags | bit) if on else (flags & ~bit)

        flags = put(mm.PREF_INVERSE_LOOK, prefs.get("inverse_look"))
        flags = put(mm.PREF_AUTO_LOOKAHEAD, prefs.get("auto_lookahead"))
        extras = []
        if prefs.get("auto_aim"):
            flags = put(mm.PREF_AUTO_AIM, prefs["auto_aim"] == 2)
            extras.append("Auto Aim " + ("on" if prefs["auto_aim"] == 2 else "off"))
        if prefs.get("aim_mode"):
            flags = put(mm.PREF_AIM_TOGGLE, prefs["aim_mode"] == 2)
            extras.append("Aim Mode " + ("toggle" if prefs["aim_mode"] == 2 else "hold"))
        if prefs.get("crouch_mode"):
            flags = put(mm.PREF_CROUCH_TOGGLE, prefs["crouch_mode"] == 2)
            extras.append("Crouch " + ("toggle" if prefs["crouch_mode"] == 2 else "hold"))
        if prefs.get("rumble"):
            bits = {1: 0, 2: mm.PREF_RUMBLE | mm.PREF_RUMBLE_FIRE, 3: mm.PREF_RUMBLE | mm.PREF_RUMBLE_HIT,
                    4: mm.PREF_RUMBLE_MASK}[prefs["rumble"]]
            flags = (flags & ~mm.PREF_RUMBLE_MASK) | bits
            extras.append("Rumble " + {1: "off", 2: "fire", 3: "hit", 4: "fire and hit"}[prefs["rumble"]])
        change = int(prefs.get("weapon_change", 1))
        gamestate.w32(profile + mm.PROFILE_PREF_FLAGS_OFF, flags)
        gamestate.w32(profile + mm.PROFILE_WEAPON_CHANGE_OFF, change)
        if prefs.get("crosshair"):
            gamestate.w32(profile + mm.PROFILE_CROSSHAIR_OFF, prefs["crosshair"] - 1)
            extras.append("Crosshair " + {1: "off", 2: "on and moving", 3: "on and fixed"}[prefs["crosshair"]])
        self.stored_data[self.prefs_key()] = dict(done, **{self.profile_name: True})
        asyncio.create_task(self.send_msgs([{
            "cmd": "Set", "key": self.prefs_key(), "default": {}, "want_reply": True,
            "operations": [{"operation": "update", "value": {self.profile_name: True}}]}]))
        names = {0: "always", 1: "never", 2: "best", 3: "if new", 4: "if new and best"}
        logger.info("Preferences written to profile %r: Inverse Look %s, Auto Lookahead %s, Weapon Change %s%s. "
                    "Change them in the game whenever you like; they will not be written again.",
                    self.profile_name, "on" if prefs.get("inverse_look") else "off",
                    "on" if prefs.get("auto_lookahead") else "off", names.get(change, change),
                    "".join(", " + e for e in extras))

    # ---- traps -----------------------------------------------------------
    def traps_key(self):
        return "tsfp_traps_%s_%s" % (self.team, self.slot)

    def apply_traps(self):
        """One trap at a time, TRAP_SECONDS each, in story missions only.

        Serial on purpose: on TS2, Big Heads and Small Heads together crash the game. A
        trap received elsewhere waits for the next story mission; leaving the mission ends
        the running one early, and it still counts as delivered. How many of each have
        gone off is kept on the server, so a restarted client does not repeat them.
        """
        if self.read_only or self.traps_key() not in self.stored_data:
            return
        done = list(self.stored_data[self.traps_key()] or [])[:len(TRAP_IDS)]
        done += [0] * (len(TRAP_IDS) - len(done))
        in_story = gamestate.current_mission() is not None and gamestate.player_pawn() is not None
        if self.trap is not None:
            index, bit, ends, before = self.trap
            if time.monotonic() < ends and in_story:
                gamestate.cheat_on(bit)
                return
            gamestate.cheat_off(bit, before)
            self.trap = None
            done[index] += 1
            self.stored_data[self.traps_key()] = done
            asyncio.create_task(self.send_msgs([{
                "cmd": "Set", "key": self.traps_key(), "default": [], "want_reply": True,
                "operations": [{"operation": "replace", "value": done}]}]))
            note("%s is over.", data.TRAP_ITEMS[index])
            return
        if not in_story:
            return
        for index, name in enumerate(data.TRAP_ITEMS):
            if done[index] < self.traps_received[index]:
                bit = data.TRAP_CHEATS[name]
                self.trap = (index, bit, time.monotonic() + TRAP_SECONDS, gamestate.cheat_state(bit))
                gamestate.cheat_on(bit)
                logger.info("%s! (%d seconds)", name, TRAP_SECONDS)
                return

    def end_trap(self):
        """Take a running trap's cheat away, e.g. when the client closes."""
        if self.trap is not None and self.hooked:
            try:
                gamestate.cheat_off(self.trap[1], self.trap[3])
            except Exception:
                pass
        self.trap = None

    def remap_for(self, mission: typing.Optional[int]) -> dict:
        if self.weapon_remap_by_level:
            return self.weapon_remap_by_level.get(mission, {}) if mission is not None else {}
        pins = self.weapon_pins.get(mission)
        if not pins:
            return self.weapon_remap
        remap = dict(self.weapon_remap)
        for s in pins:
            remap[s] = s                        # keeps its identity in this mission (see data.py)
        return remap

    def apply_weapons(self):
        """Hold the shuffled tables while the game is committed to a story mission, the
        pristine ones everywhere else (Arcade and Challenge keep native weapons)."""
        if not self.slot_data.get("weapon_shuffle"):
            return
        if not self.weapons.snapshot():
            if self.weapons.unrecoverable and not self.reported_snapshot:
                self.reported_snapshot = True
                logger.warning("The weapon tables in this game session were already changed by an earlier client, "
                               "and its saved copy of the originals is gone, so the weapon shuffle is OFF until "
                               "the game is restarted. Close Dolphin and restart this client to fix it.")
            return
        if not self.reported_snapshot:
            self.reported_snapshot = True
            if self.weapons.recovered:
                note("Weapon tables recovered from this game session's saved originals; the shuffle "
                            "carries on as before.")
            else:
                note("Weapon tables snapshotted; the seed's shuffle will be applied as story missions start.")
        # The story flow sets the mode byte to 10 when its first load is set up --
        # seconds before any mission's asset pass -- and every other load sets its own
        # value first, so the tables are shuffled exactly while the game is in Story.
        # The story menu (front end with the story screens open) counts too, which is
        # harmless there and gives the shuffle the longest possible lead.
        mission = gamestate.current_mission()
        in_story = gamestate.in_story() or (gamestate.current_level() == mm.FRONT_END_LEVEL
                                            and gamestate.menu_selected_mission() is not None)
        if mission is None and in_story:
            mission = gamestate.menu_selected_mission()
        if mission is None or not in_story:
            if self.weapons.restore():
                note("Weapon tables restored to native (not in Story).")
            return
        remap = self.remap_for(mission)
        key = ("story", mission if (self.weapon_remap_by_level or mission in self.weapon_pins) else "global")
        if self.weapons.apply(remap, key, data.LEVEL_WEAPON_SLOTS.get(data.STORY[mission], ())):
            changed = [f"{data.WEAPONS[s]} -> {data.WEAPONS[t]}" for s, t in sorted(remap.items())
                       if s != t and s in data.WEAPONS and t in data.WEAPONS]
            note("Weapon shuffle applied for %s: %s", data.STORY[mission], ", ".join(changed) or "identity")
            if self.weapons.precached and self.patched and not self.patched[3]:
                logger.warning("This disc lacks the gun precache patch: a level script that spawns one of the "
                               "level's own guns can freeze the game. Close Dolphin and restart this client "
                               "to re-patch it.")

    def scale_ammo(self):
        """Under the shuffle, turn ammo gains into the shuffled-in gun's share (AmmoScaler)."""
        scale = self.weapons.ammo_scale
        pawn = gamestate.player_pawn() if scale and gamestate.current_mission() is not None else None
        if pawn is None:
            self.ammo_scaler.reset()
            return
        self.ammo_scaler.poll(pawn, scale)

    def allowed_weapon_slots(self) -> typing.Set[int]:
        """Families the player may hold: a slot yields whatever the shuffle maps it to."""
        remap = self.remap_for(gamestate.current_mission())
        allowed = set(data.WEAPON_BASELINE)
        for slot in data.WEAPONS:
            yields = remap.get(slot, slot)
            if yields in self.granted_weapons or yields in data.WEAPON_BASELINE:
                allowed.add(slot)
        return allowed

    def apply_weapon_gating(self):
        if not self.slot_data.get("weapon_gating"):
            return
        if gamestate.current_mission() is None:
            return
        pawn = gamestate.player_pawn()
        if pawn is None:
            # normal for a few polls while the level is still loading
            self.no_pawn_polls += 1
            if self.no_pawn_polls == 25 and not self.warned_no_pawn:
                self.warned_no_pawn = True
                logger.warning("In a story mission but no player pawn was found; weapon gating is not running.")
            return
        self.no_pawn_polls = 0
        self.warned_no_pawn = False
        cleared, switched = gamestate.clear_ungranted_weapons(pawn, self.allowed_weapon_slots())
        if cleared:
            names = sorted({self.describe_slot(gamestate.ROW_FAMILY[r]) for r in cleared})
            note("Weapon gating removed: %s", ", ".join(names))
        if switched:
            note("Weapon gating: was holding %s, switched to %s",
                        self.describe_slot(gamestate.ROW_FAMILY.get(switched[0], switched[0])),
                        self.describe_slot(gamestate.ROW_FAMILY.get(switched[1], switched[1])))

    def describe_slot(self, slot):
        """A weapon as the player sees it: under a shuffle, the weapon that slot has become."""
        name = data.WEAPONS.get(slot, "unarmed" if slot in (0, 1) else "row %s" % slot)
        target = self.remap_for(gamestate.current_mission()).get(slot, slot)
        if target != slot and target in data.WEAPONS:
            return "%s (in the %s's place)" % (data.WEAPONS[target], name)
        return name

    def log_gate(self, log=None):
        log = log or logger.info
        missions = sorted(self.granted_missions())
        log("Story open: %s", ", ".join(data.STORY[mi] for mi in missions) or "none")
        events = sorted(self.granted_events())
        log("Challenges/Arcade granted: %s", ", ".join(data.TROPHY_EVENT_NAMES[e] for e in events) or "none")
        if self.read_only:
            log("(read-only: this state is NOT being written to the game)")

    # ---- goal ------------------------------------------------------------
    def goal_met(self, gamedata: int) -> bool:
        if not self.slot_data.get("story_content", True):
            need = self.slot_data.get("trophy_goal_checks", 0)
            eis = set(self.slot_data.get("goal_trophy_events") or [])
            done = sum(1 for loc in self.sent_locations
                       if TROPHY_BASE <= loc < TROPHY_BASE + 48 * 4 and (loc - TROPHY_BASE) // 4 in eis)
            return need > 0 and done >= need
        if self.time_crystals < self.slot_data.get("time_crystals_required", 0):
            return False
        goal_difficulty = self.slot_data.get("goal_difficulty", "Easy")
        di = data.STORY_DIFFICULTIES.index(goal_difficulty) if goal_difficulty in data.STORY_DIFFICULTIES else 0
        return bool(gamestate.story_words(gamedata)[di] >> (len(data.STORY) - 1) & 1)

    async def shutdown(self):
        self.end_trap()
        if self.dolphin_process is not None and self.dolphin_process.poll() is None:
            logger.info("Closing the Dolphin instance this client started.")
            try:
                self.dolphin_process.terminate()
            except Exception:
                pass
        await super().shutdown()


async def game_loop(ctx: TSFPContext):
    logger.info("Waiting for Dolphin running %s...", mm.GAME_ID)
    reported_errors: typing.Set[str] = set()
    while not ctx.exit_event.is_set():
        await asyncio.sleep(POLL_INTERVAL)
        try:
            if not ctx.ensure_hooked():
                continue
            if ctx.server is None or ctx.slot is None:
                continue
            if not ctx.primed:
                ctx.seed_from_server()
            profile = ctx.profile_base()
            if profile is None:
                continue
            patched = (gamestate.story_patch_present(), gamestate.mount_patch_present(),
                       gamestate.sequencer_patch_present(), gamestate.precache_patch_present(),
                       gamestate.camera_patch_present(), gamestate.skip_intro_patch_present())
            if patched != ctx.patched:
                ctx.patched = patched
                if all(patched):
                    note("Fully patched image: every mission can be locked, Story mounts every gun, "
                                "levels precache their own guns under the shuffle, the camera survives level "
                                "transitions, missions return to the menu, and intros can be skipped.")
                else:
                    missing = [m for m, ok in zip(("story gate", "gun pak mount", "menu return", "gun precache",
                                                   "camera guard", "intro skip"),
                                                  patched) if not ok]
                    logger.warning("Partly stock image -- missing: %s. Close Dolphin and restart this client: it patches "
                                   "a copy of the disc for you.",
                                   ", ".join(missing))
            if not await ctx.check_profile(profile):
                continue
            mission = gamestate.current_mission()
            level = gamestate.current_level()
            if (level, mission) != ctx.reported_mode:
                ctx.reported_mode = (level, mission)
                if mission is not None:
                    note("%s loaded (Story).", data.STORY[mission])
            gamedata = profile + mm.GAMEDATA_OFF
            found = (gamestate.trophy_checks(gamedata) | gamestate.story_checks(gamedata)
                     | ctx.collect_objective_checks(gamedata) | ctx.collect_pickup_checks())
            new = found - ctx.sent_locations
            if new:
                ctx.sent_locations |= new
                await ctx.send_msgs([{"cmd": "LocationChecks", "locations": sorted(new)}])
                logger.info("Sent %d new check(s): %s", len(new),
                            ", ".join(gamestate.LOCATION_NAME.get(l, str(l)) for l in sorted(new)))
            ctx.apply_gate(profile)
            ctx.apply_preferences(profile)
            ctx.apply_traps()
            await ctx.publish_map_area()
            if not ctx.goal_reached and ctx.goal_met(gamedata):
                ctx.goal_reached = True
                await ctx.send_msgs([{"cmd": "StatusUpdate", "status": ClientStatus.CLIENT_GOAL}])
                logger.info("Goal complete!")
        except Exception as exc:
            key = repr(exc)
            if key not in reported_errors:
                reported_errors.add(key)
                logger.exception("Poll failed (further identical failures will be quiet): %s", exc)
            ctx.hooked = False


# ---------------------------------------------------------------------------
# Launching the game
# ---------------------------------------------------------------------------

def _settings():
    try:
        from settings import get_settings
        return get_settings().timesplittersfp_options
    except Exception:
        return None


# Every patched image carries the optional mouse-look hook too: it does nothing unless the
# mouse driver is running, so one image serves everyone (mouse_look in host.yaml decides).
ALL_PATCHES = patch_iso.PATCHES + [p for p in patch_iso.MOUSE_PATCHES if p not in patch_iso.PATCHES]


def ensure_patched(image_path, as_iso=False):
    """Return a fully patched image to run, patching a copy if need be. as_iso: the copy must be a
    plain ISO (voice packs need its free space), whatever the original's format."""

    def missing_patches(path):
        image = patch_iso.Image(path)
        try:
            dol = patch_iso.dol_offset(image)
            return [description for ram, original, patched, description in ALL_PATCHES
                    if patch_iso.words_at(image, patch_iso.ram_to_disc(image, dol, ram), len(original)) != patched]
        finally:
            image.close()

    try:
        missing = missing_patches(image_path)
    except SystemExit as exc:
        logger.error("%s", exc)
        return image_path
    with open(image_path, "rb") as f:
        compressed = f.read(4) != b"G3FE"
    need_iso = as_iso and compressed
    if not missing and not need_iso:
        note("Image is fully patched.")
        return image_path
    stem, ext = os.path.splitext(image_path)
    # the image chosen may itself be a copy this client wrote earlier ("... (AP)"): update it
    # rather than writing "(AP) (AP)" beside it
    if need_iso:
        patched_path = (stem[:-len(" (AP)")] if stem.endswith(" (AP)") else stem) + " (AP).iso"
    else:
        patched_path = image_path if stem.endswith(" (AP)") else stem + " (AP)" + ext
    if os.path.exists(patched_path):
        try:
            if not missing_patches(patched_path):
                note("Using the patched image beside it: %s", os.path.basename(patched_path))
                return patched_path
            logger.info("%s is from an earlier version; updating it.", os.path.basename(patched_path))
            patch_iso.apply(patched_path, patched_path, patches=ALL_PATCHES, in_place=True)
            return patched_path
        except (SystemExit, OSError) as exc:
            if patched_path == image_path:
                logger.error("Patching failed: %s -- if Dolphin is still running on it, close it and retry.", exc)
                return None
            logger.info("Could not update it (%s); writing a fresh copy.", exc)
    logger.info("Writing a patched copy to %s (%d patch(es))%s", os.path.basename(patched_path), len(ALL_PATCHES),
                " as a plain ISO, for the voice pack" if need_iso else "")
    try:
        patch_iso.apply(image_path, patched_path, patches=ALL_PATCHES, as_iso=need_iso)
    except (SystemExit, OSError) as exc:
        logger.error("Patching failed: %s -- if Dolphin is still running on the old copy, close it and retry.", exc)
        return None
    return patched_path


def _ask_path(title, filetypes):
    """A file picker, for the first run (the choice is saved to host.yaml)."""
    try:
        return Utils.open_filename(title, filetypes) or None
    except Exception as exc:
        note("no file dialog: %r", exc)
        return None


async def launch(ctx, dolphin=None, game=None):
    """Ask for anything missing, prepare the disc copy off the main thread (the window stays up and
    shows the progress), then start Dolphin on it."""
    chosen = choose_launch(dolphin, game)
    if chosen is None:
        return
    settings, dolphin, game = chosen
    try:
        patched = await asyncio.to_thread(prepare_disc, ctx, settings, dolphin, game)
    finally:
        ctx.hide_prep()
    if patched is not None and not ctx.exit_event.is_set():
        ctx.dolphin_process = start_game(ctx, settings, dolphin, patched)
        ctx.dolphin_exit_reported = False


def choose_launch(dolphin=None, game=None):
    """Dolphin, the disc and the music folder, asked for on the main thread (the file dialogs need it)
    before any slow work. Returns (settings, dolphin, game), or None if something was not chosen."""
    settings = _settings()
    dolphin = dolphin or (getattr(settings, "dolphin_path", None) if settings else None)
    game = game or (getattr(settings, "game_path", None) if settings else None)
    if not dolphin or not os.path.isfile(str(dolphin)):
        dolphin = _ask_path("Select Dolphin (Dolphin.exe)", [("Dolphin", [".exe"]), ("Any file", ["*"])])
    if not game or not os.path.isfile(str(game)):
        game = _ask_path("Select your TimeSplitters: Future Perfect (USA) disc image",
                         [("GameCube disc image", [".iso", ".gcm", ".ciso", ".rvz"]), ("Any file", ["*"])])
    missing = []
    if not dolphin or not os.path.isfile(str(dolphin)):
        missing.append("Dolphin")
    if not game or not os.path.isfile(str(game)):
        missing.append("the disc image")
    if missing:
        logger.error("Not launching: %s not chosen. Restart the client to pick it, or set dolphin_path and "
                     "game_path under timesplittersfp_options in host.yaml. To use a Dolphin you started "
                     "yourself, run the client with --no-launch.", " and ".join(missing))
        return None
    if str(game).lower().endswith(".rvz"):
        logger.error("RVZ images cannot be patched. Convert it to ISO in Dolphin (right-click the game, "
                     "Convert File...) and choose that instead.")
        return None
    if settings is not None:
        try:
            settings.dolphin_path = str(dolphin)
            settings.game_path = str(game)          # the original: the patched copy is kept beside it
            from settings import get_settings
            get_settings().save()
        except Exception as exc:
            note("could not save settings: %r", exc)
    ask_music_folder(settings)
    return settings, str(dolphin), str(game)


def music_mode(settings):
    mode = str(getattr(settings, "music_shuffle", "off") or "off") if settings is not None else "off"
    if mode not in music.MODES:
        logger.warning("Unknown music_shuffle %r in host.yaml; using off. Choices: %s", mode, ", ".join(music.MODES))
        mode = "off"
    return mode


def ask_music_folder(settings):
    """Your songs' folder, asked for the first time a mode needs one, and remembered as music_folder."""
    if music_mode(settings) not in ("game_and_custom", "custom_only"):
        return
    if os.path.exists(str(getattr(settings, "music_folder", "") or "")):
        return
    try:
        folder = Utils.open_directory("Select the folder with your songs for the music shuffle") or ""
    except Exception as exc:
        note("no folder dialog: %r", exc)
        folder = ""
    if folder:
        try:
            settings.music_folder = folder
            from settings import get_settings
            get_settings().save()
        except Exception as exc:
            note("could not save settings: %r", exc)


def prepare_disc(ctx, settings, dolphin, game):
    """The slow part of a launch, run off the main thread so the window stays up: patch the copy, then
    write this launch's music and voices into it. Returns the image to boot, or None."""
    voices_wanted = bool(str(getattr(settings, "voice_disc", "") or "")) if settings is not None else False
    ctx.show_prep("Patching your disc copy...")
    patched = ensure_patched(game, as_iso=voices_wanted)
    if patched is None:
        return None
    apply_disc_content(ctx, settings, str(patched), dolphin)
    return str(patched)


def start_game(ctx, settings, dolphin, patched):
    logger.info("Launching %s", os.path.basename(patched))
    try:
        proc = subprocess.Popen([dolphin, "--exec=%s" % patched, "--batch"])
    except Exception as exc:
        logger.error("Could not start Dolphin: %s", exc)
        return None
    if settings is None or bool(getattr(settings, "mouse_look", True)):
        ctx.mouse_process = start_mouse()
    return proc


def apply_disc_content(ctx, settings, image, dolphin):
    """This launch's music (host.yaml music_shuffle) and voices (voice_disc), written into the patched
    copy before boot."""
    mode = music_mode(settings)
    folder = str(getattr(settings, "music_folder", "") or "")
    if mode in ("game_and_custom", "custom_only"):
        logger.info("Preparing your music (new songs are converted once; this can take a moment)...")
    cache = Utils.cache_path("timesplittersfp", "music")
    voices = None
    disc = str(getattr(settings, "voice_disc", "") or "") if settings is not None else ""
    if disc:
        if not os.path.isfile(disc):
            logger.warning("voice_disc %r was not found; the English voices are used.", disc)
        else:
            ctx.show_prep("Preparing the voices from %s..." % os.path.basename(disc))
            try:
                voices = voice_pack.prepare(disc, dolphin, cache, patch_iso.Image, log=logger.info)
                if voices is None:
                    logger.info("%s carries the English voices; nothing to change.", os.path.basename(disc))
            except Exception as exc:
                logger.warning("Voice pack skipped: %s", exc)

    def progress(done, total, song):
        if done < total:
            ctx.show_prep("Converting your songs: %d of %d done%s" % (done, total, " (%s)" % song if done else ""),
                          done, total)
        else:
            ctx.show_prep("Writing the music into your disc copy...", total, total)

    if mode != "off" or voices:
        ctx.show_prep("Writing the music into your disc copy...")
    try:
        music.apply(image, cache, mode=mode, folder=folder,
                    seed=int(getattr(settings, "music_seed", 0) or 0),
                    ffmpeg_path=str(getattr(settings, "ffmpeg_path", "") or ""),
                    log=note, warn=logger.warning, image_factory=patch_iso.Image, voice=voices,
                    progress=progress)
        if voices:
            logger.info("Voices: %s.", voices.language.capitalize())
    except Exception as exc:
        logger.warning("Music and voices skipped: %s", exc)


def start_mouse():
    """The mouse driver, in its own process: it waits for the game, then feeds mouse look
    into it (F8 toggles capture, F6/F7 sensitivity). Windows only."""
    if sys.platform != "win32":
        logger.info("Mouse look needs Windows; skipped.")
        return None
    try:
        import multiprocessing
        from .. import mouse_driver
        proc = multiprocessing.Process(target=mouse_driver.main, args=(["--wait", "--stick-y", "2"],),
                                       name="TSFPMouse", daemon=True)
        proc.start()
        logger.info("Mouse look on: click into the Dolphin window. F8 turns capture on/off, F6/F7 "
                    "lower/raise the sensitivity. (Turn it off with mouse_look in host.yaml.)")
        return proc
    except Exception as exc:
        logger.warning("Mouse look could not start: %s", exc)
        return None


def main(*launch_args: str):
    Utils.init_logging("TSFPClient")

    async def run():
        parser = get_base_parser()
        parser.add_argument("--name", default=None, help="slot name to connect as")
        parser.add_argument("--no-launch", action="store_true", help="attach to a Dolphin that is already running")
        parser.add_argument("--read-only", action="store_true", help="send checks but never write to the game")
        parser.add_argument("--dolphin", default=None, help="Dolphin executable (remembered in host.yaml)")
        parser.add_argument("--game", default=None, help="disc image; patched beside it if it is not yet")
        args = parser.parse_args(launch_args)
        ctx = TSFPContext(args.connect, args.password)
        if args.name:
            ctx.auth = args.name
        ctx.read_only = args.read_only
        ctx.server_task = asyncio.create_task(server_loop(ctx), name="ServerLoop")
        if gui_enabled:
            ctx.run_gui()
        ctx.run_cli()
        loop = asyncio.create_task(game_loop(ctx), name="GameLoop")
        if not args.no_launch:
            await asyncio.sleep(0.5)            # let the window draw before the dialogs and the slow work
            await launch(ctx, args.dolphin, args.game)
        await ctx.exit_event.wait()
        loop.cancel()
        if getattr(ctx, "mouse_process", None) is not None and ctx.mouse_process.is_alive():
            ctx.mouse_process.terminate()
        await ctx.shutdown()

    import colorama
    colorama.init()
    asyncio.run(run())
    colorama.deinit()


if __name__ == "__main__":
    main()
