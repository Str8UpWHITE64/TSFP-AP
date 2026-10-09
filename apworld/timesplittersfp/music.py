"""Music shuffle and custom songs, written into the patched disc copy before the game boots.

The game opens every track by name through the disc's file table (FST), so a shuffle is
just FST entries pointing at other tracks' data, and a custom song is data written into
space a track this launch does not use (an unpicked game track, an unused file, or -- on
a plain ISO -- the free space after the last file). Cutscene tracks carry dialogue and are
never touched.

Every song must be Ogg Vorbis, stereo, 32000 Hz: the player decodes into two fixed
per-channel buffers and plays them back at the hardware's 32 kHz. Custom songs are
converted to that and loudness-normalised to the game's level with ffmpeg, once each
(cached by content).

Game tracks a launch overwrites are backed up first and restored on the next launch, so
the disc copy can always be put back as it was.
"""
import hashlib
import json
import os
import random
import shutil
import struct
import subprocess
import threading
import zipfile
from concurrent.futures import ThreadPoolExecutor

BGM = (
    'music/cutscene_suite_action32.ogg', 'music/cutscene_suite_badguys_sneak32.ogg',
    'music/cutscene_suite_goodguys_sneak32.ogg', 'music/mapmaker44fx.ogg', 'music/mind_the_gap44fx.ogg',
    'music/ts1_chemical_plant44fx3_7july.ogg', 'music/ts1_chinese44_july3rd_fx.ogg',
    'music/ts1_compound44_july6.ogg', 'music/ts1_docks44fx2_7july.ogg', 'music/ts1_mansion44fx_redone.ogg',
    'music/ts1_planet44fx_7july.ogg', 'music/ts1_spaceways44fxgame_7july.ogg', 'music/ts1_village44fx_7july.ogg',
    'music/ts2_fecked_up_44_fx2.ogg', 'music/ts2_mexican_remaster44fx.ogg', 'music/ts2_neo_tokyo_44_fx.ogg',
    'music/ts2_robotfac44.ogg', 'music/ts2_siberia02_44_fx.ogg', 'music/ts2_tileset_guitar_44_fx2.ogg',
    'music/ts2_training_ground32.ogg', 'music/ts2_western_44_fx.ogg', 'music/ts3_bigbeat44_fx.ogg',
    'music/ts3_castle_44_fx.ogg', 'music/ts3_castle_tankboss44_fx.ogg', 'music/ts3_catacombs44_fx.ogg',
    'music/ts3_catacombs_attack44fx.ogg', 'music/ts3_catacombs_sneak44fx.ogg', 'music/ts3_disco44fx.ogg',
    'music/ts3_dm_siberia_cm32fx.ogg', 'music/ts3_egypt_tileset44_fx.ogg', 'music/ts3_farfuture1_32fx.ogg',
    'music/ts3_farfuture1_challenge_44fx.ogg', 'music/ts3_farfuture2fx32.ogg', 'music/ts3_ff2_boss_tune1_44fx.ogg',
    'music/ts3_ff2_boss_tune_faster_44fx.ogg', 'music/ts3_firq-funeral_2k4eq2.ogg',
    'music/ts3_gameover_ph44_fx.ogg', 'music/ts3_horror_hotel_cm44fx.ogg', 'music/ts3_horror_tset44fx.ogg',
    'music/ts3_like_a_monkey32fx.ogg', 'music/ts3_like_a_robot_goteki_vox_fx.ogg', 'music/ts3_mansion_44_fx.ogg',
    'music/ts3_menu32fx.ogg', 'music/ts3_military_dm44fx.ogg', 'music/ts3_nemo32fx.ogg',
    'music/ts3_nemoboss44fx.ogg', 'music/ts3_prison_assault32fx.ogg',
    'music/ts3_rocket_launchsite_remaster44fx.ogg', 'music/ts3_train_cm44_fx.ogg',
    'music/ts3_train_cm_new32_fx.ogg', 'music/ts3_trainboss_cm44_fx.ogg', 'music/ts3_trance32_01_fx.ogg',
    'music/ts3_vietnam_32fx.ogg', 'music/ts3_virtua44fx.ogg', 'music/ts3_zeppelin32fx3.ogg',
    'music/ugenix_hq_cm32_fx2.ogg', 'music/ugenix_lab_cm32_fx.ogg', 'music/whos_da_mummy_remix32fx.ogg',
)
# The two short stingers: a mission cleared, a challenge won.
EVENTS = ('music/ts3_challenge_win32.ogg', 'music/ts3_mission_complete44.ogg')
# On the disc but never opened by the game: free space for custom songs.
UNUSED = (
    'music/ts2_goteki_remix44_fx.ogg', 'music/ts2_spacestation_44_fx2.ogg', 'music/ts3_challenge_win32b.ogg',
    'music/ts3_menu44fx.ogg',
)

