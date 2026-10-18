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
)
DEFAULT_ASSET = "auto"
MIN_SLACK = 4096


def pick_asset(exe: str, payload: bytes) -> str:
    """Return the first candidate asset that can hold the payload with some margin.

    Sizes are measured against the *pristine* bytes (from the backup when it exists),
    so re-running an install does not mistake the previous payload for the original.
    """
    bak = l10n.backup_path(exe)
    source = bak if os.path.exists(bak) else exe
    details = []
    with l10n.AssetFile(source) as af:
        for candidate in ASSET_CANDIDATES:
            try:
                found = l10n.locate_asset(af.data, af.pe, candidate)
            except LookupError:
                details.append("%s: not found" % candidate)
                continue
            packed = l10n.compress(found["raw"] + b"\n" + payload + b"\n")
            slack = found["br_len"] - len(packed)
            if slack >= MIN_SLACK:
                print("asset     : %s (slack %d bytes)" % (candidate, slack))
                return candidate
            details.append("%s: slack %d < %d" % (candidate, slack, MIN_SLACK))
    raise ValueError(
        "no startup chunk has room for the payload:\n  " + "\n  ".join(details) +
        "\nPick another chunk with `copilot_l10n.py list App-` and pass --asset."
    )


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
    """Patch the startup chunk and index.html in one write. Returns (payload, infos)."""
    payload = build_payload()
    if asset in ("auto", "", None):
        asset = pick_asset(exe, payload)
    infos = l10n.rewrite_assets(
        exe,
        [(asset, make_append_transform(payload, force)),
         ("index.html", index_html_transform)],
        dry_run,
        baseline_assets=[a for a in ASSET_CANDIDATES if a != asset],
    )
    return payload, infos


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

    payload, infos = apply_patch(exe, args.asset, args.dry_run, args.force)
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
