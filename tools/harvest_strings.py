"""harvest_strings.py - extract candidate UI strings from the embedded app bundle.

Walks every embedded JS chunk, collects quoted string literals, filters out code-ish
noise (identifiers, URLs, file paths, CSS, tokens), and writes a frequency-ranked list.

    python tools/harvest_strings.py                 # -> build/ui-strings.txt
    python tools/harvest_strings.py --min-len 3 --top 3000
    python tools/harvest_strings.py --missing       # only strings absent from the dict

The output is tab separated: `<count>\\t<string>`.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import copilot_l10n as l10n  # noqa: E402

DICT_PATH = os.path.join(ROOT, "i18n", "zh-cn.dict.json")

STRING_RE = re.compile(r'"((?:[^"\\\n]|\\.){2,200})"|\'((?:[^\'\\\n]|\\.){2,200})\'|`([^`$\\\n]{2,200})`')

# High-precision anchor: strings that are values of UI-ish props in compiled JSX.
ANCHOR_RE = re.compile(
    r'(?:children|placeholder|label|description|title|tooltip|heading|emptyText|'
    r'alt|message|subtitle|caption|helperText|"aria-label"|"aria-description"|'
    r'"aria-placeholder"|"aria-roledescription"|"data-tooltip"|"data-tooltip-content")'
    r'\s*:\s*(?:"((?:[^"\\\n]|\\.){2,200})"|`([^`$\\\n]{2,200})`|\'((?:[^\'\\\n]|\\.){2,200})\')'
)

CODE_WORDS = re.compile(
    r"\b(function|const|let|var|return|typeof|undefined|null|true|false|import|export|"
    r"class|extends|async|await|this|new|if|else|for|while|switch|case|break|default|"
    r"arguments|prototype|constructor|length|push|map|filter|reduce|apply|call|bind)\b"
)

NOISE = re.compile(
    r"^(https?:|data:|blob:|#|\./|\.\./|/|[\w-]+\.(js|mjs|css|png|svg|jpg|jpeg|gif|webp|"
    r"woff2?|ttf|json|html|map|wasm|glb|ico))"
    r"|[{}();=<>\[\]`]|\\u[0-9a-fA-F]{4}|\$\{|\bpx\b|\bvar\(--"
)

# Tailwind / CSS utility vocabulary: strings made of these are class lists, not UI text.
CSS_TOKENS = re.compile(
    r"(^|\s)(flex|grid|block|inline|hidden|absolute|relative|fixed|sticky|truncate|"
    r"shrink-?\d*|grow-?\d*|items-[\w-]+|justify-[\w-]+|gap-\d+|p[xytblr]?-\d+|m[xytblr]?-[\w\d]+|"
    r"w-[\w/.\[\]]+|h-[\w/.\[\]]+|min-[wh]-[\w/.\[\]]+|max-[wh]-[\w/.\[\]]+|"
    r"text-(xs|sm|base|lg|xl|\d?xl|muted|body|label|caption|\[\w+\])|bg-[\w-]+|"
    r"border(-[\w\d]+)?|rounded(-[\w]+)?|overflow-[\w-]+|font-[\w]+|leading-[\w]+|"
    r"tracking-[\w]+|space-[xy]-[\w]+|z-\d+|top-\d+|left-\d+|right-\d+|bottom-\d+|"
    r"col-span-\d+|row-span-\d+|opacity-\d+|shadow(-[\w]+)?|ring(-[\w]+)?|"
    r"(hover|focus|active|disabled|dark|md|sm|lg|xl):)(\s|$)"
)

DOTTED = re.compile(r"^[a-z][a-z0-9]*(\.[a-z0-9]+)+$")

CAMEL = re.compile(r"^[a-z]+[A-Z]")
SNAKE = re.compile(r"^[a-z0-9]+(_[a-z0-9]+)+$")
KEBAB = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)+$")


def is_candidate(s: str, min_len: int, max_len: int) -> bool:
    s = s.strip()
    if not (min_len <= len(s) <= max_len):
        return False
    if not re.search(r"[A-Za-z]{3}", s):
        return False
    if NOISE.search(s) or CODE_WORDS.search(s):
        return False
    if CSS_TOKENS.search(s) or DOTTED.match(s):
        return False
    if CAMEL.match(s) or SNAKE.match(s) or KEBAB.match(s):
        return False
    if "@" in s and "." in s.split("@")[-1]:
        return False
    # UI text is a single sentence or label: no trailing separators, no operators
    if re.search(r"[;{}<>=\\]", s):
        return False
    if s.count(" ") == 0:
        # single token: accept only clearly human labels
        if not re.fullmatch(r"[A-Z][A-Za-z]{2,}", s):
            return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--exe", default=os.environ.get("COPILOT_EXE", l10n.DEFAULT_EXE))
    parser.add_argument("--out", default=os.path.join(ROOT, "build", "ui-strings.txt"))
    parser.add_argument("--min-len", type=int, default=3)
    parser.add_argument("--max-len", type=int, default=120)
    parser.add_argument("--top", type=int, default=4000)
    parser.add_argument("--missing", action="store_true",
                        help="only strings that have no dictionary entry yet")
    parser.add_argument("--ui-only", action="store_true",
                        help="only scan chunks that render React markup (className / jsx)")
    parser.add_argument("--min-count", type=int, default=1,
                        help="drop strings seen fewer than N times")
    parser.add_argument("--mode", choices=("anchored", "loose"), default="anchored",
                        help="anchored = only UI-prop values (high precision); "
                             "loose = every quoted string")
    args = parser.parse_args()

    dictionary = {}
    keep = set()
    if args.missing:
        sys.path.insert(0, ROOT)
        import apply_zh
        dictionary = apply_zh.load_dictionary()
        term = apply_zh.load_terminology()
        keep = {w.strip().lower() for w in term["keep_english"]}
        keep |= {w.strip().lower() for w in term["keep_english_keys"]}
        print("dictionary: %d entries, %d keep-English terms"
              % (len(dictionary), len(keep)))

    counts: dict[str, int] = {}
    scanned = 0
    with l10n.AssetFile(args.exe) as af:
        for path, blob, length in l10n.iter_assets(af.data, af.pe):
            if not path.endswith(".js"):
                continue
            raw = l10n._try_decompress(af.data, blob, length)
            if raw is None:
                continue
            try:
                src = raw.decode("utf-8")
            except UnicodeDecodeError:
                continue
            if args.ui_only and "className" not in src and "jsx(" not in src \
                    and "createElement(" not in src:
                continue
            scanned += 1
            pattern = ANCHOR_RE if args.mode == "anchored" else STRING_RE
            for m in pattern.finditer(src):
                s = next((g for g in m.groups() if g), "").strip()
                if not is_candidate(s, args.min_len, args.max_len):
                    continue
                if args.missing and s in dictionary:
                    continue
                if args.missing and s.strip().lower() in keep:
                    continue
                counts[s] = counts.get(s, 0) + 1

    rows = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    rows = [r for r in rows if r[1] >= args.min_count][: args.top]
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
        for s, c in rows:
            fh.write("%d\t%s\n" % (c, s))
    print("scanned %d js chunks, %d unique candidates -> %s"
          % (scanned, len(counts), args.out))
    for s, c in rows[:40]:
        print("%5d  %s" % (c, s))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
