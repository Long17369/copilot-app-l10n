"""scan_nav.py - visit read-only app screens and report untranslated strings.

Navigation only: it activates sidebar/导航 entries through accessibility patterns.
No physical mouse clicks, no typing, no form submission, no create/delete actions.

    python tools/scan_nav.py
    python tools/scan_nav.py --pages "Issues" "拉取请求" "自动化" "自定义" "设置"
"""

from __future__ import annotations

import argparse
import collections
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import apply_zh  # noqa: E402
from uia_common import (  # noqa: E402
    activate, collect, describe_window, find_app_window, find_control, gap_list, wake,
)

# Sidebar entries only: opening a view changes nothing on disk or on GitHub.
DEFAULT_PAGES = ["Issues", "拉取请求", "自动化", "自定义", "设置"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pages", nargs="*", default=DEFAULT_PAGES)
    parser.add_argument("--wait", type=float, default=1.6)
    parser.add_argument("--reopen", help="control to activate when a page entry is missing")
    parser.add_argument("--out", default=os.path.join(ROOT, "build", "ui-live.txt"))
    args = parser.parse_args()

    window = find_app_window()
    if window is None:
        print("GitHub Copilot window not found", file=sys.stderr)
        return 1
    print("window: %s" % describe_window(window))
    if not wake(window):
        print("warning: accessibility tree looks empty", file=sys.stderr)

    dictionary = apply_zh.load_dictionary()
    term = apply_zh.load_terminology()
    keep = {w.strip().lower() for w in term["keep_english"]}
    keep |= {w.strip().lower() for w in term["keep_english_keys"]}

    merged = collections.Counter()

    def scan(label):
        texts = collect(window, args.wait)
        gaps = gap_list(texts, dictionary, keep)
        for count, text in gaps:
            merged[text] = max(merged[text], count)
        print("  %-12s %3d strings, %3d gaps" % (label, len(texts), len(gaps)))
        for count, text in gaps[:12]:
            print("      %3d  %s" % (count, text))
        return gaps

    print("== current ==")
    scan("current")

    for page in args.pages:
        control = find_control(window, page)
        if control is None and args.reopen:
            # Settings sub-sections only exist while the settings dialog is open.
            opener = find_control(window, args.reopen)
            if opener is not None and activate(opener):
                time.sleep(1.0)
                control = find_control(window, page)
        if control is None:
            print("== %s == (entry not found)" % page)
            continue
        how = activate(control)
        if not how:
            print("== %s == (no accessible action; skipped)" % page)
            continue
        print("== %s == via %s" % (page, how))
        time.sleep(1.3)
        scan(page)

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
        for text, count in merged.most_common():
            fh.write("%d\t%s\n" % (count, text))
    print("\nmerged %d gaps -> %s" % (len(merged), args.out))
    for text, count in merged.most_common(80):
        print("%3d  %s" % (count, text))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
