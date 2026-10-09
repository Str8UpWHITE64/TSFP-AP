"""Voice packs: the dialogue of a European disc (French, German, Italian or Spanish) in the US game.

A European disc differs from the US one only by its sound pack (`pak/sounds_<l>.pak`, every sound
effect plus the in-level dialogue) and its cutscene tracks (`music/<language>/cs*.ogg`, the cutscene
dialogue is mixed into them). The packs list the same sounds in the same order; only the voice
lines' audio differs, and the index at the end of the pack files each voice line under a hash of
its language's path (`sfx/french/...`) where the US game asks for `sfx/...`. So the pack goes in
with those hashes re-filed under the US paths, and the cutscene tracks under the US names. No code
changes.

Pack layout: "P5CK", +4 data size, +8 index size; `sound/sounddata` first (u16 count, then
length-prefixed names, voice lines marked "!"), and the index at the end: per sound
{crc32(path), offset, size, 0}, little-endian, in sounddata order.
"""
import hashlib
import os
import shutil
import struct
import subprocess
import zlib

LANGUAGES = {"f": "french", "g": "german", "i": "italian", "s": "spanish"}
VERSION = 1                                      # bump when the prepared files change


class VoicePack:
    def __init__(self, language, pak, cutscenes, key):
        self.language = language                 # "french", ...
        self.pak = pak                           # prepared sound pack, re-filed for the US game
        self.cutscenes = cutscenes               # {"music/csNN....ogg": file}
        self.key = key                           # identity of this prepared pack


def _names(sounddata):
    count = struct.unpack("<H", sounddata[:2])[0]
    i, names = 2, []
    for _ in range(count + 1):
        n = sounddata[i]
        names.append(sounddata[i + 1:i + 1 + n].decode("latin-1"))
        i += 1 + n
    return names


def _path(name, folder):
    base = name[:-4] + (".dsp" if name[-4:].lower() == ".vag" else ".mss")
    return (folder + "/" + base[1:]) if base.startswith("!") else ("sfx/" + base)


def refile(pak_path, language):
    """Re-file the pack's voice lines (in place) under the US game's paths. Returns how many."""
    with open(pak_path, "r+b") as f:
        head = f.read(0x20)
        if head[:4] != b"P5CK":
            raise ValueError("not a sound pack")
        data_size, index_size = struct.unpack("<II", head[4:12])
        names = _names(f.read(0x40000))
        remap = {zlib.crc32(_path(n, "sfx/" + language).encode()): zlib.crc32(_path(n, "sfx").encode())
                 for n in names if n.startswith("!")}
        f.seek(data_size)
        index = bytearray(f.read(index_size))
        changed = 0
        for k in range(0, len(index), 16):
            h = struct.unpack("<I", index[k:k + 4])[0]
            if h in remap:
                index[k:k + 4] = struct.pack("<I", remap[h])
                changed += 1
        f.seek(data_size)
        f.write(index)
    return changed


# --- reading the disc ----------------------------------------------------------------
def _dolphin_tool(dolphin_path):
    folder = os.path.dirname(str(dolphin_path or ""))
    for name in ("DolphinTool.exe", "dolphin-tool", "DolphinTool"):
        p = os.path.join(folder, name)
        if folder and os.path.isfile(p):
            return p
    return shutil.which("dolphin-tool") or shutil.which("DolphinTool")


def _run(args):
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace",
                          stdin=subprocess.DEVNULL, creationflags=flags, timeout=1800)


