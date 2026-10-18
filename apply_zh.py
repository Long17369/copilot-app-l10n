#!/usr/bin/env python3
"""apply_zh.py - inject the Simplified-Chinese runtime localizer into the Copilot app.

It builds ``build/zh-cn.payload.js`` from ``i18n/zh-cn.engine.js`` +
``i18n/zh-cn.dict.json`` and appends it to a startup chunk of the application, then
switches ``index.html`` to ``<html lang="zh-CN">``.

Examples
--------
    # patch a copy first (safe while the app is running)
    python apply_zh.py --copy C:\\temp\\github-zh.exe

    # apply to the installed app (close the app first)
    python apply_zh.py

    # preview sizes without writing anything
    python apply_zh.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import copilot_l10n as l10n

ROOT = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.join(ROOT, "i18n", "zh-cn.engine.js")
I18N_DIR = os.path.join(ROOT, "i18n")
DICT = os.path.join(I18N_DIR, "zh-cn.dict.json")
BUILD = os.path.join(ROOT, "build")

# Startup chunks loaded by the entry graph, in preference order. The first one with
# enough Brotli headroom is used; hashes change when the app updates, so
# `copilot_l10n.py list App-` and `--asset` are the escape hatch.
ASSET_CANDIDATES = (
    "/assets/App-DxoK3vc2.js",
    "/assets/useWebSocketTransport-Cqgftpse.js",
    "/assets/router-T3TZDMzd.js",
    "/assets/ExtensionsView-M-L961S-.js",
    "/assets/switch-cyfgugQG.js",
)
DEFAULT_ASSET = "auto"
MIN_SLACK = 1024

# The entry chunk is loaded synchronously by index.html. Appending a tiny import of the
# payload chunk there makes the translator available from the first paint, even when the
# payload lives in a chunk the router would otherwise load lazily.
ENTRY_ASSET = "/assets/index-B4Phv94s.js"
BOOT_MARKER = "/*__COPILOT_L10N_BOOT__*/"


STATE_FILE = os.path.join(BUILD, "last-chunk.json")


def _load_state() -> dict:
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def _save_state(state: dict) -> None:
    try:
        os.makedirs(BUILD, exist_ok=True)
        with open(STATE_FILE, "w", encoding="utf-8") as fh:
            json.dump(state, fh, indent=2)
    except OSError:
        pass


def _remember(exe: str, asset: str) -> None:
    import hashlib

    state = _load_state()
    state[exe] = {
        "asset": asset,
        "payload_sha": hashlib.sha1(build_payload()).hexdigest(),
        "exe_size": os.path.getsize(exe),
    }
    _save_state(state)


def is_current(exe: str, asset: str) -> bool:
    """True when the executable already carries exactly this payload and wiring."""
    import hashlib

    state = _load_state()
    entry = state.get(exe)
    if not isinstance(entry, dict):
        return False
    if entry.get("payload_sha") != hashlib.sha1(build_payload()).hexdigest():
        return False
    if entry.get("exe_size") != os.path.getsize(exe):
        return False
    chunk = entry.get("asset")
    if chunk not in ASSET_CANDIDATES:
        return False
    with l10n.AssetFile(exe) as af:
        try:
            if l10n.MARKER.encode() not in af.locate(chunk)["raw"]:
                return False
            if b'lang="zh-CN"' not in af.locate("index.html")["raw"]:
                return False
            if chunk != ENTRY_ASSET and \
                    BOOT_MARKER.encode() not in af.locate(ENTRY_ASSET)["raw"]:
                return False
        except (LookupError, KeyError):
            return False
    return True


def pick_asset(exe: str, payload: bytes) -> str:
    """Return the startup chunk to patch.

    A previously successful choice is reused without re-measuring (the caller falls back
    to a fresh scan if it no longer fits). Otherwise candidates are tried biggest-first:
    headroom scales with chunk size, so the first attempt almost always wins.
    """
    state = _load_state()
    remembered = state.get(exe)
    if isinstance(remembered, dict):
        remembered = remembered.get("asset")
    if remembered in ASSET_CANDIDATES:
        l10n.log("reusing previously chosen chunk: %s" % remembered)
        return remembered

    bak = l10n.backup_path(exe)
    source = bak if os.path.exists(bak) else exe
    found = []
    with l10n.AssetFile(source) as af:
        for candidate in ASSET_CANDIDATES:
            try:
                found.append((candidate, af.locate(candidate)))
            except LookupError:
                continue
    if not found:
        raise ValueError("none of the candidate chunks exist in %s" % source)

    found.sort(key=lambda item: -item[1]["br_len"])
    defects = []
    for candidate, info in found:
        l10n.log("measuring %s (%.1f MB)" % (candidate, len(info["raw"]) / 1e6))
        with l10n.heartbeat("  compressing"):
            packed, quality = l10n.compress_fitting(
                info["raw"] + b"\n" + payload + b"\n", info["br_len"] - MIN_SLACK)
        slack = info["br_len"] - len(packed)
        if slack >= MIN_SLACK:
            l10n.log("chosen chunk: %s (slack %d bytes, quality %d)"
                     % (candidate, slack, quality))
            _remember(exe, candidate)
            return candidate
        defects.append("%s: slack %d < %d" % (candidate, slack, MIN_SLACK))
    raise ValueError(
        "no startup chunk has room for the payload:\n  " + "\n  ".join(defects) +
        "\nPick another chunk with `copilot_l10n.py list App-` and pass --asset."
    )


def bootstrap_transform(asset: str):
    """Append a static import of `asset` to the entry chunk."""
    spec = "./" + asset.rsplit("/", 1)[-1]

    def transform(raw: bytes) -> bytes:
        text = raw.decode("utf-8")
        if BOOT_MARKER in text:
            return raw
        return (text + '\n' + BOOT_MARKER +
                'import("%s").catch(function(){});\n' % spec).encode("utf-8")

    return transform


def load_dictionary() -> dict:
    """Merge every dictionary fragment in i18n/, base dictionary first.

    ``zh-cn.dict.json`` is the core list; additional ``*.extra.json`` fragments are
    layered on top (later files win), which keeps incremental additions reviewable.
    """
    files = ["zh-cn.dict.json"]
    files += sorted(
        name for name in os.listdir(I18N_DIR)
        if name.endswith(".extra.json") and name != "zh-cn.dict.json"
    )
    merged = {}
    for name in files:
        path = os.path.join(I18N_DIR, name)
        if not os.path.exists(path):
            continue
        with open(path, "r", encoding="utf-8") as fh:
            merged.update(json.load(fh))
    return merged


def build_payload() -> bytes:
    with open(ENGINE, "r", encoding="utf-8") as fh:
        engine = fh.read()
    dictionary = load_dictionary()

    if "__DICT_JSON__" not in engine:
        raise ValueError("engine is missing the __DICT_JSON__ placeholder")
    if l10n.MARKER not in engine:
        raise ValueError("engine is missing the l10n marker")

    payload = engine.replace("__DICT_JSON__", json.dumps(dictionary, ensure_ascii=False))
    return payload.encode("utf-8")


def index_html_transform(raw: bytes) -> bytes:
    text = raw.decode("utf-8")
    if 'lang="zh-CN"' in text:
        return raw
    if 'lang="en"' not in text:
        raise ValueError('index.html has no lang="en" attribute')
    return text.replace('lang="en"', 'lang="zh-CN"', 1).encode("utf-8")


def make_append_transform(payload: bytes, force: bool):
    marker = l10n.MARKER.encode()

    def append(raw: bytes) -> bytes:
        if marker in raw:
            if not force:
                return raw  # already applied: make the install idempotent
            raise ValueError("asset already contains a l10n payload (use --force)")
        return raw + b"\n" + payload + b"\n"

    return append


def apply_patch(exe: str, asset: str, dry_run: bool = False, force: bool = False):
    """Patch the startup chunk, the entry bootstrap and index.html in one write."""
    payload = build_payload()
    l10n.log("payload: %d bytes" % len(payload))
    if asset in ("auto", "", None):
        asset = pick_asset(exe, payload)

    edits = [
        (asset, make_append_transform(payload, force)),
        ("index.html", index_html_transform),
    ]
    baseline_assets = [a for a in ASSET_CANDIDATES if a != asset]
    if asset != ENTRY_ASSET:
        edits.append((ENTRY_ASSET, bootstrap_transform(asset)))
        baseline_assets = [a for a in baseline_assets if a != ENTRY_ASSET]

    infos = l10n.rewrite_assets(exe, edits, dry_run, baseline_assets=baseline_assets)
    if not dry_run:
        _remember(exe, asset)
    return payload, infos


def apply_patch_with_fallback(exe: str, asset: str, dry_run: bool = False):
    """apply_patch, but drop a stale remembered chunk and re-measure if it no longer fits."""
    try:
        return apply_patch(exe, asset, dry_run)
    except ValueError as exc:
        if "does not fit" not in str(exc) or asset not in ("auto", "", None):
            raise
        l10n.log("remembered chunk no longer fits; re-measuring all candidates")
        state = _load_state()
        state.pop(exe, None)
        _save_state(state)
        return apply_patch(exe, asset, dry_run)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Inject the zh-CN localizer.")
    parser.add_argument("--exe", default=os.environ.get("COPILOT_EXE", l10n.DEFAULT_EXE))
    parser.add_argument("--copy", dest="to_copy",
                        help="patch this copy instead of the original executable")
    parser.add_argument("--asset", default=DEFAULT_ASSET,
                        help="startup chunk to append the payload to")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true",
                        help="append even if the payload is already present")
    args = parser.parse_args(argv)

    exe = args.exe
    if args.to_copy:
        if not os.path.exists(args.to_copy):
            os.makedirs(os.path.dirname(os.path.abspath(args.to_copy)), exist_ok=True)
            import shutil
            shutil.copy2(exe, args.to_copy)
            print("working copy created: %s" % args.to_copy)
        exe = args.to_copy

    os.makedirs(BUILD, exist_ok=True)
    payload_path = os.path.join(BUILD, "zh-cn.payload.js")

    if not args.dry_run and is_current(exe, args.asset):
        print("already up to date: this payload is installed")
        return 0

    payload, infos = apply_patch_with_fallback(exe, args.asset, args.dry_run)
    with open(payload_path, "wb") as fh:
        fh.write(payload)
    print("payload: %d bytes -> %s" % (len(payload), payload_path))
    for info in infos:
        print(json.dumps(info, ensure_ascii=False, indent=2))

    if not args.dry_run:
        print("\nDone. Restart the app to see the localized UI.")
        print("Undo with: python copilot_l10n.py restore --exe \"%s\"" % exe)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, LookupError, FileNotFoundError, PermissionError) as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        if isinstance(exc, PermissionError):
            print("hint: close the GitHub Copilot app first, or pass --copy <file>.",
                  file=sys.stderr)
        raise SystemExit(1)
