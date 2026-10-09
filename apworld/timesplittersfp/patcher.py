"""Patch a TimeSplitters: Future Perfect (G3FE69) disc image for Archipelago.

The client can write memory while the game runs, but some things the randomizer
needs are hardcoded in the executable and cannot be reached that way -- the first
story mission is unconditionally selectable, for one. Those need the code changed,
and changing it in the image rather than in RAM means it stays changed across boots
and needs no cooperation from the client.

Patches are byte-for-byte in place: nothing moves, nothing grows, so the disc layout
is untouched and both plain .iso/.gcm and Dolphin's compact .ciso work. The original
file is never modified -- a patched copy is written instead.

    python patcher.py "TimeSplitters - Future Perfect (USA).ciso" -o tsfp-ap.ciso
    python patcher.py <image> --verify        report which patches are present
    python patcher.py <image> --mouse         also apply the optional mouse-look hook
    python patcher.py <image> --mouse-only    only the mouse-look hook (no randomizer)
"""
import argparse
import os
import shutil
import struct
import sys

GAME_ID = b"G3FE69"
DOL_HEADER_OFFSET = 0x420          # disc header field holding the DOL's ISO offset


class Image:
    """Random access to a disc image, whether plain or CISO-compressed.

    CISO stores only the blocks that contain data, so a logical disc offset has to
    be mapped through its block table. Patching in place is still fine: every byte
    we touch lives in a block that necessarily exists, because it holds code.
    """

    def __init__(self, path, writable=False):
        self.path = path
        self.file = open(path, "r+b" if writable else "rb")
        header = self.file.read(8)
        self.ciso = header[:4] == b"CISO"
        if not self.ciso:
            self.file.seek(0)
            return
        self.block_size = struct.unpack("<I", header[4:8])[0]
        flags = self.file.read(0x8000 - 8)
        self.physical = {}
        present = 0
        for index, flag in enumerate(flags):
            if flag:
                self.physical[index] = present
                present += 1

    def _place(self, offset):
        """Physical file offset for a logical disc offset, or None if not stored."""
        if not self.ciso:
            return offset
        block, within = divmod(offset, self.block_size)
        if block not in self.physical:
            return None
        return 0x8000 + self.physical[block] * self.block_size + within

    def read(self, offset, length):
        out = bytearray()
        while length:
            place = self._place(offset)
            span = length if not self.ciso else min(
                length, self.block_size - (offset % self.block_size))
            if place is None:
                out += b"\0" * span
            else:
                self.file.seek(place)
                out += self.file.read(span)
            offset += span
            length -= span
        return bytes(out)

    def write(self, offset, payload):
        place = self._place(offset)
        if place is None:
            raise ValueError("disc offset 0x%x is not stored in this image" % offset)
        if self.ciso and (offset % self.block_size) + len(payload) > self.block_size:
            raise ValueError("write at 0x%x spans a block boundary" % offset)
        self.file.seek(place)
        self.file.write(payload)

    def write_span(self, offset, payload):
        """write() across any number of blocks; every block touched must already be stored."""
        if not self.ciso:
            self.write(offset, payload)
            return
        done = 0
        while done < len(payload):
            span = min(len(payload) - done, self.block_size - ((offset + done) % self.block_size))
            self.write(offset + done, payload[done:done + span])
            done += span

    def close(self):
        self.file.close()


# --- patches -----------------------------------------------------------------
# Each entry is (RAM address, expected original words, patched words, description).
# The expected words are checked before anything is written: refusing to patch a
# build that does not match is the whole reason they are here.

NOP = 0x60000000

