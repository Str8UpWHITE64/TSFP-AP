"""GameCube memory map for TimeSplitters: Future Perfect — G3FE69 (NTSC-U).

Port knowledge only: every address the client reads or writes, kept out of
data.py so the content catalog stays a plain description of the game.

Offsets named `*_OFF` are relative to the start of a profile record; offsets named
`*_G` are relative to the game-data block (a profile's, or the co-op aggregate).
Absolute addresses are GameCube RAM addresses, big-endian.

Confirmation status per entry:
  [static]  derived from main.dol
  [live]    observed in a running game
"""

GAME_ID = "G3FE69"

# --- profile array -----------------------------------------------------------
# Static, in .bss: 8 slots. Slot 0 is player 1's profile; at boot the game fills
# slots 0..3 with default "Player N" profiles until a card profile is loaded. [live]
PROFILE_BASE = 0x80501608
PROFILE_STRIDE = 0x1EDC
PROFILE_MAX = 8
# profile+0 is a pointer to a card-info record (non-null = slot in use); the profile
# NAME lives at that record +4, not in the profile itself.                    [live]
PROFILE_INFO_PTR_OFF = 0x00
PROFILE_INFO_NAME_OFF = 0x04
PROFILE_NAME_LEN = 32

# --- game-data sub-struct ----------------------------------------------------
# Zeroed on a new profile; the cross-profile aggregate at AGGREGATE_GAMEDATA is
# memset to the same size. The unlock code reads whichever block
# ACTIVE_GAMEDATA_PTR points at: profile 0's with one player, the aggregate with
# more.                                                                      [live]
GAMEDATA_OFF = 0x1290
GAMEDATA_SIZE = 0xC4C
AGGREGATE_GAMEDATA = 0x80510CE8
ACTIVE_GAMEDATA_PTR = 0x80611938
PLAYER_COUNT_ADDR = 0x80611014

# --- trophy / medal records --------------------------------------------------
# 48 records, indexed directly by EVENT id (0..20 challenges, 21..47 arcade league):
# the same index the apworld uses, so no permutation table is needed.        [live]
TROPHY_G = 0x490
TROPHY_STRIDE = 0x18
TROPHY_COUNT = 48
TROPHY_PLAYS = 0x00
TROPHY_SCORE = 0x04
TROPHY_TIER = 0x0C            # 0 none, 1 Bronze .. 4 Platinum; cumulative
# Medal bitfields: tier t (1..4) word w at G + 0xBFC + t*0x10 + w*4. Bit = event id.
# Only 48 of 128 bits per tier are events; the game never touches the rest, which is
# what the story gate patch borrows (see STORY_BIT_BASE).                    [live]
MEDAL_BITS_G = 0xBFC
MEDAL_TIER_STRIDE = 0x10

# --- story completion --------------------------------------------------------
# Two triples of words: solo and co-op. Word = difficulty (0 Easy, 1 Normal, 2
# Hard), bit = mission index. A clear on difficulty D sets words 0..D (cumulative)
# and never sets on a quit-out. The client never writes these.               [live]
STORY_SOLO_G = 0xBF4
STORY_COOP_G = 0xC00
STORY_CLEARS_COUNTER_G = 0x918   # clears, not attempts   [live]
STORY_RECORD_G = 0x288           # 13 x 0x28, best times [live]

# --- story gating (patched image) -------------------------------------------
# The stock gate asks "is mission N-1's story bit set?" and hardcodes mission 0
# open. The disc patch turns its requirement record into "tier-1 medal bit
# 48+N", so a mission is selectable exactly when the client sets that spare bit.
# Bits 48..60 live in tier-1 word 1, bits 16..28.                            [live]
STORY_BIT_BASE = 48
# The seed a profile belongs to: a client-chosen u32 in tier-1 word 3 (bits 96..127, which
# nothing uses), saved with the profile. 0 on a profile no client has claimed.
PROFILE_TAG_G = MEDAL_BITS_G + 1 * MEDAL_TIER_STRIDE + 3 * 4
STORY_GATE_PATCH_ADDR = 0x801C0C68
STORY_GATE_STOCK = (0x4082000C, 0x38600001, 0x4800002C, 0x38BEFFFF, 0x38600002, 0x38000000)
STORY_GATE_APPLIED = (0x4800000C, 0x38600001, 0x4800002C, 0x38BE0030, 0x38600005, 0x38000001)

