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
    python copilot_l10n.py extract <asset> [out-file]
    python copilot_l10n.py patch   <asset> <payload.js>
    python copilot_l10n.py replace <asset> <map.json>
    python copilot_l10n.py verify  <asset> [<asset> ...]
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
import json
import mmap
import os
import shutil
import struct
import sys

try:
    import brotli
except ImportError:  # pragma: no cover
    sys.exit("missing dependency: python -m pip install -r requirements.txt")

DEFAULT_EXE = r"C:\Users\long1\AppData\Local\Programs\GitHub Copilot\github.exe"
MARKER = "/*__COPILOT_L10N__*/"

BROTLI_ARGS = dict(quality=11, lgwin=22, mode=brotli.MODE_TEXT)
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


def find_descriptor(data, pe: dict, blob_off: int, expected_len=None):
    """Return (descriptor_offset, compressed_length) for a blob, or None."""
    needle = struct.pack("<Q", pe["image_base"] + rva_of(pe, blob_off))
    pos = data.find(needle)
    while pos != -1:
        length = struct.unpack_from("<Q", data, pos + 8)[0]
        if 16 < length < MAX_ASSET and blob_off + length <= len(data):
            if expected_len is None or length == expected_len:
                return pos, length
        pos = data.find(needle, pos + 1)
    return None


def locate_asset(data, pe: dict, asset: str) -> dict:
    needle = asset.encode("latin1")
    matches = []
    pos = data.find(needle)
    while pos != -1:
        blob = pos + len(needle)
        desc = find_descriptor(data, pe, blob)
        if desc:
            desc_off, length = desc
            raw = _try_decompress(data, blob, length)
            if raw is not None:
                # exact length: one byte fewer must fail, otherwise the length is wrong
                if _try_decompress(data, blob, length - 1) is None:
                    matches.append(dict(path_off=pos, blob_off=blob, desc_off=desc_off,
                                        br_len=length, raw=raw))
        pos = data.find(needle, pos + 1)

    if not matches:
        raise LookupError("asset not found: %s" % asset)
    unique = sorted({m["blob_off"] for m in matches})
    if len(unique) > 1:
        raise LookupError("ambiguous asset (%d blobs): %s" % (len(unique), asset))
    return matches[0]


def compress(raw: bytes) -> bytes:
    return brotli.compress(raw, **BROTLI_ARGS)


# ------------------------------------------------------------------- file I/O

class AssetFile:
    """Read-only mmap view of the executable (keeps memory usage low)."""

    def __init__(self, path: str):
        self.path = path
        self._fh = open(path, "rb")
        self.data = mmap.mmap(self._fh.fileno(), 0, access=mmap.ACCESS_READ)
        self.pe = parse_pe(self.data)

    def close(self):
        self.data.close()
        self._fh.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


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
    bak = backup_path(exe)
    if not os.path.exists(bak):
        shutil.copy2(exe, bak)
        return "backup created: %s" % bak
    return "backup already present: %s" % bak


def rewrite_asset(exe: str, asset: str, transform, dry_run=False) -> dict:
    with AssetFile(exe) as af:
        found = locate_asset(af.data, af.pe, asset)
        raw_before = found["raw"]
        raw_after = transform(raw_before)
        packed = compress(raw_after)
        baseline = len(compress(raw_before))
        info = dict(
            asset=asset,
            raw_before=len(raw_before),
            raw_after=len(raw_after),
            br_before=found["br_len"],
            br_after=len(packed),
            br_delta=len(packed) - baseline,
            slack=found["br_len"] - len(packed),
            blob_off=found["blob_off"],
            desc_off=found["desc_off"],
            fits=len(packed) <= found["br_len"],
        )
        if not info["fits"]:
            raise ValueError(
                "does not fit: %d > %d (overflow %d bytes). "
                "Shorten the payload or use a larger asset."
                % (len(packed), found["br_len"], len(packed) - found["br_len"])
            )
        if dry_run:
            return info
        blob_off = found["blob_off"]
        old_len = found["br_len"]
        desc_off = found["desc_off"]

    assert_writable(exe)
    info["backup"] = ensure_backup(exe)
    with open(exe, "r+b") as fh:
        fh.seek(blob_off)
        fh.write(packed)
        if len(packed) < old_len:
            fh.write(b"\0" * (old_len - len(packed)))
        fh.seek(desc_off + 8)
        fh.write(struct.pack("<Q", len(packed)))
        fh.flush()
        os.fsync(fh.fileno())
    return info


# ------------------------------------------------------------------- commands

def cmd_stat(exe: str, asset: str):
    with AssetFile(exe) as af:
        found = locate_asset(af.data, af.pe, asset)
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
                    found = locate_asset(af.data, af.pe, path)
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
        found = locate_asset(af.data, af.pe, asset)
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


def cmd_verify(exe: str, assets):
    ok = 0
    with AssetFile(exe) as af:
        for asset in assets:
            try:
                found = locate_asset(af.data, af.pe, asset)
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


if __name__ == "__main__":
    try:
        main()
    except (ValueError, LookupError, FileNotFoundError, PermissionError) as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        if isinstance(exc, PermissionError):
            print("hint: close the GitHub Copilot app first, or pass --copy <file>.",
                  file=sys.stderr)
        raise SystemExit(1)