# --- story: make the first mission lockable, and gate every mission on a bit the
# client owns ------------------------------------------------------------------
# FUN_801c0c30 answers "is story mission N selectable?". It builds a requirement
# record on the stack and hands it to the unlock evaluator FUN_801c1024:
#     801c0c64  cmpwi r30, 0          ; mission == 0 ?
#     801c0c68  bne   801c0c74
#     801c0c6c  li    r3, 1           ; -> yes, unconditionally
#     801c0c70  b     801c0c9c
#     801c0c74  subi  r5, r30, 1      ; record[1] = mission - 1
#     801c0c78  li    r3, 2           ; record[0] = type 2: "story bit set"
#     801c0c7c  li    r0, 0           ; record[2] = word 0 (any difficulty)
#     ...                             ; record[4] = co-op flag, then the call
# Type 2 reads the story-completion bitfields, which the game writes as the player
# clears missions -- the client cannot own those without losing the true progress.
# Type 5 ("event has medal tier T") reads the medal bitfields instead, which have
# 128 bits per tier for 48 events; bits 48..127 are never touched by the game. So
# the record becomes {5, 48 + mission, tier 1} and mission N is selectable exactly
# when tier-1 bit 48+N is set -- a bit only the client writes. The bne becomes an
# unconditional b so mission 0 goes through the same record instead of the
# short-circuit.
#
# The locked-item tooltip never sees this record (the story list prints a fixed
# string), which matters: describing a type-5 record looks its event up in a
# 48-entry table, and event 48+N would run off the end.
STORY_GATE = (
    0x801C0C68,
    [0x4082000C, 0x38600001, 0x4800002C, 0x38BEFFFF, 0x38600002, 0x38000000],
    [0x4800000C, 0x38600001, 0x4800002C, 0x38BE0030, 0x38600005, 0x38000001],
    "story missions (Time to Split included) are gated by client-owned medal bits",
)

# --- story mounts gun.pak and chr.pak like every other mode --------------------
# FUN_8002b314 mounts the level's paks and then, only if FUN_8002aeb8() says so,
# pak/gun.pak and pak/chr.pak. That predicate is false exactly in Story (mode byte
# 10, on a real level), so a story level can only find the guns its own pak holds.
# Mounting is index-only (the files are read on demand), so letting Story mount
# what Arcade mounts costs nothing; the game itself does it when flag 0x40 is set.
#     8002b47c  bl    FUN_8002aeb8
#     8002b480  cmplwi r3, 0
#     8002b484  beq   8002b4e8        ; skip the mounts  -> nop
PAK_MOUNT_TEST = (
    0x8002B484,
    [0x41820064],
    [NOP],
    "Story mounts gun.pak and chr.pak like Arcade does",
)

# --- story: back to the menu after a mission instead of straight into the next --
# FUN_80031fe8 sequences the story: phase 0 pre-mission cutscene, 1 the mission,
# 2 after the results screen (post-mission cutscene if there is one), 3 after that
# cutscene. Phases 2 and 3 both end in
#     addi r0, r3, 1        ; mission + 1
#     stw  r5/r3, 0x30(r31) ; phase = 0
#     stw  r0, 0x28(r31)    ; selected mission = next
# which is what starts the next mission with no menu in between. A randomizer needs
# the player back at the story list, where the next mission may not be theirs yet.
# The function's own "return to the front end" is two instructions
# (li r0,0x65 ; stb r0,0x4c(r30) -- level 101, seen at 80032068 and 80032228), so
# both sites send the player there instead; the phase is left as is and the menu
# resets it to 0 when a mission is started. The next mission's pre-mission cutscene
# still plays when it is started from the menu, and the last mission still rolls
# into the credits (that branch is untouched).
#
# The menu state must be reset too. Leaving the results screen (level 0x6A) sets the
# menu state DAT_805cc614 to 0x15, "carry on the story" (FUN_802e2650), whose
# dispatcher (FUN_802e19e4 case 0x15) sets phase 2 and runs the sequencer. Arriving at
# the front end still in 0x15, every front-end load re-ran that and was sent to the
# front end again: a black screen with music until a button press changed the state
# (seen live after Mansion of Madness and Machine Wars). The game's own lost-mission
# exit reaches the front end with state 5, which the dispatcher ignores, so both sites
# now also store 5 there (r31 = 0x805cc608, the story struct; state = r31 + 0xC).
# Site 2 has the four words for it; site 1 (three words) branches into site 2, which
# then branches on to 80032284 -- the phase-3 check it skips cannot fire in phase 2.
STORY_NO_AUTO_ADVANCE = [
    (0x8003209C,
     [0x38030001, 0x90BF0030, 0x901F0028],
     [0x480001B4, NOP, NOP],                 # b 0x80032250
     "after a mission with no post-cutscene, return to the menu (via the next site)"),
    (0x80032250,
     [0x38030001, 0x38600000, 0x907F0030, 0x90040028],
     [0x38000065, 0x981E004C, 0x38000005, 0x901F000C],   # level 0x65 ; menu state 5
     "after a mission's post-cutscene, return to the menu"),
]