class _Disc:
    """Files of a disc image: read directly for ISO/GCM/CISO, through DolphinTool otherwise."""

    def __init__(self, path, dolphin_path, image_factory):
        self.path = path
        with open(path, "rb") as f:
            head = f.read(8)
        self.image = None
        if head[:4] == b"CISO" or head[:1] == b"G":
            self.image = image_factory(path)
            self.game_id = self.image.read(0, 6).decode("latin-1")
            from .music import read_fst, fst_entries, entry_region
            _, self.fst = read_fst(self.image)
            self.files = {p: entry_region(self.fst, i) for p, i in fst_entries(self.fst).items()}
        else:
            self.tool = _dolphin_tool(dolphin_path)
            if not self.tool:
                raise ValueError("this disc format needs DolphinTool, which comes with Dolphin; set dolphin_path, "
                                 "or convert the disc to ISO in Dolphin")
            out = _run([self.tool, "header", "-i", path]).stdout
            self.game_id = next((l.split(":", 1)[1].strip() for l in out.splitlines()
                                 if l.lower().startswith("game id")), "")
            listing = _run([self.tool, "extract", "-l", "-i", path]).stdout
            self.files = {l.strip(): None for l in listing.splitlines() if l.strip() and not l.strip().endswith("/")}

    def extract(self, inner, dest):
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        if self.image is not None:
            off, size = self.files[inner]
            with open(dest + ".part", "wb") as out:
                done = 0
                while done < size:
                    n = min(16 << 20, size - done)
                    out.write(self.image.read(off + done, n))
                    done += n
        else:
            tmp = dest + ".dir"
            shutil.rmtree(tmp, ignore_errors=True)
            _run([self.tool, "extract", "-q", "-i", self.path, "-s", inner, "-o", tmp])
            got = os.path.join(tmp, "files", *inner.split("/"))
            if not os.path.isfile(got):
                got = os.path.join(tmp, *inner.split("/"))
            if not os.path.isfile(got):
                shutil.rmtree(tmp, ignore_errors=True)
                raise ValueError("could not extract %s" % inner)
            shutil.move(got, dest + ".part")
            shutil.rmtree(tmp, ignore_errors=True)
        os.replace(dest + ".part", dest)

    def close(self):
        if self.image is not None:
            self.image.close()


def prepare(disc_path, dolphin_path, cache_root, image_factory, log=print):
    """The voice pack of the disc at `disc_path`, prepared once and cached. None for an English disc."""
    st = os.stat(disc_path)
    key = hashlib.sha1(("%s|%d|%d|v%d" % (os.path.abspath(disc_path).lower(), st.st_size, int(st.st_mtime),
                                          VERSION)).encode()).hexdigest()[:16]
    root = os.path.join(cache_root, "voice_" + key)
    done = os.path.join(root, "ready.txt")
    if os.path.isfile(done):
        with open(done, encoding="utf-8") as f:
            language = f.read().strip()
        if language == "english":
            return None
        cut = {}
        cdir = os.path.join(root, "cutscenes")
        for name in sorted(os.listdir(cdir)) if os.path.isdir(cdir) else []:
            cut["music/" + name] = os.path.join(cdir, name)
        return VoicePack(language, os.path.join(root, "sounds.pak"), cut, key)

    disc = _Disc(disc_path, dolphin_path, image_factory)
    try:
        if not disc.game_id.startswith("G3F"):
            raise ValueError("%s is not TimeSplitters: Future Perfect (game ID %r)" % (os.path.basename(disc_path),
                                                                                       disc.game_id))
        paks = [p for p in disc.files if p.startswith("pak/sounds_") and p.endswith(".pak")]
        letter = paks[0][len("pak/sounds_")] if len(paks) == 1 else ""
        if letter == "e":
            os.makedirs(root, exist_ok=True)
            with open(done, "w", encoding="utf-8") as f:
                f.write("english")
            return None
        if letter not in LANGUAGES:
            raise ValueError("no single language sound pack on %s" % os.path.basename(disc_path))
        language = LANGUAGES[letter]
        log("Preparing the %s voices from %s (once; this can take a minute)..." % (language,
                                                                                  os.path.basename(disc_path)))
        shutil.rmtree(root, ignore_errors=True)
        os.makedirs(root, exist_ok=True)
        pak = os.path.join(root, "sounds.pak")
        disc.extract(paks[0], pak)
        refile(pak, language)
        prefix = "music/%s/" % language
        for inner in sorted(p for p in disc.files if p.startswith(prefix) and p.endswith(".ogg")):
            disc.extract(inner, os.path.join(root, "cutscenes", inner[len(prefix):]))
        with open(done, "w", encoding="utf-8") as f:
            f.write(language)
    finally:
        disc.close()
    return prepare(disc_path, dolphin_path, cache_root, image_factory, log)
