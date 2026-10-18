"""check_dict.py - validate i18n/zh-cn.dict.json.

Reports duplicate keys, non-string values, and optionally list entries that do not
appear in the app bundle (so stale entries can be pruned).

    python tools/check_dict.py
    python tools/check_dict.py --coverage     # needs the app executable
"""

import argparse
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DICT_PATH = os.path.join(ROOT, "i18n", "zh-cn.dict.json")


def duplicate_keys(raw: str):
    seen = set()
    dupes = []
    for m in re.finditer(r'^\s*"((?:[^"\\]|\\.)*)"\s*:', raw, re.M):
        key = json.loads('"%s"' % m.group(1))
        if key in seen:
            dupes.append(key)
        seen.add(key)
    return dupes


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--coverage", action="store_true",
                        help="check which entries still exist in the app bundle")
    parser.add_argument("--exe", default=None)
    args = parser.parse_args()

    sys.path.insert(0, ROOT)
    import apply_zh

    raw = open(DICT_PATH, encoding="utf-8").read()
    data = json.loads(raw)
    merged = apply_zh.load_dictionary()

    problems = 0
    dupes = duplicate_keys(raw)
    if dupes:
        problems += len(dupes)
        print("duplicate keys (%d):" % len(dupes))
        for d in dupes:
            print("  -", d)

    for key, value in data.items():
        if not isinstance(value, str):
            problems += 1
            print("non-string value:", key)
        elif not value.strip():
            problems += 1
            print("empty translation:", key)

    print("base dictionary: %d entries" % len(data))
    print("merged (base + *.extra.json): %d entries" % len(merged))
    for name in sorted(os.listdir(os.path.join(ROOT, "i18n"))):
        if not name.endswith(".extra.json"):
            continue
        path = os.path.join(ROOT, "i18n", name)
        with open(path, encoding="utf-8") as fh:
            frag = json.load(fh)
        bad = [k for k, v in frag.items() if not isinstance(v, str) or not v.strip()]
        print("  %-28s %4d entries%s" % (name, len(frag), "" if not bad else
                                         "  (%d invalid)" % len(bad)))
        problems += len(bad)
    print("%d problem(s)" % problems)

    if args.coverage:
        sys.path.insert(0, ROOT)
        import copilot_l10n as l10n
        exe = args.exe or l10n.DEFAULT_EXE
        blob = b""
        with l10n.AssetFile(exe) as af:
            for asset in ("/assets/App-DxoK3vc2.js", "index.html"):
                try:
                    blob += l10n.locate_asset(af.data, af.pe, asset)["raw"]
                except Exception:
                    pass
        missing = [k for k in data if k.encode("utf-8") not in blob]
        print("not found in bundle: %d" % len(missing))
        for k in missing[:40]:
            print("  ?", k)

    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