# --- weapon shuffle: also precache the level's own guns' drop models ------------
# A level precaches its guns through the gun rows: FUN_801a8144 walks the level's
# weapon set and FUN_801a7f70(slot, flag) loads model-table[slot]+4, the drop model.
# With rows swapped, a gun shuffled away never has its own drop model loaded, yet
# level scripts spawn some by hard-coded object type (Khallos: PISTOL9MM_CL at the
# wall guns). That lazy load came back NULL, FUN_80060bfc dereferenced it, and the
# page-fault handler -- handed page 0 -- filled a hash group and recursed into the
# globals: a hard freeze.
#
# The precache's last call (slot 1) is rerouted through a cave which makes that call
# and then loads each object type listed in a low-memory block the client writes
# ('TSPL', count, types; memmap PRECACHE_BLOCK) with the game's own FUN_801a7a84 --
# the native drop models of the level's shuffled-away guns. No block, no change.
#
# The cave lives in FUN_801c05f0, the UNLOCK FEATURES cheat callback (28 words),
# whose only way in is entry 0 of the controller cheat-code table; CHEAT_CALLBACK
# points that entry at a plain blr first, which also keeps the cheat from unlocking
# everything. Every word was disassembled back with Ghidra and the cave was executed
# against a model of the block.
CHEAT_CALLBACK = (
    0x8044ECF0,
    [0x801C05F0],                            # cheat 0 -> UNLOCK FEATURES toggle
    [0x801C0714],                            # -> blr
    "the unlock-everything cheat code does nothing (its code hosts the caves)",
)
PRECACHE_CAVE = (
    0x801C05F0,
    [0x9421FFC0, 0x7C0802A6, 0x90010044, 0x38610008, 0x800DACB4, 0x20000001, 0x900DACB4,
     0x4BE4E3FD, 0x800DACB4, 0x38600D13, 0x2C000000, 0x41820008, 0x38600D11, 0x90610008,
     0x38610008, 0x4BE4E2F9, 0x806DACB4, 0x48000455, 0x3C608045, 0x808DACB4, 0x3863ECB0,
     0x4CC63182, 0x4BF6E231, 0x4BFFFE7D, 0x80010044, 0x7C0803A6, 0x38210040, 0x4E800020],
    [0x7C0802A6, 0x9421FFF0, 0x90010014, 0x4BFE7975, 0x3FE08000, 0x63FF2F00, 0x801F0000,
     0x3C605453, 0x6063504C, 0x7C001800, 0x40820030, 0x83DF0004, 0x281E003A, 0x41810024,
     0x3BFF0004, 0x2C1E0000, 0x41820018, 0x847F0004, 0x63840000, 0x4BFE7449, 0x3BDEFFFF,
     0x4BFFFFE8, 0x80010014, 0x38210010, 0x7C0803A6, 0x4E800020, NOP, NOP],
    "weapon shuffle: cave that precaches the client's list of object types",
)
PRECACHE_HOOK = (
    0x801A820C,
    [0x4BFFFD65],                            # bl FUN_801a7f70
    [0x480183E5],                            # bl <cave>
    "weapon shuffle: the level's gun precache runs through the cave",
)

# --- camera: a stand-in game object ------------------------------------------
# FUN_8009df90, the per-frame camera update, loads the game object *(0x80611D74)
# into r30 and reads it with no NULL check, and its callers run it for almost every
# level id -- including the moments a level is torn down or set up, when the game
# object is NULL. Finishing The Russian Connection (shuffle off) froze the game on
# the read at 8009e3a8. Skipping the update then is no good: its first part sets up
# the camera's matrices for the render pass that follows (that froze Khallos). So
# the update always runs, and a NULL game object is swapped for a zeroed stand-in
# in unused low memory (0x80001900): at 8009e034, just past the beq that consumes
# the camera NULL check (cr0 is dead until 8009e0b0), a branch to a 6-word cave in
# the tail of FUN_801c0a88 (dead through CHEAT_CALLBACK, past the mouse cave), which
# swaps r30 if it is NULL, runs the displaced load and returns to 8009e038
# (Ghidra-checked and simulated).
CAMERA_GUARD = (
    0x801C0B60,
    [0x39610020, 0x481C1BD1, 0x80010024, 0x7C0803A6, 0x38210020, 0x4E800020],
    [0x2C1E0000, 0x4082000C, 0x3FC08000, 0x63DE1900, 0x80090200, 0x4BEDD4C4],
    "camera: cave that stands in a zeroed game object while there is none",
)
CAMERA_GUARD_HOOK = (
    0x8009E034,
    [0x80090200],                            # lwz r0,0x200(r9)
    [0x48122B2C],                            # b <cave>
    "camera: the camera update checks its game object in the cave",
)

