from dataclasses import dataclass

from Options import Choice, DefaultOnToggle, OptionSet, PerGameCommonOptions, Range, StartInventoryPool, Toggle


class GameModes(OptionSet):
    """Which of TimeSplitters: Future Perfect's three modes produce checks. Remove any you would rather not play.

    Story     - the 13 story missions, their per-difficulty completions, and their objectives.
    Arcade    - the 27 Arcade League matches, one check per trophy tier.
    Challenge - the 21 Challenges, one check per trophy tier.

    At least one must be kept. Dropping a mode removes its checks and its unlock items; what they held becomes
    filler, so a shorter list mainly makes for a smaller, denser seed.

    THE GOAL FOLLOWS THIS LIST. With Story kept, you win by clearing Future Perfect (the final mission) on your Max
    Story Difficulty once enough Time Crystals have arrived from the multiworld. With Story removed there is no final
    mission to clear, so you instead win by completing Trophy Goal Percentage of whichever Arcade / Challenge checks
    you kept, no Time Crystals are placed, and Weapon Gating / Weapon Shuffle are forced off (they only ever affect
    story missions)."""
    display_name = "Game Modes"
    valid_keys = ("Story", "Arcade", "Challenge")
    default = frozenset(valid_keys)


class TrophyGoalPercentage(Range):
    """The share of your Arcade / Challenge checks you must complete to win when Story is NOT in Game Modes.

    Counted over the trophy checks the seed actually has, so it follows Game Modes: keep only Challenge and it is a
    percentage of the Challenge checks alone. Ignored whenever Story is kept."""
    range_start = 10
    range_end = 100
    display_name = "Trophy Goal Percentage"
    default = 90


class StoryDifficulty(Choice):
    """The MAXIMUM story difficulty you intend to play. Each story mission produces a completion check for every
    difficulty up to and including this (so Normal = Easy + Normal checks). The GOAL triggers when you clear the final
    mission on THIS difficulty. (Story modes only.)"""
    display_name = "Max Story Difficulty"
    option_easy = 0
    option_normal = 1
    option_hard = 2
    default = 1


class TrophyTier(Choice):
    """The MAXIMUM trophy tier you intend to earn on Arcade matches + Challenges. Each event produces checks for every
    tier up to and including this (so Gold = Bronze + Silver + Gold checks; a single Gold clear fires all three, since
    medals are cumulative in the save)."""
    display_name = "Max Trophy Tier"
    option_bronze = 0
    option_silver = 1
    option_gold = 2
    option_platinum = 3
    default = 2


class TimeCrystalsRequired(Range):
    """How many Time Crystals you must collect before the final mission (Future Perfect) unlocks.

    Time Crystals are ITEMS sent to you from the multiworld -- they are scattered among all players' checks, so you
    receive them as other people play. Until this many have arrived, the final mission stays locked. Auto-clamped down
    if the seed has too few free item slots. Ignored without Story in Game Modes."""
    display_name = "Time Crystals Required to Finish"
    range_start = 0
    range_end = 60
    default = 8


class TimeCrystalsExtra(Range):
    """How many EXTRA Time Crystals are placed beyond the required count (padding, so collecting them isn't all
    mandatory). Total placed = Required + Extra, auto-clamped to the free item slots."""
    display_name = "Extra Time Crystals"
    range_start = 0
    range_end = 30
    default = 4


class StartingUnlocksPerCategory(Range):
    """Starting unlock items granted at the top of each active category (story / arcade / challenge) so the seed
    is enterable from the start."""
    display_name = "Starting Unlocks Per Category"
    range_start = 1
    range_end = 3
    default = 1


class WeaponGating(Toggle):
    """Weapons as items: you can only hold weapons you've received as AP items. Un-received weapons are taken away
    the moment the game hands them out -- floor pickups, scripted handouts, and your starting loadout alike. The
    Temporal Uplink (the story tool) is always available.

    STORY MISSIONS ONLY -- Arcade and Challenge always give their normal weapons. Forced OFF when Story is not in
    Game Modes."""
    display_name = "Weapon Gating"


class WeaponShuffle(Toggle):
    """Weapon randomizer: one mapping per seed swaps what each weapon IS in-game (every Scifi Handgun becomes a
    Rocket Launcher, and so on). It applies to floor pickups, scripted handouts, your starting loadout and the
    enemies' weapons alike, and a shuffled-in gun draws on the ammo of the gun it replaces. The Flamethrower,
    ElectroTool, Baseball Bat and Brick are never shuffled.

    STORY MISSIONS ONLY -- Arcade and Challenge keep their normal weapons. Forced OFF when Story is not in
    Game Modes."""
    display_name = "Weapon Shuffle"


class WeaponShuffleScope(Choice):
    """How far Weapon Shuffle is allowed to reach. Ignored unless Weapon Shuffle is on.

    completely_random - any shuffleable gun can become any other. Grenades and mines still only swap among
                        themselves (in every scope), so a thrown or placed weapon stays one. A level can end up
                        holding weapons native to some other level.
    same_class        - a gun only becomes one of its own class: regulars with regulars, launchers with launchers,
                        grenades with grenades, mines with mines.
    within_level      - each level reshuffles only its OWN weapons, so every level still offers exactly the weapons
                        it always did -- just from different pickups. The most conservative option."""
    display_name = "Weapon Shuffle Scope"
    option_completely_random = 0
    option_same_class = 1
    option_within_level = 2
    default = 0