MODES = ("off", "game_music", "game_and_custom", "custom_only")
AUDIO_EXTS = {".mp3", ".ogg", ".oga", ".flac", ".wav", ".m4a", ".aac", ".opus", ".wma", ".aif", ".aiff"}
TARGET_LUFS, TRUE_PEAK, LRA = -10.0, -1.0, 11.0     # the game's own music sits around -11..-9 LUFS
CONVERT_VERSION = 1                                  # bump when the conversion changes: re-converts every song
CONVERT_WORKERS = max(1, min(8, (os.cpu_count() or 2) // 2))   # songs converted at once; half the cores
ALIGN = 32
DISC_SIZE = 1459978240


class Song:
    def __init__(self, name, group, path=None, region=None):
        self.name, self.group = name, group
        self.path = path                # converted custom song, or None for a game track
        self.region = region            # (offset, size) on the disc for a game track
        self.size = os.path.getsize(path) if path else region[1]

    @property
    def custom(self):
        return self.path is not None


# --- the disc's file table ---------------------------------------------------------
def read_fst(image):
    off, size = struct.unpack(">II", image.read(0x424, 8))
    return off, bytearray(image.read(off, size))


def fst_entries(raw):
    """{path: entry index} for every file."""
    count = struct.unpack(">I", raw[8:12])[0]
    names = raw[count * 12:]
    out, stack = {}, [(count, "")]
    for i in range(1, count):
        while i >= stack[-1][0]:
            stack.pop()
        o = struct.unpack(">I", raw[i * 12:i * 12 + 4])[0] & 0xFFFFFF
        full = stack[-1][1] + names[o:names.index(b"\0", o)].decode("latin-1")
        if raw[i * 12]:
            stack.append((struct.unpack(">I", raw[i * 12 + 8:i * 12 + 12])[0], full + "/"))
        else:
            out[full] = i
    return out


def entry_region(raw, i):
    return struct.unpack(">II", raw[i * 12 + 4:i * 12 + 12])


def set_entry(raw, i, offset, size):
    raw[i * 12 + 4:i * 12 + 12] = struct.pack(">II", offset, size)


# --- songs -------------------------------------------------------------------------
def vorbis_ok(path):
    """True when the file is Ogg Vorbis, stereo, 32000 Hz -- usable as it is."""
    try:
        with open(path, "rb") as f:
            head = f.read(4096)
    except OSError:
        return False
    i = head.find(b"\x01vorbis")
    if head[:4] != b"OggS" or i < 0 or len(head) < i + 16:
        return False
    return head[i + 11] == 2 and struct.unpack("<I", head[i + 12:i + 16])[0] == 32000


def find_ffmpeg(configured=""):
    candidates = [configured] if configured else []
    candidates.append(shutil.which("ffmpeg") or "")
    local = os.environ.get("LOCALAPPDATA", "")
    candidates += [os.path.join(local, "Microsoft", "WinGet", "Links", "ffmpeg.exe"),
                   r"C:\ffmpeg\bin\ffmpeg.exe",
                   os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "ffmpeg", "bin", "ffmpeg.exe"),
                   "/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg", "/usr/bin/ffmpeg"]
    for c in candidates:
        if c and os.path.isfile(c):
            return c
    return None


def _ffmpeg(ffmpeg, args):
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return subprocess.run([ffmpeg, "-hide_banner", "-nostats"] + args, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", creationflags=flags)


def _loudnorm_stats(stderr):
    j = stderr[stderr.rfind("{"):stderr.rfind("}") + 1]
    return json.loads(j)


def convert(ffmpeg, src, cache_dir):
    """The song as a game-ready, loudness-matched Ogg in the cache; None if it fails."""
    with open(src, "rb") as f:
        key = hashlib.sha1(f.read() + b"|v%d" % CONVERT_VERSION).hexdigest()[:20]
    out = os.path.join(cache_dir, key + ".ogg")
    if os.path.isfile(out) and vorbis_ok(out):
        return out
    measure = _ffmpeg(ffmpeg, ["-i", src, "-af", "loudnorm=I=%s:TP=%s:LRA=%s:print_format=json"
                               % (TARGET_LUFS, TRUE_PEAK, LRA), "-f", "null", "-"])
    try:
        m = _loudnorm_stats(measure.stderr)
        af = ("loudnorm=I=%s:TP=%s:LRA=%s:measured_I=%s:measured_TP=%s:measured_LRA=%s:measured_thresh=%s:offset=%s"
              % (TARGET_LUFS, TRUE_PEAK, LRA, m["input_i"], m["input_tp"], m["input_lra"], m["input_thresh"],
                 m["target_offset"]))
    except (ValueError, KeyError):
        af = "loudnorm=I=%s:TP=%s:LRA=%s" % (TARGET_LUFS, TRUE_PEAK, LRA)
    tmp = out + ".part"
    done = _ffmpeg(ffmpeg, ["-y", "-i", src, "-vn", "-af", af, "-ac", "2", "-ar", "32000", "-c:a", "libvorbis",
                            "-q:a", "3", "-f", "ogg", tmp])
    if done.returncode != 0 or not vorbis_ok(tmp):
        if os.path.exists(tmp):
            os.remove(tmp)
        return None
    os.replace(tmp, out)
    return out


def collect(source, cache_dir):
    """[(group, display name, file)] from a folder or a .zip: files under an "events" folder
    are stingers, everything else is level/menu music."""
    if not source or not os.path.exists(source):
        return []
    found = []
    if os.path.isfile(source) and source.lower().endswith(".zip"):
        stamp = hashlib.sha1(("%s|%d|%d" % (os.path.abspath(source), os.path.getsize(source),
                                            int(os.path.getmtime(source)))).encode()).hexdigest()[:12]
        root = os.path.join(cache_dir, "zip_" + stamp)
        if not os.path.isdir(root):
            with zipfile.ZipFile(source) as z:
                z.extractall(root)
        source = root
    for dirpath, _dirs, files in os.walk(source):
        parts = {p.lower() for p in os.path.relpath(dirpath, source).split(os.sep)}
        group = "events" if "events" in parts else "bgm"
        for f in sorted(files):
            if os.path.splitext(f)[1].lower() in AUDIO_EXTS:
                found.append((group, os.path.splitext(f)[0], os.path.join(dirpath, f)))
    return sorted(found, key=lambda t: (t[0], t[2].lower()))


# --- the plan ----------------------------------------------------------------------
def plan(mode, rng, slots, game, custom):
    """{slot name: Song} for one group. `game` maps slot name -> its own Song."""
    if mode == "game_music" or not custom:
        picks = [game[n] for n in slots]
    elif mode == "game_and_custom":
        picks = rng.sample([game[n] for n in slots] + list(custom), len(slots))
    else:                                               # custom_only
        chosen = rng.sample(list(custom), min(len(custom), len(slots)))
        keep = rng.sample(slots, len(slots) - len(chosen))
        picks = chosen + [game[n] for n in keep]
    rng.shuffle(picks)
    return dict(zip(slots, picks))


def place(customs, extents):
    """First-fit-decreasing: {Song: offset} and the songs that did not fit."""
    free = sorted(([o, s] for o, s in extents if s > 0), key=lambda e: e[0])
    placed, left = {}, []
    for song in sorted(customs, key=lambda s: -s.size):
        for ext in free:
            start = (ext[0] + ALIGN - 1) & ~(ALIGN - 1)
            pad = start - ext[0]
            if ext[1] - pad >= song.size:
                placed[song] = start
                ext[0], ext[1] = start + song.size, ext[1] - pad - song.size
                break
        else:
            left.append(song)
    return placed, left


def subtract(extents, used):
    """`extents` with every range in `used` cut out."""
    out = []
    for o, s in extents:
        pieces = [(o, o + s)]
        for uo, us in used:
            nxt = []
            for a, b in pieces:
                if uo + us <= a or b <= uo:
                    nxt.append((a, b))
                else:
                    if a < uo:
                        nxt.append((a, uo))
                    if uo + us < b:
                        nxt.append((uo + us, b))
            pieces = nxt
        out += [(a, b - a) for a, b in pieces if b > a]
    return out


class _Blob:
    """Something to write onto the disc: a file, or bytes already in memory."""

    def __init__(self, size, path=None, data=None):
        self.size, self.path, self.data = size, path, data

    def read(self):
        if self.data is not None:
            return self.data
        with open(self.path, "rb") as f:
            return f.read()


# --- applying it -------------------------------------------------------------------
# State per disc copy (Archipelago's cache): the copy's original file table, backups of every range
# a launch overwrote, and manifest.json: {"fst_sha1": table written last, "music": [[off, size], ...]
# backed-up ranges, "voice": {"key", "backups", "entries" {path: [off, size]}, "used" [[off, size]]}}.
def _state_dir(cache_root, image_path):
    key = hashlib.sha1(os.path.abspath(image_path).lower().encode()).hexdigest()[:16]
    d = os.path.join(cache_root, "disc_" + key)
    os.makedirs(os.path.join(d, "backup"), exist_ok=True)
    return d


def _backup_file(state_dir, off, size):
    return os.path.join(state_dir, "backup", "%08x_%d.bin" % (off, size))


def _back_up(image, state_dir, ranges):
    for off, size in ranges:
        path = _backup_file(state_dir, off, size)
        if os.path.isfile(path) and os.path.getsize(path) == size:
            continue
        with open(path + ".part", "wb") as f:
            done = 0
            while done < size:
                n = min(16 << 20, size - done)
                f.write(image.read(off + done, n))
                done += n
        os.replace(path + ".part", path)


def _restore(image, state_dir, ranges, warn):
    lost = 0
    for off, size in ranges:
        path = _backup_file(state_dir, off, size)
        if not (os.path.isfile(path) and os.path.getsize(path) == size):
            lost += 1
            continue
        with open(path, "rb") as f:
            done = 0
            while done < size:
                chunk = f.read(16 << 20)
                image.write_span(off + done, chunk)
                done += len(chunk)
    if lost:
        warn("%d part(s) of the disc copy could not be restored. Delete the \"(AP)\" copy and restart the client "
             "to have it written fresh." % lost)


def _plan_voice(image, original, entries, voice, donors_extra):
    """Where the voice pack goes: (writes [(offset, _Blob)], entries {path: (off, size)}, backups, used)."""
    by_offset = sorted((entry_region(original, i) + (p,) for p, i in entries.items()), key=lambda t: t[0])
    o0, s0 = entry_region(original, entries["pak/sounds_e.pak"])
    size = os.path.getsize(voice.pak)
    writes, new_entries, backups, used = [(o0, _Blob(size, path=voice.pak))], {"pak/sounds_e.pak": (o0, size)}, [], []
    # the pack grows into the files after it; those move to the donor space
    moved, cover = [], o0 + s0
    for off, sz, p in by_offset:
        if cover >= o0 + size:
            break
        if off >= o0 + s0 and off < o0 + size:
            moved.append((p, off, sz))
            cover = max(cover, off + sz)
    backups.append((o0, cover - o0))
    used.append((o0, max(cover, o0 + size) - o0))
    # donor space: the free space after the last file (a plain ISO has ~28 MB of it)
    donors = list(donors_extra)
    if not donors:
        raise ValueError("the voice pack needs the patched copy as a plain ISO")
    items = [(p, _Blob(sz, data=image.read(off, sz))) for p, off, sz in moved]
    for name, path in voice.cutscenes.items():
        if name in entries:
            o, s = entry_region(original, entries[name])
            n = os.path.getsize(path)
            if n <= s:                                     # fits its own slot
                writes.append((o, _Blob(n, path=path)))
                new_entries[name] = (o, n)
                backups.append((o, s))
            else:
                items.append((name, _Blob(n, path=path)))
    placed, left = place([b for _, b in items], donors)
    if left:
        raise ValueError("not enough room on the disc copy for the voice pack")
    for name, blob in items:
        off = placed[blob]
        writes.append((off, blob))
        new_entries[name] = (off, blob.size)
        used.append((off, blob.size))
    return writes, new_entries, backups, used


def apply(image_path, cache_root, mode="off", folder="", seed=0, ffmpeg_path="", log=print, warn=print,
          image_factory=None, voice=None, progress=None):
    """Bring the disc copy at `image_path` to this launch's music and voices. Returns a short summary.
    progress(done, total, song) is called as each of your songs is ready (song = the one just done), as
    converting them is the slow part."""
    if image_factory is None:
        from .patcher import Image as image_factory
    mode = mode if mode in MODES else "off"
    key = hashlib.sha1(os.path.abspath(image_path).lower().encode()).hexdigest()[:16]
    if mode == "off" and voice is None and not os.path.isfile(os.path.join(cache_root, "disc_" + key,
                                                                          "manifest.json")):
        return "music: game soundtrack"             # never changed on this disc copy: nothing to undo
    state_dir = _state_dir(cache_root, image_path)
    manifest_path = os.path.join(state_dir, "manifest.json")
    try:
        with open(manifest_path, encoding="utf-8") as f:
            manifest = json.load(f)
    except (OSError, ValueError):
        manifest = {}

    def save():
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f)

    image = image_factory(image_path, writable=True)
    try:
        fst_off, current = read_fst(image)
        if manifest.get("fst_sha1") != hashlib.sha1(bytes(current)).hexdigest() or not os.path.isfile(
                os.path.join(state_dir, "original_fst.bin")):
            # never touched, or rewritten from the original disc since: the table on it is the original
            with open(os.path.join(state_dir, "original_fst.bin"), "wb") as f:
                f.write(current)
            manifest = {}
        with open(os.path.join(state_dir, "original_fst.bin"), "rb") as f:
            original = bytearray(f.read())
        entries = fst_entries(original)
        tail = []
        if not image.ciso:
            end = max(sum(entry_region(original, i)) for i in entries.values())
            tail = [(end, DISC_SIZE - end)]

        # 1. put back what the last launch's music overwrote (and the first format's per-track backups)
        for name in manifest.pop("overwritten", []):
            old = os.path.join(state_dir, "backup", name.replace("/", "__"))
            if name in entries and os.path.isfile(old):
                with open(old, "rb") as f:
                    image.write_span(entry_region(original, entries[name])[0], f.read())
        _restore(image, state_dir, [tuple(r) for r in manifest.get("music", [])], warn)
        manifest["music"] = []

        # 2. voices: only redone when the voice pack changes
        cur = manifest.get("voice") or {}
        want = voice.key if voice else None
        if cur.get("key") != want:
            _restore(image, state_dir, [tuple(r) for r in cur.get("backups", [])], warn)
            cur = {}
            manifest["voice"] = cur
            save()
            try:
                plan_v = _plan_voice(image, original, entries, voice, tail) if voice else None
            except ValueError as exc:
                warn("Voice pack skipped: %s" % exc)
                plan_v, voice = None, None
            if plan_v:
                writes, new_entries, backups, used = plan_v
                _back_up(image, state_dir, backups)
                cur = {"key": voice.key, "backups": backups, "used": used,
                       "entries": {k: list(v) for k, v in new_entries.items()}}
                manifest["voice"] = cur
                save()                                     # before writing: a crash can still restore
                for off, blob in writes:
                    image.write_span(off, blob.read())
        voice_used = [tuple(r) for r in cur.get("used", [])]

        table = bytearray(original)
        for path, (off, size) in cur.get("entries", {}).items():
            set_entry(table, entries[path], off, size)
        summary = ["%s voices" % voice.language] if voice else []

        # 3. music
        if mode != "off":
            rng = random.Random(seed) if seed else random.Random()
            game = {n: Song(n, g, region=entry_region(original, entries[n]))
                    for g, names in (("bgm", BGM), ("events", EVENTS)) for n in names}
            custom = {"bgm": [], "events": []}
            if mode in ("game_and_custom", "custom_only"):
                conv_dir = os.path.join(cache_root, "converted")
                os.makedirs(conv_dir, exist_ok=True)
                songs = collect(folder, cache_root)
                ffmpeg = find_ffmpeg(ffmpeg_path)
                if songs and not ffmpeg:
                    warn("ffmpeg was not found, so only songs already in the game's format (Ogg Vorbis, stereo, "
                         "32000 Hz) are used. Install ffmpeg (Windows: winget install Gyan.FFmpeg; macOS: brew "
                         "install ffmpeg) and restart the Launcher, or set ffmpeg_path under timesplittersfp_options "
                         "in host.yaml.")
                # one ffmpeg per song, several at once: each mostly keeps a single core busy
                finished = [0]
                lock = threading.Lock()

                def one(song):
                    group, label, src = song
                    out = convert(ffmpeg, src, conv_dir) if ffmpeg else (src if vorbis_ok(src) else None)
                    if progress:
                        with lock:
                            finished[0] += 1
                            progress(finished[0], len(songs), label)
                    return out

                if progress and songs:
                    progress(0, len(songs), songs[0][1])
                with ThreadPoolExecutor(max_workers=CONVERT_WORKERS) as pool:
                    outs = list(pool.map(one, songs))
                bad = 0
                for (group, label, src), out in zip(songs, outs):
                    if out:
                        custom[group].append(Song(label, group, path=out))
                    else:
                        bad += 1
                if bad:
                    warn("%d song(s) could not be used (unreadable, or not convertible without ffmpeg)." % bad)
                if not songs:
                    warn("No songs found in %r; the game's own music is shuffled instead." % folder)
            assign = {}
            assign.update(plan(mode, rng, list(BGM), game, custom["bgm"]))
            assign.update(plan(mode, rng, list(EVENTS), game, custom["events"]))

            # room for the custom songs: game tracks nobody picked, the unused files and the free tail,
            # less whatever the voices took
            picked_game = {s.name for s in assign.values() if not s.custom}
            extents = [game[n].region for n in BGM + EVENTS if n not in picked_game]
            extents += [entry_region(original, entries[n]) for n in UNUSED if n in entries]
            extents = subtract(extents + tail, voice_used)
            customs = list({id(s): s for s in assign.values() if s.custom}.values())
            placed, left = place(customs, extents)
            hit = set()
            for song, off in placed.items():
                for n in BGM + EVENTS:
                    o, s = game[n].region
                    if off < o + s and o < off + song.size:
                        hit.add(n)
            if left:
                # a slot whose song did not fit plays a game track whose data is still intact
                intact = [game[n] for n in BGM if n not in hit]
                warn("%d song(s) did not fit on the disc this time and were swapped for game tracks." % len(left))
                for slot, song in list(assign.items()):
                    if song in left:
                        assign[slot] = game[slot] if slot not in hit else rng.choice(intact)
            # back up every game range a song lands on (the tail is free space), then write the songs
            ranges = [(off, song.size) for song, off in placed.items()
                      if not any(t[0] <= off < t[0] + t[1] for t in tail)]
            _back_up(image, state_dir, ranges)
            manifest["music"] = ranges
            save()
            for song, off in placed.items():
                with open(song.path, "rb") as f:
                    image.write_span(off, f.read())
            for slot, song in assign.items():
                if song.custom:
                    set_entry(table, entries[slot], placed[song], song.size)
                else:
                    set_entry(table, entries[slot], *song.region)
            summary.append("music %s, %d custom song(s)" % (mode, len(placed)))

        image.write_span(fst_off, bytes(table))
        manifest["fst_sha1"] = hashlib.sha1(bytes(table)).hexdigest()
        save()
        text = "disc copy: " + (", ".join(summary) if summary else "normal music and voices")
        log(text)
        return text
    finally:
        image.close()