# --- skipping a mission's intro cutscene ---------------------------------------
# The story sequencer FUN_80031fe8, in phase 0 (the pre-mission cutscene), asks the stub
# FUN_8003bc88 (always 0) whether to skip it; non-zero marks the cutscene seen and loads
# the mission straight away. The phase-0 call is pointed at a 3-word cave returning the
# byte at 0x80002FF8, which the client sets from the seed's skip_intro_cutscenes option
# (RAM is zero at boot, so without the client nothing changes). The other call, after the
# results screen, is left alone: non-zero there skips the outro AND moves on to the next
# mission. The cave sits in FUN_801c0a88's dead tail, between the mouse cave and the
# camera guard (Ghidra-checked).
SKIP_INTRO_CAVE = (
    0x801C0B2C,
    [0x3BE00000, 0x3BC00004, 0x38600000],
    [0x3C608000, 0x88632FF8, 0x4E800020],    # lis r3,0x8000 ; lbz r3,0x2ff8(r3) ; blr
    "intro skip: cave that returns the client's skip flag",
)
SKIP_INTRO_HOOK = (
    0x80032290,
    [0x480099F9],                            # bl FUN_8003bc88
    [0x4818E89D],                            # bl <cave>
    "intro skip: the pre-mission cutscene asks the cave whether to skip",
)

# --- weapons: the game's hard-coded weapon checks follow the weapon ------------------
# AI (and some player) code compares the held gun-table row (pawn +0x94) with fixed slot
# numbers: the shotguns (14, 15, 53) get the shotgun animation and pacing, the Plasma
# Autorifle its long burst, launchers and snipers fire single shots, and so on. The weapon
# shuffle moves a gun's data to another row, so those checks stayed with the row: a
# Dispersion Gun on the machine gun's row was fired like a machine gun. Each check whose
# register is only compared now reads the held weapon's stats index (pawn +0x204, the
# right-hand stats, which travel with the shuffle) and compares it with the same weapon's
# stats index. Unshuffled, the result is the same. (Ghidra-checked; the remote mines' and
# Mag-Charger's checks also switch rows by number and are left alone.)
WEAPON_IDENTITY_WORDS = [
    (0x8025DB54, [0x801F0094], [0x801F0204]),
    (0x8025DB58, [0x2C00000E], [0x2C000005]),
    (0x8025DB60, [0x2C000035], [0x2C000020]),
    (0x8025DE64, [0x801F0094], [0x801F0204]),
    (0x8025DE68, [0x2C00000E], [0x2C000005]),
    (0x8025DE70, [0x2C000035], [0x2C000020]),
    (0x8025DF8C, [0x801F0094], [0x801F0204]),
    (0x8025DF90, [0x2C00000E], [0x2C000005]),
    (0x8025DF98, [0x2C000035], [0x2C000020]),
    (0x8025EBD0, [0x801E0094], [0x801E0204]),
    (0x8025EBD4, [0x2C00000E], [0x2C000005]),
    (0x8025EBDC, [0x2C000035], [0x2C000020]),
    (0x8025EBE4, [0x2C00000F], [0x2C000006]),
    (0x80263198, [0x801F0094], [0x801F0204]),
    (0x8026319C, [0x2C00000E], [0x2C000005]),
    (0x802631A4, [0x2C000035], [0x2C000020]),
    (0x802631AC, [0x2C00000F], [0x2C000006]),
    (0x8027ABC0, [0x807F0094], [0x807F0204]),
    (0x8027ABC8, [0x2C03000E], [0x2C030005]),
    (0x8027ABD0, [0x2C030035], [0x2C030020]),
    (0x8027ABD8, [0x2C03000F], [0x2C030006]),
    (0x8027B26C, [0x807F0094], [0x807F0204]),
    (0x8027B274, [0x2C03000E], [0x2C030005]),
    (0x8027B27C, [0x2C030035], [0x2C030020]),
    (0x8027B284, [0x2C03000F], [0x2C030006]),
    (0x802B496C, [0x801C0094], [0x801C0204]),
    (0x802B4970, [0x2C00000E], [0x2C000005]),
    (0x802B4978, [0x2C000035], [0x2C000020]),
    (0x802B4980, [0x2C00000F], [0x2C000006]),
    (0x802B6168, [0x80040094], [0x80040204]),
    (0x802B616C, [0x2C00000E], [0x2C000005]),
    (0x802B6174, [0x2C000035], [0x2C000020]),
    (0x801B6760, [0x809E0094], [0x809E0204]),
    (0x801B6764, [0x2C040023], [0x2C040013]),
    (0x802C2AFC, [0x801D0094], [0x801D0204]),
    (0x802C2B00, [0x2C000023], [0x2C000013]),
    (0x802C2B6C, [0x801D0094], [0x801D0204]),
    (0x802C2B70, [0x2C000023], [0x2C000013]),
    (0x8025B064, [0x801F0094], [0x801F0204]),
    (0x8025B068, [0x2C00000C], [0x2C000004]),
    (0x801B6998, [0x801E0094], [0x801E0204]),
    (0x801B699C, [0x2C000010], [0x2C000007]),
    (0x8013B410, [0x801F0094], [0x801F0204]),
    (0x8013B414, [0x2C000012], [0x2C000008]),
    (0x802B4F24, [0x801C0094], [0x801C0204]),
    (0x802B4F28, [0x2C00001D], [0x2C00000F]),
    (0x802B4F30, [0x2C00001E], [0x2C000010]),
    # Shots fired by an animation (a guard leaning out of cover sprays: the animation fires
    # many times): launchers and snipers (rows 29, 30, 18, 19, 32) fire only once per
    # animation. Rewritten as a stats bitmask so the shotguns (stats 5, 6, 32) join them,
    # or a shuffled Dispersion Gun is sprayed like a machine gun from cover.
    (0x802C3218,
     [0x807D0094, 0x2C03001D, 0x418201FC, 0x2C03001E, 0x418201F4,     # lwz r3,0x94(r29); 29? 30?
      0x3803FFEE, 0x28000001, 0x408101E8, 0x2C030020, 0x418201E0],    # 18..19? 32? -> once only
     [0x807D0204,                                                      # lwz r3,0x204(r29)
      0x3C0006C1, 0x6000C000,                                          # r0 = stats 5,6,8,9,15,16,17
      0x7C001831, 0x418001F4,                                          # slw. r0,r0,r3; blt once only
      0x2C030020, 0x418201EC,                                          # stats 32? -> once only
      NOP, NOP, NOP]),
]
WEAPON_IDENTITY = [(ram, original, patched, "weapons: hard-coded weapon check follows the weapon (%08x)" % ram)
                   for ram, original, patched in WEAPON_IDENTITY_WORDS]

