"""dedupe_dict.py - remove duplicate keys from the dictionary, keeping the first value."""

import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "i18n", "zh-cn.dict.json")


def main() -> None:
    raw = open(PATH, encoding="utf-8").read()
    pairs = []
    seen = set()
    for m in re.finditer(r'^  "((?:[^"\\]|\\.)*)":\s*"((?:[^"\\]|\\.)*)"\s*,?\s*$',
                         raw, re.M):
        key = json.loads('"%s"' % m.group(1))
        value = json.loads('"%s"' % m.group(2))
        if key in seen or key == value:
            continue
        seen.add(key)
        pairs.append((key, value))

    out = "{\n" + ",\n".join(
        '  %s: %s' % (json.dumps(k, ensure_ascii=False), json.dumps(v, ensure_ascii=False))
        for k, v in pairs
    ) + "\n}\n"
    json.loads(out)
    open(PATH, "w", encoding="utf-8", newline="\n").write(out)
    print("kept %d entries" % len(pairs))


if __name__ == "__main__":
    main()
