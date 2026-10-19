#!/usr/bin/env python3
"""copilot_l10n.py - patch the web assets embedded in the GitHub Copilot desktop app.

The app is a Tauri/Rust binary. Its front-end files live Brotli-compressed inside the
PE `.rdata` section and each asset is described by an (absolute pointer, compressed
length) pair in a descriptor table. Re-compressing at Brotli quality 11 usually beats
the size produced at build time, so an asset can be rewritten in place as long as the
new stream is not larger than the old one. The descriptor length is updated as well.

Commands
--------
    python copilot_l10n.py stat    <asset>
    python copilot_l10n.py find    <substring>
    python copilot_l10n.py status  [asset]
    python copilot_l10n.py list    [pattern]
    python copilot_l10n.py extract <asset> [out-file]
    python copilot_l10n.py patch   <asset> <payload.js>
    python copilot_l10n.py replace <asset> <map.json>
    python copilot_l10n.py verify  <asset> [<asset> ...]
    python copilot_l10n.py baseline <asset> ...
    python copilot_l10n.py rebaseline <asset> ...
    python copilot_l10n.py restore

Options
-------
    --exe PATH     target executable (defaults to the installed app)
    --copy PATH    patch a copy instead of the original (safe while the app runs)
    --dry-run      compute everything but do not write
    --force        append even if the payload marker is already present

Notes
-----
* A backup is created once at ``<exe>.l10n-bak``.
* Modifying the binary invalidates its Authenticode signature. The app still runs, but
  Windows SmartScreen may warn, and app updates overwrite the patch - re-run afterwards.
* The executable is locked while the app is running, so close the app first (or use
  ``--copy``).
"""

from __future__ import annotations

import argparse
import concurrent.futures
import contextlib
import json
import mmap
import os
import shutil
import struct
import sys
import threading
import time

try:
    import brotli
except ImportError:  # pragma: no cover
    sys.exit("missing dependency: python -m pip install -r requirements.txt")

DEFAULT_EXE = r"C:\Users\long1\AppData\Local\Programs\GitHub Copilot\github.exe"
MARKER = "/*__COPILOT_L10N__*/"

BROTLI_ARGS = dict(quality=11, lgwin=22, mode=brotli.MODE_TEXT)
BROTLI_QUALITIES = (10, 11)
MAX_ASSET = 64 * 1024 * 1024


# --------------------------------------------------------------------------- PE

def parse_pe(data) -> dict:
    if bytes(data[0:2]) != b"MZ":
        raise ValueError("not a PE file (missing MZ header)")
    pe_off = struct.unpack_from("<I", data, 0x3C)[0]
    if bytes(data[pe_off:pe_off + 4]) != b"PE\0\0":
        raise ValueError("not a PE file (bad signature)")
    num_sections = struct.unpack_from("<H", data, pe_off + 6)[0]
    opt_size = struct.unpack_from("<H", data, pe_off + 20)[0]
    opt = pe_off + 24
    if struct.unpack_from("<H", data, opt)[0] != 0x20B:
        raise ValueError("only PE32+ executables are supported")
    image_base = struct.unpack_from("<Q", data, opt + 24)[0]

    sections = []
    pos = opt + opt_size
    for _ in range(num_sections):
        name = bytes(data[pos:pos + 8]).rstrip(b"\0").decode("latin1")
        vsize, va, raw_size, raw_ptr = struct.unpack_from("<IIII", data, pos + 8)
        sections.append(dict(name=name, va=va, vsize=vsize,
                             raw_ptr=raw_ptr, raw_size=raw_size))
        pos += 40
    return dict(image_base=image_base, sections=sections)


def section_for(pe: dict, file_off: int):
    for sec in pe["sections"]:
        if sec["raw_ptr"] <= file_off < sec["raw_ptr"] + sec["raw_size"]:
            return sec
    return None


def rva_of(pe: dict, file_off: int) -> int:
    sec = section_for(pe, file_off)
    if sec is None:
        raise ValueError("offset 0x%x is outside every PE section" % file_off)
    return sec["va"] + (file_off - sec["raw_ptr"])


# ---------------------------------------------------------------------- assets

def _try_decompress(data, start: int, length: int):
    try:
        return brotli.decompress(bytes(data[start:start + length]))
    except Exception:
        return None