# --- arcade / challenge gating: requirement records in RAM --------------------
# Every event carries a 5-dword typed requirement record at +0xA8 of its struct,
# built at boot (position 0 of a group = always, others = "medal on the previous
# match"). The client overwrites them: {0} = locked, {1} = unlocked. Type 0 and 1
# never dereference anything; a type-5 record pointing past event 47 crashes the
# locked-item tooltip.                                                       [live]
EVENT_PTRS_CHALLENGE = 0x80461EE8     # events 0..20: pointer array
EVENT_PTRS_ARCADE = 0x804653BC        # events 21..47: index by event id * 4
EVENT_REQ_OFF = 0xA8
EVENT_REQ_WORDS = 5
REQ_NEVER = 0
REQ_ALWAYS = 1
GROUPS_A = 0x80461F3C                 # groups 0..6 (challenge), stride 0x38
GROUPS_B = 0x80465218                 # groups 7..15 (arcade league)
GROUP_STRIDE = 0x38
GROUP_LEAGUE = 0x00                   # -1 challenge, 0 Amateur, 1 Honorary, 2 Elite
GROUP_COUNT_OFF = 0x04
GROUP_IDS_OFF = 0x08
# The league-select screen gates Honorary and Elite with two static records of the
# same shape (stock: every group of the previous league has a medal).       [live]
LEAGUE_REQ = {1: 0x8047629C, 2: 0x804762B0}     # league index -> record address
# Per-kind debug "unlock everything" bytes; must stay 0.                     [static]
UNLOCK_OVERRIDE_BYTES = 0x80610CF8     # +1 story +2 arcade +3 challenge +4 character +5 extras
UNLOCK_ALL_GLOBAL = 0x806125F4         # the UNLOCK FEATURES toggle; must stay 0

# --- client session tag (low RAM) ---------------------------------------------
# The weapon shuffle is computed from a snapshot of the tables as the game booted. A
# client started later in the same session would otherwise snapshot tables an earlier
# client had already shuffled and shuffle them again -- composing the mapping, which
# crashed the game within seconds (seen live). So the first snapshot of a boot is saved
# to a file and tagged here; a later client finds the tag and loads the file. RAM is
# cleared when the game boots, so a fresh boot always snapshots afresh. 0x80001800 holds
# the optional mouse block (16 bytes), 0x80001900..0x80002D00 the camera's zeroed stand-in
# game object (CAMERA_STAND_IN below) and 0x80002F00 the precache list; the rest of
# 0x80001800..0x80003000 is unused.
SESSION_TAG_ADDR = 0x80002FF0          # 'TSFS' + u32 tag
# 1 = skip the story missions' intro cutscenes (patcher SKIP_INTRO_*), from the seed.
SKIP_INTRO_FLAG = 0x80002FF8
SKIP_INTRO_HOOK_ADDR = 0x80032290
SKIP_INTRO_HOOK_APPLIED = 0x4818E89D   # bl <cave at 0x801C0B2C>
SESSION_TAG_MAGIC = b"TSFS"

# --- weapon shuffle: extra precache list (low RAM) ------------------------------
# A level precaches each gun's drop model through the (swapped) gun rows, so a gun
# shuffled away never has its own loaded -- but level scripts spawn some by hard-coded
# object type (Khallos's wall guns: PISTOL9MM_CL), and that mid-level load hard-froze
# the game. The patched precache (patcher PRECACHE_CAVE) also loads every object type
# listed here; the client lists the native drop models of the level's shuffled guns.
PRECACHE_BLOCK_ADDR = 0x80002F00       # 'TSPL', u32 count, count x u32 object type
PRECACHE_MAGIC = b"TSPL"
PRECACHE_MAX_TYPES = 58                # the cave ignores a longer list
PRECACHE_HOOK_ADDR = 0x801A820C
PRECACHE_HOOK_APPLIED = 0x480183E5     # bl <cave at 0x801C05F0>
# The camera update reads a zeroed stand-in when there is no game object (patcher
# CAMERA_GUARD); without it, finishing The Russian Connection froze the game.
CAMERA_GUARD_HOOK_ADDR = 0x8009E034
CAMERA_GUARD_HOOK_APPLIED = 0x48122B2C # b <cave at 0x801C0B60>
CAMERA_STAND_IN = 0x80001900           # ..0x80002D00, must stay zero