PATCHES = [
    STORY_GATE,
    PAK_MOUNT_TEST,
] + STORY_NO_AUTO_ADVANCE + [
    CHEAT_CALLBACK,
    PRECACHE_CAVE,
    PRECACHE_HOOK,
    CAMERA_GUARD,
    CAMERA_GUARD_HOOK,
    SKIP_INTRO_CAVE,
    SKIP_INTRO_HOOK,
] + WEAPON_IDENTITY


# --- optional: mouse look (--mouse) ---------------------------------------------
# Not part of the randomizer. Lets an external mouse tool feed the game's C-stick.
#
# FUN_8018c8b8 converts one pad port's PADStatus into the game's input record each
# frame; the C-stick ints (0x80 centre) are written by the call
#     8018ca18  bl FUN_8018c6cc            (r29 = record, r30 = port)
# That call is rerouted into a cave which calls the original and then adds the
# deltas from a block at 0x80001800 ('MOUS', port, dx, dy) to the C-stick ints,
# clamps them to 0..255 and zeroes the deltas. Every control mode -- first person,
# vehicles, turrets, scoped aiming -- reads its look axes from those ints through
# the same accessor, so the mouse works everywhere, in the frame, with no race
# against the game's own pad write. Without the block the cave does nothing.
#
# THE CAVE lives in FUN_801c0a88, the debug "unlock everything" routine (60 words),
# called only by the UNLOCK FEATURES cheat callback FUN_801c05f0 -- dead once
# CHEAT_CALLBACK points cheat entry 0 at a plain blr, which this set applies too.
# Every word was disassembled back with Ghidra and the cave was executed against a
# model of the record and block.
MOUSE_HOOK = (
    0x8018CA18,
    [0x4BFFFCB5],                            # bl FUN_8018c6cc
    [0x48034071],                            # bl <cave>
    "mouse: the C-stick conversion runs through the cave",
)
MOUSE_CAVE = 0x801C0A88
MOUSE_CAVE_ORIGINAL = [
    0x9421FFE0, 0x7C0802A6, 0x90010024, 0x39610020, 0x481C1C51, 0x20630000,
    0x3800FFFF, 0x7C631910, 0x3BA00000, 0x7C1B1838, 0x3BC00000, 0x38600000,
    0x4BE73AA1, 0x381E0BF4, 0x7F63012E, 0x38600000, 0x4BE73A91, 0x3BBD0001,
    0x381E0C00, 0x2C1D0003, 0x7F63012E, 0x3BDE0004, 0x4180FFD4, 0x3BA00000,
    0x3BE00000, 0x3B800000, 0x3BC00000, 0x38600000, 0x4BE73A61, 0x7C63F214,
    0x3B9C0001, 0x38030C0C, 0x3BDE0004, 0x2C1C0004, 0x7F7F012E, 0x4180FFE0,
    0x3BBD0001, 0x3BFF0010, 0x2C1D0004, 0x4180FFC8, 0x3BA00000,
]
MOUSE_CAVE_CODE = [
    0x7C0802A6, 0x9421FFF0, 0x90010014, 0x4BFCBC39, 0x3CA08000, 0x38A51800,
    0x80050000, 0x3CC04D4F, 0x60C65553, 0x7C003000, 0x4082006C, 0x80050004,
    0x7C00F000, 0x40820060, 0x807D0024, 0x80850008, 0x7C632214, 0x2C030000,
    0x40800008, 0x38600000, 0x2C0300FF, 0x40810008, 0x386000FF, 0x907D0024,
    0x807D0028, 0x8085000C, 0x7C632214, 0x2C030000, 0x40800008, 0x38600000,
    0x2C0300FF, 0x40810008, 0x386000FF, 0x907D0028, 0x38000000, 0x90050008,
    0x9005000C, 0x80010014, 0x38210010, 0x7C0803A6, 0x4E800020,
]
MOUSE_PATCHES = [
    CHEAT_CALLBACK,                          # also in PATCHES; applying it twice is a no-op
    (MOUSE_CAVE, MOUSE_CAVE_ORIGINAL, MOUSE_CAVE_CODE, "mouse: cave that adds the block's deltas to the C-stick"),
    MOUSE_HOOK,
]