def build_descriptor_index(data, pe: dict) -> dict:
    """Map rva -> (descriptor_offset, compressed_length) by scanning each section once.

    Without this, locating an asset rescans the whole executable for every path string
    that happens to match, which costs tens of seconds on a 490 MB binary.
    """
    index = {}
    hi = struct.pack("<I", pe["image_base"] >> 32)
    image_base = pe["image_base"]
    for sec in pe["sections"]:
        if sec["raw_size"] < 1024:
            continue
        start = sec["raw_ptr"]
        end = sec["raw_ptr"] + sec["raw_size"] - 16
        pos = data.find(hi, start, end)
        while pos != -1:
            ptr_off = pos - 4
            if ptr_off >= start and (ptr_off - start) % 8 == 0:
                ptr = struct.unpack_from("<Q", data, ptr_off)[0]
                rva = ptr - image_base
                if 0 < rva < 0x80000000 and rva not in index:
                    length = struct.unpack_from("<Q", data, ptr_off + 8)[0]
                    if 16 < length < MAX_ASSET:
                        index[rva] = (ptr_off, length)
            pos = data.find(hi, pos + 1, end)
    return index


def find_descriptor(data, pe: dict, blob_off: int, expected_len=None, index=None):
    """Return (descriptor_offset, compressed_length) for a blob, or None.

    The search is bounded to the section that holds the blob: descriptors live next to
    the asset blobs, so a full-file scan is never needed.
    """
    rva = rva_of(pe, blob_off)
    if index is not None:
        hit = index.get(rva)
        if hit is None:
            return None
        desc_off, length = hit
        if blob_off + length > len(data):
            return None
        if expected_len is not None and length != expected_len:
            return None
        return desc_off, length

    sec = section_for(pe, blob_off)
    start = sec["raw_ptr"] if sec else 0
    end = (sec["raw_ptr"] + sec["raw_size"]) if sec else len(data)
    needle = struct.pack("<Q", pe["image_base"] + rva)
    pos = data.find(needle, start, end)
    while pos != -1:
        length = struct.unpack_from("<Q", data, pos + 8)[0]
        if 16 < length < MAX_ASSET and blob_off + length <= len(data):
            if expected_len is None or length == expected_len:
                return pos, length
        pos = data.find(needle, pos + 1, end)
    return None


def locate_asset(data, pe: dict, asset: str, index=None) -> dict:
    needle = asset.encode("latin1")
    matches = []
    # Asset blobs and their path strings live in the read-only data section, so scan
    # that range first; only fall back to the whole file when nothing is found.
    ranges = []
    for sec in pe["sections"]:
        if "rdata" in sec["name"].lower() or "rodata" in sec["name"].lower():
            ranges.append((sec["raw_ptr"], sec["raw_ptr"] + sec["raw_size"]))
    ranges.append((0, len(data)))

    seen_pos = set()
    for start, end in ranges:
        pos = data.find(needle, start, end)
        while pos != -1:
            if pos in seen_pos:
                pos = data.find(needle, pos + 1, end)
                continue
            seen_pos.add(pos)
            blob = pos + len(needle)
            desc = find_descriptor(data, pe, blob, index=index)
            if desc:
                desc_off, length = desc
                raw = _try_decompress(data, blob, length)
                if raw is not None:
                    # exact length: one byte fewer must fail, otherwise the length is wrong
                    if _try_decompress(data, blob, length - 1) is None:
                        matches.append(dict(path_off=pos, blob_off=blob,
                                            desc_off=desc_off,
                                            br_len=length, raw=raw))
            pos = data.find(needle, pos + 1, end)
        if matches:
            break

    if not matches:
        raise LookupError("asset not found: %s" % asset)
    unique = sorted({m["blob_off"] for m in matches})
    if len(unique) > 1:
        raise LookupError("ambiguous asset (%d blobs): %s" % (len(unique), asset))
    return matches[0]


def compress_at(raw: bytes, quality: int) -> bytes:
    import hashlib

    key = (hashlib.sha1(raw).digest(), quality)
    cached = _COMPRESS_CACHE.get(key)
    if cached is not None:
        return cached

    packed = brotli.compress(raw, quality=quality, lgwin=22, mode=brotli.MODE_TEXT)
    if len(_COMPRESS_CACHE) >= _COMPRESS_CACHE_LIMIT:
        _COMPRESS_CACHE.clear()
    _COMPRESS_CACHE[key] = packed
    return packed


def compress(raw: bytes) -> bytes:
    """Best-quality compression (memoised). Used for reporting/stat."""
    return compress_at(raw, 11)


