"""scan_ui.py - read the live GitHub Copilot window through Windows UI Automation.

Read-only: walks the accessibility tree and reports English text that has no entry in
the translation dictionary. Clicking is never involved.

    python tools/scan_ui.py                     # gaps on the current screen
    python tools/scan_ui.py --all               # every visible string
    python tools/scan_ui.py --tree build/t.txt  # dump the raw tree
    python tools/scan_ui.py --wait 3            # sample longer

The window is matched by executable (github.exe) and class ("Tauri Window"), so an
Edge tab titled "GitHub Copilot" can never be picked up by mistake.
"""

from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import apply_zh  # noqa: E402
from uia_common import (  # noqa: E402
    collect, describe_window, find_app_window, gap_list, walk, wake,
)


def load_filters():
    dictionary = apply_zh.load_dictionary()
    term = apply_zh.load_terminology()
    keep = {w.strip().lower() for w in term["keep_english"]}
    keep |= {w.strip().lower() for w in term["keep_english_keys"]}
    return dictionary, keep


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true", help="list every visible string")
    parser.add_argument("--tree", help="write the raw tree to this file")
    parser.add_argument("--wait", type=float, default=1.5)
    parser.add_argument("--limit", type=int, default=80)
    parser.add_argument("--out", default=os.path.join(ROOT, "build", "ui-live.txt"))
    args = parser.parse_args()

    window = find_app_window()
    if window is None:
        print("GitHub Copilot window (github.exe / Tauri Window) not found",
              file=sys.stderr)
        return 1
    print("window: %s" % describe_window(window))
    if not wake(window):
        print("warning: accessibility tree looks empty; is the app responsive?",
              file=sys.stderr)

    if args.tree:
        rows = []
        walk(window, rows)
        os.makedirs(os.path.dirname(args.tree) or ".", exist_ok=True)
        with open(args.tree, "w", encoding="utf-8") as fh:
            for depth, ctype, name in rows:
                fh.write("%s%s | %r\n" % ("  " * depth, ctype, name))
        print("tree: %d nodes -> %s" % (len(rows), args.tree))

    texts = collect(window, args.wait)
    dictionary, keep = load_filters()
    gaps = gap_list(texts, dictionary, keep)

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
        for count, text in gaps:
            fh.write("%d\t%s\n" % (count, text))

    print("%d distinct strings, %d untranslated" % (len(texts), len(gaps)))
    for count, text in gaps[: args.limit]:
        print("%3d  %s" % (count, text))
    print("-> %s" % args.out)

    if args.all:
        print("\n== every visible string ==")
        for text, count in texts.most_common(500):
            print("%3d  %s" % (count, text))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