PLAYER_POS_OFF = 0x64                 # player object: x, y, z floats (y up, feet)  [live]

# --- health / armour pickups (live) ---------------------------------------------
# Placed items get a 0xD8-byte data block in a pool; the pickup handlers write the
# taker into +4 -- for walking over it and for the Temporal Uplink alike (the uplink
# collects even at full health). Story pickups never respawn, so +4 stays set.
ITEM_POOL_PTR = 0x80611CD0             # -> data blocks                           [live]
ITEM_POOL_COUNT = 0x80611CD4           # number in use (max 0x78)
ITEM_DATA_STRIDE = 0xD8
ITEM_TAKEN_BY = 0x04
ITEM_TYPE = 0x0C                       # 8 health, 0x10 armour
ITEM_WAR_RECORD = 0x18                 # -> .war item record + 0x34; elsewhere for spawned drops
ITEM_SPAWN_POS = 0x1C                  # 3 floats: where a spawned drop appeared
PICKUP_TYPES = {8: "Health", 0x10: "Armour"}
# A level's .war item list: the level table row (stride 0x80; +4 u16 non-zero while the
# table goes on, +8 level id, +0x24 params) -> params +0x14 = first item record.
LEVEL_TABLE = 0x80467D08
WAR_ITEM_STRIDE = 0x58
WAR_ITEM_PROPS = 0x34

# --- preferences (in the profile) ---------------------------------------------
# Found by flipping each on the Preferences screen and diffing RAM, then accepting:
# the screen edits a working copy (flags at 0x8051A918) and Accept copies it into the
# profile. Gameplay reads the profile directly -- flipping only the profile's inverse
# look bit reversed the same stick push, instantly. Same flags layout as TS2.  [live]
PROFILE_PREF_FLAGS_OFF = 0x04
PREF_INVERSE_LOOK = 1 << 0
PREF_AIM_TOGGLE = 1 << 1               # clear = hold
PREF_CROUCH_TOGGLE = 1 << 2            # clear = hold
PREF_AUTO_LOOKAHEAD = 1 << 3
PREF_RUMBLE = 1 << 4                   # rumble at all; with one or both of:
PREF_RUMBLE_HIT = 1 << 5
PREF_RUMBLE_FIRE = 1 << 6
PREF_AUTO_AIM = 1 << 7
PREF_RUMBLE_MASK = PREF_RUMBLE | PREF_RUMBLE_HIT | PREF_RUMBLE_FIRE
PROFILE_WEAPON_CHANGE_OFF = 0x6C       # 0 always, 1 never, 2 best, 3 if new, 4 if new and best
PROFILE_CROSSHAIR_OFF = 0x78           # 0 off, 1 on and moving, 2 on and fixed
# A brand-new profile holds flags 0x000100FD (inverse look, crouch toggle, lookahead,
# rumble on fire and hit, auto aim), weapon change 4, crosshair 2.

# --- mode / level globals ----------------------------------------------------
CURRENT_LEVEL_ADDR = 0x80612614        # level id loaded (101 = front end)      [live]
MODE_BYTE_ADDR = 0x805015BD            # 10 = Story; 0 at the front end          [live]
MODE_STORY = 10
DIFFICULTY_BYTE_ADDR = 0x805015BF      # 0 Easy 1 Normal 2 Hard                  [live]
MENU_STATE_ADDR = 0x805CC614           # 4 once a story mission is picked        [static]
MENU_STATE_STORY = 4
SELECTED_MISSION_ADDR = 0x805CC630     # story mission index picked in the menu  [static]
FRONT_END_LEVEL = 101

# --- live objectives ---------------------------------------------------------
# A runtime pool, allocated once when a game session starts and reset per level:
# entry = objective index * OBJ_STRIDE. Status 5 = complete.                 [live]
OBJ_POOL_PTR = 0x806128AC
OBJ_STRIDE = 0x4C
OBJ_INDEX = 0x00              # u16
OBJ_TEXTID = 0x02             # u16
OBJ_TYPE = 0x08               # u8: 0 main, 1 secondary, 2 internal trigger
OBJ_STATUS = 0x0B             # u8: 1 defined, 2 active, 3 reminded, 4 failed, 5 complete
OBJ_STATUS_COMPLETE = 5
OBJ_POOL_ENTRIES = 48