class InverseLook(Toggle):
    """GameCube preference: Inverse Look. Written to your profile once, the first time the client sees you in a
    level, so a new profile starts the way you want without a trip through the Preferences screen. Anything you
    change in the game afterwards stays changed -- this is only the starting point. The game's own default is on."""
    display_name = "Inverse Look"
    default = 0


class AutoLookahead(Toggle):
    """GameCube preference: Auto Lookahead (the camera tilts on its own on slopes and stairs). Applied once, like
    Inverse Look. The game's own default is on."""
    display_name = "Auto Lookahead"
    default = 0


class WeaponChange(Choice):
    """GameCube preference: when picking up a weapon switches you to it. Applied once, like Inverse Look.

    The game's own default is if_new_and_best, which fights Weapon Gating: picking up a weapon you have not received
    switches you to it for an instant before the client takes it away again. never is the comfortable choice with
    gating on, and the default here."""
    display_name = "Weapon Change"
    option_always = 0
    option_never = 1
    option_best = 2
    option_if_new = 3
    option_if_new_and_best = 4
    default = 1


class Crosshair(Choice):
    """GameCube preference: the crosshair. Applied once, like Inverse Look -- but only when set to something other
    than unchanged, so a profile you have already set up keeps its own choice. The game's own default is
    on_and_fixed."""
    display_name = "Crosshair"
    option_unchanged = 0
    option_off = 1
    option_on_and_moving = 2
    option_on_and_fixed = 3
    default = 0


class AutoAim(Choice):
    """GameCube preference: Auto Aim. Applied once, and only when not unchanged, like Crosshair. The game's own
    default is on."""
    display_name = "Auto Aim"
    option_unchanged = 0
    option_off = 1
    option_on = 2
    default = 0


class AimMode(Choice):
    """GameCube preference: whether the aim button is held or toggled. Applied once, and only when not unchanged,
    like Crosshair. The game's own default is hold."""
    display_name = "Aim Mode"
    option_unchanged = 0
    option_hold = 1
    option_toggle = 2
    default = 0


class CrouchMode(Choice):
    """GameCube preference: whether crouch is held or toggled. Applied once, and only when not unchanged, like
    Crosshair. The game's own default is toggle."""
    display_name = "Crouch Mode"
    option_unchanged = 0
    option_hold = 1
    option_toggle = 2
    default = 0


class Rumble(Choice):
    """GameCube preference: controller rumble. Applied once, and only when not unchanged, like Crosshair. The
    game's own default is fire_and_hit."""
    display_name = "Rumble"
    option_unchanged = 0
    option_off = 1
    option_fire = 2
    option_hit = 3
    option_fire_and_hit = 4
    default = 0


class PickupChecks(Toggle):
    """Health and armour pickups in the story missions become checks: the packs placed in
    each level, plus those inside cabinets, boxes and safes. They can hold any item; the
    Temporal Uplink collects them even at full health. A few that were never confirmed
    reachable only ever hold filler. Time to Split's are a separate option (that mission has
    no uplink)."""
    display_name = "Health and Armour Checks"


class TimeToSplitPickups(Toggle):
    """Also make Time to Split's health packs checks (needs Health and Armour Checks).
    That mission has no Temporal Uplink, so each pack can only be taken while hurt."""
    display_name = "Time to Split Pickup Checks"


class SkipIntroCutscenes(DefaultOnToggle):
    """Starting a story mission goes straight into it, without the intro cutscene and its
    loading screen. The cutscenes still unlock in the gallery. The cutscene after a
    mission plays as normal."""
    display_name = "Skip Intro Cutscenes"


class TrapCount(Range):
    """How many traps to place, in place of filler. A trap switches on one of the game's
    cheats for 30 seconds during a story mission: big heads, rotating heads, cardboard
    enemies, the 8-Bit screen and so on, one trap at a time. Traps received outside a story
    mission wait for the next one. Without Story in Game Modes there are none."""
    display_name = "Trap Count"
    range_start = 0
    range_end = 60
    default = 8


@dataclass
class TSFPOptions(PerGameCommonOptions):
    game_modes: GameModes
    trophy_goal_percentage: TrophyGoalPercentage
    story_difficulty: StoryDifficulty
    trophy_tier: TrophyTier
    time_crystals_required: TimeCrystalsRequired
    time_crystals_extra: TimeCrystalsExtra
    starting_unlocks_per_category: StartingUnlocksPerCategory
    weapon_gating: WeaponGating
    weapon_shuffle: WeaponShuffle
    weapon_shuffle_scope: WeaponShuffleScope
    inverse_look: InverseLook
    auto_lookahead: AutoLookahead
    weapon_change: WeaponChange
    crosshair: Crosshair
    auto_aim: AutoAim
    aim_mode: AimMode
    crouch_mode: CrouchMode
    rumble: Rumble
    pickup_checks: PickupChecks
    time_to_split_pickups: TimeToSplitPickups
    skip_intro_cutscenes: SkipIntroCutscenes
    trap_count: TrapCount
    start_inventory_from_pool: StartInventoryPool
