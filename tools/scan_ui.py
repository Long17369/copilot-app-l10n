"""scan_ui.py - read the live GitHub Copilot window through Windows UI Automation.

This is read-only: it walks the accessibility tree and collects the text the app is
actually displaying, then diffs it against the translation dictionary. Nothing is
clicked or typed.

    python tools/scan_ui.py                 # gaps for the current screen
    python tools/scan_ui.py --all           # list every visible string
    python tools/scan_ui.py --tree out.txt  # dump the raw tree for inspection
    python tools/scan_ui.py --wait 5        # keep collecting for N seconds

Why not the computer-use MCP server: it refuses to automate the Copilot app itself.
UI Automation from Python has no such restriction, and the accessibility tree is a
plain read, so it is safe to use for inspection.
"""

from __future__ import annotations

import argparse
import collections
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import uiautomation as auto  # noqa: E402

import apply_zh  # noqa: E402

HAS_LATIN = re.compile(r"[A-Za-z]{2}")
HAS_CJK = re.compile(r"[\u4e00-\u9fff]")

NOISE = [
    re.compile(r"^[A-Za-z]:[\\/]"),
    re.compile(r"^\.{0,2}/"),
    re.compile(r"^(Ctrl|Control|Alt|Shift|Cmd|Meta|Option)\b", re.I),
    re.compile(r"^[\w.-]+\.(js|mjs|ts|tsx|jsx|py|md|json|exe|cmd|bat|txt|yml|yaml|css|html)$", re.I),
    re.compile(r"^[A-Z_]{3,}$"),
    re.compile(r"^[0-9a-f]{7,}$", re.I),
    re.compile(r"^[\w-]+/[\w-]+$"),
    re.compile(r"^[a-z]+[A-Z]\w+$"),
    re.compile(r"^(cd|git|npm|node|python|pip|gh|npx|yarn|pnpm)\s"),
    re.compile(r"[\\/][\w.-]+[\\/]"),
    re.compile(r"[`{}<>]|=>|::"),
    re.compile(r"^[·•]\s*[\w.-]+$"),
]


def is_candidate(text: str, min_len: int, max_len: int) -> bool:
    text = text.strip()
    if not (min_len <= len(text) <= max_len):
        return False
    if not HAS_LATIN.search(text):
        return False
    if HAS_CJK.search(text):
        return False
    for pattern in NOISE:
        if pattern.search(text):
            return False
    return True


def find_window(name: str):
    windows = auto.GetRootControl().GetChildren()
    best = None
    for win in windows:
        try:
            title = win.Name or ""
        except Exception:
            continue
        if name.lower() in title.lower():
            best = win
    return best


def walk(control, out, depth=0, max_depth=60):
    """Collect (depth, control_type, name, value) for the subtree."""
    try:
        name = control.Name or ""
        ctype = control.ControlTypeName or ""
        value = ""
        try:
            value = control.GetValuePattern().Value or ""
        except Exception:
            pass
        out.append((depth, ctype, name, value))
    except Exception:
        return
    if depth >= max_depth:
        return
    try:
        children = control.GetChildren()
    except Exception:
        return
    for child in children:
        walk(child, out, depth + 1, max_depth)


def collect(window, seconds: float):
    """Sample the tree repeatedly; the app rebuilds its DOM while rendering."""
    seen = collections.Counter()
    deadline = time.time() + seconds
    while True:
        rows = []
        walk(window, rows)
        for _depth, _ctype, name, value in rows:
            for text in (name, value):
                if text:
                    seen[text.strip()] += 1
        if time.time() >= deadline:
            break
        time.sleep(0.5)
    return seen


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--window", default="GitHub Copilot")
    parser.add_argument("--all", action="store_true", help="list every visible string")
    parser.add_argument("--tree", help="write the raw tree to this file")
    parser.add_argument("--wait", type=float, default=1.5,
                        help="seconds to keep sampling (default 1.5)")
    parser.add_argument("--min-len", type=int, default=2)
    parser.add_argument("--max-len", type=int, default=120)
    parser.add_argument("--out", default=os.path.join(ROOT, "build", "ui-live.txt"))
    args = parser.parse_args()

    window = find_window(args.window)
    if window is None:
        print("window not found: %s" % args.window, file=sys.stderr)
        print("open the app, or pass --window <title substring>", file=sys.stderr)
        return 1
    print("window: %s" % window.Name)

    if args.tree:
        rows = []
        walk(window, rows)
        with open(args.tree, "w", encoding="utf-8") as fh:
            for depth, ctype, name, value in rows:
                fh.write("%s%s | %r | %r\n" % ("  " * depth, ctype, name, value))
        print("tree written: %s (%d nodes)" % (args.tree, len(rows)))

    texts = collect(window, args.wait)
    print("collected %d distinct strings" % len(texts))

    dictionary = apply_zh.load_dictionary()
    term = apply_zh.load_terminology()
    keep = {w.strip().lower() for w in term["keep_english"]}
    keep |= {w.strip().lower() for w in term["keep_english_keys"]}

    missing = []
    for text, count in texts.most_common():
        if not is_candidate(text, args.min_len, args.max_len):
            continue
        if text in dictionary or text.strip().lower() in keep:
            continue
        missing.append((count, text))

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
        for count, text in missing:
            fh.write("%d\t%s\n" % (count, text))

    print("\n== untranslated on the current screen: %d ==" % len(missing))
    for count, text in missing[:120]:
        print("%3d  %s" % (count, text))
    print("\nwritten to %s" % args.out)

    if args.all:
        print("\n== every visible string ==")
        for text, count in texts.most_common(400):
            print("%3d  %s" % (count, text))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