def compress_fitting(raw: bytes, limit: int):
    """Compress as cheaply as possible while staying within `limit` bytes.

    Quality 10 runs roughly 2.5x faster than 11 on multi-megabyte chunks and is only
    ~2% larger, so it is tried first and 11 is the fallback. Returns (bytes, quality).
    """
    smallest = None
    smallest_q = BROTLI_QUALITIES[-1]
    for quality in BROTLI_QUALITIES:
        packed = compress_at(raw, quality)
        if smallest is None or len(packed) < len(smallest):
            smallest, smallest_q = packed, quality
        if len(packed) <= limit:
            return packed, quality
    return smallest, smallest_q


_COMPRESS_CACHE: dict = {}
_COMPRESS_CACHE_LIMIT = 16


def log(message: str) -> None:
    print("[%6.1fs] %s" % (time.monotonic() - _START, message), flush=True)


@contextlib.contextmanager
def heartbeat(label: str):
    """Print a dot per second while a slow native call runs, so it never looks hung."""
    stop = threading.Event()

    def run():
        while not stop.wait(1.0):
            sys.stdout.write(".")
            sys.stdout.flush()

    started = time.monotonic()
    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    sys.stdout.write("%s " % label)
    sys.stdout.flush()
    try:
        yield
    finally:
        stop.set()
        thread.join(timeout=2)
        sys.stdout.write(" done in %.1fs\n" % (time.monotonic() - started))
        sys.stdout.flush()


def _locate_cache_path(path: str):
    import hashlib
    import tempfile

    try:
        size = os.path.getsize(path)
    except OSError:
        return None
    # Keyed by size only: patching changes the mtime but never moves an asset, and every
    # cached entry is validated by decompressing at the recorded offset.
    digest = hashlib.sha1(
        ("%s|%d" % (os.path.abspath(path), size)).encode()
    ).hexdigest()[:20]
    return os.path.join(tempfile.gettempdir(), "copilot-l10n-loc-%s.json" % digest)