def dol_offset(image):
    header = image.read(0, 0x440)
    if header[:6] != GAME_ID:
        raise SystemExit("this is not %s (found %r)" % (GAME_ID.decode(), header[:6]))
    return struct.unpack(">I", header[DOL_HEADER_OFFSET:DOL_HEADER_OFFSET + 4])[0]


def ram_to_disc(image, dol_start, ram):
    """Translate a RAM address into a disc offset via the DOL's section table."""
    head = image.read(dol_start, 0x100)
    offsets = struct.unpack(">18I", head[0x00:0x48])
    addresses = struct.unpack(">18I", head[0x48:0x90])
    sizes = struct.unpack(">18I", head[0x90:0xD8])
    for file_offset, address, size in zip(offsets, addresses, sizes):
        if size and address <= ram < address + size:
            return dol_start + file_offset + (ram - address)
    raise SystemExit("0x%08x is not inside any DOL section" % ram)


def words_at(image, disc, count):
    raw = image.read(disc, count * 4)
    return list(struct.unpack(">%dI" % count, raw))


# --- images patched by an earlier version ----------------------------------------
# An image an older build patched is upgraded in place: at each site the words may be the
# original, the current patch, or an older version of it (LEGACY, same length as the
# original). REVERT lists sites an older version patched that are no longer patched at
# all; they are put back to the original first.
LEGACY = {
    0x8003209C: [[0x38000065, 0x981E004C, NOP]],                       # return to menu, v1
    0x80032250: [[0x38000065, 0x981E004C, NOP, NOP]],                  # return to menu, v1
    0x801C0B60: [[0x39610020, 0x800DA434, 0x2C000000, 0x4D820020,      # camera guard, v1
                  0x9421FD40, 0x4BEDD420]],
}
REVERT = [
    (0x8009DF90, [0x9421FD40], [[0x48122BD4]], "camera guard v1's entry hook (replaced by the stand-in)"),
]