# --- weapons -----------------------------------------------------------------
# Gun table: one row per weapon variant. Rows sharing a family id (+0x38, filled at
# BOOT -- the disc holds zeros) are one weapon: base, alt-fire, dual-wield. The
# apworld's weapon slot is the family's base row.                            [live]
GUN_TABLE = 0x8043E22C
GUN_STRIDE = 0x3C
GUN_COUNT = 71
GUN_FLAGS = 0x00
# Thrown (0x10: grenades) and placed (0x200: mines, TNT, the Brick) weapons. They are
# used straight from their ammo: a family the gating took away can still be thrown while
# its ammo lasts, so gating empties that too.                                 [live]
GUN_FLAGS_SPENT_FROM_AMMO = 0x10 | 0x200
GUN_LEFT_STATS = 0x0C
GUN_RIGHT_STATS = 0x10
GUN_ANIM_PATH = 0x18
GUN_REQ_OFF = 0x1C            # 5-dword unlock record, kept on swap
GUN_REQ_END = 0x30
GUN_FAMILY = 0x38             # kept on swap
# Model / HUD table, parallel: name id, drop and inventory graphics, scales, and a
# per-gun script callback at +0x50 that is kept on swap.                     [live]
GUN_UI_TABLE = 0x8043F294
GUN_UI_STRIDE = 0x54
GUN_UI_DROP_MODEL = 0x04       # object type of the gun lying on the floor
GUN_UI_CALLBACK = 0x50
# Gun Stats, indexed by the gun table's +0x0C (left hand) / +0x10 (right hand). A gun
# fires the ammo type at +0x14 (+0x1C: alt fire), but pickups and scripted handouts give
# the ammo type the level's own data names -- the native gun's. So under the shuffle the
# stats a slot borrows get that slot's native ammo types, and a shuffled-in gun draws on
# the supply of the gun it replaces (as on TS2). Only the two ammo fields are touched. [live]
GUN_STATS = 0x80432D64
GUN_STATS_STRIDE = 0x29C
GUN_STATS_COUNT = 66
GUN_STATS_AMMO = 0x14
GUN_STATS_AMMO2 = 0x1C
# Ammo types (FUN_801a7818): +0 the most a player can carry, clip included. Under the
# shuffle a borrowed type gets the shuffled-in gun's own maximum, and the client scales
# every gain of it by (that maximum / the native one): a pickup fills the same share of
# the new gun as it would have of the old one.                              [static]
AMMO_TYPES = 0x8042E238
AMMO_TYPE_STRIDE = 0xE0
AMMO_TYPE_COUNT = 44
AMMO_TYPE_MAX = 0x00
# Weapon-wheel icon table, parallel.                                          [live]
GUN_ICON_TABLE = 0x8043D99C
GUN_ICON_STRIDE = 0x14
# Story weapon sets: the level's params +4 picks one; bots, placed pickups and asset
# loading all follow it. Unchanged by the shuffle (the identity swap above is what
# makes "gun X" mean "gun Y" everywhere, scripted handouts included).        [live]
WEAPON_SETS = 0x8046A908
WEAPON_SET_STRIDE = 0x44

# --- the player pawn ---------------------------------------------------------
# game struct -> +0x14 player -> +0x7C pawn.                                  [live]
GAME_PTR = 0x80611D74
PLAYER_OFF = 0x14
PAWN_OFF = 0x7C
PAWN_OWNED = 0x54C            # byte per gun-table row; a give marks the whole family
PAWN_HELD = 0x94              # held weapon slot; writing it IS the switch     [live]
PAWN_AMMO = 0x61E             # s16 per ammo type
UNARMED_SLOT = 1

# --- patched-image detection -------------------------------------------------
PAK_MOUNT_PATCH_ADDR = 0x8002B484
PAK_MOUNT_STOCK = 0x41820064
PAK_MOUNT_APPLIED = 0x60000000
SEQUENCER_PATCH_ADDRS = (0x8003209C, 0x80032250)
SEQUENCER_APPLIED = (0x480001B4, 0x38000065)   # site 1 branches to site 2, which sets level 0x65
SEQUENCER_MENU_STATE = (0x8003225C, 0x901F000C)  # ... and menu state 5 (stw r0,0xc(r31))
