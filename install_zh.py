#!/usr/bin/env python3
"""install_zh.py - one-shot installer for the Simplified-Chinese localizer.

Waits until the GitHub Copilot app is fully closed (the executable is locked while it
runs), patches it, verifies the result, and relaunches the app.

Usage
-----
    python install_zh.py                 # wait for exit, patch, relaunch
    python install_zh.py --no-launch     # wait for exit and patch only
    python install_zh.py --exe PATH      # non-default install location
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time

import apply_zh
import copilot_l10n as l10n


def is_writable(exe: str) -> bool:
    try:
        with open(exe, "r+b"):
            return True
    except (PermissionError, OSError):
        return False


def wait_until_writable(exe: str, timeout: int) -> bool:
    if is_writable(exe):
        return True
    print("GitHub Copilot 正在运行，文件被占用。")
    print("请完全退出应用（包括托盘图标），脚本会每 2 秒检测一次…")
    started = time.time()
    while time.time() - started < timeout:
        time.sleep(2)
        if is_writable(exe):
            print("已检测到应用退出，继续。")
            return True
    return False


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Install the zh-CN localizer.")
    parser.add_argument("--exe", default=os.environ.get("COPILOT_EXE", l10n.DEFAULT_EXE))
    parser.add_argument("--asset", default=apply_zh.DEFAULT_ASSET)
    parser.add_argument("--no-launch", action="store_true",
                        help="do not start the app after patching")
    parser.add_argument("--timeout", type=int, default=600,
                        help="seconds to wait for the app to close (default 600)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    if not os.path.exists(args.exe):
        print("ERROR: executable not found: %s" % args.exe, file=sys.stderr)
        return 1

    if not args.dry_run and not wait_until_writable(args.exe, args.timeout):
        print("ERROR: timed out waiting for the app to close.", file=sys.stderr)
        return 1

    payload, asset_info, html_info = apply_zh.apply_patch(
        args.exe, args.asset, dry_run=args.dry_run, force=False
    )
    print("payload: %d bytes" % len(payload))
    print(json.dumps(asset_info, ensure_ascii=False, indent=2))
    print(json.dumps(html_info, ensure_ascii=False, indent=2))

    if args.dry_run:
        print("dry run: nothing written")
        return 0

    # Validate the result by re-reading the patched executable.
    with l10n.AssetFile(args.exe) as af:
        found = l10n.locate_asset(af.data, af.pe, args.asset)
        assert l10n.MARKER.encode() in found["raw"], "payload marker missing after patch"
        print("verified: %s decompresses, payload present" % args.asset)

    print("\n完成。回滚命令：")
    print('  .venv\\Scripts\\python.exe copilot_l10n.py restore --exe "%s"' % args.exe)

    if not args.no_launch:
        print("正在启动应用…")
        subprocess.Popen([args.exe], close_fds=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, LookupError, FileNotFoundError) as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        raise SystemExit(1)
