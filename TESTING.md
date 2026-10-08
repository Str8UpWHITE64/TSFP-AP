# Building and testing

## Building

    python apworld/build_apworld.py                 -> apworld/timesplittersfp.apworld
    python apworld/build_apworld.py --install DIR   -> also copied into DIR (an Archipelago custom_worlds)

The `.apworld` is self-contained: the world, the client (`client/`), the disc patcher (`patcher.py`), the mouse
driver (`mouse_driver.py`) and the tracker's floor lookup (`client/tracker_areas.json`). The build verifies
every member against its source and refuses a stray `__pycache__`.

## Running from a source checkout

With the `.apworld` installed into the checkout's `custom_worlds`:

    python Launcher.py "TimeSplitters FP Client" -- --connect localhost:38281 --name Player1

Client options (after `--`): `--dolphin <Dolphin.exe>` and `--game <disc image>` (remembered in `host.yaml`),
`--no-launch` to attach to a Dolphin that is already running the patched game, `--read-only` to send checks but
write nothing. The installed Archipelago already ships `dolphin-memory-engine`; a source checkout needs
`pip install dolphin-memory-engine`.

## Patching the disc

The client writes a patched copy beside the original, `<name> (AP).<ext>`, and refreshes it when a newer build
adds patches. By hand:

    python apworld/timesplittersfp/patcher.py "<original image>" --mouse
    python apworld/timesplittersfp/patcher.py "<image>" --verify

The randomizer patches: the story gate (every mission can be locked), the gun pak mount (Story can load any
gun), the return to the menu after a mission (two sequencer sites, which also clear the menu's "carry on the
story" state), the gun precache (a level still loads its own guns' floor models when the shuffle swaps them out),
a camera fix (the camera update reads a zeroed stand-in while a level is torn down), and the intro skip (the
pre-mission cutscene asks a flag the client sets from the seed whether to skip; zero, as at boot, plays it). The optional mouse hook
is added to every image the client writes; it does nothing without the mouse driver. The precache and camera
code reuse the routines behind the "unlock everything" cheat code, so that cheat does nothing on a patched disc.

The patches use low RAM at `0x80001800`..`0x80003000` (mouse block, camera stand-in, precache list, session
tag, intro-skip flag). Dolphin puts its Gecko cheat handler there when a game has active cheat codes: keep them off.

## Behaviour worth knowing

**If either the game or the client crashes, restart both**: close Dolphin and start the client again, and it
launches the game fresh. The client says so when it loses the game or the Dolphin it started closes.

Restarting only the client is still safe for the weapon shuffle. The first client of a game boot saves the
original weapon tables to `%TEMP%\tsfp_ap\` and leaves a tag in low RAM (`0x80002FF0`); a later client in the
same boot works from the saved originals, not the live tables an earlier client left shuffled.

The client tracks profile slot 0 (player 1's profile), and only the profile that belongs to the seed: a tag in
tier-1 medal word 3 (`PROFILE_TAG_G`, bits nothing uses), a hash of the seed name, team and slot, saved with the
profile. A profile with no tag and no progress (no story clear, no medal, no story locks) is claimed on its own;
the claim is confirmed on the next poll, and dropped if progress appeared under it (a card profile loading into
the slot). Any other profile is ignored until `/use_profile`. The default "Player 1".."Player 4" stand-ins are
never claimed. The name of the seed's profile is kept in data storage, key `tsfp_profile_<team>_<slot>`. Locks are applied every poll; the menus pick them up
when a screen is built, so an unlock received while a list is on screen shows after backing out and back in.

For the PopTracker pack the client publishes the mission and map area the player is in to data storage, key
`tsfp_map_<team>_<slot>`.

## What to check

0. Profile: connect with an old profile loaded, and nothing is sent; create a new profile, and the client
   registers it; save, restart the game and client, and it is still recognised.
1. Story: only granted missions selectable (Time to Split included); a clear sends the difficulty check and the
   mission's main objectives; objectives also send live as they complete. After the results screen the game
   returns to the story menu.
2. Challenges / Arcade League: only granted matches selectable; Honorary and Elite open when any of their
   matches is granted; a medal sends one check per tier earned.
3. Weapon Gating: an un-received gun disappears from the weapon wheel within half a second of being handed out;
   the held weapon switches away from it. An un-received grenade or mine also loses its ammo, since those are
   thrown straight from it.
4. Weapon Shuffle: `/weapons` lists the mapping; the shuffle is applied as a story mission is picked in the
   menu and undone at the front end, so Challenges and Arcade keep native weapons. A shuffled-in gun fires
   the ammo of the gun it replaces, so that gun's pickups and handouts keep it loaded; the client scales each
   gain to the same share of the new gun's own maximum (half a Pistol clip's worth is half a rocket load).
5. Health and armour checks: taking a pack (on foot or with the uplink) sends its check.
6. Mouse look: on foot, turrets, tanks and security cameras; nothing moves while the game is paused.

## Memory card

The client writes lock bits into the profile's medal bitfield (bits the game never uses). They are saved with
the profile and re-asserted on every connect. Back the card up first if the profile matters to you:

    %APPDATA%\Dolphin Emulator\GC\USA\Card A

## Content model

| Locations | Count | Detail |
| --- | --- | --- |
| Challenge & Arcade League medals | 192 | 48 events (21 Challenges + 27 Arcade League matches) x 4 tiers |
| Story difficulties | 39 | 13 missions x Easy / Normal / Hard |
| Objectives | 68 | per-mission objective completions |
| Health & armour pickups | 93 | optional (`pickup_checks`); the few never taken in a mapping run are excluded |

Medals are cumulative (a Gold fires Bronze + Silver + Gold). Which checks are active depends on the options, but
every location id is pre-allocated, so options never renumber anything.

Items: one unlock per challenge, arcade match and story mission (61); Time Crystals (gate the final mission); one
weapon item per weapon family (36, with Weapon Gating); filler (Banana).
