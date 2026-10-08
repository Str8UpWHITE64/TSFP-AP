# TimeSplitters: Future Perfect — Archipelago

An [Archipelago](https://archipelago.gg) randomizer for **TimeSplitters: Future Perfect** (GameCube, USA),
played in Dolphin. Story missions, objectives, Challenges and Arcade League matches are locked behind items
from the multiworld, and completing them sends checks to everyone else.

Features:

- **Everything is a check**: mission clears on each difficulty, mission objectives, Challenge and Arcade
  League medals (Bronze to Platinum), and optionally every health and armour pickup in the story.
- **Play the modes you want**: any mix of Story, Arcade League and Challenges, each with its own goal.
- **Weapon Gating and Weapon Shuffle**: weapons become items, and story levels can hand out a different gun
  in each weapon's place.
- **Mouse look** built in: no extra program to install or run.
- **One Launcher entry**: the client patches your disc, starts Dolphin and connects, all on its own.

## What you need

- [Archipelago](https://github.com/ArchipelagoMW/Archipelago/releases) 0.6.4 or newer.
- [Dolphin](https://dolphin-emu.org/) (a recent build).
- Your own **TimeSplitters: Future Perfect (USA)** disc image (game ID `G3FE69`) as `.iso`, `.gcm` or
  `.ciso`. RVZ images cannot be patched: convert one to ISO in Dolphin first (right-click the game,
  *Convert File...*).
- Windows, for mouse look. Everything else works wherever Archipelago and Dolphin do.

## Installing

Download `timesplittersfp.apworld` from the [releases](../../releases) and double-click it, or copy it into
Archipelago's `custom_worlds` folder. That is all: the client, the disc patcher and mouse look are inside it.

## Playing

1. Make a yaml: in the Archipelago Launcher, **Generate Template Options** writes one with every option
   explained (`TimeSplitters Future Perfect.yaml`). Generate and host as usual.
2. Open the Archipelago Launcher and click **TimeSplitters FP Client**.
3. The first time, it asks for `Dolphin.exe` and your disc image. It remembers both (in `host.yaml`, under
   `timesplittersfp_options`).
4. The client writes a patched copy of your disc beside the original, `<name> (AP).<ext>`, and launches it in
   Dolphin. Your original is never changed, and the copy is refreshed automatically after an update.
5. Connect with `/connect <server>` and your slot name.
6. In the game, **create a new profile** for this seed. The client registers it as this seed's profile, and
   from then on only that profile counts: load it whenever you come back to the seed. A profile that already
   has progress is ignored, so nothing from outside the seed is sent by mistake. To play a seed on a profile
   that already has progress anyway (its clears and medals are then sent as checks), load it and type
   `/use_profile`.

**If the game or the client crashes, restart both**: close Dolphin and start the client again, and it launches
the game fresh. The client tells you when it loses the game.

**Do not enable cheat codes (Gecko or Action Replay) for this game.** Dolphin loads its cheat handler into the
same spot in memory the randomizer's patches use.

### Mouse look

On by default. Click into the Dolphin window and the mouse aims; turrets, tanks and security cameras are handled
too. **F8** turns capture on and off, **F6** / **F7** lower and raise the sensitivity. Turn it off with
`mouse_look: false` under `timesplittersfp_options` in `host.yaml`. The game's own Inverse Look setting is
followed.

## Options

The template yaml from the Launcher lists every option with its choices.

- **Game modes**: any combination of **Story**, **Arcade** (the Arcade League) and **Challenge**; only the
  modes you pick have checks and unlock items. With Story, the goal is to clear the final mission
  (*Future Perfect*) on your Max Story Difficulty once you hold enough **Time Crystals**. Without it, the goal
  is a share of the medal checks in the modes you picked (**Trophy Goal Percentage**, 90% by default), there
  are no Time Crystals, and Weapon Gating and Weapon Shuffle are off (they only affect the story).
- **Weapon Gating**: weapons are items; a gun you have not received is taken off you.
- **Weapon Shuffle**: each weapon is replaced by another in the story, everywhere at once, by class, or only
  among a level's own guns. Guns a level cannot be finished without keep their identity there.
- **Health and Armour Checks**: every health and armour pickup in the story is a check that can hold any
  item (a handful never confirmed reachable only hold filler). The Temporal Uplink collects them even at full
  health. Time to Split's are a separate option, as
  that mission has no uplink.
- **Skip Intro Cutscenes** (on by default): starting a story mission goes straight into it, without the
  intro cutscene and its loading screen. The cutscenes still unlock in the gallery.
- **Profile preferences**: Inverse Look, Auto Lookahead, Weapon Change and more are written to your profile
  once; change them in the game afterwards as you like.

## Memory card

The client keeps the randomizer's locks in your profile's save data (in parts the game never uses), so they are
saved with the profile. Back up your memory card first if the profile matters to you:
`%APPDATA%\Dolphin Emulator\GC\USA\Card A`.

## Known issues

- The guns mounted on vehicles aim up and down slowly with the mouse.
- In The Khallos Express, the health pack in the safe only appears if Harry Tipper opens it; doing something
  else first means he never does, until the mission is restarted. It is not a check.

## For developers

See [`TESTING.md`](TESTING.md) for building from source, what to verify, and the content model.