def _load_locate_cache(path: str) -> dict:
    cache_file = _locate_cache_path(path)
    if not cache_file:
        return {}
    try:
        with open(cache_file, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def _save_locate_cache(path: str, entries: dict) -> None:
    cache_file = _locate_cache_path(path)
    if not cache_file:
        return
    try:
        with open(cache_file, "w", encoding="utf-8") as fh:
            json.dump(entries, fh)
    except OSError:
        pass


_START = time.monotonic()


def reset_timer() -> None:
    global _START
    _START = time.monotonic()


# ------------------------------------------------------------------- file I/O

_INDEX_CACHE: dict = {}


def _cached_index(path: str, data, pe: dict) -> dict:
    """Descriptor index for an executable revision, cached in memory and on disk.

    Scanning every section takes seconds on a 490 MB binary and the pipeline opens the
    file (and its backup) several times, so the result is persisted in the temp dir and
    keyed by absolute path + size + mtime.
    """
    try:
        stat = os.stat(path)
        key = (stat.st_size, stat.st_mtime_ns)
    except OSError:
        return build_descriptor_index(data, pe)

    entry = _INDEX_CACHE.get(path)
    if entry and entry[0] == key:
        return entry[1]

    disk = None
    import hashlib
    import pickle
    import tempfile

    try:
        digest = hashlib.sha1(
            ("%s|%d|%d" % (os.path.abspath(path), key[0], key[1])).encode()
        ).hexdigest()[:20]
        disk = os.path.join(tempfile.gettempdir(), "copilot-l10n-idx-%s.pkl" % digest)
        with open(disk, "rb") as fh:
            index = pickle.load(fh)
        _INDEX_CACHE[path] = (key, index)
        return index
    except Exception:  # noqa: BLE001 - any cache miss is fine
        pass

    index = build_descriptor_index(data, pe)
    _INDEX_CACHE[path] = (key, index)
    if disk:
        try:
            with open(disk, "wb") as fh:
                pickle.dump(index, fh, protocol=pickle.HIGHEST_PROTOCOL)
        except OSError:
            pass
    return index


_INSTANCES: dict = {}


def invalidate(path: str) -> None:
    """Drop the cached view of a file after it has been modified."""
    inst = _INSTANCES.pop(os.path.abspath(path), None)
    if inst is not None:
        inst.close()
    _INDEX_CACHE.pop(path, None)


class AssetFile:
    """Mmap view of the executable, reused across opens.

    A 490 MB mmap costs real time to fault in, and the pipeline inspects the same file
    (and its backup) several times per run, so instances are cached by path.
    """

    def __new__(cls, path: str):
        key = os.path.abspath(path)
        inst = _INSTANCES.get(key)
        if inst is not None and not inst._closed:
            return inst
        inst = super().__new__(cls)
        _INSTANCES[key] = inst
        return inst

    def __init__(self, path: str):
        if getattr(self, "_ready", False):
            return
        self.path = path
        self._closed = False
        self._fh = open(path, "rb")
        self.data = mmap.mmap(self._fh.fileno(), 0, access=mmap.ACCESS_READ)
        self.pe = parse_pe(self.data)
        self._index = None
        self._found = {}
        self._locate_cache = None
        self._ready = True

    @property
    def index(self) -> dict:
        if self._index is None:
            self._index = _cached_index(self.path, self.data, self.pe)
        return self._index

    def locate(self, asset: str) -> dict:
        cached = self._found.get(asset)
        if cached is not None:
            return cached

        if self._locate_cache is None:
            self._locate_cache = _load_locate_cache(self.path)
        hint = self._locate_cache.get(asset)
        if hint:
            # The descriptor is a stable offset; read the current length from it so a
            # previously patched file still validates.
            length = struct.unpack_from("<Q", self.data, hint["desc_off"] + 8)[0]
            if 16 < length < MAX_ASSET:
                raw = _try_decompress(self.data, hint["blob_off"], length)
                if raw is not None:
                    cached = dict(path_off=hint.get("path_off", 0),
                                  blob_off=hint["blob_off"],
                                  desc_off=hint["desc_off"],
                                  br_len=length, raw=raw)
                    self._found[asset] = cached
                    return cached

        # No descriptor index: the pointer search is bounded to one PE section and
        # costs milliseconds, while building the index scans the whole binary.
        cached = locate_asset(self.data, self.pe, asset)
        self._found[asset] = cached
        self._locate_cache[asset] = dict(path_off=cached["path_off"],
                                         blob_off=cached["blob_off"],
                                         desc_off=cached["desc_off"],
                                         br_len=cached["br_len"])
        _save_locate_cache(self.path, self._locate_cache)
        return cached

    def close(self):
        if getattr(self, "_closed", True):
            return
        self._closed = True
        try:
            self.data.close()
        finally:
            self._fh.close()
        _INSTANCES.pop(os.path.abspath(self.path), None)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        # Instances stay open so later steps reuse the same mapping.
        return False


def backup_path(exe: str) -> str:
    return exe + ".l10n-bak"


def assert_writable(exe: str) -> None:
    """Fail fast (before copying a 500 MB backup) when the app is still running."""
    try:
        with open(exe, "r+b"):
            pass
    except PermissionError:
        raise PermissionError(
            "%s is locked (the app is running). Close it first, or use --copy."
            % exe
        )


def ensure_backup(exe: str) -> str:
    """Create the pristine backup if it does not exist yet. Never overwrites it."""
    bak = backup_path(exe)
    if not os.path.exists(bak):
        size = os.path.getsize(exe)
        log("creating pristine backup (%.0f MB, one time only)" % (size / 1e6))
        with heartbeat("  copying"):
            shutil.copy2(exe, bak)
        log("backup ready: %s" % bak)
        return "backup created: %s" % bak
    return "backup already present: %s" % bak


def _is_pristine(raw: bytes) -> bool:
    return MARKER.encode() not in raw and b'lang="zh-CN"' not in raw


def ensure_clean_baseline(exe: str, assets, dry_run=False) -> dict:
    """Guarantee every target asset is at its pristine state before patching.

    The patch is always computed on top of the original (unpatched) bytes, so repeated
    installs never stack payloads. The pristine bytes come from ``<exe>.l10n-bak``,
    which is created once and never overwritten.
    """
    bak = backup_path(exe)
    result = {}

    if not os.path.exists(bak):
        with AssetFile(exe) as af:
            for asset in assets:
                raw = af.locate(asset)["raw"]
                if not _is_pristine(raw):
                    raise ValueError(
                        "%s is already patched but no pristine backup exists at %s. "
                        "Reinstall the app, or restore it manually, then run again."
                        % (exe, bak)
                    )
        if dry_run:
            return {a: "would-create-backup" for a in assets}
        ensure_backup(exe)
        return {a: "backup-created" for a in assets}

    if os.path.getsize(exe) != os.path.getsize(bak):
        raise ValueError(
            "executable size differs from the backup (%d vs %d): the app was probably "
            "updated. Delete %s to adopt the new version as the new baseline, then "
            "re-run." % (os.path.getsize(exe), os.path.getsize(bak), bak)
        )

    restores = []
    with AssetFile(bak) as b_af, AssetFile(exe) as e_af:
        for asset in assets:
            b = b_af.locate(asset)
            if not _is_pristine(b["raw"]):
                raise ValueError(
                    "backup %s is not pristine for %s; it cannot be used as a baseline. "
                    "Delete it and reinstall the app." % (bak, asset)
                )
            e = e_af.locate(asset)
            if e["blob_off"] != b["blob_off"] or e["desc_off"] != b["desc_off"]:
                raise ValueError(
                    "asset layout in %s differs from the backup; delete %s and re-install."
                    % (exe, bak)
                )
            same_len = e["br_len"] == b["br_len"]
            if same_len:
                clean = bytes(b_af.data[b["blob_off"]:b["blob_off"] + b["br_len"]])
                current = bytes(e_af.data[e["blob_off"]:e["blob_off"] + e["br_len"]])
                same_len = clean == current
            if same_len:
                result[asset] = "pristine"
            else:
                restores.append((asset, b["blob_off"], b["br_len"], b["desc_off"]))
                result[asset] = "restored"

    if not restores:
        return result
    if dry_run:
        return {a: ("would-restore" if a in [r[0] for r in restores] else v)
                for a, v in result.items()}

    assert_writable(exe)
    with open(exe, "r+b") as fh:
        for _asset, blob_off, br_len, desc_off in restores:
            fh.seek(blob_off)
            with open(bak, "rb") as bf:
                bf.seek(blob_off)
                fh.write(bf.read(br_len))
            fh.seek(desc_off + 8)
            fh.write(struct.pack("<Q", br_len))
        fh.flush()
        os.fsync(fh.fileno())
    # The bytes on disk just changed; drop the cached mapping and locate results.
    invalidate(exe)
    return result


def rebaseline(exe: str, assets) -> str:
    """Replace the backup with the current executable (only when it is pristine)."""
    with AssetFile(exe) as af:
        for asset in assets:
            if not _is_pristine(af.locate(asset)["raw"]):
                raise ValueError(
                    "%s still contains a patch (%s); run `restore` before re-baselining."
                    % (exe, asset)
                )
    bak = backup_path(exe)
    if os.path.exists(bak):
        os.remove(bak)
    shutil.copy2(exe, bak)
    return "baseline adopted from %s: %s" % (exe, bak)


def rewrite_asset(exe: str, asset: str, transform, dry_run=False) -> dict:
    return rewrite_assets(exe, [(asset, transform)], dry_run)[0]


def rewrite_assets(exe: str, edits, dry_run=False, baseline_assets=None) -> list:
    """Apply several asset edits through a single open handle.

    Writing everything in one `open()` window matters: the app may be relaunched by a
    watchdog between two separate writes, which would leave a half-applied patch.
    """
    plan = []
    reset_targets = list(baseline_assets or [])
    for asset, _transform in edits:
        if asset not in reset_targets:
            reset_targets.append(asset)
    if not dry_run:
        log("checking pristine baseline (%d assets)" % len(reset_targets))
        baseline = ensure_clean_baseline(exe, reset_targets)
        log("baseline ready: %s" % ", ".join(
            "%s=%s" % (k.rsplit("/", 1)[-1], v) for k, v in baseline.items()))
    else:
        baseline = {}

    pending = []
    with AssetFile(exe) as af:
        for asset, transform in edits:
            log("reading %s" % asset)
            found = af.locate(asset)
            raw_after = transform(found["raw"])
            if raw_after == found["raw"]:
                # Nothing to change (already patched, or the transform is a no-op here).
                # Rewriting the descriptor would pair a stale length with current bytes.
                log("  unchanged, skipped")
                continue
            pending.append((asset, found, raw_after))

    # Compress the chunks concurrently: brotli releases the GIL, and the big chunks
    # dominate the runtime.
    if pending:
        log("compressing %d chunk(s) in parallel" % len(pending))
        with heartbeat("  brotli q10"):
            with concurrent.futures.ThreadPoolExecutor(len(pending)) as pool:
                futures = [
                    pool.submit(compress_fitting, raw_after, found["br_len"])
                    for _asset, found, raw_after in pending
                ]
                results = [f.result() for f in futures]

    for (asset, found, raw_after), (payload_bytes, quality) in zip(pending, results):
        log("  %s -> %d bytes (quality %d, %d bytes of headroom)"
            % (asset.rsplit("/", 1)[-1], len(payload_bytes), quality,
               found["br_len"] - len(payload_bytes)))
        info = dict(
            asset=asset,
            raw_before=len(found["raw"]),
            raw_after=len(raw_after),
            br_before=found["br_len"],
            br_after=len(payload_bytes),
            slack=found["br_len"] - len(payload_bytes),
            blob_off=found["blob_off"],
            desc_off=found["desc_off"],
            fits=len(payload_bytes) <= found["br_len"],
        )
        if not info["fits"]:
            raise ValueError(
                "does not fit: %s needs %d > %d (overflow %d bytes). "
                "Shorten the payload or use a larger asset."
                % (asset, len(payload_bytes), found["br_len"],
                   len(payload_bytes) - found["br_len"])
            )
        plan.append(dict(info=info, packed=payload_bytes,
                         old_len=found["br_len"],
                         blob_off=found["blob_off"],
                         desc_off=found["desc_off"]))

    if dry_run:
        return [p["info"] for p in plan]

    if not plan:
        log("nothing to write")
        return []

    assert_writable(exe)
    log("writing %d asset(s) in one pass" % len(plan))
    backup = ensure_backup(exe)
    log("backup: %s" % backup)
    try:
        with open(exe, "r+b") as fh:
            for p in plan:
                packed, old_len = p["packed"], p["old_len"]
                fh.seek(p["blob_off"])
                fh.write(packed)
                if len(packed) < old_len:
                    fh.write(b"\0" * (old_len - len(packed)))
                fh.seek(p["desc_off"] + 8)
                fh.write(struct.pack("<Q", len(packed)))
            fh.flush()
            os.fsync(fh.fileno())
    except PermissionError:
        raise PermissionError(
            "%s is locked (the app was restarted). Nothing was written; "
            "close the app and run again." % exe
        )
    for p in plan:
        p["info"]["backup"] = backup
        p["info"]["baseline"] = baseline.get(p["info"]["asset"], "unknown")
    _INDEX_CACHE.pop(exe, None)
    invalidate(exe)
    log("write complete")
    return [p["info"] for p in plan]


# ------------------------------------------------------------------- commands

def cmd_stat(exe: str, asset: str):
    with AssetFile(exe) as af:
        found = af.locate(asset)
        recom = compress(found["raw"])
        print(json.dumps({
            "asset": asset,
            "blob_off": "0x%x" % found["blob_off"],
            "desc_off": "0x%x" % found["desc_off"],
            "raw_size": len(found["raw"]),
            "compressed_size": found["br_len"],
            "recompress_q11": len(recom),
            "headroom": found["br_len"] - len(recom),
        }, ensure_ascii=False, indent=2))


def cmd_find(exe: str, substring: str):
    """List embedded assets whose path contains `substring` (useful after updates)."""
    needle = b"/assets/" + substring.encode("latin1")
    path_chars = set(b"abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-/@")
    seen = set()
    with AssetFile(exe) as af:
        pos = af.data.find(needle)
        while pos != -1:
            end = pos
            while end < len(af.data) and af.data[end] in path_chars:
                end += 1
            path = bytes(af.data[pos:end]).decode("latin1")
            if path not in seen:
                seen.add(path)
                try:
                    found = af.locate(path)
                except Exception:
                    found = None
                if found:
                    headroom = found["br_len"] - len(compress(found["raw"]))
                    print("%-52s raw=%-9d br=%-8d headroom=%d"
                          % (path, len(found["raw"]), found["br_len"], headroom))
            pos = af.data.find(needle, pos + 1)
    if not seen:
        print("no asset matched %r" % substring)


def cmd_extract(exe: str, asset: str, out_file=None):
    with AssetFile(exe) as af:
        found = af.locate(asset)
        raw = found["raw"]
    out_file = out_file or os.path.basename(asset) or "asset.bin"
    with open(out_file, "wb") as fh:
        fh.write(raw)
    print("wrote %d bytes to %s" % (len(raw), out_file))


def cmd_patch(exe: str, asset: str, payload_file: str, dry_run=False, force=False):
    with open(payload_file, "rb") as fh:
        payload = fh.read()

    def transform(raw: bytes) -> bytes:
        text = raw.decode("utf-8")
        if not force and MARKER in text:
            raise ValueError("asset already contains a l10n payload (use --force)")
        return raw + b"\n" + payload + b"\n"

    info = rewrite_asset(exe, asset, transform, dry_run)
    print(json.dumps(info, ensure_ascii=False, indent=2))


def cmd_replace(exe: str, asset: str, map_file: str, dry_run=False):
    with open(map_file, "r", encoding="utf-8") as fh:
        mapping = json.load(fh)

    def transform(raw: bytes) -> bytes:
        text = raw.decode("utf-8")
        applied = 0
        for old, new in mapping.items():
            if old in text:
                text = text.replace(old, new)
                applied += 1
        print("applied %d/%d replacements" % (applied, len(mapping)))
        if applied == 0:
            raise ValueError("no replacement matched")
        return text.encode("utf-8")

    info = rewrite_asset(exe, asset, transform, dry_run)
    print(json.dumps(info, ensure_ascii=False, indent=2))


def iter_assets(data, pe: dict):
    """Yield (path, blob_off, br_len) for every embedded asset, using the descriptor table.

    Descriptors are (absolute_pointer, length) qwords; the asset path is stored as a
    plain string immediately before its compressed blob.
    """
    path_chars = set(b"abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-/@")
    image_base = pe["image_base"]
    # A pointer is 0x0000000140000000+rva, i.e. in little endian the high dword is 0x01.
    hi = struct.pack("<I", image_base >> 32)
    seen = set()
    for sec in pe["sections"]:
        if sec["raw_size"] < 1024:
            continue
        start = sec["raw_ptr"]
        end = sec["raw_ptr"] + sec["raw_size"] - 16
        pos = data.find(hi, start, end)
        while pos != -1:
            ptr_off = pos - 4
            if ptr_off >= start and (ptr_off - start) % 8 == 0:
                ptr = struct.unpack_from("<Q", data, ptr_off)[0]
                rva = ptr - image_base
                if 0 < rva < 0x80000000:
                    blob = file_off_of_rva(pe, rva)
                    if blob > 0:
                        length = struct.unpack_from("<Q", data, ptr_off + 8)[0]
                        if 16 < length < MAX_ASSET and blob + length <= len(data):
                            s = blob
                            while s > 0 and blob - s < 240 and data[s - 1] in path_chars:
                                s -= 1
                            if s < blob:
                                path = bytes(data[s:blob]).decode("latin1")
                                key = (path, blob)
                                if key not in seen:
                                    seen.add(key)
                                    yield path, blob, length
            pos = data.find(hi, pos + 1, end)


def file_off_of_rva(pe: dict, rva: int) -> int:
    for sec in pe["sections"]:
        if sec["va"] <= rva < sec["va"] + sec["raw_size"]:
            return sec["raw_ptr"] + (rva - sec["va"])
    return -1


def cmd_list(exe: str, pattern: str = ""):
    with AssetFile(exe) as af:
        rows = [a for a in iter_assets(af.data, af.pe) if pattern in a[0]]
    rows.sort()
    for path, _blob, length in rows:
        print("%-56s br=%d" % (path, length))
    print("%d asset(s)" % len(rows))


def cmd_status(exe: str, asset: str):
    """Report whether the localizer is installed and up to date."""
    import apply_zh  # local import: apply_zh imports this module

    engine_sig = b'[copilot-l10n] zh-CN active'
    candidates = list(apply_zh.ASSET_CANDIDATES) if asset in ("auto", "", None) else [asset]
    shards = len(apply_zh.build_shard_scripts())
    found_engine = 0
    found_shards = 0
    with AssetFile(exe) as af:
        for candidate in candidates:
            try:
                raw = af.locate(candidate)["raw"]
            except Exception:
                continue
            count = raw.count(MARKER.encode())
            if count:
                found_shards += count
                print("chunk     : %s -> shards x%d" % (candidate, count))
            found_engine += raw.count(engine_sig)
        try:
            html = af.locate("index.html")["raw"]
            lang_zh = b'lang="zh-CN"' in html
        except Exception:
            lang_zh = None
    print("index.html: lang=\"zh-CN\" %s" % ("present" if lang_zh else "absent"))
    print("engine    : %d copy(ies), %d shard(s) found / %d expected"
          % (found_engine, found_shards, shards))
    bak = backup_path(exe)
    print("backup    : %s (%s)" % (bak, "ok" if os.path.exists(bak) else "MISSING"))

    installed = found_engine >= 1 and lang_zh is True
    print("state     : %s" % ("INSTALLED" if installed else "NOT INSTALLED"))

    if found_engine > 1:
        print("WARNING   : %d engine copies found; re-run install to reset the baseline."
              % found_engine)
    if installed:
        current = apply_zh.is_current(exe, "auto")
        print("up to date: %s" % ("yes" if current else
                                  "no (dictionary changed, re-run install)"))


def cmd_verify(exe: str, assets):
    ok = 0
    with AssetFile(exe) as af:
        for asset in assets:
            try:
                found = af.locate(asset)
                print("OK   %-48s raw=%-8d br=%d" % (asset, len(found["raw"]), found["br_len"]))
                ok += 1
            except Exception as exc:  # noqa: BLE001 - report and continue
                print("FAIL %-48s %s" % (asset, exc))
    print("%d/%d assets verified" % (ok, len(assets)))
    if ok != len(assets):
        raise SystemExit(1)


def cmd_restore(exe: str):
    bak = backup_path(exe)
    if not os.path.exists(bak):
        raise FileNotFoundError("no backup at %s" % bak)
    shutil.copy2(bak, exe)
    print("restored %s from %s" % (exe, bak))


# ------------------------------------------------------------------------ CLI

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Patch embedded web assets of the GitHub Copilot desktop app.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--exe", default=os.environ.get("COPILOT_EXE", DEFAULT_EXE),
                        help="target executable")
    parser.add_argument("--copy", dest="to_copy",
                        help="apply the change to this copy instead of the original")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")

    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("stat", help="show asset sizes and headroom")
    p.add_argument("asset")
    p = sub.add_parser("find", help="list assets whose path matches a substring")
    p.add_argument("substring")
    p = sub.add_parser("status", help="report whether the localizer is applied")
    p.add_argument("asset", nargs="?", default="auto")
    p = sub.add_parser("list", help="list every embedded asset (optionally filtered)")
    p.add_argument("pattern", nargs="?", default="")
    p = sub.add_parser("extract", help="write the decompressed asset to disk")
    p.add_argument("asset")
    p.add_argument("out", nargs="?")
    p = sub.add_parser("patch", help="append a JS payload and recompress in place")
    p.add_argument("asset")
    p.add_argument("payload")
    p = sub.add_parser("replace", help="apply a JSON {old: new} string map")
    p.add_argument("asset")
    p.add_argument("map_file")
    p = sub.add_parser("verify", help="verify assets decompress and match descriptors")
    p.add_argument("assets", nargs="+")
    sub.add_parser("restore", help="restore the backup over the executable")
    p = sub.add_parser("rebaseline",
                       help="adopt the current (pristine) executable as the new backup")
    p.add_argument("assets", nargs="+",
                   help="assets that must be pristine, e.g. index.html")
    p = sub.add_parser("baseline",
                       help="check whether the pristine backup is usable")
    p.add_argument("assets", nargs="+")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    exe = args.exe
    if args.to_copy:
        if not os.path.exists(args.to_copy):
            shutil.copy2(exe, args.to_copy)
            print("working copy created: %s" % args.to_copy)
        exe = args.to_copy

    if args.cmd == "stat":
        cmd_stat(exe, args.asset)
    elif args.cmd == "find":
        cmd_find(exe, args.substring)
    elif args.cmd == "status":
        cmd_status(exe, args.asset)
    elif args.cmd == "list":
        cmd_list(exe, args.pattern)
    elif args.cmd == "extract":
        cmd_extract(exe, args.asset, args.out)
    elif args.cmd == "patch":
        cmd_patch(exe, args.asset, args.payload, args.dry_run, args.force)
    elif args.cmd == "replace":
        cmd_replace(exe, args.asset, args.map_file, args.dry_run)
    elif args.cmd == "verify":
        cmd_verify(exe, args.assets)
    elif args.cmd == "restore":
        cmd_restore(exe)
    elif args.cmd == "rebaseline":
        print(rebaseline(exe, args.assets))
    elif args.cmd == "baseline":
        print(json.dumps(ensure_clean_baseline(exe, args.assets, dry_run=True), indent=2))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, LookupError, FileNotFoundError, PermissionError) as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        if isinstance(exc, PermissionError):
            print("hint: close the GitHub Copilot app first, or pass --copy <file>.",
                  file=sys.stderr)
        raise SystemExit(1)