DISC_SIZE = 1459978240


def write_iso(path, out_path):
    """A plain ISO of the disc at `path` (any format Image reads): the full disc size, so the
    free space after the last file is real space a later step can use."""
    source = Image(path)
    try:
        with open(out_path, "wb") as out:
            for off in range(0, DISC_SIZE, 16 << 20):
                out.write(source.read(off, min(16 << 20, DISC_SIZE - off)))
    finally:
        source.close()


def apply(path, out_path, verify_only=False, patches=None, title="patches", header=True, in_place=False,
          as_iso=False):
    """Patch a copy of `path` into `out_path` -- or, with in_place, `path` itself (only for an
    image this patcher already wrote, e.g. upgrading "(AP)" after an update). as_iso writes the
    copy as a plain ISO whatever the original's format."""
    patches = PATCHES if patches is None else patches
    if verify_only or in_place:
        target = path
    else:
        if os.path.abspath(path) == os.path.abspath(out_path):
            raise SystemExit("refusing to write over the original image")
        print("copying %s -> %s" % (os.path.basename(path), os.path.basename(out_path)))
        if as_iso:
            write_iso(path, out_path)
        else:
            shutil.copyfile(path, out_path)
        target = out_path

    image = Image(target, writable=not verify_only)
    try:
        dol_start = dol_offset(image)
        if header:
            print("%s, DOL at disc offset 0x%x%s"
                  % (GAME_ID.decode(), dol_start, " (CISO)" if image.ciso else ""))
        applied = already = 0
        if not verify_only:
            for ram, original, olds, description in REVERT:
                disc = ram_to_disc(image, dol_start, ram)
                if words_at(image, disc, len(original)) in olds:
                    image.write(disc, struct.pack(">%dI" % len(original), *original))
                    print("  restored         %08x  %s" % (ram, description))
        for ram, original, patched, description in patches:
            disc = ram_to_disc(image, dol_start, ram)
            current = words_at(image, disc, len(original))
            if current == patched:
                print("  already patched  %08x  %s" % (ram, description))
                already += 1
                continue
            if current != original and current not in LEGACY.get(ram, []):
                raise SystemExit(
                    "unexpected code at %08x: found %s, expected %s.\n"
                    "This image is not the build these patches were written for: choose your original, "
                    "unpatched TimeSplitters: Future Perfect (USA) disc image."
                    % (ram, " ".join("%08x" % w for w in current),
                       " ".join("%08x" % w for w in original)))
            if verify_only:
                print("  NOT patched      %08x  %s" % (ram, description))
                continue
            image.write(disc, struct.pack(">%dI" % len(patched), *patched))
            print("  patched          %08x  %s" % (ram, description))
            applied += 1
        if verify_only:
            print("%s: %d of %d present" % (title, already, len(patches)))
        else:
            print("done: %d applied, %d already present" % (applied, already))
    finally:
        image.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("image", help="TimeSplitters: Future Perfect disc image (.iso, .gcm or .ciso)")
    parser.add_argument("-o", "--out", help="where to write the patched copy")
    parser.add_argument("--verify", action="store_true",
                        help="report which patches are present, changing nothing")
    parser.add_argument("--mouse", action="store_true",
                        help="also apply the optional mouse-look hook (see MOUSE_PATCHES)")
    parser.add_argument("--mouse-only", action="store_true",
                        help="apply ONLY the mouse-look hook: the stock game with mouse look, "
                             "no randomizer changes")
    args = parser.parse_args()
    if args.mouse_only:
        patches = MOUSE_PATCHES
    else:
        patches = PATCHES + ([p for p in MOUSE_PATCHES if p not in PATCHES] if args.mouse else [])
    if args.verify:
        # reported separately: the mouse hook is optional, so its absence is not a fault
        apply(args.image, None, verify_only=True, patches=PATCHES, title="randomizer")
        print()
        apply(args.image, None, verify_only=True, patches=[p for p in MOUSE_PATCHES if p not in PATCHES],
              title="optional mouse hook (--mouse)", header=False)
        return
    out = args.out
    if not out:
        stem, ext = os.path.splitext(args.image)
        out = stem + (" (mouse)" if args.mouse_only else " (AP)") + ext
    apply(args.image, out, patches=patches)
    print()
    print("Run this patched image in Dolphin. The original is untouched.")


if __name__ == "__main__":
    main()
